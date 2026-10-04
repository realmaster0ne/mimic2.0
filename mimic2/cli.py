"""
Mimic 2.0 — Command-Line Interface
Usage:
    mimic2 clone <url> [--output DIR] [--depth N] [--max-pages N] [--no-assets] [--theme NAME]
    mimic2 redesign <project_dir> [--theme dark|light|custom|FILE.yaml] [--palette #FF5733,#33FF57]
    mimic2 themes
"""

import argparse
import sys

from mimic2 import themes
from mimic2.clone.web_cloner import WebAppCloner
from mimic2.redesign.theme_engine import ThemeEngine


def cmd_clone(args):
    """Clone a web application, optionally redesigning it straight away."""
    cloner = WebAppCloner(
        url=args.url,
        output_dir=args.output,
        theme=args.theme,
        max_depth=args.depth,
        include_assets=not args.no_assets,
        max_pages=args.max_pages,
    )
    cloner.run()
    print(f"[+] App cloned to {args.output}")
    if args.theme:
        ThemeEngine(project_dir=args.output, theme=args.theme).apply()
        print(f"[+] Redesigned with {args.theme}")


def cmd_redesign(args):
    """Redesign a cloned project with a new theme/palette."""
    engine = ThemeEngine(
        project_dir=args.project,
        theme=args.theme,
        palette=args.palette.split(",") if args.palette else None,
    )
    engine.apply()
    print("[+] Redesign applied successfully.")


def cmd_themes(args):
    """List the built-in themes."""
    for name in themes.available():
        t = themes.load(name)
        print(f"{name:16} {t.get('description', '')}")
    print("\nShorthands: dark = modern-dark, light = minimal-light. "
          "You can also pass a path to your own .yaml theme.")


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="mimic2",
        description="Mimic 2.0 - Clone and Redesign Web Applications",
    )
    subparsers = parser.add_subparsers(dest="command")

    # clone
    clone_parser = subparsers.add_parser("clone", help="Clone a web application")
    clone_parser.add_argument("url", help="URL of the app to clone")
    clone_parser.add_argument("--output", "-o", default="./cloned_app", help="Output directory")
    clone_parser.add_argument("--depth", "-d", type=int, default=3, help="Max link depth to follow")
    clone_parser.add_argument("--max-pages", type=int, default=50, help="Stop after this many pages")
    clone_parser.add_argument("--no-assets", action="store_true",
                              help="Don't download CSS, JS, images and fonts")
    clone_parser.add_argument("--theme", "-t",
                              help="Redesign right after cloning (e.g. dark, light)")

    # redesign
    redesign_parser = subparsers.add_parser("redesign", help="Redesign a cloned app")
    redesign_parser.add_argument("project", help="Path to the cloned project directory")
    redesign_parser.add_argument("--theme", "-t", default="custom",
                                 help="dark, light, a theme name, a .yaml path, or custom "
                                      "(needs --palette)")
    redesign_parser.add_argument("--palette", "-p",
                                 help="Comma-separated hex colors, e.g. #FF5733,#33FF57")

    # themes
    subparsers.add_parser("themes", help="List built-in themes")

    args = parser.parse_args(argv)

    if not args.command:
        parser.print_help()
        sys.exit(1)

    commands = {
        "clone": cmd_clone,
        "redesign": cmd_redesign,
        "themes": cmd_themes,
    }
    try:
        commands[args.command](args)
    except (themes.ThemeError, FileNotFoundError, RuntimeError) as e:
        print(f"[!] {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
