"""HTML/CSS helpers for cloning a site: fetch pages, find what they link to,
and rewrite those links to point at the local copy.

Standard library only. Finding uses html.parser; rewriting uses regexes on the
original text so everything we don't touch (whitespace, comments, inline
scripts) is kept byte-for-byte.
"""
import hashlib
import posixpath
import re
from html.parser import HTMLParser
from urllib.parse import unquote, urldefrag, urljoin, urlparse
from urllib.request import Request, urlopen

USER_AGENT = "Mozilla/5.0 (compatible; mimic2/2.0)"

PAGE_EXTS = {"", ".html", ".htm", ".php", ".asp", ".aspx", ".jsp"}

# url(...) and @import "..." inside CSS.
_CSS_URL = re.compile(r"""url\(\s*(['"]?)([^'")]+)\1\s*\)""", re.I)
_CSS_IMPORT = re.compile(r"""@import\s+(['"])([^'"]+)\1""", re.I)
# href/src attributes in HTML: quoted (href="...") or bare (href=/x, common
# in minified pages).
_ATTR = re.compile(r"""(\b(?:href|src)\s*=\s*)(?:(['"])(.*?)\2|([^\s>'"`=]+))""", re.I | re.S)
# <style>...</style> blocks and style="..." attributes, for CSS url()s.
_STYLE_BLOCK = re.compile(r"(<style\b[^>]*>)(.*?)(</style>)", re.I | re.S)
_STYLE_ATTR = re.compile(r"""(\bstyle\s*=\s*)(['"])(.*?)\2""", re.I | re.S)


def fetch(url, timeout=15):
    """GET a URL and return (body bytes, content type, final URL after redirects)."""
    req = Request(url, headers={"User-Agent": USER_AGENT})
    with urlopen(req, timeout=timeout) as resp:
        ctype = resp.headers.get("Content-Type", "").split(";")[0].strip().lower()
        return resp.read(), ctype, resp.geturl()


def decode(body, default="utf-8"):
    """Decode page bytes, honouring a <meta charset> if there is one."""
    m = re.search(rb"""<meta[^>]+charset=['"]?([\w-]+)""", body[:2048], re.I)
    encoding = m.group(1).decode("ascii") if m else default
    try:
        return body.decode(encoding, errors="replace")
    except LookupError:
        return body.decode(default, errors="replace")


def _absolute(ref, base_url):
    """Resolve a reference against base_url; None for links we can't clone."""
    ref = (ref or "").strip()
    if not ref or ref.startswith(("#", "data:", "javascript:", "mailto:", "tel:")):
        return None
    url, _ = urldefrag(urljoin(base_url, ref))
    return url if urlparse(url).scheme in ("http", "https") else None


class _RefCollector(HTMLParser):
    """Collects page links and asset URLs from one HTML document."""

    def __init__(self, base_url):
        super().__init__(convert_charrefs=True)
        self.base_url = base_url
        self.links = []
        self.assets = []

    def _add(self, bucket, ref):
        url = _absolute(ref, self.base_url)
        if url and url not in bucket:
            bucket.append(url)

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "base" and a.get("href"):
            self.base_url = urljoin(self.base_url, a["href"])
        elif tag == "a":
            self._add(self.links, a.get("href"))
        elif tag == "link":
            rel = (a.get("rel") or "").lower()
            if any(r in rel for r in ("stylesheet", "icon", "preload", "manifest")):
                self._add(self.assets, a.get("href"))
        elif tag in ("img", "script", "source", "video", "audio", "iframe"):
            self._add(self.assets, a.get("src"))
            for part in (a.get("srcset") or "").split(","):
                if part.strip():
                    self._add(self.assets, part.split()[0])
        if a.get("style"):
            for url in css_urls(a["style"], self.base_url):
                if url not in self.assets:
                    self.assets.append(url)

    def handle_data(self, data):
        if self.lasttag == "style":
            for url in css_urls(data, self.base_url):
                if url not in self.assets:
                    self.assets.append(url)


def find_links(html, base_url):
    """Absolute URLs of <a href> links in the page, in order, no duplicates."""
    c = _RefCollector(base_url)
    c.feed(html)
    return c.links


def find_assets(html, base_url):
    """Absolute URLs of stylesheets, scripts, images, icons and media."""
    c = _RefCollector(base_url)
    c.feed(html)
    return c.assets


def css_urls(css, base_url):
    """Absolute URLs referenced from CSS via url(...) or @import."""
    found = []
    for pattern in (_CSS_URL, _CSS_IMPORT):
        for m in pattern.finditer(css):
            url = _absolute(m.group(2), base_url)
            if url and url not in found:
                found.append(url)
    return found


def same_site(url, root_url):
    """True if url is on the same host as root_url."""
    return urlparse(url).netloc.lower() == urlparse(root_url).netloc.lower()


def is_page(url):
    """Guess from the path whether a URL is an HTML page rather than an asset."""
    return posixpath.splitext(urlparse(url).path)[1].lower() in PAGE_EXTS


def local_path(url, page=None):
    """Relative file path to save url under, e.g. 'about/index.html'.

    Pages get an .html file (folders become index.html); assets keep their
    path. Query strings are folded into the name with a short hash so
    style.css?v=1 and style.css?v=2 don't overwrite each other.
    """
    parsed = urlparse(url)
    path = unquote(parsed.path)
    if page is None:
        page = is_page(url)
    if path.endswith("/") or not path:
        path += "index.html" if page else "index"
    path = posixpath.normpath(path).lstrip("/")
    if path in (".", ""):
        path = "index.html"
    root, ext = posixpath.splitext(path)
    if page and ext.lower() not in (".html", ".htm"):
        root, ext = path, ".html"
    if parsed.query:
        root += "_" + hashlib.sha1(parsed.query.encode()).hexdigest()[:8]
    # Keep paths safe on Windows.
    root = re.sub(r'[<>:"|?*]', "_", root)
    return root + ext


def relative_link(from_file, to_file):
    """Link from one saved file to another, e.g. ('a/b.html', 'c.css') -> '../c.css'."""
    start = posixpath.dirname(from_file) or "."
    return posixpath.relpath(to_file, start)


def _rewrite_css_text(css, base_url, mapper):
    def css_sub(m):
        new = mapper(_absolute(m.group(2), base_url))
        return f"url({m.group(1)}{new}{m.group(1)})" if new else m.group(0)

    def import_sub(m):
        new = mapper(_absolute(m.group(2), base_url))
        return f"@import {m.group(1)}{new}{m.group(1)}" if new else m.group(0)

    return _CSS_IMPORT.sub(import_sub, _CSS_URL.sub(css_sub, css))


def rewrite_html(html, base_url, mapper):
    """Rewrite href/src attributes and CSS url()s in a page.

    mapper(absolute_url) returns the replacement link, or None to leave that
    reference as it is (e.g. external links we didn't download).
    """

    def attr_sub(m):
        quote = m.group(2) or '"'
        ref = m.group(3) if m.group(2) else m.group(4)
        new = mapper(_absolute(ref, base_url))
        return f"{m.group(1)}{quote}{new}{quote}" if new else m.group(0)

    def style_block(m):
        return m.group(1) + _rewrite_css_text(m.group(2), base_url, mapper) + m.group(3)

    def style_attr(m):
        css = _rewrite_css_text(m.group(3), base_url, mapper)
        return f"{m.group(1)}{m.group(2)}{css}{m.group(2)}"

    html = _ATTR.sub(attr_sub, html)
    html = _STYLE_BLOCK.sub(style_block, html)
    return _STYLE_ATTR.sub(style_attr, html)


def rewrite_css(css, base_url, mapper):
    """Rewrite url(...) and @import references in a stylesheet (see rewrite_html)."""
    return _rewrite_css_text(css, base_url, mapper)
