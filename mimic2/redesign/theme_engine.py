"""Redesign a cloned site so it looks different from the original.

ThemeEngine works on a folder made by `mimic2 clone`:

1. Collects every colour used in the site's stylesheets, <style> blocks,
   style="..." attributes and old-style colour attributes (bgcolor=...).
2. Maps them onto the theme with color_utils.build_color_map(): greys onto
   the theme's background-to-text ramp, brand colours onto its palette.
3. Rewrites those colours, swaps font-family declarations for the theme's
   fonts and normalises corner rounding.
4. Adds mimic2-theme.css to every page, which sets the theme's background,
   text, link, heading and form styles so even pages with no CSS change.

The untouched files are kept in .mimic2-original/ and every run starts from
them, so you can apply a different theme as many times as you like.
"""
import json
import os
import re
import shutil
from datetime import datetime, timezone

from mimic2 import themes
from mimic2.clone.web_cloner import MANIFEST
from mimic2.utils import color_utils as cu
from mimic2.utils import html_utils as hu

ORIGINALS = ".mimic2-original"
THEME_CSS = "mimic2-theme.css"
SKIP_DIRS = {ORIGINALS, ".git"}

# Old HTML colour attributes: <body bgcolor="#fff" text="#000" link="#00f">.
_COLOR_ATTR = re.compile(
    r"""(\b(?:bgcolor|color|text|link|vlink|alink)\s*=\s*)(['"]?)(#[0-9a-f]{3,8}|[a-z]+)\2""",
    re.I,
)
_FONT_FAMILY = re.compile(r"(font-family\s*:\s*)([^;}{]+)", re.I)
_RADIUS = re.compile(r"(border-radius\s*:\s*)([0-9.]+)(px|rem|em)(?=\s*[;}!])", re.I)
_HEAD_CLOSE = re.compile(r"</head\s*>", re.I)
_MONO_HINT = re.compile(r"mono|courier|consolas|menlo|code", re.I)


class ThemeEngine:
    def __init__(self, project_dir, theme="custom", palette=None, log=print):
        self.project_dir = project_dir
        self.theme = self._resolve_theme(theme, palette)
        self.log = log
        self.color_map = {}

    @staticmethod
    def _resolve_theme(theme, palette):
        """Load the theme; a --palette replaces its accent colours."""
        if theme == "custom":
            if not palette:
                raise themes.ThemeError(
                    "The custom theme needs --palette, e.g. --palette #FF5733,#33FF57")
            theme = "light"
        loaded = themes.load(theme)
        if palette:
            colours = [p.strip() for p in palette if p.strip()]
            bad = [p for p in colours if cu.parse_color(p) is None]
            if bad:
                raise themes.ThemeError(f"Not a colour: {', '.join(bad)}")
            loaded["palette"] = colours
            loaded["name"] = loaded["name"] + "+custom"
        return loaded

    # -- public -----------------------------------------------------------

    def apply(self):
        """Redesign the project in place. Returns a summary dict."""
        if not os.path.isdir(self.project_dir):
            raise FileNotFoundError(f"No such project folder: {self.project_dir}")
        files = self._files()
        pages = [f for f in files if f.lower().endswith((".html", ".htm"))]
        if not pages:
            raise FileNotFoundError(
                f"No HTML pages in {self.project_dir}. Run `mimic2 clone` first.")
        sources = {f: self._original(f) for f in files}

        self.color_map = self._build_color_map(sources)
        for rel, text in sources.items():
            if rel.lower().endswith(".css"):
                out = self._restyle_css(text)
            else:
                out = self._restyle_html(text, rel)
            self._write(rel, out)
        self._write(THEME_CSS, self._theme_css())

        summary = {
            "theme": self.theme["name"],
            "applied_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "pages": len(pages),
            "stylesheets": len(files) - len(pages),
            "colors_changed": sum(1 for k, v in self.color_map.items() if k != v),
        }
        self._update_manifest(summary)
        self.log(f"[+] {summary['theme']}: {summary['pages']} page(s), "
                 f"{summary['stylesheets']} stylesheet(s), "
                 f"{summary['colors_changed']} colour(s) changed")
        return summary

    # -- files ------------------------------------------------------------

    def _files(self):
        """Relative paths of the HTML and CSS files we restyle."""
        found = []
        for root, dirs, names in os.walk(self.project_dir):
            dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
            for name in names:
                if name == THEME_CSS or not name.lower().endswith((".html", ".htm", ".css")):
                    continue
                full = os.path.join(root, name)
                found.append(os.path.relpath(full, self.project_dir).replace(os.sep, "/"))
        return sorted(found)

    def _original(self, rel):
        """Text of the file as cloned, saving a copy the first time we see it."""
        live = os.path.join(self.project_dir, *rel.split("/"))
        backup = os.path.join(self.project_dir, ORIGINALS, *rel.split("/"))
        if not os.path.exists(backup):
            os.makedirs(os.path.dirname(backup), exist_ok=True)
            shutil.copy2(live, backup)
        with open(backup, encoding="utf-8", errors="replace") as f:
            return f.read()

    def _write(self, rel, text):
        with open(os.path.join(self.project_dir, *rel.split("/")), "w",
                  encoding="utf-8") as f:
            f.write(text)

    def _update_manifest(self, summary):
        path = os.path.join(self.project_dir, MANIFEST)
        manifest = {}
        if os.path.exists(path):
            with open(path, encoding="utf-8") as f:
                manifest = json.load(f)
        manifest["redesign"] = summary
        with open(path, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2)

    # -- colours ----------------------------------------------------------

    def _build_color_map(self, sources):
        counts = {}
        for rel, text in sources.items():
            css = text if rel.lower().endswith(".css") else hu.inline_css(text)
            for colour, n in cu.find_colors(css).items():
                counts[colour] = counts.get(colour, 0) + n
            if not rel.lower().endswith(".css"):
                for m in _COLOR_ATTR.finditer(text):
                    if cu.parse_color(m.group(3)):
                        counts[m.group(3)] = counts.get(m.group(3), 0) + 1
        t = self.theme
        return cu.build_color_map(counts, t["palette"], t["background"], t["text"])

    # -- restyling --------------------------------------------------------

    def _restyle_css(self, css):
        fonts = self.theme["fonts"]

        def font(m):
            stack = fonts["mono"] if _MONO_HINT.search(m.group(2)) else fonts["body"]
            important = " !important" if "!important" in m.group(2) else ""
            return m.group(1) + stack + important

        def radius(m):
            # Leave 0 (square) and large values (pills/circles) alone.
            size = float(m.group(2)) * (16 if m.group(3).lower() != "px" else 1)
            if self.theme["radius"] and 0 < size < 24:
                return m.group(1) + str(self.theme["radius"])
            return m.group(0)

        css = cu.recolor(css, self.color_map)
        css = _FONT_FAMILY.sub(font, css)
        return _RADIUS.sub(radius, css)

    def _restyle_html(self, html, rel):
        def colour_attr(m):
            new = self.color_map.get(m.group(3))
            return f"{m.group(1)}{m.group(2)}{new}{m.group(2)}" if new else m.group(0)

        html = hu.rewrite_inline_css(html, self._restyle_css)
        html = _COLOR_ATTR.sub(colour_attr, html)
        link = (f'<link rel="stylesheet" href="{hu.relative_link(rel, THEME_CSS)}" '
                f'data-mimic2-theme>\n')
        if _HEAD_CLOSE.search(html):
            return _HEAD_CLOSE.sub(lambda m: link + m.group(0), html, count=1)
        return link + html

    def _theme_css(self):
        t = self.theme
        f = t["fonts"]
        radius = t["radius"] or "inherit"
        accent = t["palette"][0]
        accent2 = t["palette"][1] if len(t["palette"]) > 1 else accent
        on_accent = "#000000" if cu.luminance(cu.parse_color(accent)) > 0.4 else "#ffffff"
        font_import = f'@import url("{f["import"]}");\n' if f.get("import") else ""
        return f"""{font_import}/* mimic2 redesign: {t['name']} */
:root {{
  color-scheme: {t.get('mode', 'light')};
  --mimic2-bg: {t['background']};
  --mimic2-surface: {t['surface']};
  --mimic2-text: {t['text']};
  --mimic2-muted: {t['muted']};
  --mimic2-border: {t['border']};
  --mimic2-accent: {accent};
  --mimic2-accent-2: {accent2};
  --mimic2-radius: {radius};
}}
html, body {{
  background-color: var(--mimic2-bg);
  color: var(--mimic2-text);
}}
body {{ font-family: {f['body']}; line-height: 1.6; }}
h1, h2, h3, h4, h5, h6 {{ font-family: {f['heading']}; letter-spacing: -0.01em; }}
code, pre, kbd, samp {{ font-family: {f['mono']}; }}
a {{ color: var(--mimic2-accent); }}
a:visited {{ color: var(--mimic2-accent-2); }}
hr {{ border-color: var(--mimic2-border); }}
button, input, select, textarea {{
  background-color: var(--mimic2-surface);
  color: var(--mimic2-text);
  border: 1px solid var(--mimic2-border);
  border-radius: var(--mimic2-radius);
}}
button, input[type="submit"], input[type="button"] {{
  background-color: var(--mimic2-accent);
  color: {on_accent};
  border-color: var(--mimic2-accent);
}}
"""
