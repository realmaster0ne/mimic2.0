"""End-to-end tests: run the mimic2 CLI against a small local site, the way a
user would, and check the clone works offline and the redesign changed it."""
import functools
import http.server
import json
import re
import threading
from pathlib import Path

import pytest

from mimic2 import themes
from mimic2.cli import main
from mimic2.redesign.theme_engine import ORIGINALS, THEME_CSS
from mimic2.utils import color_utils as cu

SITE = {
    "index.html": """<!doctype html><html><head><title>Shop</title>
<link rel="stylesheet" href="/static/site.css">
</head><body>
<header class="top"><a href="/">Shop</a> <a href="/products/">Products</a></header>
<h1>Welcome</h1>
<img src="/static/logo.png" alt="logo">
<a class="btn" href="/products/">Browse</a>
<a href="https://elsewhere.example/">Partner</a>
</body></html>""",
    "products/index.html": """<!doctype html><html><head>
<link rel="stylesheet" href="../static/site.css"></head><body>
<a href="../">Home</a> <span class="price" style="color: #2e7d32">$9.99</span>
</body></html>""",
    "static/site.css": """body { background: #ffffff; color: #212121; font-family: Arial, sans-serif; }
.top { background: #f5f5f5; border-bottom: 1px solid #e0e0e0; }
a { color: #1565c0; } a:hover { color: #0d47a1; }
.btn { background: #1565c0; color: #ffffff; border-radius: 6px; }
h1 { background-image: url(hero.png); }
""",
    "static/logo.png": "LOGO",
    "static/hero.png": "HERO",
}
ORIGINAL_COLORS = {"#ffffff", "#212121", "#1565c0", "#0d47a1", "#2e7d32"}


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


@pytest.fixture(autouse=True)
def no_delay(monkeypatch):
    # Keep the polite crawl delay out of the test run.
    from mimic2.clone import web_cloner
    original = web_cloner.WebAppCloner.__init__
    monkeypatch.setattr(web_cloner.WebAppCloner, "__init__",
                        lambda self, *a, **kw: original(self, *a, **{**kw, "delay": 0}))


def run(*argv):
    """Run the CLI; returns the exit code (0 on success)."""
    try:
        main([str(a) for a in argv])
    except SystemExit as e:
        return e.code
    return 0


def local_refs(page):
    """href/src values in a saved page that point at files in the clone."""
    refs = re.findall(r'(?:href|src)="([^"]+)"', page.read_text())
    return [r for r in refs if not re.match(r"[a-z]+:|#", r)]


def test_clone_then_redesign(site, tmp_path):
    out = tmp_path / "my-app"
    assert run("clone", site, "--output", out) == 0
    assert run("redesign", out, "--theme", "dark") == 0

    dark = themes.load("dark")
    css = (out / "static" / "site.css").read_text()
    pages = [out / "index.html", out / "products" / "index.html"]

    # Colours: none of the originals survive, the theme's are in.
    styled = css + "".join(p.read_text() for p in pages)
    assert not ORIGINAL_COLORS & {c.lower() for c in cu.find_colors(styled)}
    assert f"background: {dark['background']}" in css
    assert dark["palette"][0] in css
    assert f"font-family: {dark['fonts']['body']}" in css

    # Offline: every local link on every page points at a file in the clone.
    for page in pages:
        for ref in local_refs(page):
            assert (page.parent / ref).resolve().is_file(), f"{page.name}: broken {ref}"
    assert (out / "static" / "hero.png").read_text() == "HERO"  # found via CSS url()
    assert 'href="https://elsewhere.example/"' in pages[0].read_text()

    # Originals kept untouched, theme stylesheet added, manifest updated.
    assert (out / ORIGINALS / "static" / "site.css").read_text() == SITE["static/site.css"]
    assert (out / THEME_CSS).exists()
    manifest = json.loads((out / "mimic2.json").read_text())
    assert manifest["source_url"] == site
    assert manifest["redesign"]["theme"] == "modern-dark"


def test_clone_with_theme_in_one_step(site, tmp_path):
    out = tmp_path / "app"
    assert run("clone", site, "-o", out, "--theme", "light") == 0
    light = themes.load("light")
    assert f"background: {light['background']}" in (out / "static" / "site.css").read_text()


def test_switching_themes_and_custom_palette(site, tmp_path):
    out = tmp_path / "app"
    run("clone", site, "-o", out, "--theme", "dark")
    assert run("redesign", out, "-t", "light") == 0
    assert run("redesign", out, "-t", "dark", "-p", "#ff5733,#3366ff") == 0
    css = (out / "static" / "site.css").read_text()
    assert "a { color: #ff5733; }" in css  # main brand colour -> first custom colour
    assert themes.load("dark")["background"] in css
    assert (out / "index.html").read_text().count("data-mimic2-theme") == 1


def test_text_is_readable_after_redesign(site, tmp_path):
    out = tmp_path / "app"
    run("clone", site, "-o", out)
    for theme in ("dark", "light"):
        run("redesign", out, "-t", theme)
        t = themes.load(theme)
        css = (out / "static" / "site.css").read_text()
        body_text = re.search(r"body \{[^}]*?[^-]color: (#[0-9a-f]{6})", css).group(1)
        ratio = cu.contrast_ratio(cu.parse_color(body_text), cu.parse_color(t["background"]))
        assert ratio >= 4.5, f"{theme}: body text contrast {ratio:.1f}"


def test_no_assets(site, tmp_path):
    out = tmp_path / "app"
    assert run("clone", site, "-o", out, "--no-assets", "--depth", "0") == 0
    assert not (out / "static").exists()
    assert sorted(p.name for p in out.iterdir()) == ["index.html", "mimic2.json"]


def test_themes_command(capsys):
    assert run("themes") == 0
    out = capsys.readouterr().out
    assert "modern-dark" in out and "minimal-light" in out


@pytest.mark.parametrize("argv, message", [
    (["redesign", "{out}"], "--palette"),
    (["redesign", "{out}", "-t", "neon"], "Unknown theme"),
    (["redesign", "{missing}", "-t", "dark"], "No such project folder"),
    (["clone", "http://127.0.0.1:9/", "-o", "{missing}"], "Could not clone"),
    ([], None),
])
def test_errors_exit_nonzero(site, tmp_path, capsys, argv, message):
    out = tmp_path / "app"
    run("clone", site, "-o", out, "--depth", "0")
    capsys.readouterr()
    argv = [a.format(out=out, missing=tmp_path / "missing") for a in argv]
    assert run(*argv) == 1
    if message:
        assert message in capsys.readouterr().err
