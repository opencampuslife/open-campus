#!/usr/bin/env python3
"""Collect staging percentage-canary evidence and produce a JSON report.

Reads the rendered config, validates the environment, and generates evidence.
If STAGING_ENV_CONFIRMED != "true", writes status=skipped (never fakes passed).

Usage:
    python3 tools/collect_staging_percentage_canary_result.py \
        --config /tmp/staging-1pct-canary.yaml \
        --policy configs/cutover_policy.yaml \
        --percent 1 \
        --report reports/staging/percentage-canary-1pct-latest.json
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    print("PyYAML is required. Install it with: pip install pyyaml", file=sys.stderr)
    sys.exit(1)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Collect staging percentage-canary evidence"
    )
    parser.add_argument("--config", required=True, help="Rendered canary config path")
    parser.add_argument("--policy", required=True, help="cutover_policy.yaml path")
    parser.add_argument(
        "--percent",
        type=int,
        required=True,
        choices=[1, 5, 25, 50, 100],
        help="Canary percentage for this evidence run",
    )
    parser.add_argument("--report", required=True, help="Output report JSON path")
    parser.add_argument(
        "--staging-url",
        default=os.environ.get("STAGING_URL", "http://localhost:8788"),
        help="Staging gateway URL (default from STAGING_URL or localhost:8788)",
    )
    parser.add_argument(
        "--config-applied",
        default=os.environ.get("CONFIG_APPLIED", "unknown"),
        help="Whether rendered config was applied to staging (true/false/unknown)",
    )
    parser.add_argument(
        "--rollback-verified",
        default=os.environ.get("ROLLBACK_VERIFIED", "unknown"),
        help="Whether rollback to 0%% was verified (true/false/unknown)",
    )
    return parser.parse_args()


def load_yaml(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    data = yaml.safe_load(text)
    if not isinstance(data, dict):
        raise ValueError(f"{path}: root must be an object")
    return data


def check_staging_env_confirmed() -> bool:
    return os.environ.get("STAGING_ENV_CONFIRMED", "").lower() == "true"


def run_evidence_checks(config: dict, staging_url: str, percent: int) -> dict:
    summary = {
        "staging_env_confirmed": check_staging_env_confirmed(),
        "config_rendered": True,
        "current_weight": config.get("canary", {}).get("current_weight", 0),
        "routes_checked": 0,
        "health_ok": None,
        "chat_parity": "skipped",
        "admin_post_parity": "skipped",
        "mirror_result": "skipped",
        "legacy_get_usage_events": None,
        "deprecated_get_blocked": None,
        "unexpected_diffs": None,
        "latency_fail_count": None,
        "rollback_verified": None,
    }

    if not summary["staging_env_confirmed"]:
        return summary

    # Placeholder for actual staging checks (requires live staging environment)
    # In a real run, these would make HTTP calls to the staging gateway
    summary["health_ok"] = "skipped_live_check"
    summary["chat_parity"] = "skipped_live_check"
    summary["admin_post_parity"] = "skipped_live_check"
    summary["mirror_result"] = "skipped_live_check"
    summary["legacy_get_usage_events"] = "skipped_live_check"
    summary["deprecated_get_blocked"] = "skipped_live_check"
    summary["unexpected_diffs"] = "skipped_live_check"
    summary["latency_fail_count"] = "skipped_live_check"
    summary["rollback_verified"] = "skipped_live_check"

    return summary


def build_report(config_path: Path, policy_path: Path, percent: int, staging_url: str, config_applied: str = "unknown", rollback_verified: str = "unknown") -> dict:
    config = load_yaml(config_path)
    policy = load_yaml(policy_path)

    canary = config.get("canary", {})
    actual_weight = canary.get("current_weight",0)

    # Validate config invariants
    if canary.get("type") != "percentage":
        raise ValueError("config canary.type must be 'percentage'")
    if actual_weight != percent:
        raise ValueError(
            f"config current_weight={actual_weight} != requested percent={percent}"
        )
    if actual_weight not in [1, 5, 25, 50, 100]:
        raise ValueError(f"current_weight={actual_weight} not in allowed stages")

    summary = run_evidence_checks(config, staging_url, percent)

    # Override with explicit CLI args if provided
    if config_applied != "unknown":
        summary["config_applied"] = config_applied == "true"
    if rollback_verified != "unknown":
        summary["rollback_verified"] = rollback_verified == "true"

    env_confirmed = summary["staging_env_confirmed"]

    # Compute status
    if not env_confirmed:
        status = "skipped"
    elif config_applied == "unknown" or rollback_verified == "unknown":
        status = "skipped_live_check"
    elif config_applied == "false" or rollback_verified == "false":
        status = "failed"
    elif (
        config_applied == "true"
        and rollback_verified == "true"
        and summary.get("health_ok") in [True, "passed"]
        and summary.get("deprecated_get_blocked") in [True, "passed"]
    ):
        status = "passed"
    else:
        status = "failed"

    report = {
        "mode": "staging_percentage_canary",
        "percent": percent,
        "status": status,
        "generated_at": datetime.datetime.now(datetime.timezone.utc)
        .isoformat()
        .replace("+00:00", "Z"),
        "config": str(config_path),
        "policy": str(policy_path),
        "staging_url": staging_url,
        "summary": summary,
        "privacy": {
            "raw_payload_included": False,
            "contains_pii": False,
        },
        "_note": "PR-6E: 1% evidence only. Does not submit weight=1 config. Does not fake passed.",
    }

    return report


def main() -> int:
    args = parse_args()
    config_path = Path(args.config)
    policy_path = Path(args.policy)
    report_path = Path(args.report)

    if not config_path.is_file():
        print(f"ERROR: config not found: {config_path}", file=sys.stderr)
        return 1
    if not policy_path.is_file():
        print(f"ERROR: policy not found: {policy_path}", file=sys.stderr)
        return 1

    try:
        report = build_report(
            config_path, policy_path, args.percent, args.staging_url,
            args.config_applied, args.rollback_verified
        )
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    print(f"Evidence report: {report_path}")
    print(f"Status: {report['status']}")
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
