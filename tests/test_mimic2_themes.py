"""Tests for the built-in mimic2 themes and their loader."""
import pytest

from mimic2 import themes
from mimic2.utils.color_utils import contrast_ratio, parse_color


def test_available():
    assert themes.available() == ["minimal-light", "modern-dark"]


@pytest.mark.parametrize("name", ["modern-dark", "modern_dark", "dark", "minimal-light", "light"])
def test_load_by_name_and_alias(name):
    t = themes.load(name)
    assert t["name"] in themes.available()


@pytest.mark.parametrize("name", ["modern-dark", "minimal-light"])
def test_builtin_themes_are_readable(name):
    t = themes.load(name)
    bg, text = parse_color(t["background"]), parse_color(t["text"])
    assert contrast_ratio(text, bg) >= 7  # WCAG AAA for body text
    assert contrast_ratio(parse_color(t["muted"]), bg) >= 4.5
    for accent in t["palette"][:2]:
        assert contrast_ratio(parse_color(accent), bg) >= 3  # links/buttons stand out


def test_dark_and_light_modes():
    assert themes.load("dark")["mode"] == "dark"
    assert themes.load("light")["mode"] == "light"


def test_unknown_theme():
    with pytest.raises(themes.ThemeError, match="Unknown theme"):
        themes.load("neon-banana")


def test_custom_theme_file(tmp_path):
    f = tmp_path / "mine.yaml"
    f.write_text(
        'background: "#000"\nsurface: "#111"\ntext: "#fff"\nmuted: "#aaa"\nborder: "#333"\n'
        'palette: ["#ff0"]\nfonts: {body: Arial, heading: Arial, mono: monospace}\n'
    )
    t = themes.load(str(f))
    assert t["name"] == "mine"
    assert t["radius"] is None and t["fonts"]["import"] is None


def test_invalid_colour_rejected(tmp_path):
    f = tmp_path / "bad.yaml"
    f.write_text(
        'background: "blurple"\nsurface: "#111"\ntext: "#fff"\nmuted: "#aaa"\nborder: "#333"\n'
        'palette: ["#ff0"]\nfonts: {body: a, heading: a, mono: a}\n'
    )
    with pytest.raises(themes.ThemeError, match="background"):
        themes.load(str(f))


def test_builtin_layouts_differ():
    dark, light = themes.load("dark")["layout"], themes.load("light")["layout"]
    for key in ("header", "cards", "buttons", "nav_style"):
        assert dark[key] != light[key]


def test_layout_defaults_and_validation(tmp_path):
    base = ('background: "#000"\nsurface: "#111"\ntext: "#fff"\nmuted: "#aaa"\nborder: "#333"\n'
            'palette: ["#ff0"]\nfonts: {body: a, heading: a, mono: a}\n')
    ok = tmp_path / "ok.yaml"
    ok.write_text(base + "layout: {cards: elevated}\n")
    layout = themes.load(str(ok))["layout"]
    assert layout["cards"] == "elevated" and layout["buttons"] == "rounded"  # default filled in
    bad = tmp_path / "bad.yaml"
    bad.write_text(base + "layout: {buttons: blob}\n")
    with pytest.raises(themes.ThemeError, match="layout.buttons"):
        themes.load(str(bad))
