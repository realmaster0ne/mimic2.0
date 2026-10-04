"""
Mimic 2.0 — Command-Line Interface
Usage:
    mimic2 clone <url> [--output DIR] [--theme dark|light|custom]
    mimic2 analyze <project_dir>
    mimic2 redesign <project_dir> --theme custom --palette #FF5733,#33FF57
    mimic2 metrics <project_dir>
"""

import argparse
import sys
import os
from pathlib import Path

from mimic2.clone.web_cloner import WebAppCloner
from mimic2.analyze.architecture import ArchitectureAnalyzer
from mimic2.redesign.theme_engine import ThemeEngine
from mimic2.analytics.metrics import DesignMetrics


def cmd_clone(args):
    """Clone a web application."""
    output = args.output or "./cloned_app"
    cloner = WebAppCloner(
        url=args.url,
        output_dir=output,
        theme=args.theme,
        max_depth=args.depth,
        include_assets=args.assets,
    )
    cloner.run()
    print(f"[✓] App cloned to {output}")


def cmd_analyze(args):
    """Analyze the architecture of a cloned app."""
    analyzer = ArchitectureAnalyzer(project_dir=args.project)
    report = analyzer.generate_report()
    print(report)


def cmd_redesign(args):
    """Redesign an existing project with new themes/palettes."""
    engine = ThemeEngine(
        project_dir=args.project,
        theme=args.theme,
        palette=args.palette.split(",") if args.palette else None,
    )
    engine.apply()
    print("[✓] Redesign applied successfully.")


def cmd_metrics(args):
    """Generate design metrics for a project."""
    metrics = DesignMetrics(project_dir=args.project)
    report = metrics.generate_report()
    print(report)


def main():
    parser = argparse.ArgumentParser(
        prog="mimic2",
        description="Mimic 2.0 — Clone, Analyze, and Redesign Web Applications",
    )
    subparsers = parser.add_subparsers(dest="command")

    # clone
    clone_parser = subparsers.add_parser("clone", help="Clone a web application")
    clone_parser.add_argument("url", help="URL of the app to clone")
    clone_parser.add_argument("--output", "-o", default="./cloned_app", help="Output directory")
    clone_parser.add_argument("--theme", "-t", choices=["dark", "light", "custom"], default="dark")
    clone_parser.add_argument("--depth", "-d", type=int, default=3, help="Max link depth to follow")
    clone_parser.add_argument("--assets", action="store_true", help="Download assets (images, CSS, JS)")

    # analyze
    analyze_parser = subparsers.add_parser("analyze", help="Analyze project architecture")
    analyze_parser.add_argument("project", help="Path to the cloned project directory")

    # redesign
    redesign_parser = subparsers.add_parser("redesign", help="Redesign a cloned app")
    redesign_parser.add_argument("project", help="Path to the cloned project directory")
    redesign_parser.add_argument("--theme", "-t", choices=["dark", "light", "custom"], default="custom")
    redesign_parser.add_argument("--palette", "-p", help="Comma-separated hex colors, e.g. #FF5733,#33FF57")

    # metrics
    metrics_parser = subparsers.add_parser("metrics", help="Generate design metrics")
    metrics_parser.add_argument("project", help="Path to the cloned project directory")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    commands = {
        "clone": cmd_clone,
        "analyze": cmd_analyze,
        "redesign": cmd_redesign,
        "metrics": cmd_metrics,
    }
    commands[args.command](args)


if __name__ == "__main__":
    main()
