#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

import check_shadow_evidence

LEGACY_BLOCKING_FLAGS = {"deprecated_compatibility_alias", "state_changing_get", "legacy_policy_gap"}
PUBLIC_PHASES = {"production_canary_public"}
ADMIN_PHASES = {"production_canary_admin"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check controlled ingress cutover readiness policy.")
    parser.add_argument("--policy", required=True, help="cutover policy path")
    parser.add_argument("--routes", required=True, help="route contract path")
    parser.add_argument("--shadow-report", default=None, help="optional reports/shadow/latest.json")
    parser.add_argument("--mirror-report", default=None, help="optional reports/shadow/mirror-latest.json")
    parser.add_argument("--strict", action="store_true", help="require complete staging evidence")
    parser.add_argument("--allow-legacy-usage-waiver", action="store_true", help="allow legacy GET usage with waiver")
    return parser.parse_args()


def load_json_yaml(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValueError(f"missing file: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid JSON-compatible YAML {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"{path}: root must be an object")
    return payload


def route_key(method: object, path: object) -> tuple[str, str]:
    return (str(method).strip().upper(), str(path).strip())


def normalize_template(path: str) -> str:
    return re.sub(r"\{[^{}]+\}", "{param}", path)


def path_pattern_matches(pattern: str, path: str) -> bool:
    if pattern.endswith("/**"):
        return path.startswith(pattern[:-3])
    return normalize_template(pattern) == normalize_template(path)


def validate_policy_shape(policy: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if policy.get("version") != 1:
        errors.append("cutover policy version must be 1")
    if policy.get("mode") != "design_only":
        errors.append("cutover policy mode must be design_only")

    required_evidence = policy.get("required_evidence")
    if not isinstance(required_evidence, dict):
        errors.append("required_evidence must be an object")
    else:
        expected = {
            "staging_shadow_runs",
            "strict_evidence_passed",
            "unexpected_diffs",
            "latency_fail_count",
            "latency_warn_count_requires_note",
            "legacy_gaps",
            "state_changing_get_gaps",
            "deprecated_aliases",
            "legacy_get_usage_events_allowed",
        }
        missing = expected - set(required_evidence)
        if missing:
            errors.append(f"required_evidence missing fields: {', '.join(sorted(missing))}")
        if required_evidence.get("staging_shadow_runs") != 3:
            errors.append("required_evidence.staging_shadow_runs must be 3")
        if required_evidence.get("strict_evidence_passed") is not True:
            errors.append("required_evidence.strict_evidence_passed must be true")
        for field in ("unexpected_diffs", "latency_fail_count", "legacy_gaps", "state_changing_get_gaps", "legacy_get_usage_events_allowed"):
            if required_evidence.get(field) != 0:
                errors.append(f"required_evidence.{field} must be 0")
        if required_evidence.get("deprecated_aliases") != 5:
            errors.append("required_evidence.deprecated_aliases must be 5")

    if not isinstance(policy.get("allowed_cutover_routes"), list) or not policy.get("allowed_cutover_routes"):
        errors.append("allowed_cutover_routes must be a non-empty list")
    if not isinstance(policy.get("blocked_routes"), list) or not policy.get("blocked_routes"):
        errors.append("blocked_routes must be a non-empty list")
    if not isinstance(policy.get("rollback_triggers"), dict):
        errors.append("rollback_triggers must be an object")
    return errors


def validate_allowed_routes(policy: dict[str, Any], routes: dict[str, Any]) -> list[str]:
    entries = routes.get("routes", [])
    entries_by_key = {route_key(entry.get("method"), entry.get("path")): entry for entry in entries if isinstance(entry, dict)}
    errors: list[str] = []
    seen: set[tuple[str, str]] = set()

    for index, item in enumerate(policy.get("allowed_cutover_routes", [])):
        location = f"allowed_cutover_routes[{index}]"
        if not isinstance(item, dict):
            errors.append(f"{location} must be an object")
            continue
        method, path = route_key(item.get("method"), item.get("path"))
        key = (method, path)
        if key in seen:
            errors.append(f"{location} duplicates route {method} {path}")
        seen.add(key)
        if method in {"", "*"}:
            errors.append(f"{location} must use an explicit HTTP method")
        if "*" in path:
            errors.append(f"{location} must not use wildcard path {path}")
        if item.get("max_initial_percent") != 1:
            errors.append(f"{location} max_initial_percent must be 1")
        entry = entries_by_key.get(key)
        if entry is None:
            errors.append(f"{location} route not found in routes.yaml: {method} {path}")
            continue

        legacy_flags = set(entry.get("legacy_flags", []))
        if legacy_flags & LEGACY_BLOCKING_FLAGS:
            errors.append(f"{location} cannot include legacy/deprecated route: {method} {path}")
        if path.startswith("/api/admin/"):
            errors.extend(validate_admin_cutover_route(location, method, path, item, entry))
        else:
            errors.extend(validate_public_cutover_route(location, method, path, item, entry))

    return errors


def validate_public_cutover_route(location: str, method: str, path: str, item: dict[str, Any], entry: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if item.get("phase") not in PUBLIC_PHASES:
        errors.append(f"{location} public route has invalid phase {item.get('phase')!r}")
    if entry.get("visibility") != "public":
        errors.append(f"{location} public route must have visibility=public: {method} {path}")
    return errors


def validate_admin_cutover_route(location: str, method: str, path: str, item: dict[str, Any], entry: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if item.get("phase") not in ADMIN_PHASES:
        errors.append(f"{location} admin route has invalid phase {item.get('phase')!r}")
    if method != "POST":
        errors.append(f"{location} admin route must use POST: {method} {path}")
    if entry.get("csrf") != "required":
        errors.append(f"{location} admin route must set csrf=required: {method} {path}")
    if entry.get("audit") is not True:
        errors.append(f"{location} admin route must set audit=true: {method} {path}")
    if str(entry.get("auth", "")).lower() in {"", "anonymous", "none"}:
        errors.append(f"{location} admin route must require authenticated staff/admin access: {method} {path}")
    return errors


def validate_blocked_routes(policy: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    blocked_routes = policy.get("blocked_routes", [])
    has_admin_get_block = False
    has_admin_wildcard_block = False
    for index, item in enumerate(blocked_routes):
        location = f"blocked_routes[{index}]"
        if not isinstance(item, dict):
            errors.append(f"{location} must be an object")
            continue
        method = str(item.get("method", "")).upper()
        pattern = str(item.get("path_pattern", ""))
        if not method or not pattern:
            errors.append(f"{location} must define method and path_pattern")
        if method == "GET" and pattern == "/api/admin/**":
            has_admin_get_block = True
        if method == "*" and pattern == "/api/admin/**" and item.get("allow_if_explicitly_listed") is True:
            has_admin_wildcard_block = True
    if not has_admin_get_block:
        errors.append("blocked_routes must include GET /api/admin/**")
    if not has_admin_wildcard_block:
        errors.append("blocked_routes must include wildcard /api/admin/** with allow_if_explicitly_listed=true")
    return errors


def validate_blocked_vs_allowed(policy: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    for allowed in policy.get("allowed_cutover_routes", []):
        if not isinstance(allowed, dict):
            continue
        method, path = route_key(allowed.get("method"), allowed.get("path"))
        for blocked in policy.get("blocked_routes", []):
            if not isinstance(blocked, dict):
                continue
            blocked_method = str(blocked.get("method", "")).upper()
            pattern = str(blocked.get("path_pattern", ""))
            allow_explicit = blocked.get("allow_if_explicitly_listed") is True
            method_matches = blocked_method in {"*", method}
            if method_matches and path_pattern_matches(pattern, path) and not allow_explicit:
                errors.append(f"allowed route is blocked by policy: {method} {path} via {blocked_method} {pattern}")
    return errors


def validate_rollback_triggers(policy: dict[str, Any]) -> list[str]:
    triggers = policy.get("rollback_triggers", {})
    errors: list[str] = []
    expected_zero = ("unexpected_diff_count_gt", "latency_fail_count_gt")
    for field in expected_zero:
        if triggers.get(field) != 0:
            errors.append(f"rollback_triggers.{field} must be 0")
    if triggers.get("upstream_5xx_increase_pct_gt") != 1:
        errors.append("rollback_triggers.upstream_5xx_increase_pct_gt must be 1")
    for field in ("auth_csrf_mismatch", "missing_admin_audit_event", "deprecated_get_routed_to_go"):
        if triggers.get(field) is not True:
            errors.append(f"rollback_triggers.{field} must be true")
    return errors


def validate_strict_evidence(args: argparse.Namespace) -> list[str]:
    errors: list[str] = []
    if not args.shadow_report:
        errors.append("strict mode requires --shadow-report")
    if not args.mirror_report:
        errors.append("strict mode requires --mirror-report")
    if errors:
        return errors
    try:
        latest = check_shadow_evidence.load_json(Path(args.shadow_report))
        mirror = check_shadow_evidence.load_json(Path(args.mirror_report))
    except ValueError as exc:
        return [str(exc)]
    check_shadow_evidence.check_forbidden_fields(latest, "latest.json", errors)
    check_shadow_evidence.check_forbidden_fields(mirror, "mirror-latest.json", errors)
    errors.extend(
        check_shadow_evidence.validate_dry_run_report(
            latest,
            strict=True,
            allow_legacy_usage_waiver=args.allow_legacy_usage_waiver,
        )
    )
    errors.extend(check_shadow_evidence.validate_mirror_report(mirror, strict=True))
    return errors


def main() -> int:
    args = parse_args()
    try:
        policy = load_json_yaml(Path(args.policy))
        routes = load_json_yaml(Path(args.routes))
    except ValueError as exc:
        print(exc, file=sys.stderr)
        return 1

    errors: list[str] = []
    errors.extend(validate_policy_shape(policy))
    errors.extend(validate_allowed_routes(policy, routes))
    errors.extend(validate_blocked_routes(policy))
    errors.extend(validate_blocked_vs_allowed(policy))
    errors.extend(validate_rollback_triggers(policy))
    if args.strict:
        errors.extend(validate_strict_evidence(args))

    if errors:
        for error in errors:
            print(f"CUTOVER READINESS FAIL: {error}", file=sys.stderr)
        return 1

    print(f"cutover readiness checks: OK ({'strict' if args.strict else 'default'})")
    print(
        json.dumps(
            {
                "policy": str(args.policy),
                "routes": str(args.routes),
                "strict": args.strict,
                "allowed_routes": len(policy.get("allowed_cutover_routes", [])),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
