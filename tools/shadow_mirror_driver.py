#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

FORBIDDEN_HEADERS = {"authorization", "cookie", "set-cookie"}
ALLOWED_ID_PREFIXES = ("synthetic-", "parity-", "test-", "req_")
PATH_ID_MARKERS = ("parity", "synthetic", "test", "req_")
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
PATH_TOKEN_RE = re.compile(r"(doc|run|user|student|school)-([A-Za-z0-9_-]+)")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run external shadow mirror checks with redacted reports.")
    parser.add_argument("--root", required=True, help="project root path")
    parser.add_argument("--input", required=True, help="fixture/replay input (.jsonl, .json, or JSON-compatible .yaml)")
    parser.add_argument("--legacy-base-url", default=None, help="legacy Python gateway base URL")
    parser.add_argument("--shadow-base-url", default=None, help="Go shadow gateway base URL")
    parser.add_argument("--timeout-ms", type=int, default=5000, help="per-request timeout in milliseconds")
    parser.add_argument("--dry-run", action="store_true", help="validate input and emit skipped report without network calls")
    parser.add_argument("--output-json", default=None, help="default: reports/shadow/mirror-latest.json")
    parser.add_argument("--output-md", default=None, help="default: reports/shadow/mirror-latest.md")
    return parser.parse_args()


def load_cases(path: Path) -> list[dict[str, Any]]:
    if path.suffix == ".jsonl":
        cases: list[dict[str, Any]] = []
        for line_number, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            line = raw_line.strip()
            if not line:
                continue
            try:
                case = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}: line {line_number}: invalid JSON: {exc}") from exc
            if not isinstance(case, dict):
                raise ValueError(f"{path}: line {line_number}: case must be an object")
            cases.append(case)
        if not cases:
            raise ValueError(f"{path}: expected at least one JSONL case")
        validate_cases(path, cases)
        return cases

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"{path}: invalid JSON-compatible fixture: {exc}") from exc
    cases = payload.get("cases")
    if not isinstance(cases, list) or not cases:
        raise ValueError(f"{path}: cases must be a non-empty list")
    validate_cases(path, cases)
    return cases


def validate_cases(path: Path, cases: list[dict[str, Any]]) -> None:
    errors: list[str] = []
    for index, case in enumerate(cases):
        errors.extend(validate_case(path, index, case))
    if errors:
        raise ValueError("\n".join(errors))


def validate_case(path: Path, index: int, case: dict[str, Any]) -> list[str]:
    prefix = f"{path}: case[{index}]"
    errors: list[str] = []

    for field in ("name", "method", "path"):
        value = case.get(field)
        if not isinstance(value, str) or not value.strip():
            errors.append(f"{prefix}: {field} is required")

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

    method = str(case.get("method", "")).strip().upper()
    path_value = str(case.get("path", "")).strip()
    route = case.get("route")
    if isinstance(route, str) and route.strip():
        normalized_path = path_value.split("?", 1)[0]
        expected_route = f"{method} {normalized_path}"
        if route != expected_route:
            errors.append(f"{prefix}: route must equal {expected_route!r}")

    headers = case.get("headers")
    if headers is not None and not isinstance(headers, dict):
        errors.append(f"{prefix}: headers must be an object")
    if isinstance(headers, dict):
        lowered_headers = {str(key).lower(): value for key, value in headers.items()}
        for forbidden in FORBIDDEN_HEADERS:
            if forbidden in lowered_headers:
                errors.append(f"{prefix}: forbidden header {forbidden}")
        request_id = lowered_headers.get("x-request-id")
        if isinstance(request_id, str) and request_id and not request_id.startswith(ALLOWED_ID_PREFIXES):
            errors.append(f"{prefix}: x-request-id must use a synthetic/parity/test prefix")

    body = case.get("body")
    body_json = case.get("body_json")
    if body is not None and body_json is not None:
        errors.append(f"{prefix}: use either body or body_json, not both")

    errors.extend(scan_object(case.get("name"), f"{prefix}.name"))
    errors.extend(scan_object(path_value, f"{prefix}.path"))
    errors.extend(scan_object(headers, f"{prefix}.headers"))
    errors.extend(scan_object(body_json, f"{prefix}.body_json"))
    errors.extend(scan_object(body, f"{prefix}.body"))

    for match in PATH_TOKEN_RE.finditer(path_value):
        token = match.group(2).lower()
        if not any(marker in token for marker in PATH_ID_MARKERS):
            errors.append(f"{prefix}: path token {match.group(0)!r} must use synthetic/parity/test marker")

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


def canonical_body(case: dict[str, Any]) -> tuple[bytes, str]:
    if case.get("body_json") is not None:
        return json.dumps(case["body_json"], ensure_ascii=False, separators=(",", ":")).encode("utf-8"), "application/json"
    if case.get("body") is not None:
        return str(case["body"]).encode("utf-8"), ""
    return b"", ""


def normalize_headers(headers: dict[str, Any] | None, body_content_type: str) -> dict[str, str]:
    normalized: dict[str, str] = {}
    for key, value in (headers or {}).items():
        normalized[str(key)] = str(value)
    if body_content_type and not any(key.lower() == "content-type" for key in normalized):
        normalized["Content-Type"] = body_content_type
    return normalized


def perform_request(base_url: str, case: dict[str, Any], timeout_seconds: float) -> dict[str, Any]:
    body_bytes, default_content_type = canonical_body(case)
    headers = normalize_headers(case.get("headers"), default_content_type)
    url = urllib.parse.urljoin(base_url.rstrip("/") + "/", case["path"].lstrip("/"))
    request = urllib.request.Request(
        url=url,
        data=body_bytes if body_bytes else None,
        headers=headers,
        method=str(case["method"]).upper(),
    )
    started_at = time.perf_counter()
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            payload = response.read()
            return build_endpoint_result(response.status, response.headers.get("Content-Type"), payload, started_at)
    except urllib.error.HTTPError as exc:
        payload = exc.read()
        return build_endpoint_result(exc.code, exc.headers.get("Content-Type"), payload, started_at)
    except Exception as exc:  # pragma: no cover - network errors depend on host state
        elapsed_ms = round((time.perf_counter() - started_at) * 1000)
        return {
            "status": None,
            "latency_ms": elapsed_ms,
            "content_type": None,
            "body_summary": None,
            "body_sha256": None,
            "error": exc.__class__.__name__,
        }


def build_endpoint_result(status: int | None, content_type: str | None, payload: bytes, started_at: float) -> dict[str, Any]:
    elapsed_ms = round((time.perf_counter() - started_at) * 1000)
    body_sha256 = hashlib.sha256(payload).hexdigest()[:16]
    body_summary = f"[redacted len={len(payload)} sha256={body_sha256}]"
    return {
        "status": status,
        "latency_ms": elapsed_ms,
        "content_type": content_type,
        "body_summary": body_summary,
        "body_sha256": body_sha256,
        "error": None,
    }


def content_type_compatible(left: str | None, right: str | None) -> bool:
    if left == right:
        return True
    if not left or not right:
        return False
    return left.split(";", 1)[0].strip().lower() == right.split(";", 1)[0].strip().lower()


def diff_category(legacy: dict[str, Any], shadow: dict[str, Any]) -> str:
    if legacy.get("status") is None or shadow.get("status") is None:
        return "unavailable"
    if legacy["status"] != shadow["status"]:
        return "status"
    if not content_type_compatible(legacy.get("content_type"), shadow.get("content_type")):
        return "headers"
    if legacy.get("body_sha256") != shadow.get("body_sha256"):
        return "body_hash"
    return "none"


def comparison_status(category: str) -> str:
    if category == "none":
        return "passed"
    if category == "skipped":
        return "skipped"
    return "drifted"


def latency_ratio(legacy: dict[str, Any], shadow: dict[str, Any]) -> float | None:
    legacy_ms = legacy.get("latency_ms")
    shadow_ms = shadow.get("latency_ms")
    if not legacy_ms or not shadow_ms:
        return None
    return round(float(shadow_ms) / float(legacy_ms), 4)


def run_cases(
    cases: list[dict[str, Any]],
    legacy_base_url: str | None,
    shadow_base_url: str | None,
    timeout_seconds: float,
    dry_run: bool,
) -> dict[str, Any]:
    results: list[dict[str, Any]] = []
    executed = 0
    skipped = 0
    drifted = 0
    for case in cases:
        method = str(case["method"]).upper()
        path = str(case["path"])
        if dry_run or not legacy_base_url or not shadow_base_url:
            skipped += 1
            results.append(
                {
                    "name": case["name"],
                    "method": method,
                    "path": path,
                    "comparison_status": "skipped",
                    "legacy_status": None,
                    "shadow_status": None,
                    "legacy_latency_ms": None,
                    "shadow_latency_ms": None,
                    "latency_ratio": None,
                    "diff_category": "skipped",
                    "legacy_body_summary": None,
                    "shadow_body_summary": None,
                }
            )
            continue

        executed += 1
        legacy_result = perform_request(legacy_base_url, case, timeout_seconds)
        shadow_result = perform_request(shadow_base_url, case, timeout_seconds)
        category = diff_category(legacy_result, shadow_result)
        if category != "none":
            drifted += 1
        results.append(
            {
                "name": case["name"],
                "method": method,
                "path": path,
                "comparison_status": comparison_status(category),
                "legacy_status": legacy_result.get("status"),
                "shadow_status": shadow_result.get("status"),
                "legacy_latency_ms": legacy_result.get("latency_ms"),
                "shadow_latency_ms": shadow_result.get("latency_ms"),
                "latency_ratio": latency_ratio(legacy_result, shadow_result),
                "diff_category": category,
                "legacy_body_summary": legacy_result.get("body_summary"),
                "shadow_body_summary": shadow_result.get("body_summary"),
            }
        )

    return {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "mode": "dry_run" if dry_run or not legacy_base_url or not shadow_base_url else "live",
        "summary": {
            "total_cases": len(cases),
            "executed_cases": executed,
            "skipped_cases": skipped,
            "drifted_cases": drifted,
        },
        "cases": results,
    }


def write_json_report(report: dict[str, Any], output_path: Path) -> None:
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_markdown_report(report: dict[str, Any], output_path: Path) -> None:
    lines = [
        "# Shadow Mirror Report",
        "",
        f"- Generated at: `{report['generated_at']}`",
        f"- Mode: `{report['mode']}`",
        f"- Total cases: `{report['summary']['total_cases']}`",
        f"- Executed cases: `{report['summary']['executed_cases']}`",
        f"- Skipped cases: `{report['summary']['skipped_cases']}`",
        f"- Drifted cases: `{report['summary']['drifted_cases']}`",
        "",
        "| Case | Method | Path | Legacy | Shadow | Ratio | Diff | Legacy Body | Shadow Body |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for case in report["cases"]:
        lines.append(
            "| {name} | {method} | `{path}` | {legacy} | {shadow} | {ratio} | {diff} | `{legacy_body}` | `{shadow_body}` |".format(
                name=case["name"],
                method=case["method"],
                path=case["path"],
                legacy=case["legacy_status"] if case["legacy_status"] is not None else "skipped",
                shadow=case["shadow_status"] if case["shadow_status"] is not None else "skipped",
                ratio=case["latency_ratio"] if case["latency_ratio"] is not None else "-",
                diff=case["diff_category"],
                legacy_body=case["legacy_body_summary"] or "-",
                shadow_body=case["shadow_body_summary"] or "-",
            )
        )
    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    args = parse_args()
    root = Path(args.root).resolve()
    input_path = Path(args.input)
    if not input_path.is_absolute():
        input_path = root / input_path
    report_dir = root / "reports" / "shadow"
    report_dir.mkdir(parents=True, exist_ok=True)

    output_json = Path(args.output_json) if args.output_json else report_dir / "mirror-latest.json"
    output_md = Path(args.output_md) if args.output_md else report_dir / "mirror-latest.md"

    try:
        cases = load_cases(input_path)
    except ValueError as exc:
        print(exc, file=sys.stderr)
        return 1

    report = run_cases(
        cases=cases,
        legacy_base_url=args.legacy_base_url,
        shadow_base_url=args.shadow_base_url,
        timeout_seconds=max(args.timeout_ms, 1) / 1000.0,
        dry_run=args.dry_run,
    )
    write_json_report(report, output_json)
    write_markdown_report(report, output_md)
    print(f"shadow mirror report written to {output_json}")
    print(f"shadow mirror markdown written to {output_md}")
    print(json.dumps(report["summary"], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
