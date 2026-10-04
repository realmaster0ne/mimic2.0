"""Tests for mimic2.redesign.theme_engine on a small cloned-site folder."""
import json
import re

import pytest

from mimic2 import themes
from mimic2.redesign.theme_engine import ORIGINALS, THEME_CSS, ThemeEngine
from mimic2.utils import color_utils as cu

INDEX = """<!doctype html><html><head>
<link rel="stylesheet" href="css/site.css">
<style>.hero { background: #0066cc; color: #ffffff; }</style>
</head><body bgcolor="#ffffff">
<a href="#top">Top</a>
<div style="border: 1px solid #cccccc">Card</div>
</body></html>"""

SITE_CSS = """body { background: #ffffff; color: #222222; font-family: Helvetica, Arial, sans-serif; }
a { color: #0066cc; } a:hover { color: #004c99; }
.btn { background: #e53935; border-radius: 6px; }
.avatar { border-radius: 50%; } .pill { border-radius: 999px; }
code { font-family: "Courier New", monospace; }
"""

NO_CSS_PAGE = "<html><body><p>Plain old page</p></body></html>"


@pytest.fixture
def project(tmp_path):
    (tmp_path / "css").mkdir()
    (tmp_path / "about").mkdir()
    (tmp_path / "index.html").write_text(INDEX)
    (tmp_path / "css" / "site.css").write_text(SITE_CSS)
    (tmp_path / "about" / "index.html").write_text(NO_CSS_PAGE)
    (tmp_path / "mimic2.json").write_text(json.dumps({"tool": "mimic2", "pages": {}}))
    return tmp_path


def redesign(project, theme="dark", palette=None):
    return ThemeEngine(str(project), theme=theme, palette=palette, log=lambda *a: None).apply()


def test_colors_replaced_with_theme(project):
    redesign(project, "dark")
    dark = themes.load("dark")
    css = (project / "css" / "site.css").read_text()
    assert "#ffffff" not in css and "#0066cc" not in css
    assert f"background: {dark['background']}" in css      # white page -> dark bg
    assert f"a {{ color: {dark['palette'][0]}; }}" in css   # main brand colour -> accent 1
    assert dark["palette"][1] in css                       # second hue -> accent 2


def test_text_stays_readable(project):
    redesign(project, "dark")
    css = (project / "css" / "site.css").read_text()
    bg = cu.parse_color(themes.load("dark")["background"])
    text = cu.parse_color(css.split("color: ")[1].split(";")[0])
    assert cu.contrast_ratio(text, bg) >= 4.5


def test_inline_styles_and_color_attributes(project):
    redesign(project, "light")
    html = (project / "index.html").read_text()
    assert "#0066cc" not in html and "#cccccc" not in html
    assert 'bgcolor="#ffffff"' not in html
    assert 'href="#top"' in html  # anchors are not mistaken for colours


def test_fonts_and_radius(project):
    redesign(project, "dark")
    dark = themes.load("dark")
    css = (project / "css" / "site.css").read_text()
    assert f"font-family: {dark['fonts']['body']}" in css
    assert f"font-family: {dark['fonts']['mono']}" in css  # code stays monospace
    assert f"border-radius: {dark['radius']}" in css
    assert "border-radius: 50%" in css and "border-radius: 999px" in css


def test_theme_stylesheet_linked_on_every_page(project):
    redesign(project, "dark")
    assert (project / THEME_CSS).exists()
    assert f'href="{THEME_CSS}" data-mimic2-theme' in (project / "index.html").read_text()
    about = (project / "about" / "index.html").read_text()
    assert f'href="../{THEME_CSS}" data-mimic2-theme' in about  # works without a <head>


def test_reapply_starts_from_original(project):
    redesign(project, "dark")
    redesign(project, "light")
    light = themes.load("light")
    css = (project / "css" / "site.css").read_text()
    assert f"background: {light['background']}" in css
    assert (project / ORIGINALS / "css" / "site.css").read_text() == SITE_CSS
    html = (project / "index.html").read_text()
    assert html.count("data-mimic2-theme") == 1  # not injected twice


def test_custom_palette(project):
    redesign(project, "custom", ["#ff5733", "#33ff57"])
    css = (project / "css" / "site.css").read_text()
    assert "a { color: #ff5733; }" in css
    # The bright green is too faint on the light page, so a darker green is used.
    green = cu.parse_color(re.search(r"\.btn \{ background: (#[0-9a-f]{6})", css).group(1))
    assert abs(cu.to_hsl(green)[0] - cu.to_hsl(cu.parse_color("#33ff57"))[0]) < 2
    assert cu.contrast_ratio(green, cu.parse_color(themes.load("light")["background"])) >= 3


def test_custom_needs_palette(project):
    with pytest.raises(themes.ThemeError, match="--palette"):
        ThemeEngine(str(project), theme="custom")
    with pytest.raises(themes.ThemeError, match="Not a colour"):
        ThemeEngine(str(project), theme="dark", palette=["#zzz"])


def test_manifest_records_redesign(project):
    summary = redesign(project, "dark")
    m = json.loads((project / "mimic2.json").read_text())
    assert m["redesign"]["theme"] == "modern-dark"
    assert m["redesign"]["pages"] == 2 and summary["colors_changed"] > 0


def test_empty_folder(tmp_path):
    with pytest.raises(FileNotFoundError, match="clone"):
        redesign(tmp_path)
