"""Colour helpers for redesigning a cloned site.

Colours are (r, g, b, a) tuples: r/g/b are 0-255 ints, a is a 0-1 float.

The core idea of a redesign (build_color_map) keeps the *structure* of the
original colour scheme while changing what it looks like:

* Greys/neutrals (backgrounds, text, borders) are placed on a ramp between the
  new theme's text colour (for the darkest originals) and background colour
  (for the lightest). A white page with black text on a dark theme therefore
  becomes a dark page with light text, and mid-greys land in between.
* Brand/accent colours are grouped by hue, most used first, and each group is
  given the next colour from the new palette. Shades inside a group (hover,
  pressed, light tints) keep their relative lightness.
"""
import colorsys
import re

NAMED = {
    "black": "#000000", "white": "#ffffff", "red": "#ff0000", "green": "#008000",
    "blue": "#0000ff", "yellow": "#ffff00", "orange": "#ffa500", "purple": "#800080",
    "gray": "#808080", "grey": "#808080", "silver": "#c0c0c0", "navy": "#000080",
    "teal": "#008080", "maroon": "#800000", "olive": "#808000", "lime": "#00ff00",
    "aqua": "#00ffff", "cyan": "#00ffff", "fuchsia": "#ff00ff", "magenta": "#ff00ff",
    "pink": "#ffc0cb", "brown": "#a52a2a", "gold": "#ffd700", "indigo": "#4b0082",
    "violet": "#ee82ee", "whitesmoke": "#f5f5f5", "gainsboro": "#dcdcdc",
    "lightgray": "#d3d3d3", "lightgrey": "#d3d3d3", "darkgray": "#a9a9a9",
    "darkgrey": "#a9a9a9", "dimgray": "#696969", "dimgrey": "#696969",
    "transparent": "#00000000",
}

# Colour literals inside CSS. Named colours are deliberately not matched here:
# words like "red" also appear in class names, URLs and font names.
COLOR_RE = re.compile(
    r"#(?:[0-9a-f]{8}|[0-9a-f]{6}|[0-9a-f]{3,4})\b"
    r"|\b(?:rgba?|hsla?)\(\s*[^()]*\)",
    re.I,
)

NEUTRAL_SATURATION = 0.12  # below this a colour counts as grey
HUE_GROUP_DEGREES = 30     # colours within this hue distance share a palette colour
MAX_SHADE_SHIFT = 0.25     # how far a shade's lightness may move from its new main colour
MIN_ACCENT_CONTRAST = 3.0  # WCAG minimum for accents (links, buttons) on the background


def _clamp(x, lo=0.0, hi=1.0):
    return max(lo, min(hi, x))


def _num(token, scale):
    """Parse '50%' (relative to scale) or '128' / '0.5'."""
    token = token.strip()
    if token.endswith("%"):
        return float(token[:-1]) / 100 * scale
    return float(token)


def parse_color(text):
    """Parse a CSS colour into (r, g, b, a), or None if it isn't one."""
    s = text.strip().lower()
    s = NAMED.get(s, s)
    if s.startswith("#"):
        h = s[1:]
        if len(h) in (3, 4):
            h = "".join(c * 2 for c in h)
        if len(h) not in (6, 8) or not re.fullmatch(r"[0-9a-f]+", h):
            return None
        a = int(h[6:8], 16) / 255 if len(h) == 8 else 1.0
        return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), round(a, 3)
    m = re.fullmatch(r"(rgba?|hsla?)\((.*)\)", s)
    if not m:
        return None
    parts = [p for p in re.split(r"[\s,/]+", m.group(2).strip()) if p]
    if len(parts) not in (3, 4):
        return None
    try:
        a = _clamp(_num(parts[3], 1.0)) if len(parts) == 4 else 1.0
        if m.group(1).startswith("rgb"):
            r, g, b = (round(_clamp(_num(p, 255), 0, 255)) for p in parts[:3])
        else:
            hue = float(parts[0].replace("deg", "")) % 360 / 360
            sat = _clamp(_num(parts[1], 1.0))
            lig = _clamp(_num(parts[2], 1.0))
            r, g, b = (round(c * 255) for c in colorsys.hls_to_rgb(hue, lig, sat))
    except ValueError:
        return None
    return r, g, b, round(a, 3)


def to_css(color):
    """Format a colour as #rrggbb, or rgba(...) when it is see-through."""
    r, g, b, a = color
    if a >= 1:
        return f"#{r:02x}{g:02x}{b:02x}"
    return f"rgba({r}, {g}, {b}, {a:g})"


def to_hsl(color):
    """(hue 0-360, saturation 0-1, lightness 0-1) of a colour."""
    r, g, b, _ = color
    h, l, s = colorsys.rgb_to_hls(r / 255, g / 255, b / 255)
    return h * 360, s, l


def from_hsl(h, s, l, a=1.0):
    r, g, b = colorsys.hls_to_rgb((h % 360) / 360, _clamp(l), _clamp(s))
    return round(r * 255), round(g * 255), round(b * 255), a


def lighten(color, amount):
    """Raise lightness by amount (0-1). Negative amounts darken."""
    h, s, l = to_hsl(color)
    return from_hsl(h, s, l + amount, color[3])


def darken(color, amount):
    return lighten(color, -amount)


def mix(c1, c2, t):
    """Blend from c1 (t=0) to c2 (t=1); alpha is taken from c1."""
    return tuple(round(a + (b - a) * t) for a, b in zip(c1[:3], c2[:3])) + (c1[3],)


def luminance(color):
    """WCAG relative luminance, 0 (black) to 1 (white)."""
    def channel(c):
        c /= 255
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = (channel(c) for c in color[:3])
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast_ratio(c1, c2):
    """WCAG contrast ratio, 1 to 21. Body text needs at least 4.5."""
    hi, lo = sorted((luminance(c1), luminance(c2)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


def ensure_contrast(color, background, minimum=3.0):
    """Darken (on light backgrounds) or lighten (on dark) until readable."""
    step = -0.02 if luminance(background) > 0.5 else 0.02
    for _ in range(50):
        if contrast_ratio(color, background) >= minimum:
            break
        color = lighten(color, step)
    return color


def is_neutral(color):
    return to_hsl(color)[1] < NEUTRAL_SATURATION


def find_colors(css):
    """Colour literals in CSS text, most frequent first, as {css_text: count}."""
    counts = {}
    for m in COLOR_RE.finditer(css):
        if parse_color(m.group(0)):
            counts[m.group(0)] = counts.get(m.group(0), 0) + 1
    return dict(sorted(counts.items(), key=lambda kv: -kv[1]))


def _hue_distance(h1, h2):
    d = abs(h1 - h2) % 360
    return min(d, 360 - d)


def build_color_map(colors, palette, background, text):
    """Map original colours to new ones (see module docstring).

    colors: {css colour text: usage count}, e.g. from find_colors().
    palette: accent colours of the new theme, most important first.
    background / text: the new theme's page background and text colours.
    Returns {original css text: new css text}.
    """
    bg = parse_color(background)
    fg = parse_color(text)
    accents = [parse_color(p) for p in palette if parse_color(p)] or [fg]
    parsed = {t: parse_color(t) for t in colors}

    # Group the chromatic colours by hue, weighting each group by usage.
    groups = []  # [hue, total count, [css texts]]
    for t, c in parsed.items():
        if c is None or is_neutral(c):
            continue
        hue = to_hsl(c)[0]
        for g in groups:
            if _hue_distance(g[0], hue) <= HUE_GROUP_DEGREES:
                g[1] += colors[t]
                g[2].append(t)
                break
        else:
            groups.append([hue, colors[t], [t]])
    groups.sort(key=lambda g: -g[1])

    mapping = {}
    for t, c in parsed.items():
        if c is not None and is_neutral(c):
            # Lightest originals -> new background, darkest -> new text.
            mapping[t] = to_css(mix(fg, bg, to_hsl(c)[2])[:3] + (c[3],))

    for i, (_, _, members) in enumerate(groups):
        accent = accents[i % len(accents)]
        ah, as_, al = to_hsl(accent)
        # Shades keep their lightness offset from the group's main colour.
        base_l = to_hsl(parsed[members[0]])[2]
        for t in members:
            c = parsed[t]
            _, s, l = to_hsl(c)
            new_s = as_ * (s / max(to_hsl(parsed[members[0]])[1], 1e-6)) if as_ else 0
            offset = max(-MAX_SHADE_SHIFT, min(MAX_SHADE_SHIFT, l - base_l))
            new = from_hsl(ah, _clamp(new_s), al + offset, c[3])
            mapping[t] = to_css(ensure_contrast(new, bg, MIN_ACCENT_CONTRAST))
    return mapping


def recolor(css, mapping):
    """Replace every colour literal found in mapping; others are left as is."""
    return COLOR_RE.sub(lambda m: mapping.get(m.group(0), m.group(0)), css)
