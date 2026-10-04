"""Tests for mimic2.utils.color_utils."""
import pytest

from mimic2.utils import color_utils as cu


@pytest.mark.parametrize("text, expected", [
    ("#fff", (255, 255, 255, 1.0)),
    ("#FF8000", (255, 128, 0, 1.0)),
    ("#ff800080", (255, 128, 0, 0.502)),
    ("rgb(10, 20, 30)", (10, 20, 30, 1.0)),
    ("rgba(10,20,30,0.5)", (10, 20, 30, 0.5)),
    ("rgb(10 20 30 / 50%)", (10, 20, 30, 0.5)),
    ("hsl(0, 100%, 50%)", (255, 0, 0, 1.0)),
    ("hsla(120deg 100% 25% / 0.25)", (0, 128, 0, 0.25)),
    ("white", (255, 255, 255, 1.0)),
    ("transparent", (0, 0, 0, 0.0)),
])
def test_parse_color(text, expected):
    assert cu.parse_color(text) == expected


@pytest.mark.parametrize("text", ["#ggg", "#12345", "rgb(1,2)", "notacolor", "url(x)"])
def test_parse_color_rejects(text):
    assert cu.parse_color(text) is None


def test_to_css():
    assert cu.to_css((255, 128, 0, 1.0)) == "#ff8000"
    assert cu.to_css((255, 128, 0, 0.5)) == "rgba(255, 128, 0, 0.5)"


def test_lighten_darken():
    red = cu.parse_color("#ff0000")
    assert cu.to_hsl(cu.lighten(red, 0.2))[2] == pytest.approx(0.7, abs=0.01)
    assert cu.to_hsl(cu.darken(red, 0.2))[2] == pytest.approx(0.3, abs=0.01)
    assert cu.lighten(cu.parse_color("#fff"), 0.5)[:3] == (255, 255, 255)


def test_contrast_ratio():
    black, white = cu.parse_color("#000"), cu.parse_color("#fff")
    assert cu.contrast_ratio(black, white) == pytest.approx(21)
    assert cu.contrast_ratio(white, white) == pytest.approx(1)


def test_find_colors_counts_and_ignores_names():
    css = "a{color:#06c} a:hover{color:#06c} .red{background:rgb(0 0 0 / 50%)} b{color:red}"
    assert cu.find_colors(css) == {"#06c": 2, "rgb(0 0 0 / 50%)": 1}


def test_color_map_dark_theme_inverts_neutrals():
    colors = {"#ffffff": 5, "#222222": 3, "#888888": 1}
    m = cu.build_color_map(colors, ["#8b5cf6"], background="#111111", text="#eeeeee")
    assert m["#ffffff"] == "#111111"  # white page -> dark background
    # Dark text becomes light text that is still readable on the new background.
    new_text, new_bg = cu.parse_color(m["#222222"]), cu.parse_color(m["#ffffff"])
    assert cu.luminance(new_text) > cu.luminance(new_bg)
    assert cu.contrast_ratio(new_text, new_bg) >= 4.5
    mid = cu.luminance(cu.parse_color(m["#888888"]))
    assert 0.1 < mid < 0.6


def test_color_map_accents_by_usage_and_shades():
    colors = {"#0066cc": 10, "#004c99": 2, "#e53935": 4}
    m = cu.build_color_map(colors, ["#10b981", "#f59e0b"], background="#fff", text="#000")
    assert m["#0066cc"] == "#10b981"  # most used hue gets the first palette colour
    assert m["#e53935"] == "#f59e0b"
    # The darker hover shade stays darker than its new main colour.
    assert cu.to_hsl(cu.parse_color(m["#004c99"]))[2] < cu.to_hsl(cu.parse_color(m["#0066cc"]))[2]
    assert abs(cu.to_hsl(cu.parse_color(m["#004c99"]))[0] - cu.to_hsl(cu.parse_color("#10b981"))[0]) < 2


def test_color_map_keeps_alpha():
    m = cu.build_color_map({"rgba(0,0,0,0.5)": 1}, ["#f00"], background="#fff", text="#123456")
    assert m["rgba(0,0,0,0.5)"] == "rgba(18, 52, 86, 0.5)"


def test_recolor_only_mapped():
    css = "body{background:#fff;color:#333} a{color:#06c}"
    out = cu.recolor(css, {"#fff": "#111111", "#333": "#eeeeee"})
    assert out == "body{background:#111111;color:#eeeeee} a{color:#06c}"
