#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from check_route_contract import load_json_yaml


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check observability contract compliance.")
    parser.add_argument("--contract", type=Path, default=None, help="observability_contract.yaml path")
    parser.add_argument("--fixtures", type=Path, default=None, help="tests/fixtures/observability directory")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    return parser.parse_args()


def resolve_contract(args: argparse.Namespace) -> Path:
    if args.contract:
        return args.contract
    return args.root / "configs" / "observability_contract.yaml"


def resolve_fixtures(args: argparse.Namespace) -> Path:
    if args.fixtures:
        return args.fixtures
    return args.root / "tests" / "fixtures" / "observability"


def validate_contract_shape(contract: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if contract.get("version") != 1:
        errors.append("contract version must be 1")
    required_request = contract.get("required_request_log_fields", [])
    if not isinstance(required_request, list) or not required_request:
        errors.append("required_request_log_fields must be a non-empty list")
    required_admin = contract.get("required_admin_fields", [])
    if not isinstance(required_admin, list):
        errors.append("required_admin_fields must be a list")
    forbidden = contract.get("forbidden_fields", [])
    if not isinstance(forbidden, list) or not forbidden:
        errors.append("forbidden_fields must be a non-empty list")
    metrics = contract.get("metrics", [])
    if not isinstance(metrics, list) or not metrics:
        errors.append("metrics must be a non-empty list")
    return errors


def check_log_fixture(fixture: dict[str, Any], contract: dict[str, Any], path: str) -> list[str]:
    errors: list[str] = []
    required_fields = contract.get("required_request_log_fields", [])
    forbidden_fields = contract.get("forbidden_fields", [])

    for field in required_fields:
        if field not in fixture:
            errors.append(f"{path}: missing required field {field!r}")

    log_keys = set(fixture.keys())
    for field in forbidden_fields:
        if field in log_keys:
            errors.append(f"{path}: contains forbidden field {field!r}")

    surface = fixture.get("surface", "")
    if surface == "admin":
        admin_fields = contract.get("required_admin_fields", [])
        for field in admin_fields:
            if field not in fixture:
                errors.append(f"{path}: missing admin field {field!r}")

    error_code = fixture.get("error_code")
    allowed_codes = contract.get("error_codes", [])
    if error_code and error_code not in allowed_codes:
        errors.append(f"{path}: unknown error_code {error_code!r}, expected one of {allowed_codes}")

    return errors


def check_metric_fixture(fixture: dict[str, Any], contract: dict[str, Any], path: str) -> list[str]:
    errors: list[str] = []
    allowed_metric_names = {m["name"] for m in contract.get("metrics", [])}
    allowed_labels_by_metric = {m["name"]: set(m["labels"]) for m in contract.get("metrics", [])}
    forbidden_label_names = set(contract.get("forbidden_metric_labels", []))

    metric_name = fixture.get("name", "")
    if metric_name not in allowed_metric_names:
        errors.append(f"{path}: unknown metric name {metric_name!r}")
        return errors

    labels = fixture.get("labels", {})
    expected_labels = allowed_labels_by_metric.get(metric_name, set())
    actual_labels = set(labels.keys())

    missing_labels = expected_labels - actual_labels
    if missing_labels:
        errors.append(f"{path}: metric {metric_name!r} missing labels {sorted(missing_labels)}")

    extra_labels = actual_labels - expected_labels
    if extra_labels:
        errors.append(f"{path}: metric {metric_name!r} has unexpected labels {sorted(extra_labels)}")

    for label in actual_labels:
        if label in forbidden_label_names:
            errors.append(f"{path}: metric {metric_name!r} label {label!r} is forbidden (high cardinality)")

    return errors


def check_fixtures(fixtures_dir: Path, contract: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if not fixtures_dir.is_dir():
        errors.append(f"fixtures directory not found: {fixtures_dir}")
        return errors

    for fixture_path in sorted(fixtures_dir.iterdir()):
        if not fixture_path.is_file() or fixture_path.suffix not in {".json", ".yaml", ".yml"}:
            continue
        try:
            data = load_json_yaml(fixture_path)
        except ValueError as exc:
            errors.append(str(exc))
            continue

        rel = str(fixture_path.relative_to(fixtures_dir.parents[1]))
        if isinstance(data, list):
            for idx, entry in enumerate(data):
                loc = f"{rel}[{idx}]"
                if entry.get("type") == "metric":
                    errors.extend(check_metric_fixture(entry, contract, loc))
                else:
                    errors.extend(check_log_fixture(entry, contract, loc))
        elif isinstance(data, dict):
            if data.get("type") == "metric":
                errors.extend(check_metric_fixture(data, contract, rel))
            else:
                errors.extend(check_log_fixture(data, contract, rel))
    return errors


def main() -> int:
    args = parse_args()
    contract_path = resolve_contract(args)
    fixtures_dir = resolve_fixtures(args)

    if not contract_path.is_file():
        print(f"OBSERVABILITY CONTRACT FAIL: contract not found: {contract_path}", file=sys.stderr)
        return 1

    try:
        contract = load_json_yaml(contract_path)
    except ValueError as exc:
        print(f"OBSERVABILITY CONTRACT FAIL: {exc}", file=sys.stderr)
        return 1

    errors: list[str] = []
    errors.extend(validate_contract_shape(contract))
    errors.extend(check_fixtures(fixtures_dir, contract))

    if errors:
        for error in errors:
            print(f"OBSERVABILITY CONTRACT FAIL: {error}", file=sys.stderr)
        return 1

    print("observability contract checks: OK")
    print(
        json.dumps(
            {
                "contract": str(contract_path),
                "fixtures": str(fixtures_dir),
                "required_fields": len(contract.get("required_request_log_fields", [])),
                "admin_fields": len(contract.get("required_admin_fields", [])),
                "forbidden_fields": len(contract.get("forbidden_fields", [])),
                "metrics": len(contract.get("metrics", [])),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
