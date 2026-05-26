#!/usr/bin/env python3
import argparse
import json
import re
import sys
from pathlib import Path

FORBIDDEN_HEADERS = {"authorization", "cookie", "set-cookie"}
ALLOWED_ID_PREFIXES = ("synthetic-", "parity-", "test-", "req_")
PHONE_RE = re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)")
EMAIL_RE = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)
ID_CARD_RE = re.compile(r"(?<!\d)(\d{15}|\d{17}[\dXx])(?!\d)")
SENSITIVE_KEYWORDS = {"authorization", "cookie", "set-cookie"}
SYNTHETIC_ID_KEYS = {
    "user_id",
    "student_id",
    "school_id",
    "openid",
    "unionid",
    "userid",
    "request_id",
    "trace_id",
    "x-request-id",
}
ALLOWED_CATEGORIES = {
    "deterministic_error",
    "deterministic_policy",
    "nondeterministic_success",
}
ALLOWED_SOURCES = {"handcrafted", "sanitized_real_traffic"}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True)
    args = parser.parse_args()

    root = Path(args.root)
    fixture_dir = root / "tests" / "parity"
    fixture_paths = sorted(path for path in fixture_dir.glob("*.yaml") if path.is_file())
    if not fixture_paths:
        print("no parity fixtures found", file=sys.stderr)
        return 1

    errors: list[str] = []
    for fixture_path in fixture_paths:
        errors.extend(validate_fixture_file(fixture_path))

    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1

    print(f"validated parity fixtures: {len(fixture_paths)} file(s)")
    return 0


def validate_fixture_file(path: Path) -> list[str]:
    try:
        fixture = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return [f"{path}: parse error: {exc}"]
    cases = fixture.get("cases")
    if not isinstance(cases, list) or not cases:
        return [f"{path}: cases must be a non-empty list"]
    errors: list[str] = []
    for index, case in enumerate(cases):
        errors.extend(validate_case(path, index, case))
    return errors


def validate_case(path: Path, index: int, case: object) -> list[str]:
    prefix = f"{path}: case[{index}]"
    if not isinstance(case, dict):
        return [f"{prefix}: case must be an object"]
    errors: list[str] = []
    category = case.get("category")
    source = case.get("source")
    if category not in ALLOWED_CATEGORIES:
        errors.append(f"{prefix}: unsupported category {category!r}")
    if source not in ALLOWED_SOURCES:
        errors.append(f"{prefix}: unsupported source {source!r}")

    privacy = case.get("privacy")
    if not isinstance(privacy, dict):
        errors.append(f"{prefix}: privacy is required")
    else:
        if privacy.get("sanitized") is not True:
            errors.append(f"{prefix}: privacy.sanitized must be true")
        if privacy.get("contains_pii") is not False:
            errors.append(f"{prefix}: privacy.contains_pii must be false")
        if not isinstance(privacy.get("reviewed_by"), str) or not privacy.get("reviewed_by").strip():
            errors.append(f"{prefix}: privacy.reviewed_by is required")

    route = case.get("route")
    method = case.get("method")
    path_value = case.get("path")
    if not isinstance(route, str) or not route.strip():
        errors.append(f"{prefix}: route is required")
    elif isinstance(method, str) and isinstance(path_value, str):
        normalized_path = path_value.split("?", 1)[0]
        expected_route = f"{method.strip().upper()} {normalized_path.strip()}"
        if route != expected_route:
            errors.append(f"{prefix}: route must equal {expected_route!r}")

    errors.extend(scan_object(case.get("headers"), f"{prefix}.headers"))
    errors.extend(scan_object(case.get("body_json"), f"{prefix}.body_json"))
    errors.extend(scan_object(case.get("body"), f"{prefix}.body"))
    errors.extend(scan_object(case.get("name"), f"{prefix}.name"))

    headers = case.get("headers")
    if isinstance(headers, dict):
        lowered_headers = {str(key).lower(): value for key, value in headers.items()}
        for forbidden in FORBIDDEN_HEADERS:
            if forbidden in lowered_headers:
                errors.append(f"{prefix}: forbidden header {forbidden}")
        request_id = lowered_headers.get("x-request-id")
        if isinstance(request_id, str) and not request_id.startswith(ALLOWED_ID_PREFIXES):
            errors.append(f"{prefix}: x-request-id must use synthetic/parity/test prefix")

    return errors


def scan_object(value: object, location: str, key_hint: str | None = None) -> list[str]:
    errors: list[str] = []
    if isinstance(value, dict):
        for key, nested in value.items():
            key_name = str(key)
            lowered = key_name.lower()
            if lowered in SENSITIVE_KEYWORDS:
                errors.append(f"{location}: forbidden key {key_name}")
            errors.extend(scan_object(nested, f"{location}.{key_name}", lowered))
        return errors
    if isinstance(value, list):
        for index, nested in enumerate(value):
            errors.extend(scan_object(nested, f"{location}[{index}]", key_hint))
        return errors
    if isinstance(value, str):
        text = value.strip()
        if PHONE_RE.search(text):
            errors.append(f"{location}: contains phone number")
        if EMAIL_RE.search(text):
            errors.append(f"{location}: contains email")
        if ID_CARD_RE.search(text):
            errors.append(f"{location}: contains id card number")
        if key_hint in SYNTHETIC_ID_KEYS and text and not text.startswith(ALLOWED_ID_PREFIXES):
            errors.append(f"{location}: must use synthetic/parity/test identifier")
    return errors


if __name__ == "__main__":
    sys.exit(main())
