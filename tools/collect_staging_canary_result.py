#!/usr/bin/env python3
"""Collect and validate staging header-canary evidence results."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Collect staging header-canary evidence.")
    parser.add_argument("--report", type=Path, default=Path("reports/staging/header-canary-latest.json"))
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    return parser.parse_args()


def collect_evidence(report_path: Path, root: Path) -> dict[str, Any]:
    timestamp = __import__("time").strftime("%Y-%m-%dT%H:%M:%SZ", __import__("time").gmtime())

    # Load the staging evidence JSON if it exists
    evidence: dict[str, Any] = {
        "mode": "staging_header_canary",
        "generated_at": timestamp,
        "staging_available": False,
        "staging_url": None,
        "summary": {
            "header_canary_enabled": None,
            "fallback_without_header_ok": None,
            "go_header_canary_ok": None,
            "admin_post_canary_ok": None,
            "deprecated_get_blocked": None,
            "rollback_verified": None,
            "unexpected_diffs": None,
            "latency_fail_count": None,
        },
        "routes": [],
        "privacy": {
            "raw_payload_included": False,
            "contains_pii": False,
        },
        "status": "unknown",
    }

    if not report_path.is_file():
        evidence["status"] = "no_report"
        evidence["note"] = "No staging evidence available; run scripts/run_staging_header_canary_evidence.sh first"
        return evidence

    try:
        raw = json.loads(report_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        evidence["status"] = "invalid_report"
        evidence["error"] = str(exc)
        return evidence

    # Merge loaded evidence
    for key in ("mode", "generated_at", "staging_available", "staging_url"):
        if key in raw:
            evidence[key] = raw[key]

    if "summary" in raw and isinstance(raw["summary"], dict):
        evidence["summary"].update(raw["summary"])

    if "routes" in raw and isinstance(raw["routes"], list):
        evidence["routes"] = raw["routes"]

    if "privacy" in raw and isinstance(raw["privacy"], dict):
        evidence["privacy"] = raw["privacy"]

    if "status" in raw:
        evidence["status"] = raw["status"]

    # Validate: if status is "skipped", that's acceptable for local dev
    if evidence["status"] == "skipped":
        evidence["note"] = "Staging evidence skipped (no environment available)"
    elif evidence["status"] == "running":
        # Check if we have meaningful results
        summary = evidence["summary"]
        has_results = any(
            v is not None for v in summary.values()
        )
        if has_results:
            evidence["status"] = "completed"
        else:
            evidence["status"] = "incomplete"

    return evidence


def write_markdown(report_path: Path, evidence: dict[str, Any]) -> None:
    lines: list[str] = []
    lines.append("# Staging Header-Canary Evidence")
    lines.append("")
    lines.append(f"## Generated: {evidence.get('generated_at', 'unknown')}")
    lines.append(f"## Status: {evidence.get('status', 'unknown').upper()}")
    lines.append("")

    summary = evidence.get("summary", {})
    lines.append("## Summary")
    for key, label in [
        ("header_canary_enabled", "Header Canary Enabled"),
        ("fallback_without_header_ok", "Fallback without Header"),
        ("go_header_canary_ok", "Go Header-Canary Hits"),
        ("admin_post_canary_ok", "Admin POST Canary"),
        ("deprecated_get_blocked", "Deprecated GET Blocked"),
        ("rollback_verified", "Rollback Verified"),
        ("unexpected_diffs", "Unexpected Diffs"),
        ("latency_fail_count", "Latency Fail Count"),
    ]:
        value = summary.get(key)
        display = str(value) if value is not None else "N/A"
        lines.append(f"- {label}: {display}")
    lines.append("")

    routes = evidence.get("routes", [])
    if routes:
        lines.append("## Routes")
        for r in routes:
            lines.append(f"- {r.get('method', '')} {r.get('path', '')}: {r.get('status', 'unknown')}")
        lines.append("")

    privacy = evidence.get("privacy", {})
    lines.append("## Privacy")
    lines.append(f"- Raw payload included: {privacy.get('raw_payload_included', 'N/A')}")
    lines.append(f"- Contains PII: {privacy.get('contains_pii', 'N/A')}")
    lines.append("")

    lines.append("## Next Action")
    status = evidence.get("status", "")
    if status == "completed":
        lines.append("Evidence collection complete. Review summary before proceeding to next phase.")
    elif status == "skipped":
        lines.append("No staging environment available. Evidence collection skipped for local development.")
    elif status == "incomplete":
        lines.append("Evidence collection incomplete. Check staging environment and re-run.")
    else:
        lines.append("Evidence status unknown. Review report for details.")

    md_path = report_path.with_suffix(".md")
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    args = parse_args()
    report_path = args.report

    evidence = collect_evidence(report_path, args.root)

    # Write updated report
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(evidence, indent=2, ensure_ascii=False), encoding="utf-8")

    # Write markdown summary
    write_markdown(report_path, evidence)

    status = evidence.get("status", "")
    if status == "skipped":
        print(f"staging header-canary evidence: SKIPPED (no environment)")
        print(json.dumps(evidence, indent=2))
        return 0
    elif status in ("completed", "running"):
        print(f"staging header-canary evidence: {status.upper()}")
        print(json.dumps(evidence, indent=2))
        return 0
    else:
        print(f"staging header-canary evidence: {status.upper()}", file=sys.stderr)
        print(json.dumps(evidence, indent=2), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
