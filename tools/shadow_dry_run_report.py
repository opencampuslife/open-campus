#!/usr/bin/env python3
import argparse
import json
import re
import sys
import time
from pathlib import Path


def load_json(path: Path):
    if not path.exists():
        return None
    try:
        with open(path) as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return None


def _strip_go_test_log_prefix(output: str) -> str:
    return re.sub(r"^\s*[\w./-]+\.go:\d+:\s?", "", output)


def _extract_json_reports(output_text: str) -> list[dict]:
    decoder = json.JSONDecoder()
    reports = []
    for match in re.finditer(r"\{", output_text):
        try:
            candidate, _ = decoder.raw_decode(output_text[match.start():])
        except json.JSONDecodeError:
            continue
        if isinstance(candidate, dict) and "summary" in candidate and "cases" in candidate:
            reports.append(candidate)
    return reports


def _latency_ratio(case: dict) -> float | None:
    legacy_latency = case.get("legacy", {}).get("latency_ms", 0)
    shadow_latency = case.get("shadow", {}).get("latency_ms", 0)
    if not legacy_latency or not shadow_latency:
        return None
    return round(float(shadow_latency) / float(legacy_latency), 4)


def _diff_category(diffs: list[str]) -> str:
    if not diffs:
        return "none"
    joined = " ".join(diffs).lower()
    if "status" in joined:
        return "status"
    if "header" in joined or "content-type" in joined:
        return "headers"
    if "latency" in joined:
        return "latency"
    if "body" in joined or "json" in joined or "required field" in joined:
        return "body"
    return "other"


def _case_summaries(report: dict | None) -> list[dict]:
    if not report:
        return []
    summaries = []
    for case in report.get("cases", []):
        summaries.append(
            {
                "name": case.get("name", ""),
                "status": case.get("status", "unknown"),
                "latency_ratio": _latency_ratio(case),
                "diff_category": _diff_category(case.get("diffs", [])),
            }
        )
    return summaries


def parse_go_test_jsonl(path: Path) -> dict:
    if not path.exists():
        return {"status": "skipped", "passed": 0, "failed": 0, "skipped": 0, "latency_warns": 0, "cases": []}
    result = {"status": "skipped", "passed": 0, "failed": 0, "skipped": 0, "latency_warns": 0, "cases": []}
    output_chunks = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                ev = json.loads(line)
            except json.JSONDecodeError:
                continue
            action = ev.get("Action", "")
            if action == "pass":
                result["passed"] += 1
            elif action == "fail":
                result["failed"] += 1
            elif action == "skip":
                result["skipped"] += 1
            out = ev.get("Output", "")
            if "latency" in out.lower():
                result["latency_warns"] += 1
            if out:
                output_chunks.append(_strip_go_test_log_prefix(out))
            if ev.get("status") == "skipped":
                result["status"] = "skipped"
                result["skipped"] += 1

    reports = _extract_json_reports("".join(output_chunks))
    if reports:
        latest_report = reports[-1]
        summary = latest_report.get("summary", {})
        result["passed"] = summary.get("passed", result["passed"])
        result["failed"] = summary.get("failed", result["failed"])
        result["skipped"] = result["skipped"] or 0
        result["latency_warns"] = summary.get("warned", result["latency_warns"])
        result["cases"] = _case_summaries(latest_report)

    if result["failed"] == 0 and result["passed"] > 0:
        result["status"] = "passed"
    elif result["failed"] > 0:
        result["status"] = "failed"
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="generate shadow dry-run report")
    parser.add_argument("--root", required=True, help="project root path")
    parser.add_argument("--output", default=None, help="output JSON path (default: reports/shadow/latest.json)")
    args = parser.parse_args()
    root = Path(args.root).resolve()
    report_dir = root / "reports" / "shadow"
    report_dir.mkdir(parents=True, exist_ok=True)
    output_path = Path(args.output) if args.output else (report_dir / "latest.json")

    health = load_json(report_dir / "health.json")
    chat_parity = parse_go_test_jsonl(report_dir / "chat_parity.jsonl")
    admin_parity = parse_go_test_jsonl(report_dir / "admin_parity.jsonl")
    legacy_usage = load_json(report_dir / "legacy_usage.json")
    inv_data = load_json(report_dir / "inventory.json")

    health_ok = health is not None and health.get("status") == "ok"
    route_count = health.get("route_count", 0) if health else 0
    legacy_gaps = health.get("legacy_gap_count", 0) if health else 0
    deprecated_aliases = health.get("deprecated_compatibility_alias_count", 0) if health else 0
    legacy_usage_events = legacy_usage.get("count", 0) if legacy_usage else 0

    report = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "summary": {
            "health_ok": health_ok,
            "route_count": route_count,
            "legacy_gaps": legacy_gaps,
            "deprecated_aliases": deprecated_aliases,
            "chat_parity": chat_parity["status"],
            "admin_post_parity": admin_parity["status"],
            "legacy_get_usage_events": legacy_usage_events,
        },
        "latency": {
            "chat_warn_count": chat_parity["latency_warns"],
            "admin_warn_count": admin_parity["latency_warns"],
        },
        "details": {
            "chat_passed": chat_parity["passed"],
            "chat_failed": chat_parity["failed"],
            "chat_skipped": chat_parity["skipped"],
            "admin_passed": admin_parity["passed"],
            "admin_failed": admin_parity["failed"],
            "admin_skipped": admin_parity["skipped"],
        },
        "parity_cases": {
            "chat": chat_parity["cases"],
            "admin": admin_parity["cases"],
        },
        "diffs": [],
        "inventory": inv_data or {},
    }

    with open(output_path, "w") as f:
        json.dump(report, f, indent=2)
        f.write("\n")

    print(f"shadow dry-run report written to {output_path}")
    print(json.dumps(report["summary"], indent=2))

    if not health_ok:
        print("WARNING: shadow gateway health check failed", file=sys.stderr)
        return 1
    if chat_parity["status"] == "failed":
        print("WARNING: chat parity had failures", file=sys.stderr)
    if admin_parity["status"] == "failed":
        print("WARNING: admin parity had failures", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
