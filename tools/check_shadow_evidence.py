#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

REDACTED_BODY_RE = re.compile(r"^\[redacted len=\d+ sha256=[0-9a-f]{16}\]$")
ALLOWED_PARITY_STATUSES = {"passed", "skipped"}
ALLOWED_MIRROR_DIFFS = {"none", "skipped", "unavailable", "status", "headers", "body_hash"}
FORBIDDEN_REPORT_KEYS = {
    "body",
    "raw_body",
    "raw_request_body",
    "raw_response_body",
    "request_body",
    "response_body",
    "authorization",
    "cookie",
    "set-cookie",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check shadow dry-run and mirror evidence reports.")
    parser.add_argument("--root", required=True, help="project root path")
    parser.add_argument("--latest", default=None, help="path to reports/shadow/latest.json")
    parser.add_argument("--mirror", default=None, help="path to reports/shadow/mirror-latest.json")
    parser.add_argument("--strict", action="store_true", help="apply staging-level evidence requirements")
    parser.add_argument(
        "--allow-legacy-usage-waiver",
        action="store_true",
        help="allow non-zero legacy_get_usage_events in strict mode when there is an external waiver",
    )
    return parser.parse_args()


def load_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValueError(f"missing report: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid JSON report {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"report must be a JSON object: {path}")
    return payload


def check_forbidden_fields(value: object, location: str, errors: list[str]) -> None:
    if isinstance(value, dict):
        for key, nested in value.items():
            lowered = str(key).lower()
            if lowered in FORBIDDEN_REPORT_KEYS:
                errors.append(f"{location}: forbidden report field {key}")
            check_forbidden_fields(nested, f"{location}.{key}", errors)
        return
    if isinstance(value, list):
        for index, nested in enumerate(value):
            check_forbidden_fields(nested, f"{location}[{index}]", errors)


def require(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def validate_dry_run_report(report: dict[str, Any], strict: bool, allow_legacy_usage_waiver: bool) -> list[str]:
    errors: list[str] = []
    summary = report.get("summary")
    details = report.get("details")
    latency = report.get("latency")
    parity_cases = report.get("parity_cases")
    inventory = report.get("inventory", {})

    require(isinstance(summary, dict), "latest.json: summary is required", errors)
    require(isinstance(details, dict), "latest.json: details is required", errors)
    require(isinstance(latency, dict), "latest.json: latency is required", errors)
    require(isinstance(parity_cases, dict), "latest.json: parity_cases is required", errors)
    if errors:
        return errors

    require(summary.get("health_ok") is True, "latest.json: health_ok must be true", errors)
    require(summary.get("route_count") == 115, "latest.json: route_count must be 115", errors)
    require(summary.get("legacy_gaps") == 0, "latest.json: legacy_gaps must be 0", errors)
    require(summary.get("deprecated_aliases") == 5, "latest.json: deprecated_aliases must be 5", errors)
    require(inventory.get("state-changing GET gaps") in ("0", 0, None), "latest.json: state-changing GET gaps must be 0", errors)

    for field in ("chat_parity", "admin_post_parity"):
        require(summary.get(field) in ALLOWED_PARITY_STATUSES, f"latest.json: {field} must be passed or skipped", errors)

    for field in ("chat_warn_count", "admin_warn_count"):
        require(isinstance(latency.get(field), int), f"latest.json: {field} must be an integer", errors)

    for surface in ("chat", "admin"):
        cases = parity_cases.get(surface, [])
        require(isinstance(cases, list), f"latest.json: parity_cases.{surface} must be a list", errors)
        for index, case in enumerate(cases):
            require(isinstance(case, dict), f"latest.json: parity_cases.{surface}[{index}] must be an object", errors)
            if not isinstance(case, dict):
                continue
            require(case.get("status") in {"passed", "warned", "failed"}, f"latest.json: parity case {surface}[{index}] has invalid status", errors)
            require(case.get("diff_category") in {"none", "status", "headers", "body", "latency", "other"}, f"latest.json: parity case {surface}[{index}] has invalid diff_category", errors)

    if strict:
        require(summary.get("chat_parity") == "passed", "latest.json: strict mode requires chat_parity=passed", errors)
        require(summary.get("admin_post_parity") == "passed", "latest.json: strict mode requires admin_post_parity=passed", errors)
        require(latency.get("chat_warn_count") == 0, "latest.json: strict mode requires chat_warn_count=0", errors)
        require(latency.get("admin_warn_count") == 0, "latest.json: strict mode requires admin_warn_count=0", errors)
        if not allow_legacy_usage_waiver:
            require(summary.get("legacy_get_usage_events") == 0, "latest.json: strict mode requires legacy_get_usage_events=0", errors)

    return errors


def validate_mirror_report(report: dict[str, Any], strict: bool) -> list[str]:
    errors: list[str] = []
    summary = report.get("summary")
    cases = report.get("cases")
    require(isinstance(summary, dict), "mirror-latest.json: summary is required", errors)
    require(isinstance(cases, list), "mirror-latest.json: cases is required", errors)
    if errors:
        return errors

    mode = report.get("mode")
    require(mode in {"dry_run", "live"}, "mirror-latest.json: mode must be dry_run or live", errors)
    for field in ("total_cases", "executed_cases", "skipped_cases", "drifted_cases"):
        require(isinstance(summary.get(field), int), f"mirror-latest.json: {field} must be an integer", errors)

    for index, case in enumerate(cases):
        require(isinstance(case, dict), f"mirror-latest.json: case[{index}] must be an object", errors)
        if not isinstance(case, dict):
            continue
        require(isinstance(case.get("name"), str) and bool(case.get("name")), f"mirror-latest.json: case[{index}].name is required", errors)
        require(case.get("comparison_status") in {"passed", "skipped", "drifted"}, f"mirror-latest.json: case[{index}].comparison_status invalid", errors)
        require(case.get("diff_category") in ALLOWED_MIRROR_DIFFS, f"mirror-latest.json: case[{index}].diff_category invalid", errors)
        for body_field in ("legacy_body_summary", "shadow_body_summary"):
            value = case.get(body_field)
            if value is None:
                continue
            require(isinstance(value, str) and bool(REDACTED_BODY_RE.match(value)), f"mirror-latest.json: case[{index}].{body_field} must be a redacted summary", errors)

    if strict:
        require(mode == "live", "mirror-latest.json: strict mode requires mode=live", errors)
        require(summary.get("executed_cases", 0) > 0, "mirror-latest.json: strict mode requires executed_cases>0", errors)
        require(summary.get("drifted_cases") == 0, "mirror-latest.json: strict mode requires drifted_cases=0", errors)
        require(summary.get("skipped_cases") == 0, "mirror-latest.json: strict mode requires skipped_cases=0", errors)

    return errors


def main() -> int:
    args = parse_args()
    root = Path(args.root).resolve()
    report_dir = root / "reports" / "shadow"
    latest_path = Path(args.latest) if args.latest else report_dir / "latest.json"
    mirror_path = Path(args.mirror) if args.mirror else report_dir / "mirror-latest.json"

    try:
        latest = load_json(latest_path)
        mirror = load_json(mirror_path)
    except ValueError as exc:
        print(exc, file=sys.stderr)
        return 1

    errors: list[str] = []
    check_forbidden_fields(latest, "latest.json", errors)
    check_forbidden_fields(mirror, "mirror-latest.json", errors)
    errors.extend(validate_dry_run_report(latest, args.strict, args.allow_legacy_usage_waiver))
    errors.extend(validate_mirror_report(mirror, args.strict))

    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1

    print(f"shadow evidence checks: OK ({'strict' if args.strict else 'default'})")
    print(
        json.dumps(
            {
                "latest": str(latest_path),
                "mirror": str(mirror_path),
                "strict": args.strict,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
