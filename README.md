# 🎨 Mimic 2.0 — App Clone & Redesign Platform

A powerful platform for cloning, analyzing, and redesigning applications with modern UI/UX patterns.

## Features

- **📦 App Cloning** — Clone any web/mobile app structure
- **🔍 Deep Analysis** — Analyze app architecture, design patterns, and UX flows
- **🎨 Redesign Engine** — Generate redesigned versions with improved aesthetics
- **🧩 Component Extraction** — Extract and catalog reusable components
- **📊 Analytics Dashboard** — Visualize design metrics and improvements
- **🔄 Theme System** — Apply custom themes across the entire app
- **📱 Responsive Design** — Ensure cross-device compatibility
- **♿ Accessibility** — WCAG 2.1 AA compliance built-in
- **⚡ Performance Optimization** — Auto-optimize assets and code
- **🧪 Testing Suite** — Automated visual regression testing

## Quick Start

```bash
# Install (from the repo folder)
pip install -e .

# Clone an app (pages + CSS/JS/images/fonts), then redesign it in one go
python -m mimic2 clone https://example.com --output ./my-app --theme dark

# Or redesign an existing clone; re-running starts from the original files
python -m mimic2 redesign ./my-app --theme light
python -m mimic2 redesign ./my-app --theme dark --palette "#FF5733,#33FF57"

# List built-in themes
python -m mimic2 themes
```

> Analysis, metrics, mobile cloning and the dashboard below are planned (see
> PROGRESS.md); `clone`, `redesign` and `themes` work today.

## Architecture

```
mimic2.0/
├── mimic2/                    # Main package
│   ├── __init__.py
│   ├── cli.py                 # CLI entry point
│   ├── clone/                 # App cloning engine
│   │   ├── __init__.py
│   │   ├── web_cloner.py      # Web app cloner
│   │   ├── mobile_cloner.py   # Mobile app cloner
│   │   └── asset_extractor.py # Asset extraction
│   ├── analyze/               # Analysis engine
│   │   ├── __init__.py
│   │   ├── architecture.py    # Architecture analysis
│   │   ├── design_patterns.py # Design pattern detection
│   │   ├── ux_audit.py        # UX audit
│   │   └── accessibility.py   # Accessibility audit
│   ├── redesign/              # Redesign engine
│   │   ├── __init__.py
│   │   ├── theme_engine.py    # Theme generation
│   │   ├── layout_rebuilder.py # Layout reconstruction
│   │   ├── component_generator.py # Component generation
│   │   └── style_transformer.py # Style transformation
│   ├── analytics/             # Analytics engine
│   │   ├── __init__.py
│   │   ├── metrics.py         # Design metrics
│   │   └── dashboard.py       # Dashboard generation
│   ├── themes/                # Built-in themes
│   │   ├── modern_dark.yaml
│   │   ├── minimal_light.yaml
│   │   ├── vibrant_gradient.yaml
│   │   └── professional_blue.yaml
│   ├── templates/             # Redesign templates
│   │   ├── web/
│   │   └── mobile/
│   └── utils/                 # Utilities
│       ├── __init__.py
│       ├── file_utils.py
│       ├── color_utils.py
│       └── html_utils.py
├── tests/                     # Test suite
├── docs/                      # Documentation
├── examples/                  # Example projects
├── pyproject.toml
├── requirements.txt
└── setup.py
```

## Built-in Themes

| Theme | Description | Best For |
|-------|-------------|----------|
| `modern-dark` | Sleek dark mode with accent colors | Developer tools, dashboards |
| `minimal-light` | Clean, minimal light theme | Content apps, blogs |
| `vibrant-gradient` | Bold gradients and modern aesthetics | Creative apps, portfolios |
| `professional-blue` | Corporate blue palette | Business apps, SaaS |
| `neon-cyberpunk` | Neon accents on dark background | Gaming, entertainment |
| `nature-organic` | Earth tones with organic shapes | Health, wellness, eco |

## Redesign Capabilities

1. **Color Palette Transformation** — Generate harmonious palettes from any source
2. **Typography System** — Modern font pairings and hierarchy
3. **Layout Restructuring** — Improved information architecture
4. **Component Library** — Reusable, consistent UI components
5. **Animation & Micro-interactions** — Smooth transitions and feedback
6. **Responsive Breakpoints** — Mobile-first responsive design
7. **Accessibility Compliance** — WCAG 2.1 AA standards
8. **Performance Optimization** — Asset compression, lazy loading

## License

MIT
