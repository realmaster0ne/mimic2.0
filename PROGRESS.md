# mimic2 build progress

Goal (see README.md): `mimic2` clones a web app, then redesigns the copy so it looks
different from the original. Build one item at a time. `mimic2/cli.py` shows how each
class is called. Keep each file short and working rather than complete.

## Checklist

- [x] 1. `mimic2/utils/__init__.py` + `mimic2/utils/html_utils.py` — helpers to fetch a page, find links/CSS/images, rewrite URLs to local paths (tests: `tests/test_mimic2_html_utils.py`)
- [x] 2. `mimic2/clone/__init__.py` + `mimic2/clone/web_cloner.py` — `WebAppCloner(url, output_dir, theme, max_depth, include_assets)` with `.run()`: saves pages (and assets if asked) into `output_dir`, writes `mimic2.json` manifest (tests: `tests/test_mimic2_web_cloner.py`)
- [x] 3. `mimic2/utils/color_utils.py` — hex/RGB conversion, lighten/darken, map old colors to a new palette (`find_colors` → `build_color_map` → `recolor`; tests: `tests/test_mimic2_color_utils.py`)
- [x] 4. `mimic2/themes/modern_dark.yaml` + `mimic2/themes/minimal_light.yaml` — colors and fonts for each theme (loader: `mimic2.themes.load()`; tests: `tests/test_mimic2_themes.py`)
- [x] 5. `mimic2/redesign/__init__.py` + `mimic2/redesign/theme_engine.py` — `ThemeEngine(project_dir, theme, palette)` with `.apply()`: swaps colors/fonts in the cloned CSS/HTML; originals kept in `.mimic2-original/` (tests: `tests/test_mimic2_theme_engine.py`)
- [ ] 6. `mimic2/__main__.py` so `python -m mimic2` works; remove the `analyze` and `metrics` commands from `cli.py` for now
- [ ] 7. `tests/test_mimic2.py` — clone a local HTML fixture, redesign it, check colors changed

## Later (not now)

- analyze, metrics, mobile cloning, dashboard

## Notes

- Original `mimic/` package (traffic capture → API clients) is untouched; don't edit it.
