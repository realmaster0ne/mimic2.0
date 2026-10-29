"""Tests for the second round of code-review fixes on PR #1."""
import socket
import threading
import time

import pytest

from mimic2.clone.web_cloner import WebAppCloner
from mimic2.utils import html_utils as hu


def cloner(url, out, **kw):
    kw.setdefault("delay", 0)
    kw.setdefault("log", lambda *a: None)
    return WebAppCloner(url=url, output_dir=str(out), **kw)


# -- download limits ------------------------------------------------------

@pytest.fixture
def trickle_url():
    """A server that promises 1 MB but sends one byte every 0.1 s."""
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    listener.listen(1)
    stop = threading.Event()

    def serve():
        conn, _ = listener.accept()
        conn.recv(4096)
        conn.sendall(b"HTTP/1.1 200 OK\r\nContent-Type: text/plain\r\n"
                     b"Content-Length: 1000000\r\n\r\n")
        try:
            while not stop.is_set():
                conn.sendall(b"x")
                time.sleep(0.1)
        except OSError:
            pass
        conn.close()

    threading.Thread(target=serve, daemon=True).start()
    yield f"http://127.0.0.1:{listener.getsockname()[1]}/slow"
    stop.set()
    listener.close()


def test_slow_trickle_download_still_hits_the_time_limit(trickle_url):
    start = time.monotonic()
    with pytest.raises(ValueError, match="longer than"):
        hu.fetch(trickle_url, max_seconds=1)
    assert time.monotonic() - start < 5


def test_huge_robots_crawl_delay_is_capped(monkeypatch, tmp_path):
    robots = b"User-agent: *\nCrawl-delay: 86400\n"
    monkeypatch.setattr(hu, "fetch", lambda url: (robots, "text/plain", url))
    c = cloner("http://example.com/", tmp_path / "out")
    c._load_robots()
    assert 0 < c.delay <= 10


# -- names and URLs -------------------------------------------------------

@pytest.mark.parametrize("url, expected", [
    ("http://x.com/con.tar.gz", "con_.tar.gz"),
    ("http://x.com/CON.txt", "CON_.txt"),
    ("http://x.com/files/nul", "files/nul_"),
    ("http://x.com/console.css", "console.css"),
])
def test_windows_reserved_names_are_renamed_before_the_first_dot(url, expected):
    assert hu.local_path(url, page=False) == expected


def test_url_without_scheme_can_contain_another_url():
    from mimic2.clone.web_cloner import normalize_url
    assert (normalize_url("example.com/login?next=https://example.com/")
            == "https://example.com/login?next=https://example.com/")
    with pytest.raises(ValueError):
        normalize_url("ftp://example.com/?x=https://y")


# -- charsets and the top of the page ------------------------------------

@pytest.mark.parametrize("start", ["﻿", "<!-- built 2026 -->\n", "﻿ <!-- x -->"])
def test_theme_link_stays_after_doctype_behind_bom_or_comment(tmp_path, start):
    from mimic2.redesign.theme_engine import ThemeEngine
    (tmp_path / "index.html").write_text(
        start + "<!DOCTYPE html><html><body>Hi</body></html>", encoding="utf-8")
    ThemeEngine(str(tmp_path), theme="dark", log=lambda *a: None).apply()
    page = (tmp_path / "index.html").read_text(encoding="utf-8")
    assert page.index("<!DOCTYPE") < page.index("data-mimic2-theme")


def test_decode_drops_a_utf8_bom():
    assert hu.decode(b"\xef\xbb\xbf<p>caf\xc3\xa9</p>") == "<p>café</p>"


def test_page_without_meta_charset_gets_one():
    out = hu.declare_utf8("<!DOCTYPE html><html><head><title>x</title></head></html>")
    assert out.startswith('<!DOCTYPE html><html><head><meta charset="utf-8"><title>')


def test_declare_utf8_rewrites_only_real_charset_declarations():
    desc = '<meta name="description" content="charset=koi8-r explained">'
    out = hu.declare_utf8(f"<html><head>{desc}</head></html>")
    assert desc in out and '<meta charset="utf-8">' in out

    http_equiv = ('<html><head><meta http-equiv="Content-Type" '
                  'content="text/html; charset=iso-8859-1"></head></html>')
    out = hu.declare_utf8(http_equiv)
    assert "charset=utf-8" in out and "iso-8859-1" not in out
    assert '<meta charset="utf-8">' not in out

    assert hu.declare_utf8('<meta charset="iso-8859-1">') == '<meta charset="utf-8">'


def test_css_charset_is_used_and_updated(monkeypatch, tmp_path):
    css = '@charset "iso-8859-1";\nbody::after { content: "caf\xe9"; }'.encode("iso-8859-1")
    files = {
        "http://example.com/": (b'<html><head><link rel="stylesheet" href="/s.css">'
                                b"</head></html>", "text/html"),
        "http://example.com/s.css": (css, "text/css"),
    }
    monkeypatch.setattr(hu, "fetch", lambda url: (*files[url], url))
    out = tmp_path / "out"
    cloner("http://example.com/", out, include_assets=True, respect_robots=False).run()
    saved = (out / "s.css").read_bytes().decode("utf-8")
    assert saved.startswith('@charset "utf-8";') and "café" in saved
