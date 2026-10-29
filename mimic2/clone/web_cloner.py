"""Clone a website into a local folder that works offline.

The cloner crawls same-site pages breadth-first up to max_depth links from the
start URL, optionally downloads the assets they use (CSS, JS, images, fonts),
then rewrites every link so the copy points at its own files. A mimic2.json
manifest records what was cloned so `mimic2 redesign` can find it later.

Assets from other hosts (CDNs) are saved under _external/<host>/. Links to
pages we didn't clone are made absolute so they still work from the copy.
"""
import hashlib
import json
import os
import posixpath
import shutil
import time
from collections import deque
from datetime import datetime, timezone
from urllib import robotparser
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlparse

from mimic2.utils import html_utils as hu

MANIFEST = "mimic2.json"
# Left behind by `mimic2 redesign`; cleared when a folder is cloned again.
ORIGINALS = ".mimic2-original"
THEME_CSS = "mimic2-theme.css"
# Longest robots.txt Crawl-delay we'll wait between requests, in seconds.
MAX_CRAWL_DELAY = 10


def normalize_url(url):
    """Add https:// if there's no scheme; only http(s) sites can be cloned."""
    url = url.strip()
    if "://" not in url:
        url = "https://" + url
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise ValueError(f"Can only clone http:// or https:// websites, not {url!r}")
    return url


class WebAppCloner:
    def __init__(self, url, output_dir, theme=None, max_depth=3,
                 include_assets=False, max_pages=50, max_assets=500, delay=0.2,
                 respect_robots=True, log=print):
        self.url = normalize_url(url)
        self.site = self.url  # becomes the redirect target if the start URL redirects
        self.output_dir = output_dir
        self.theme = theme
        self.max_depth = max_depth
        self.include_assets = include_assets
        self.max_pages = max_pages
        self.max_assets = max_assets
        self.delay = delay
        self.respect_robots = respect_robots
        self.log = log
        self.pages = {}    # page URL -> (local path, html text, final URL)
        self.assets = {}   # asset URL -> local path
        self.failed = []   # (url, reason)
        self._css_pending = []  # stylesheets to rewrite once all assets are known
        self._robots = None
        self._paths = {}   # lower-cased local path -> URL that owns it

    # -- public -----------------------------------------------------------

    def run(self):
        """Crawl, download, rewrite and save. Returns the manifest dict."""
        os.makedirs(self.output_dir, exist_ok=True)
        self._load_robots()
        self._crawl()
        if not self.pages:
            raise RuntimeError(f"Could not clone {self.url}: " +
                               (self.failed[0][1] if self.failed else "no pages"))
        self._clear_old_redesign()
        if self.include_assets:
            self._download_assets()
        self._write_pages()
        manifest = self._write_manifest()
        self.log(f"[+] {len(self.pages)} page(s), {len(self.assets)} asset(s)"
                 + (f", {len(self.failed)} failed" if self.failed else ""))
        return manifest

    # -- crawling ---------------------------------------------------------

    def _load_robots(self):
        if not self.respect_robots:
            return
        rp = robotparser.RobotFileParser(urljoin(self.site, "/robots.txt"))
        try:
            body, ctype, _ = hu.fetch(rp.url)
            rp.parse(hu.decode(body, charset=hu.charset_of(ctype)).splitlines())
            self._robots = rp
        except HTTPError as e:
            if e.code in (401, 403):
                # Same rule as the standard library: a locked robots.txt means keep out.
                rp.disallow_all = True
                self._robots = rp
            else:
                self._robots = None  # no robots.txt: everything allowed
        except (URLError, OSError, ValueError):
            self._robots = None
        if self._robots is not None:
            wait = self._robots.crawl_delay(hu.ROBOTS_AGENT)
            if wait:
                if float(wait) > MAX_CRAWL_DELAY:
                    self.log(f"[!] robots.txt asks for {wait}s between requests; "
                             f"using {MAX_CRAWL_DELAY}s")
                self.delay = max(self.delay, min(float(wait), MAX_CRAWL_DELAY))

    def _allowed(self, url):
        """robots.txt only speaks for its own host; other hosts are allowed."""
        if self._robots is None or not hu.same_site(url, self.site):
            return True
        return self._robots.can_fetch(hu.ROBOTS_AGENT, url)

    def _get(self, url):
        """Fetch with polite delay; returns (body, ctype, final) or None."""
        if self.delay:
            time.sleep(self.delay)
        try:
            got = hu.fetch(url)
        except (URLError, OSError, ValueError) as e:
            return self._fail(url, str(getattr(e, "reason", e)))
        if not self._allowed(got[2]):
            return self._fail(url, f"redirected to {got[2]}, blocked by robots.txt")
        return got

    def _fail(self, url, reason):
        self.failed.append((url, reason))
        self.log(f"[!] {url}: {reason}")
        return None

    def _crawl(self):
        queue = deque([(self.url, 0)])
        seen = {self.url}
        while queue and len(self.pages) < self.max_pages:
            url, depth = queue.popleft()
            if not self._allowed(url):
                self.log(f"[-] skipped by robots.txt: {url}")
                continue
            got = self._get(url)
            if got is None:
                continue
            body, ctype, final = got
            if url == self.url and not hu.same_site(final, self.site):
                # example.com -> www.example.com: follow the site where it lives.
                self.site = final
                self._load_robots()
                if not self._allowed(final):
                    self._fail(url, f"redirected to {final}, blocked by robots.txt")
                    continue
            if "html" not in hu.mime_type(ctype):
                # A link that turned out to be a file (PDF, image...).
                if self.include_assets and len(self.assets) < self.max_assets:
                    self._save_asset(url, body)
                continue
            html = hu.decode(body, charset=hu.charset_of(ctype))
            self.pages[url] = (self._claim(hu.local_path(final, page=True), final), html, final)
            self.log(f"[+] page {self.pages[url][0]}")
            if depth >= self.max_depth:
                continue
            for link in hu.find_links(html, final):
                if link not in seen and hu.same_site(link, self.site):
                    seen.add(link)
                    queue.append((link, depth + 1))

    def _claim(self, path, url):
        """Reserve a local path for url, renaming it if another URL has it.

        Windows paths ignore case, so /Foo and /foo would share one file.
        """
        key = path.lower()
        owner = self._paths.get(key)
        if owner is not None and owner != url:
            root, ext = posixpath.splitext(path)
            path = f"{root}_{hashlib.sha1(url.encode()).hexdigest()[:8]}{ext}"
            key = path.lower()
        self._paths[key] = url
        return path

    # -- assets -----------------------------------------------------------

    def _asset_path(self, url):
        if hu.same_site(url, self.site):
            path = hu.local_path(url, page=False)
        else:
            host = urlparse(url).netloc.replace(":", "_")
            path = f"_external/{host}/" + hu.local_path(url, page=False)
        return self._claim(path, url)

    def _save_asset(self, url, body):
        path = self._asset_path(url)
        if not self._write(path, body, url):
            return None
        self.assets[url] = path
        return path

    def _download_assets(self):
        queue = deque()
        for _, html, final in self.pages.values():
            queue.extend(hu.find_assets(html, final))
        while queue:
            url = queue.popleft()
            if url in self.assets or url in self.pages:
                continue
            if len(self.assets) >= self.max_assets:
                self.log(f"[!] stopped at {self.max_assets} assets (max_assets)")
                break
            if not self._allowed(url):
                self.log(f"[-] skipped by robots.txt: {url}")
                continue
            got = self._get(url)
            if got is None:
                continue
            body, ctype, final = got
            path = self._save_asset(url, body)
            if path is None:
                continue
            if hu.mime_type(ctype) == "text/css" or path.endswith(".css"):
                # Stylesheets pull in fonts, images and other CSS.
                css = hu.decode(body, charset=hu.charset_of(ctype))
                queue.extend(hu.css_urls(css, final))
                self._css_pending.append((url, path, css, final))
        self.log(f"[+] downloaded {len(self.assets)} asset(s)")
        for url, path, css, final in self._css_pending:
            mapper = self._mapper(path)
            self._write(path, hu.rewrite_css(css, final, mapper).encode("utf-8"), url)

    # -- writing ----------------------------------------------------------

    def _clear_old_redesign(self):
        """Drop a previous redesign's backups so they can't replace this fresh clone."""
        shutil.rmtree(os.path.join(self.output_dir, ORIGINALS), ignore_errors=True)
        theme_css = os.path.join(self.output_dir, THEME_CSS)
        if os.path.isfile(theme_css):
            os.remove(theme_css)

    def _mapper(self, from_path):
        """Map absolute URLs to links relative to the file at from_path."""
        page_paths = {u: p for u, (p, _, _) in self.pages.items()}
        page_paths.update({final: p for _, (p, _, final) in self.pages.items()})

        def mapper(url):
            if url is None:
                return None
            target = page_paths.get(url) or self.assets.get(url)
            if target:
                return hu.relative_link(from_path, target)
            return url  # not cloned: keep it working as an absolute link

        return mapper

    def _write_pages(self):
        for url, (path, html, final) in list(self.pages.items()):
            out = hu.declare_utf8(hu.rewrite_html(html, final, self._mapper(path)))
            if not self._write(path, out.encode("utf-8"), url):
                del self.pages[url]

    def _write(self, rel_path, data, url):
        """Save one file; a file we can't save is recorded, not fatal."""
        full = os.path.join(self.output_dir, *rel_path.split("/"))
        try:
            os.makedirs(os.path.dirname(full), exist_ok=True)
            with open(full, "wb") as f:
                f.write(data)
        except OSError as e:
            self._fail(url, f"could not save {rel_path}: {e.strerror or e}")
            return False
        return True

    def _write_manifest(self):
        if not self.pages:
            raise RuntimeError(f"Could not save any pages from {self.url}")
        manifest = {
            "tool": "mimic2",
            "source_url": self.url,
            "cloned_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "theme": self.theme,
            "entry": self.pages[self.url][0] if self.url in self.pages
                     else next(iter(self.pages.values()))[0],
            "pages": {u: p for u, (p, _, _) in self.pages.items()},
            "assets": self.assets,
            "failed": [{"url": u, "reason": r} for u, r in self.failed],
        }
        with open(os.path.join(self.output_dir, MANIFEST), "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2)
        return manifest
