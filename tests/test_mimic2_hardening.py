"""Tests for the code-review fixes: download limits, robots.txt, redirects,
re-cloning, Windows-safe names, charsets, redesign edge cases and CLI errors."""
import functools
import http.server
import threading

import pytest

from mimic2 import themes
from mimic2.cli import main, split_palette
from mimic2.clone.web_cloner import ORIGINALS, THEME_CSS, WebAppCloner, normalize_url
from mimic2.redesign.theme_engine import ThemeEngine
from mimic2.utils import html_utils as hu

SITE = {
    "index.html": '<html><head><link rel="stylesheet" href="/css/site.css"></head>'
                  '<body><a href="/about/">About</a><img src="/img/logo.png"></body></html>',
    "about/index.html": "<html><body>About us</body></html>",
    "css/site.css": "body { color: #333333; background: #ffffff; }",
    "img/logo.png": "PNGDATA",
    "big.bin": "x" * 5000,
    "latin.html": None,  # bytes, written below
}
LATIN_PAGE = '<html><head><meta charset="iso-8859-1"></head><body>caf\xe9</body></html>'


class Handler(http.server.SimpleHTTPRequestHandler):
    """Static files, plus a few special routes set per test."""
    routes = {}

    def log_message(self, *a):
        pass

    def do_GET(self):
        route = self.routes.get(self.path)
        if route is None:
            return super().do_GET()
        status, headers = route
        self.send_response(status)
        for k, v in headers.items():
            self.send_header(k, v.format(port=self.server.server_port))
        self.send_header("Content-Length", "0")
        self.end_headers()


@pytest.fixture
def site(tmp_path):
    root = tmp_path / "site"
    for rel, content in SITE.items():
        f = root / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        if content is None:
            f.write_bytes(LATIN_PAGE.encode("iso-8859-1"))
        else:
            f.write_text(content)
    handler = type("H", (Handler,), {"routes": {}})
    server = http.server.ThreadingHTTPServer(
        ("127.0.0.1", 0), functools.partial(handler, directory=str(root)))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    site = type("Site", (), {})()
    site.url = f"http://127.0.0.1:{server.server_port}/"
    site.port = server.server_port
    site.root = root
    site.routes = handler.routes
    yield site
    server.shutdown()


def cloner(url, out, **kw):
    kw.setdefault("delay", 0)
    kw.setdefault("log", lambda *a: None)
    return WebAppCloner(url=url, output_dir=str(out), **kw)


# -- download limits ------------------------------------------------------

def test_fetch_refuses_oversized_files(site):
    with pytest.raises(ValueError, match="too large"):
        hu.fetch(site.url + "big.bin", max_bytes=1000)
    body, _, _ = hu.fetch(site.url + "big.bin", max_bytes=10000)
    assert len(body) == 5000


def test_asset_count_is_capped(site, tmp_path):
    m = cloner(site.url, tmp_path / "out", include_assets=True, max_assets=1).run()
    assert len(m["assets"]) == 1


# -- robots.txt -------------------------------------------------------------

def test_robots_rules_for_mimic2_are_obeyed(site, tmp_path):
    (site.root / "robots.txt").write_text("User-agent: mimic2\nDisallow: /about/\n")
    m = cloner(site.url, tmp_path / "out").run()
    assert "about/index.html" not in m["pages"].values()


def test_robots_applies_to_assets(site, tmp_path):
    (site.root / "robots.txt").write_text("User-agent: *\nDisallow: /img/\n")
    m = cloner(site.url, tmp_path / "out", include_assets=True).run()
    assert "img/logo.png" not in m["assets"].values()
    assert "css/site.css" in m["assets"].values()


def test_forbidden_robots_txt_means_keep_out(site, tmp_path):
    site.routes["/robots.txt"] = (403, {})
    with pytest.raises(RuntimeError):
        cloner(site.url, tmp_path / "out").run()


def test_crawl_delay_is_honoured(site, tmp_path):
    (site.root / "robots.txt").write_text("User-agent: *\nCrawl-delay: 2\n")
    c = cloner(site.url, tmp_path / "out")
    c._load_robots()
    assert c.delay == 2


# -- URLs and redirects ---------------------------------------------------

def test_normalize_url():
    assert normalize_url("localhost:8080") == "https://localhost:8080"
    assert normalize_url("example.com/shop") == "https://example.com/shop"
    for bad in ("file:///etc/passwd", "ftp://example.com/", "https://"):
        with pytest.raises(ValueError):
            normalize_url(bad)


def test_start_url_redirecting_to_another_host_is_followed(site, tmp_path):
    # localhost -> 127.0.0.1 is a different host, like example.com -> www.example.com.
    site.routes["/go"] = (302, {"Location": "http://127.0.0.1:{port}/"})
    m = cloner(f"http://localhost:{site.port}/go", tmp_path / "out", respect_robots=False).run()
    assert "about/index.html" in m["pages"].values()


# -- saving files ---------------------------------------------------------

def test_unsavable_file_is_recorded_not_fatal(site, tmp_path):
    out = tmp_path / "out"
    (out / "img" / "logo.png").mkdir(parents=True)  # a folder where the file should go
    m = cloner(site.url, out, include_assets=True).run()
    assert any("could not save img/logo.png" in f["reason"] for f in m["failed"])
    assert (out / "index.html").exists()


def test_paths_that_differ_only_in_case_get_their_own_file(tmp_path):
    c = cloner("http://example.com/", tmp_path)
    first = c._claim("Foo.html", "http://example.com/Foo")
    second = c._claim("foo.html", "http://example.com/foo")
    assert first == "Foo.html"
    assert second.lower() != first.lower()
    assert c._claim("Foo.html", "http://example.com/Foo") == "Foo.html"


def test_local_path_is_windows_safe():
    assert hu.local_path("https://x.com/con.html") == "con_.html"
    assert hu.local_path("https://x.com/aux/x.png") == "aux_/x.png"
    assert hu.local_path("https://x.com/a./b.png") == "a/b.png"
    assert len(hu.local_path("https://x.com/" + "a" * 300 + ".png")) <= 120


def test_pages_saved_as_utf8_say_so(site, tmp_path):
    out = tmp_path / "out"
    cloner(site.url + "latin.html", out, max_depth=0).run()
    saved = (out / "latin.html").read_text(encoding="utf-8")
    assert "café" in saved
    assert 'charset="utf-8"' in saved


# -- re-cloning and redesign ----------------------------------------------

def test_reclone_replaces_old_redesign_backups(site, tmp_path):
    out = tmp_path / "out"
    cloner(site.url, out, max_depth=0).run()
    ThemeEngine(str(out), theme="dark", log=lambda *a: None).apply()
    assert (out / ORIGINALS).exists()

    (site.root / "index.html").write_text("<html><body>New content</body></html>")
    cloner(site.url, out, max_depth=0).run()
    assert not (out / ORIGINALS).exists() and not (out / THEME_CSS).exists()
    ThemeEngine(str(out), theme="light", log=lambda *a: None).apply()
    assert "New content" in (out / "index.html").read_text()


def redesign_page(tmp_path, html):
    (tmp_path / "index.html").write_text(html)
    ThemeEngine(str(tmp_path), theme="dark", log=lambda *a: None).apply()
    return (tmp_path / "index.html").read_text()


def test_theme_link_goes_after_doctype_when_no_head(tmp_path):
    page = redesign_page(tmp_path, "<!DOCTYPE html><html><body>Hi</body></html>")
    assert page.startswith("<!DOCTYPE html><html>")
    assert "data-mimic2-theme" in page


def test_head_in_a_comment_is_not_used(tmp_path):
    page = redesign_page(
        tmp_path, "<html><head><!-- </head> --><title>x</title></head><body></body></html>")
    assert page.index("data-mimic2-theme") > page.index("<title>")


def test_colour_words_outside_tags_are_left_alone(tmp_path):
    page = redesign_page(
        tmp_path,
        '<html><head></head><body bgcolor="white"><a href="/s?text=white">x</a>'
        '<script>var text = "white";</script></body></html>')
    assert 'bgcolor="white"' not in page
    assert "?text=white" in page and 'text = "white"' in page


# -- CLI and themes -------------------------------------------------------

def test_palette_split_keeps_rgb_together():
    assert split_palette("#f00, rgb(0, 128, 0),hsl(200,50%,40%)") == [
        "#f00", "rgb(0, 128, 0)", "hsl(200,50%,40%)"]


def test_bad_theme_fails_before_downloading(tmp_path, capsys):
    out = tmp_path / "never"
    with pytest.raises(SystemExit) as e:
        main(["clone", "http://127.0.0.1:9/", "-o", str(out), "-t", "drak"])
    assert e.value.code == 1
    assert "Unknown theme" in capsys.readouterr().err
    assert not out.exists()


def test_bad_url_is_a_clean_error(tmp_path, capsys):
    with pytest.raises(SystemExit) as e:
        main(["clone", "file:///etc/passwd", "-o", str(tmp_path / "x")])
    assert e.value.code == 1
    assert "http" in capsys.readouterr().err


def test_broken_theme_yaml_is_a_theme_error(tmp_path):
    bad = tmp_path / "bad.yaml"
    bad.write_text("palette: [#fff\n  oops: : :")
    with pytest.raises(themes.ThemeError):
        themes.load(str(bad))
    bad.write_text("- just\n- a list\n")
    with pytest.raises(themes.ThemeError):
        themes.load(str(bad))
