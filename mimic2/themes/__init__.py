"""Built-in redesign themes (the *.yaml files in this folder).

A theme gives the colours and fonts a cloned site is redesigned with. Load one
by name ("modern-dark", "minimal_light") or by the CLI shorthand ("dark",
"light"), or pass a path to your own YAML file with the same keys.
"""
import os

import yaml

from mimic2.utils.color_utils import parse_color

THEMES_DIR = os.path.dirname(os.path.abspath(__file__))

ALIASES = {"dark": "modern_dark", "light": "minimal_light"}

COLOR_KEYS = ("background", "surface", "text", "muted", "border")
FONT_KEYS = ("body", "heading", "mono")


class ThemeError(ValueError):
    pass


def available():
    """Names of the built-in themes, e.g. ['minimal-light', 'modern-dark']."""
    return sorted(f[:-5].replace("_", "-") for f in os.listdir(THEMES_DIR)
                  if f.endswith(".yaml"))


def _path_for(name):
    if os.path.isfile(name):
        return name
    key = name.lower().replace("-", "_")
    key = ALIASES.get(key, key)
    path = os.path.join(THEMES_DIR, key + ".yaml")
    if not os.path.isfile(path):
        raise ThemeError(f"Unknown theme {name!r}. Built-in themes: "
                         + ", ".join(available() + sorted(ALIASES)))
    return path


def validate(theme, source="theme"):
    """Check a theme dict has the keys and valid colours we rely on."""
    missing = [k for k in COLOR_KEYS + ("palette", "fonts") if k not in theme]
    if missing:
        raise ThemeError(f"{source}: missing {', '.join(missing)}")
    for key in COLOR_KEYS:
        if parse_color(str(theme[key])) is None:
            raise ThemeError(f"{source}: {key} is not a colour: {theme[key]!r}")
    if not theme["palette"]:
        raise ThemeError(f"{source}: palette needs at least one colour")
    for colour in theme["palette"]:
        if parse_color(str(colour)) is None:
            raise ThemeError(f"{source}: palette entry is not a colour: {colour!r}")
    for key in FONT_KEYS:
        if key not in theme["fonts"]:
            raise ThemeError(f"{source}: fonts.{key} is missing")
    return theme


def load(name):
    """Load and validate a theme by name, CLI alias or YAML file path."""
    path = _path_for(name)
    with open(path, encoding="utf-8") as f:
        theme = yaml.safe_load(f) or {}
    theme.setdefault("name", os.path.basename(path)[:-5].replace("_", "-"))
    theme.setdefault("radius", None)
    theme["fonts"].setdefault("import", None)
    return validate(theme, os.path.basename(path))
