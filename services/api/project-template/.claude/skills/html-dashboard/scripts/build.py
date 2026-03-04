#!/usr/bin/env python3
"""Build a standalone HTML dashboard by embedding data.json into the template."""

import argparse
import json
import sys
from pathlib import Path


def build(data_path: str, template_path: str, output_path: str) -> None:
    data_file = Path(data_path)
    template_file = Path(template_path)

    if not data_file.exists():
        print(f"Error: {data_file} not found", file=sys.stderr)
        sys.exit(1)
    if not template_file.exists():
        print(f"Error: {template_file} not found", file=sys.stderr)
        sys.exit(1)

    with open(data_file) as f:
        data = json.load(f)

    with open(template_file) as f:
        template = f.read()

    title = data.get("title", "Dashboard")
    data_json = json.dumps(data, ensure_ascii=False)
    custom_css = data.get("custom_css", "")

    html = template.replace("{{TITLE}}", title)
    html = html.replace("{{DATA_JSON}}", data_json)
    html = html.replace("{{CUSTOM_CSS}}", custom_css)

    out = Path(output_path)
    out.write_text(html)
    sections = len(data.get("sections", []))
    print(f"Built: {out} ({sections} sections)")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Build standalone HTML dashboard")
    parser.add_argument("data", help="Path to data.json")
    parser.add_argument("-o", "--output", default="dashboard.html", help="Output HTML path")
    parser.add_argument("-t", "--template", default=None, help="Template HTML path")
    args = parser.parse_args()

    template = args.template
    if template is None:
        template = str(Path(__file__).parent.parent / "assets" / "template.html")

    build(args.data, template, args.output)
