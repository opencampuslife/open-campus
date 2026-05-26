#!/usr/bin/env python3
"""Validate staging ingress config against cutover policy and safety rules.

Rules enforced:
- mode must be staging_only
- enabled must be false (unless --allow-enabled or --allow-header-canary)
- canary.enabled must be false (unless --allow-header-canary)
- default_weight must be 0 (unless --allow-weight)
- All routes must be in cutover_policy.yaml allowed_cutover_routes
- No wildcard /api/* or /api/admin/* routes
- No GET /api/admin/** routes
- No production host references
- All route weights must be 0 (unless --allow-weight)
- Header canary type/header/value must be exact (X-Gaokao-Gateway-Canary / go)
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check staging ingress config.")
    parser.add_argument("--config", required=True, help="staging ingress config path")
    parser.add_argument("--policy", required=True, help="cutover_policy.yaml path")
    parser.add_argument("--allow-enabled", action="store_true", help="allow enabled=true (for future staging flip)")
    parser.add_argument("--allow-weight", action="store_true", help="allow weight>0 (for future staging rollout)")
    parser.add_argument("--allow-header-canary", action="store_true", help="allow canary.enabled=true and enabled=true (for PR-6B header canary)")
    parser.add_argument("--allow-percentage-canary", action="store_true", help="allow canary.type=percentage and enabled=true (for PR-6D percentage canary)")
    return parser.parse_args()


def load_json_yaml(path: Path) -> dict[str, Any]:
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise ValueError(f"missing file: {path}") from exc
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        try:
            import yaml
            payload = yaml.safe_load(text)
        except ImportError:
            raise ValueError(f"invalid JSON/YAML {path}: install PyYAML or use JSON format") from None
        except Exception as exc:
            raise ValueError(f"invalid YAML {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"{path}: root must be an object")
    return payload


def route_key(method: str, path: str) -> tuple[str, str]:
    return (method.strip().upper(), path.strip())


def normalize_template(path: str) -> str:
    return re.sub(r"\{[^{}]+\}", "{param}", path)


def path_matches(pattern: str, path: str) -> bool:
    if pattern.endswith("/**"):
        return path.startswith(pattern[:-3])
    return normalize_template(pattern) == normalize_template(path)


def validate_config_shape(config: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if config.get("mode") != "staging_only":
        errors.append("config mode must be 'staging_only'")
    if config.get("default_weight") != 0:
        errors.append("config default_weight must be 0")
    if not isinstance(config.get("upstreams"), dict):
        errors.append("config must define upstreams as a mapping")
    if not isinstance(config.get("routes"), list):
        errors.append("config must define routes as a list")
    return errors


def validate_enabled(config: dict[str, Any], allow_enabled: bool, allow_header_canary: bool, allow_percentage_canary: bool) -> list[str]:
    errors: list[str] = []
    enabled = config.get("enabled", False)
    canary = config.get("canary", {})
    canary_enabled = isinstance(canary, dict) and canary.get("enabled", False)
    canary_type = canary.get("type", "") if isinstance(canary, dict) else ""

    # Header-canary mode
    if enabled and not allow_enabled and not (canary_enabled and (allow_header_canary or allow_percentage_canary)):
        errors.append("config enabled must be false (use --allow-enabled, --allow-header-canary, or --allow-percentage-canary to override)")
    if canary_enabled and not allow_header_canary and not allow_percentage_canary:
        errors.append("config canary.enabled must be false (use --allow-header-canary or --allow-percentage-canary to override)")
    # Percentage-canary specific: reject if type=percentage without flag
    if canary_type == "percentage" and not allow_percentage_canary:
        errors.append("config canary.type=percentage must be allowed with --allow-percentage-canary")
    return errors


def validate_canary_config(config: dict[str, Any], allow_header_canary: bool, allow_percentage_canary: bool, allow_weight: bool = False) -> list[str]:
    errors: list[str] = []
    canary = config.get("canary")
    if canary is None:
        return errors

    if not isinstance(canary, dict):
        errors.append("canary must be a mapping")
        return errors

    canary_type = canary.get("type", "")
    canary_enabled = canary.get("enabled", False)

    # Header-canary validation
    if canary_type == "header":
        if canary_enabled and not allow_header_canary:
            errors.append("canary.enabled must be false (use --allow-header-canary to override)")
        if canary_enabled:
            header = canary.get("header", "")
            if not header:
                errors.append("canary.header is required when canary.enabled=true")
            elif header != "X-Gaokao-Gateway-Canary":
                errors.append(f"canary.header must be 'X-Gaokao-Gateway-Canary', got {header!r}")
            value = canary.get("value", "")
            if value and value != "go":
                errors.append(f"canary.value must be 'go', got {value!r}")

    # Percentage-canary validation
    elif canary_type == "percentage":
        if canary_enabled and not allow_percentage_canary:
            errors.append("canary.type=percentage must be allowed with --allow-percentage-canary")
        current_weight = canary.get("current_weight")
        if current_weight is not None and current_weight != 0 and not allow_weight:
            errors.append("canary.current_weight must be 0 (use --allow-weight for traffic rollout)")
        # Validate stages regardless of current_weight (stages should be defined even when current_weight=0)
        stages = canary.get("stages", [])
        if not isinstance(stages, list):
            errors.append("canary.stages must be a list")
        else:
            valid_stages = [1, 5, 25, 50, 100]
            for s in stages:
                if s not in valid_stages:
                    errors.append(f"canary.stages includes invalid value {s}, must be from {valid_stages}")
            # Check stages are increasing
            if len(stages) >= 2:
                for i in range(1, len(stages)):
                    if stages[i] <= stages[i-1]:
                        errors.append(f"canary.stages must be increasing, got {stages}")
                        break

    elif canary_type:
        errors.append(f"canary.type must be 'header' or 'percentage', got {canary_type!r}")

    # Validate per-route canary config
    for idx, route in enumerate(config.get("routes", [])):
        if not isinstance(route, dict):
            continue
        route_canary = route.get("canary")
        if route_canary is None:
            continue
        if not isinstance(route_canary, dict):
            errors.append(f"routes[{idx}] canary must be a mapping")
            continue
        rt_type = route_canary.get("type", "")
        if rt_type == "header":
            rt_header = route_canary.get("header", "")
            if rt_header and rt_header != "X-Gaokao-Gateway-Canary":
                errors.append(f"routes[{idx}] canary.header must be 'X-Gaokao-Gateway-Canary', got {rt_header!r}")
            rt_value = route_canary.get("value", "")
            if rt_value and rt_value != "go":
                errors.append(f"routes[{idx}] canary.value must be 'go', got {rt_value!r}")
        elif rt_type == "percentage":
            if not allow_percentage_canary:
                errors.append(f"routes[{idx}] canary.type=percentage must be allowed with --allow-percentage-canary")
        elif rt_type:
            errors.append(f"routes[{idx}] canary.type must be 'header' or 'percentage', got {rt_type!r}")

    return errors

    if not isinstance(canary, dict):
        errors.append("canary must be a mapping")
        return errors

    canary_type = canary.get("type", "")
    if canary_type and canary_type != "header":
        errors.append(f"canary.type must be 'header', got {canary_type!r}")

    header = canary.get("header", "")
    if canary.get("enabled", False):
        if not header:
            errors.append("canary.header is required when canary.enabled=true")
        elif header != "X-Gaokao-Gateway-Canary":
            errors.append(f"canary.header must be 'X-Gaokao-Gateway-Canary', got {header!r}")
        value = canary.get("value", "")
        if value and value != "go":
            errors.append(f"canary.value must be 'go', got {value!r}")

    for idx, route in enumerate(config.get("routes", [])):
        if not isinstance(route, dict):
            continue
        route_canary = route.get("canary")
        if route_canary is None:
            continue
        if not isinstance(route_canary, dict):
            errors.append(f"routes[{idx}] canary must be a mapping")
            continue
        rt_header = route_canary.get("header", "")
        if rt_header and rt_header != "X-Gaokao-Gateway-Canary":
            errors.append(f"routes[{idx}] canary.header must be 'X-Gaokao-Gateway-Canary', got {rt_header!r}")
        rt_value = route_canary.get("value", "")
        if rt_value and rt_value != "go":
            errors.append(f"routes[{idx}] canary.value must be 'go', got {rt_value!r}")

    return errors


def validate_routes_against_policy(config: dict[str, Any], policy: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    allowed = policy.get("allowed_cutover_routes", [])
    allowed_keys = {route_key(r.get("method", ""), r.get("path", "")) for r in allowed if isinstance(r, dict)}

    for idx, route in enumerate(config.get("routes", [])):
        if not isinstance(route, dict):
            errors.append(f"routes[{idx}] must be an object")
            continue
        method = route.get("method", "")
        path = route.get("path", "")
        key = route_key(method, path)
        location = f"routes[{idx}] ({method} {path})"
        if not method or not path:
            errors.append(f"{location}: method and path are required")
            continue
        if key not in allowed_keys:
            errors.append(f"{location} is not in cutover_policy.yaml allowed_cutover_routes")
    return errors


def validate_no_wildcards(config: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    for idx, route in enumerate(config.get("routes", [])):
        if not isinstance(route, dict):
            continue
        method = route.get("method", "")
        path = route.get("path", "")
        location = f"routes[{idx}] ({method} {path})"
        if "*" in path:
            errors.append(f"{location}: wildcard path is forbidden")
        if path.startswith("/api/admin/") and method.upper() == "GET":
            errors.append(f"{location}: GET /api/admin/** is forbidden")
    return errors


def validate_no_api_wildcards(config: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    for idx, route in enumerate(config.get("routes", [])):
        if not isinstance(route, dict):
            continue
        path = route.get("path", "")
        if path in ("/api/*", "/api/**"):
            errors.append(f"routes[{idx}]: wildcard /api/* is forbidden")
    return errors


def validate_weights(config: dict[str, Any], allow_weight: bool, allow_header_canary: bool, allow_percentage_canary: bool) -> list[str]:
    errors: list[str] = []
    default_weight = config.get("default_weight", 0)
    # PR-6D: percentage-canary config still requires default_weight=0 unless --allow-weight
    if default_weight != 0 and not allow_weight:
        errors.append("default_weight must be 0 (use --allow-weight to override)")

    for idx, route in enumerate(config.get("routes", [])):
        if not isinstance(route, dict):
            continue
        weight = route.get("weight", 0)
        # In PR-6D percentage-canary, per-route weight must still be 0 unless --allow-weight
        if weight != 0 and not allow_weight:
            method = route.get("method", "")
            path = route.get("path", "")
            errors.append(f"routes[{idx}] ({method} {path}): weight must be 0 (use --allow-weight)")
    return errors


def validate_no_production_host(config: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    text = json.dumps(config, ensure_ascii=False)
    production_patterns = [r"\.example\.com", r"\.production\.", r"prod-", r"production-"]
    for pattern in production_patterns:
        if re.search(pattern, text, re.IGNORECASE):
            errors.append(f"config contains potential production host reference: matches {pattern}")
    return errors


def validate_blocked_patterns(config: dict[str, Any], policy: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    blocked = policy.get("blocked_routes", [])
    blocked_entries = []
    for b in blocked:
        if isinstance(b, dict):
            blocked_entries.append({
                "method": b.get("method", ""),
                "path_pattern": b.get("path_pattern", ""),
                "allow_if_explicitly_listed": b.get("allow_if_explicitly_listed", False),
            })

    config_blocked = config.get("blocked_patterns", [])
    for b in config_blocked:
        if isinstance(b, dict) and b.get("method") and b.get("path_pattern"):
            blocked_entries.append({
                "method": b.get("method", ""),
                "path_pattern": b.get("path_pattern", ""),
                "allow_if_explicitly_listed": b.get("allow_if_explicitly_listed", False),
                "_from_config": True,
            })

    allowed_keys = set()
    for allowed in policy.get("allowed_cutover_routes", []):
        if isinstance(allowed, dict):
            allowed_keys.add(route_key(allowed.get("method", ""), allowed.get("path", "")))

    for idx, route in enumerate(config.get("routes", [])):
        if not isinstance(route, dict):
            continue
        method = route.get("method", "").upper()
        path = route.get("path", "")
        route_key_val = route_key(method, path)
        location = f"routes[{idx}] ({method} {path})"

        for entry in blocked_entries:
            blocked_method = str(entry.get("method", "")).upper()
            blocked_pattern = entry.get("path_pattern", "")
            allow_explicit = entry.get("allow_if_explicitly_listed") is True
            method_match = blocked_method in {"*", method}
            if not method_match:
                continue
            if not path_matches(blocked_pattern, path):
                continue
            if allow_explicit and route_key_val in allowed_keys:
                continue
            source = "config blocked_patterns" if entry.get("_from_config") else "policy blocked_routes"
            errors.append(f"{location}: matches blocked pattern {entry.get('method', '')} {blocked_pattern} ({source})")
    return errors


def main() -> int:
    args = parse_args()
    config_path = Path(args.config)
    policy_path = Path(args.policy)

    try:
        config = load_json_yaml(config_path)
        policy = load_json_yaml(policy_path)
    except ValueError as exc:
        print(f"STAGING INGRESS FAIL: {exc}", file=sys.stderr)
        return 1

    errors: list[str] = []
    errors.extend(validate_config_shape(config))
    errors.extend(validate_enabled(config, args.allow_enabled, args.allow_header_canary, args.allow_percentage_canary))
    errors.extend(validate_canary_config(config, args.allow_header_canary, args.allow_percentage_canary, args.allow_weight))
    errors.extend(validate_routes_against_policy(config, policy))
    errors.extend(validate_no_wildcards(config))
    errors.extend(validate_no_api_wildcards(config))
    errors.extend(validate_weights(config, args.allow_weight, args.allow_header_canary, args.allow_percentage_canary))
    errors.extend(validate_no_production_host(config))
    errors.extend(validate_blocked_patterns(config, policy))

    if errors:
        for error in errors:
            print(f"STAGING INGRESS FAIL: {error}", file=sys.stderr)
        return 1

    print("staging ingress config checks: OK")
    canary = config.get("canary", {})
    canary_enabled = canary.get("enabled", False) if isinstance(canary, dict) else None
    print(
        json.dumps(
            {
                "config": str(config_path),
                "policy": str(policy_path),
                "enabled": config.get("enabled", False),
                "default_weight": config.get("default_weight", 0),
        "canary_enabled": canary_enabled if isinstance(canary, dict) else None,
        "canary_type": canary.get("type", None) if isinstance(canary, dict) else None,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
