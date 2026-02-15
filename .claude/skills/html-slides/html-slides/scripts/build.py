#!/usr/bin/env python3
"""Build a standalone HTML presentation from slides.json and the template.

Usage:
    python build.py slides.json                    # outputs presentation.html
    python build.py slides.json -o my-deck.html    # custom output name
    python build.py slides.json -t template.html   # custom template path
"""

import argparse
import json
import sys
from pathlib import Path


def build(slides_path: str, template_path: str, output_path: str) -> None:
    slides_file = Path(slides_path)
    template_file = Path(template_path)

    if not slides_file.exists():
        print(f"Error: {slides_file} not found", file=sys.stderr)
        sys.exit(1)
    if not template_file.exists():
        print(f"Error: {template_file} not found", file=sys.stderr)
        sys.exit(1)

    with open(slides_file) as f:
        data = json.load(f)

    with open(template_file) as f:
        template = f.read()

    title = data.get("title", "Presentation")
    slides_html = data.get("slides_html", "")
    custom_css = data.get("custom_css", "")

    html = template.replace("{{TITLE}}", title)
    html = html.replace("{{SLIDES_HTML}}", slides_html)
    html = html.replace("{{CUSTOM_CSS}}", custom_css)

    out = Path(output_path)
    out.write_text(html)
    print(f"Built: {out} ({len(data.get('slides_html', '').splitlines())} slide lines)")


def main():
    parser = argparse.ArgumentParser(description="Build standalone HTML presentation")
    parser.add_argument("slides", help="Path to slides.json")
    parser.add_argument("-o", "--output", default="presentation.html", help="Output HTML path")
    parser.add_argument("-t", "--template", default=None, help="Template HTML path")
    args = parser.parse_args()

    template = args.template
    if template is None:
        # Look for template relative to this script
        template = str(Path(__file__).parent.parent / "assets" / "template.html")

    build(args.slides, template, args.output)


if __name__ == "__main__":
    main()
