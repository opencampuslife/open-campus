#!/usr/bin/env python3
"""Render a temporary staging percentage-canary config with a specific percentage.

Reads the PR-6D percentage-canary example as a base, overrides current_weight
to the requested percentage, and writes the result to a temp file.

Usage:
    python3 tools/render_staging_percentage_canary_config.py \
        --source deploy/staging/ingress/go-gateway-shadow.percentage-canary.example.yaml \
        --percent 1 \
        --output /tmp/staging-1pct-canary.yaml
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    print("PyYAML is required. Install it with: pip install pyyaml", file=sys.stderr)
    sys.exit(1)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Render temporary staging percentage-canary config"
    )
    parser.add_argument(
        "--source",
        required=True,
        help="Source percentage-canary example YAML",
    )
    parser.add_argument(
        "--percent",
        type=int,
        required=True,
        choices=[1, 5, 25, 50, 100],
        help="Canary percentage (must be from stages whitelist)",
    )
    parser.add_argument(
        "--output",
        required=True,
        help="Output path for rendered config",
    )
    return parser.parse_args()


def render_config(source_path: Path, percent: int) -> dict:
    text = source_path.read_text(encoding="utf-8")
    config = yaml.safe_load(text)

    if not isinstance(config, dict):
        raise ValueError(f"{source_path}: root must be an object")

    # Validate source has expected structure
    canary = config.get("canary")
    if not isinstance(canary, dict):
        raise ValueError(f"{source_path}: missing canary config")
    if canary.get("type") != "percentage":
        raise ValueError(f"{source_path}: canary.type must be 'percentage'")

    # Verify source has weight=0 (PR-6D invariant)
    if canary.get("current_weight") != 0:
        raise ValueError(
            f"{source_path}: current_weight must be 0 in PR-6D source, "
            f"got {canary.get('current_weight')}"
        )
    for route in config.get("routes", []):
        if isinstance(route, dict) and route.get("weight", 0) != 0:
            raise ValueError(
                f"{source_path}: route {route.get('path', '?')} weight must be 0 in PR-6D source"
            )

    # Render with requested percentage
    config["canary"] = dict(canary)  # shallow copy
    config["canary"]["current_weight"] = percent

    # Add metadata
    config["_rendered"] = {
        "source": str(source_path),
        "percent": percent,
        "note": "Temporary config for PR-6E evidence run. Do NOT commit.",
    }

    return config


def main() -> int:
    args = parse_args()
    source = Path(args.source)
    output = Path(args.output)

    if not source.is_file():
        print(f"ERROR: source not found: {source}", file=sys.stderr)
        return 1

    try:
        rendered = render_config(source, args.percent)
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        yaml.safe_dump(rendered, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )

    print(f"Rendered {args.percent}% config: {output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
