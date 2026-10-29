"""Layout styles that make a redesigned site look like a different site, not
just the same site in new colours.

layout_css(theme) turns a theme's `layout:` section into CSS that targets the
building blocks most sites share — header, navigation, content container,
item lists, cards, buttons, forms, sidebar and footer — by tag, ARIA role and
common class names (Bootstrap and friends). It changes spacing, sizes, shapes
and arrangement (e.g. product lists become a responsive card grid) but never
hides or removes content.

Site CSS often sets these properties with more specific selectors, so the
structural rules use !important. Motion (card fade-in, hover lift) is turned
off for visitors whose system asks for reduced motion.
"""

HEADER = "header, .header, .site-header, #header, .navbar, [role='banner']"
# Menu links only; the site name in the header keeps its own size.
NAV_LINKS = ("nav a, .nav a, .navbar-nav a, .menu a, .breadcrumb a, "
             "[role='navigation'] a")
CONTAINER = (".container, .container-fluid, main, .main, .page, .page_inner, "
             ".wrapper, .site-content, #content, #main")
# (Not .thumbnail: in Bootstrap that is the image itself, not its card.)
ITEM = "article, .card, .product, .product_pod, .post, [itemtype*='Product']"
# A list (or Bootstrap row) whose children each hold one item becomes a grid.
GRID = (f":is(ul, ol, .row):has(> li > :is({ITEM})), "
        f".row:has(> [class*='col-'] > :is({ITEM}))")
GRID_CHILD = (f":is(ul, ol, .row):has(> li > :is({ITEM})) > li, "
              f".row:has(> [class*='col-'] > :is({ITEM})) > [class*='col-']")
BUTTON = ("button, .btn, .button, input[type='submit'], input[type='button'], "
          "a[class*='btn']")
FIELD = "input:not([type='submit']):not([type='button']):not([type='checkbox']):not([type='radio']), select, textarea"
SIDEBAR = "aside, .sidebar, .side_categories, [role='complementary']"
FOOTER = "footer, .footer, #footer, [role='contentinfo']"

SHADOWS = {
    "dark": ("0 12px 32px -14px rgba(0, 0, 0, 0.75)",
             "0 22px 48px -16px rgba(0, 0, 0, 0.85)"),
    "light": ("0 10px 28px -16px rgba(15, 23, 42, 0.35)",
              "0 18px 40px -18px rgba(15, 23, 42, 0.45)"),
}


def _space(layout, rem):
    """A spacing value scaled by the theme's spacing factor."""
    return f"{round(rem * float(layout['spacing']), 3)}rem"


def layout_css(theme):
    """CSS for the theme's layout section ('' when the theme has none)."""
    layout = theme.get("layout")
    if not layout:
        return ""
    s = lambda rem: _space(layout, rem)  # noqa: E731
    scale = float(layout["heading_scale"])
    shadow, shadow_hover = SHADOWS["dark" if theme.get("mode") == "dark" else "light"]
    parts = [f"""
/* ---- layout: {theme['name']} ---- */
body {{ margin: 0 !important; }}
:is({CONTAINER}) {{
  max-width: {layout['max_width']} !important;
  margin-left: auto !important;
  margin-right: auto !important;
  padding-left: {s(1.25)} !important;
  padding-right: {s(1.25)} !important;
  float: none !important;
  box-sizing: border-box;
}}
:is({CONTAINER}) :is({CONTAINER}) {{ padding-left: 0 !important; padding-right: 0 !important; }}
p, li {{ line-height: 1.7; }}
h1, h2, h3 {{ font-weight: {layout['heading_weight']} !important; line-height: 1.15; }}
h1 {{ font-size: {round(2.25 * scale, 2)}rem !important; margin: {s(1.5)} 0 {s(0.75)} !important; letter-spacing: -0.03em; }}
h2 {{ font-size: {round(1.6 * scale, 2)}rem !important; margin: {s(1.25)} 0 {s(0.6)} !important; letter-spacing: -0.02em; }}
:is({ITEM}) :is(h2, h3, h4) {{ font-size: 1.02rem !important; margin: {s(0.6)} 0 {s(0.3)} !important; letter-spacing: 0; }}
"""]

    # Header and navigation.
    if layout["header"] == "sticky":
        parts.append(f"""
:is({HEADER}) {{
  position: sticky !important;
  top: 0;
  z-index: 50;
  background: color-mix(in srgb, var(--mimic2-surface) 88%, transparent) !important;
  backdrop-filter: blur(12px);
  border: 0 !important;
  border-bottom: 1px solid var(--mimic2-border) !important;
  box-shadow: {shadow};
  padding-top: {s(0.6)} !important;
  padding-bottom: {s(0.6)} !important;
  margin-bottom: {s(1.5)} !important;
}}
:is({HEADER}) :is({HEADER}) {{ position: static !important; box-shadow: none; border: 0 !important; margin: 0 !important; backdrop-filter: none; background: transparent !important; }}
""")
    else:
        parts.append(f"""
:is({HEADER}) {{
  position: static !important;
  background: transparent !important;
  border: 0 !important;
  border-bottom: 1px solid var(--mimic2-text) !important;
  padding-top: {s(1)} !important;
  padding-bottom: {s(1)} !important;
  margin-bottom: {s(2)} !important;
}}
:is({HEADER}) :is({HEADER}) {{ border: 0 !important; margin: 0 !important; padding: 0 !important; }}
""")
    if layout["nav_style"] == "caps":
        parts.append(f"""
:is({NAV_LINKS}) {{
  text-transform: uppercase;
  letter-spacing: 0.08em;
  font-size: 0.78rem;
  font-weight: 700;
  text-decoration: none !important;
}}
""")
    else:
        parts.append(f"""
:is({NAV_LINKS}) {{
  text-decoration: underline !important;
  text-decoration-thickness: 1px;
  text-underline-offset: 5px;
}}
""")

    # Item lists become a responsive grid of cards.
    parts.append(f"""
:is({GRID}) {{
  display: grid !important;
  grid-template-columns: repeat(auto-fill, minmax({layout['card_min_width']}, 1fr));
  gap: {s(1.25)} !important;
  list-style: none !important;
  padding: 0 !important;
  margin: {s(1)} 0 !important;
}}
:is({GRID})::before, :is({GRID})::after {{ display: none !important; }}
:is({GRID_CHILD}) {{
  width: auto !important;
  max-width: none !important;
  float: none !important;
  margin: 0 !important;
  padding: 0 !important;
  display: flex !important;
}}
:is({GRID_CHILD}) > :is({ITEM}) {{ flex: 1; }}
/* Cards keep the site's own height: many sites pin prices/buttons to the
   bottom of a fixed-height card, and collapsing it overlaps them. */
:is({ITEM}) {{
  padding: {s(1)} !important;
  border-radius: var(--mimic2-radius);
}}
:is({ITEM}) img {{
  border-radius: {layout['image_radius']} !important;
  max-width: 100%;
  height: auto;
  display: block;
  margin-left: auto;
  margin-right: auto;
}}
""")
    if layout["cards"] == "elevated":
        parts.append(f"""
:is({ITEM}) {{
  background: var(--mimic2-surface) !important;
  border: 1px solid var(--mimic2-border) !important;
  box-shadow: {shadow};
  transition: transform 0.18s ease, box-shadow 0.18s ease;
}}
:is({ITEM}):hover {{ transform: translateY(-4px); box-shadow: {shadow_hover}; }}
""")
    elif layout["cards"] == "outlined":
        parts.append(f"""
:is({ITEM}) {{
  background: transparent !important;
  border: 0 !important;
  border-top: 2px solid var(--mimic2-text) !important;
  border-radius: 0 !important;
  box-shadow: none !important;
  padding-left: 0 !important;
  padding-right: 0 !important;
  transition: border-color 0.18s ease;
}}
:is({ITEM}):hover {{ border-top-color: var(--mimic2-accent) !important; }}
""")
    else:
        parts.append(f"""
:is({ITEM}) {{ background: var(--mimic2-surface) !important; border: 0 !important; box-shadow: none !important; }}
""")

    # Buttons and form fields.
    shape = {"pill": "999px", "rounded": "var(--mimic2-radius)", "square": "0"}[layout["buttons"]]
    parts.append(f"""
:is({BUTTON}) {{
  border-radius: {shape} !important;
  padding: 0.55em 1.35em !important;
  font-weight: 600 !important;
  line-height: 1.4 !important;
  background-image: none !important;
  text-shadow: none !important;
  transition: transform 0.15s ease, filter 0.15s ease, background-color 0.15s ease;
}}
:is({BUTTON}):hover {{ transform: translateY(-1px); filter: brightness(1.08); }}
:is({FIELD}) {{ padding: 0.5em 0.8em !important; border-radius: {shape if shape != '999px' else 'var(--mimic2-radius)'} !important; box-shadow: none !important; }}
""")
    if layout["buttons"] == "square":
        # Editorial look: outlined, uppercase buttons.
        parts.append(f"""
:is({BUTTON}) {{
  background: transparent !important;
  color: var(--mimic2-text) !important;
  border: 1.5px solid var(--mimic2-text) !important;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  font-size: 0.78rem !important;
}}
:is({BUTTON}):hover {{ background: var(--mimic2-text) !important; color: var(--mimic2-bg) !important; filter: none; }}
""")

    # Sidebar, footer, tables.
    parts.append(f"""
:is({SIDEBAR}) {{
  background: {'var(--mimic2-surface)' if layout['cards'] != 'outlined' else 'transparent'} !important;
  border: {'1px solid var(--mimic2-border)' if layout['cards'] != 'outlined' else '0'} !important;
  border-radius: var(--mimic2-radius);
  padding: {s(1)} !important;
}}
:is({SIDEBAR}) :is({SIDEBAR}) {{ background: transparent !important; border: 0 !important; padding: 0 !important; }}
:is({SIDEBAR}) ul {{ list-style: none !important; padding-left: 0 !important; }}
:is({SIDEBAR}) li {{ margin: {s(0.25)} 0 !important; }}
:is({FOOTER}) {{
  margin-top: {s(3)} !important;
  padding: {s(1.5)} 0 !important;
  border-top: 1px solid var(--mimic2-border) !important;
  color: var(--mimic2-muted) !important;
  background: transparent !important;
}}
table {{ border-collapse: collapse; }}
th, td {{ padding: {s(0.5)} {s(0.75)} !important; border-bottom: 1px solid var(--mimic2-border) !important; }}

@keyframes mimic2-rise {{ from {{ opacity: 0; transform: translateY(10px); }} to {{ opacity: 1; transform: none; }} }}
:is({ITEM}) {{ animation: mimic2-rise 0.4s ease both; }}
@media (prefers-reduced-motion: reduce) {{
  * {{ animation: none !important; transition: none !important; }}
}}
""")
    return "".join(parts)
