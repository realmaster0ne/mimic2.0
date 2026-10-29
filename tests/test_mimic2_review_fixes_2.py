"""Tests for the full-PR code review of PR #1."""
import pytest

from mimic2 import themes
from mimic2.clone.web_cloner import ORIGINALS, THEME_CSS, WebAppCloner
from mimic2.redesign.theme_engine import ThemeEngine
from mimic2.utils import color_utils as cu
from mimic2.utils import html_utils as hu


def cloner(url, out, **kw):
    kw.setdefault("delay", 0)
    kw.setdefault("log", lambda *a: None)
    kw.setdefault("respect_robots", False)
    return WebAppCloner(url=url, output_dir=str(out), **kw)


def fake_site(monkeypatch, files, redirects=None):
    """files: url -> (body str, content type). redirects: url -> final url."""
    redirects = redirects or {}

    def fetch(url):
        final = redirects.get(url, url)
        body, ctype = files[final]
        return body.encode(), ctype, final

    monkeypatch.setattr(hu, "fetch", fetch)


def same_url(url):
    return url


# -- colours --------------------------------------------------------------

def test_id_selectors_that_look_like_hex_are_not_colours():
    css = "#feed { color: #ff0000; } .a #add .x, #cafe:hover{border:1px solid #abc}"
    assert cu.find_colors(css) == {"#ff0000": 1, "#abc": 1}
    out = cu.recolor(css, {"#feed": "#111111", "#add": "#222222", "#cafe": "#333333",
                           "#ff0000": "#00ff00", "#abc": "#123"})
    assert out == "#feed { color: #00ff00; } .a #add .x, #cafe:hover{border:1px solid #123}"


def test_url_fragments_and_strings_are_not_colours():
    css = 'path { fill: url(#abc); } a::after { content: "#fff"; } /* #ddd */ b{color:#eee}'
    assert cu.find_colors(css) == {"#eee": 1}


def test_inline_style_colours_are_still_found():
    assert cu.find_colors("color: #fff; background: rgb(1, 2, 3)") == {
        "#fff": 1, "rgb(1, 2, 3)": 1}


# -- link rewriting -------------------------------------------------------

def local(url):
    return {"http://s.com/p?a=1&b=2": "p.html", "http://s.com/a.png": "a.png",
            "http://s.com/a2.png": "a2.png", "http://s.com/about": "about.html",
            "http://s.com/sub/x.css": "sub/x.css"}.get(url, url) if url else None


def test_links_with_html_entities_are_rewritten():
    out = hu.rewrite_html('<a href="/p?a=1&amp;b=2">P</a>', "http://s.com/", local)
    assert out == '<a href="p.html">P</a>'


def test_unmapped_link_with_entities_stays_valid_html():
    out = hu.rewrite_html('<a href="/q?a=1&amp;b=2">Q</a>', "http://s.com/", local)
    assert out == '<a href="http://s.com/q?a=1&amp;b=2">Q</a>'


def test_srcset_is_rewritten():
    out = hu.rewrite_html('<img src="/a.png" srcset="/a.png 1x, /a2.png 2x">',
                          "http://s.com/", local)
    assert out == '<img src="a.png" srcset="a.png 1x, a2.png 2x">'


def test_fragments_are_kept():
    out = hu.rewrite_html('<a href="/about#team">T</a>', "http://s.com/", local)
    assert out == '<a href="about.html#team">T</a>'


def test_base_href_is_used_for_links_and_then_removed():
    page = '<head><base href="/sub/" target="_blank"></head><link href="x.css">'
    out = hu.rewrite_html(page, "http://s.com/deep/page.html", local)
    assert 'href="sub/x.css"' in out
    assert "<base" in out and "/sub/" not in out.split("<link")[0]


def test_script_bodies_are_not_rewritten():
    page = ('<script src="/a.png"></script>'
            '<script>location.href = "/about"; img.src="/a.png"</script>')
    out = hu.rewrite_html(page, "http://s.com/", local)
    assert out == ('<script src="a.png"></script>'
                   '<script>location.href = "/about"; img.src="/a.png"</script>')


# -- charsets and content types -------------------------------------------

def test_content_type_meta_without_charset_gets_a_utf8_declaration():
    page = '<html><head><meta http-equiv="Content-Type" content="text/html"></head></html>'
    assert '<meta charset="utf-8">' in hu.declare_utf8(page)


def test_page_with_no_content_type_is_still_a_page(monkeypatch, tmp_path):
    fake_site(monkeypatch, {"http://s.com/": ("<!DOCTYPE html><html><body>Hi</body></html>", "")})
    m = cloner("http://s.com/", tmp_path / "out", include_assets=False).run()
    assert list(m["pages"]) == ["http://s.com/"]


# -- crawling and re-cloning ----------------------------------------------

def test_redirected_start_page_is_not_cloned_twice(monkeypatch, tmp_path):
    fake_site(monkeypatch,
              {"http://s.com/index.html": ('<a href="/index.html">Home</a><a href="/">Home</a>',
                                           "text/html")},
              redirects={"http://s.com/": "http://s.com/index.html"})
    m = cloner("http://s.com/", tmp_path / "out").run()
    assert list(m["pages"].values()) == ["index.html"]
    assert 'href="index.html"' in (tmp_path / "out" / "index.html").read_text()


def test_shallower_reclone_keeps_backups_of_pages_it_left_alone(monkeypatch, tmp_path):
    fake_site(monkeypatch, {
        "http://s.com/": ('<a href="/deep.html">Deep</a>', "text/html"),
        "http://s.com/deep.html": ("<p style='color:#336699'>Deep</p>", "text/html"),
    })
    out = tmp_path / "out"
    cloner("http://s.com/", out, max_depth=1).run()
    ThemeEngine(str(out), theme="dark", log=lambda *a: None).apply()
    cloner("http://s.com/", out, max_depth=0).run()

    assert (out / ORIGINALS / "deep.html").exists()
    assert not (out / ORIGINALS / "index.html").exists()
    assert (out / THEME_CSS).exists()  # deep.html still uses it
    ThemeEngine(str(out), theme="dark", log=lambda *a: None).apply()
    assert (out / "deep.html").read_text().count("data-mimic2-theme") == 1


def test_find_refs_returns_links_and_assets_in_one_pass():
    links, assets = hu.find_refs('<a href="/x">X</a><img src="/y.png">', "http://s.com/")
    assert links == ["http://s.com/x"] and assets == ["http://s.com/y.png"]


# -- themes ---------------------------------------------------------------

def test_theme_name_must_be_text(tmp_path):
    import yaml
    theme = themes.load("dark")
    theme["name"] = 123
    path = tmp_path / "bad.yaml"
    path.write_text(yaml.safe_dump(theme))
    with pytest.raises(themes.ThemeError, match="name"):
        themes.load(str(path))
