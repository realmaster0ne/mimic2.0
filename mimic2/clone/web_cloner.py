"""Clone a website into a local folder that works offline.

The cloner crawls same-site pages breadth-first up to max_depth links from the
start URL, optionally downloads the assets they use (CSS, JS, images, fonts),
then rewrites every link so the copy points at its own files. A mimic2.json
manifest records what was cloned so `mimic2 redesign` can find it later.

Assets from other hosts (CDNs) are saved under _external/<host>/. Links to
pages we didn't clone are made absolute so they still work from the copy.
"""
import json
import os
import time
from collections import deque
from datetime import datetime, timezone
from urllib import robotparser
from urllib.error import URLError
from urllib.parse import urljoin, urlparse

from mimic2.utils import html_utils as hu

MANIFEST = "mimic2.json"


class WebAppCloner:
    def __init__(self, url, output_dir, theme=None, max_depth=3,
                 include_assets=False, max_pages=50, delay=0.2,
                 respect_robots=True, log=print):
        if not urlparse(url).scheme:
            url = "https://" + url
        self.url = url
        self.output_dir = output_dir
        self.theme = theme
        self.max_depth = max_depth
        self.include_assets = include_assets
        self.max_pages = max_pages
        self.delay = delay
        self.respect_robots = respect_robots
        self.log = log
        self.pages = {}    # page URL -> (local path, html text, final URL)
        self.assets = {}   # asset URL -> local path
        self.failed = []   # (url, reason)
        self._css_pending = []  # stylesheets to rewrite once all assets are known
        self._robots = None

    # -- public -----------------------------------------------------------

    def run(self):
        """Crawl, download, rewrite and save. Returns the manifest dict."""
        os.makedirs(self.output_dir, exist_ok=True)
        self._load_robots()
        self._crawl()
        if not self.pages:
            raise RuntimeError(f"Could not clone {self.url}: " +
                               (self.failed[0][1] if self.failed else "no pages"))
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
        rp = robotparser.RobotFileParser(urljoin(self.url, "/robots.txt"))
        try:
            body, _, _ = hu.fetch(rp.url)
            rp.parse(hu.decode(body).splitlines())
            self._robots = rp
        except (URLError, OSError, ValueError):
            self._robots = None  # no robots.txt: everything allowed

    def _allowed(self, url):
        return self._robots is None or self._robots.can_fetch(hu.USER_AGENT, url)

    def _get(self, url):
        """Fetch with polite delay; returns (body, ctype, final) or None."""
        if self.delay:
            time.sleep(self.delay)
        try:
            return hu.fetch(url)
        except (URLError, OSError, ValueError) as e:
            self.failed.append((url, str(getattr(e, "reason", e))))
            self.log(f"[!] {url}: {self.failed[-1][1]}")
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
            if "html" not in ctype:
                # A link that turned out to be a file (PDF, image...).
                if self.include_assets:
                    self._save_asset(url, body)
                continue
            html = hu.decode(body)
            self.pages[url] = (hu.local_path(final, page=True), html, final)
            self.log(f"[+] page {self.pages[url][0]}")
            if depth >= self.max_depth:
                continue
            for link in hu.find_links(html, final):
                if link not in seen and hu.same_site(link, self.url):
                    seen.add(link)
                    queue.append((link, depth + 1))

    # -- assets -----------------------------------------------------------

    def _asset_path(self, url):
        if hu.same_site(url, self.url):
            return hu.local_path(url, page=False)
        host = urlparse(url).netloc.replace(":", "_")
        return f"_external/{host}/" + hu.local_path(url, page=False)

    def _save_asset(self, url, body):
        path = self._asset_path(url)
        self._write(path, body)
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
            got = self._get(url)
            if got is None:
                continue
            body, ctype, final = got
            path = self._save_asset(url, body)
            if ctype == "text/css" or path.endswith(".css"):
                # Stylesheets pull in fonts, images and other CSS.
                css = hu.decode(body)
                queue.extend(hu.css_urls(css, final))
                self._css_pending.append((url, path, css, final))
        self.log(f"[+] downloaded {len(self.assets)} asset(s)")
        for url, path, css, final in self._css_pending:
            mapper = self._mapper(path)
            self._write(path, hu.rewrite_css(css, final, mapper).encode("utf-8"))

    # -- writing ----------------------------------------------------------

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
        for path, html, final in self.pages.values():
            out = hu.rewrite_html(html, final, self._mapper(path))
            self._write(path, out.encode("utf-8"))

    def _write(self, rel_path, data):
        full = os.path.join(self.output_dir, *rel_path.split("/"))
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "wb") as f:
            f.write(data)

    def _write_manifest(self):
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
