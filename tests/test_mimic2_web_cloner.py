"""Tests for mimic2.clone.web_cloner against a tiny local HTTP site."""
import functools
import http.server
import json
import os
import threading

import pytest

from mimic2.clone.web_cloner import MANIFEST, WebAppCloner

SITE = {
    "index.html": '<html><head><link rel="stylesheet" href="/css/site.css"></head>'
                  '<body><a href="/about/">About</a> <a href="https://other.example/">Out</a>'
                  '<img src="img/logo.png"></body></html>',
    "about/index.html": '<html><body><a href="/">Home</a> <a href="/team.html">Team</a></body></html>',
    "team.html": '<html><body><a href="/deep.html">Deeper</a></body></html>',
    "deep.html": "<html><body>Too deep</body></html>",
    "css/site.css": "body { background: url(../img/bg.png); color: #333; }",
    "img/logo.png": "PNGDATA",
    "img/bg.png": "BGDATA",
    "robots.txt": "User-agent: *\nDisallow:\n",
}


@pytest.fixture
def site(tmp_path):
    root = tmp_path / "site"
    for rel, content in SITE.items():
        f = root / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(content)
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(root))
    handler.log_message = lambda *a: None
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_port}/"
    server.shutdown()


def clone(url, out, **kw):
    kw.setdefault("delay", 0)
    kw.setdefault("log", lambda *a: None)
    return WebAppCloner(url=url, output_dir=str(out), **kw).run()


def test_clone_pages_respects_depth(site, tmp_path):
    out = tmp_path / "out"
    m = clone(site, out, max_depth=2)
    assert sorted(m["pages"].values()) == ["about/index.html", "index.html", "team.html"]
    assert m["entry"] == "index.html"
    assert not (out / "deep.html").exists()


def test_clone_rewrites_links_to_local_copy(site, tmp_path):
    out = tmp_path / "out"
    clone(site, out, include_assets=True)
    index = (out / "index.html").read_text()
    assert 'href="about/index.html"' in index
    assert 'href="css/site.css"' in index
    assert 'src="img/logo.png"' in index
    assert 'href="https://other.example/"' in index  # external link untouched
    about = (out / "about" / "index.html").read_text()
    assert 'href="../index.html"' in about


def test_clone_assets_and_css_references(site, tmp_path):
    out = tmp_path / "out"
    m = clone(site, out, include_assets=True)
    assert (out / "img" / "logo.png").read_text() == "PNGDATA"
    assert (out / "img" / "bg.png").read_text() == "BGDATA"  # found via CSS url()
    assert "url(../img/bg.png)" in (out / "css" / "site.css").read_text()
    assert set(m["assets"].values()) >= {"css/site.css", "img/logo.png", "img/bg.png"}


def test_without_assets_links_stay_absolute(site, tmp_path):
    out = tmp_path / "out"
    clone(site, out)
    assert not (out / "css").exists()
    assert f'href="{site}css/site.css"' in (out / "index.html").read_text()


def test_manifest_written(site, tmp_path):
    out = tmp_path / "out"
    clone(site, out, theme="dark", max_depth=0)
    m = json.loads((out / MANIFEST).read_text())
    assert m["tool"] == "mimic2"
    assert m["source_url"] == site
    assert m["theme"] == "dark"
    assert list(m["pages"].values()) == ["index.html"]


def test_robots_disallow(site, tmp_path):
    robots = os.path.join(tmp_path, "site", "robots.txt")
    with open(robots, "w") as f:
        f.write("User-agent: *\nDisallow: /about/\n")
    m = clone(site, tmp_path / "out")
    assert "about/index.html" not in m["pages"].values()


def test_unreachable_site_raises(tmp_path):
    with pytest.raises(RuntimeError):
        clone("http://127.0.0.1:9/", tmp_path / "out", respect_robots=False)
