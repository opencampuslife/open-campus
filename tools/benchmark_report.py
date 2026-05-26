from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args()

    report_path = args.root / "data" / "reports" / "benchmark_report.json"
    if not report_path.exists():
        print("No benchmark report found. Run 'make benchmark' first.", file=sys.stderr)
        sys.exit(1)

    report = json.loads(report_path.read_text(encoding="utf-8"))
    cases_path = args.root / "tests" / "benchmark_cases" / "admissions_qa.yaml"
    cases_yaml = _load_yaml_simple(cases_path.read_text(encoding="utf-8"))

    case_map: dict[str, dict[str, Any]] = {}
    for case in cases_yaml.get("cases", []):
        case_map[case["id"]] = case

    failures: list[dict[str, Any]] = []
    for item in report.get("cases", []):
        if item["passed"]:
            continue
        cid = item["id"]
        orig = case_map.get(cid, {})

        failure_types = []
        for check in item["checks"]:
            if not check["passed"]:
                failure_types.append(_classify_failure(check["name"]))

        if not failure_types:
            failure_types.append("all_checks_failed")

        failures.append({
            "id": cid,
            "category": item.get("category", "unknown"),
            "message": orig.get("message", ""),
            "expected_intent": orig.get("expected_intent", ""),
            "actual_intent": item.get("intent", ""),
            "expected_doc_ids": orig.get("expected_doc_ids", []),
            "failure_types": failure_types,
            "answer_preview": item.get("answer", "")[:120],
        })

    print(f"Benchmark: {report['total']} total, {report['passed']} passed, {len(failures)} failed\n")

    by_type: dict[str, list[dict[str, Any]]] = {}
    for f in failures:
        for ft in f["failure_types"]:
            if ft not in by_type:
                by_type[ft] = []
            by_type[ft].append(f)

    print("Failure Type Distribution:")
    for ft in sorted(by_type):
        cases = by_type[ft]
        print(f"\n  [{ft}] ({len(cases)} cases)")
        for f in cases[:3]:
            print(f"    - {f['id']}")
            print(f"      msg: {f['message'][:80]}")
            print(f"      expected intent: {f['expected_intent']}, actual: {f['actual_intent']}")
            print(f"      answer: {f['answer_preview'][:100]}")

        if len(cases) > 3:
            remaining = [f["id"] for f in cases[3:]]
            print(f"    ... and {len(remaining)} more: {', '.join(remaining)}")


def _classify_failure(check_name: str) -> str:
    if check_name.startswith("intent"):
        return "intent_mismatch"
    if check_name.startswith("denied_doc"):
        return "permission_block"
    if "cite" in check_name or "citation" in check_name or "来源" in check_name:
        return "citation_missing"
    if "empty" in check_name or "fallback" in check_name:
        return "no_answer_fallback"
    if "mention" in check_name or "suggest" in check_name:
        return "content_missing"
    if "no L3" in check_name or "no internal" in check_name or "no admin" in check_name or "no L4" in check_name:
        return "permission_safe"
    if "promise" in check_name or "commitment" in check_name or "guarantee" in check_name:
        return "compliance_safe"
    if "handoff" in check_name:
        return "handoff_missing"
    if "recommend" in check_name or "cite" in check_name or "management" in check_name:
        return "content_quality"
    if "answer is non-empty" in check_name:
        return "empty_answer"
    if "no internal pricing" in check_name or "do not reveal" in check_name:
        return "compliance_safe"
    if "dormitory" in check_name or "campus" in check_name:
        return "content_quality"
    if "enrollment" in check_name or "suggestion" in check_name:
        return "content_quality"
    return "other"


def _load_yaml_simple(text: str) -> dict[str, Any]:
    import os, sys
    sys.path.insert(0, str(ROOT / "services" / "knowledge-service" / "src"))
    from simple_yaml import loads
    return loads(text)


if __name__ == "__main__":
    main()
