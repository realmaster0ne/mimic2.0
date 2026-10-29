"""Tests for mimic2.utils.html_utils (link finding, local paths, rewriting)."""
from mimic2.utils import html_utils as hu

BASE = "https://example.com/blog/post.html"

PAGE = """<html><head>
<link rel="stylesheet" href="/css/site.css?v=2">
<link rel="icon" href="favicon.ico">
<style>body { background: url('img/bg.png'); }</style>
<script src="https://cdn.other.com/lib.js"></script>
</head><body>
<a href="/">Home</a>
<a href="about/">About</a>
<a href="#top">Top</a>
<a href="mailto:me@example.com">Mail</a>
<a href="https://other.com/x">Elsewhere</a>
<img src="pic.jpg" srcset="pic-2x.jpg 2x, pic-3x.jpg 3x">
<div style="background-image: url(/img/hero.png)"></div>
</body></html>"""


def test_find_links_skips_anchors_and_mailto():
    assert hu.find_links(PAGE, BASE) == [
        "https://example.com/",
        "https://example.com/blog/about/",
        "https://other.com/x",
    ]


def test_find_assets():
    assets = hu.find_assets(PAGE, BASE)
    assert "https://example.com/css/site.css?v=2" in assets
    assert "https://example.com/blog/favicon.ico" in assets
    assert "https://example.com/blog/img/bg.png" in assets
    assert "https://cdn.other.com/lib.js" in assets
    assert "https://example.com/blog/pic-3x.jpg" in assets
    assert "https://example.com/img/hero.png" in assets


def test_css_urls():
    css = "@import 'base.css'; .a { background: url(\"../img/x.png\") }"
    assert hu.css_urls(css, "https://example.com/css/site.css") == [
        "https://example.com/img/x.png",
        "https://example.com/css/base.css",
    ]


def test_local_path():
    assert hu.local_path("https://example.com/") == "index.html"
    assert hu.local_path("https://example.com/about/") == "about/index.html"
    assert hu.local_path("https://example.com/contact") == "contact.html"
    assert hu.local_path("https://example.com/css/site.css") == "css/site.css"
    versioned = hu.local_path("https://example.com/css/site.css?v=2")
    assert versioned.startswith("css/site_") and versioned.endswith(".css")
    # Encoded characters Windows can't use in file names are replaced.
    assert hu.local_path("https://example.com/f/font.eot%3Fv=3", page=False) == "f/font.eot_v=3"


def test_relative_link():
    assert hu.relative_link("blog/post.html", "css/site.css") == "../css/site.css"
    assert hu.relative_link("index.html", "css/site.css") == "css/site.css"


def test_rewrite_html_maps_known_urls_only():
    mapping = {
        "https://example.com/css/site.css?v=2": "../css/site.css",
        "https://example.com/blog/img/bg.png": "img/bg.png",
        "https://example.com/img/hero.png": "../img/hero.png",
    }
    out = hu.rewrite_html(PAGE, BASE, mapping.get)
    assert 'href="../css/site.css"' in out
    assert "url('img/bg.png')" in out
    assert "url(../img/hero.png)" in out
    # Unmapped references are left exactly as they were.
    assert 'src="https://cdn.other.com/lib.js"' in out
    assert 'href="#top"' in out


def test_rewrite_html_unquoted_attributes():
    html = "<link rel=icon href=data:,><script src=/s.js></script><a href=about>A</a>"
    mapping = {"https://example.com/s.js": "s.js"}
    out = hu.rewrite_html(html, "https://example.com/", mapping.get)
    assert '<script src="s.js">' in out
    assert "href=data:," in out  # data: URL left alone
    assert "href=about>" in out  # unmapped left alone


def test_same_site_and_is_page():
    assert hu.same_site("https://Example.com/a", "https://example.com/")
    assert not hu.same_site("https://cdn.example.com/a", "https://example.com/")
    assert hu.is_page("https://example.com/about/")
    assert not hu.is_page("https://example.com/a.png")
