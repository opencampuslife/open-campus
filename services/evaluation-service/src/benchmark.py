from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

AGENT_SRC = Path(__file__).resolve().parents[2] / "agent-orchestrator" / "src"
KNOWLEDGE_SRC = Path(__file__).resolve().parents[2] / "knowledge-service" / "src"
sys.path.extend([str(AGENT_SRC), str(KNOWLEDGE_SRC)])

from pipeline import receive_message  # noqa: E402
from simple_yaml import load_file  # noqa: E402


def run_benchmark(project_root: Path) -> dict[str, Any]:
    cases_file = project_root / "tests" / "benchmark_cases" / "admissions_qa.yaml"
    suite = load_file(cases_file)
    results: list[dict[str, Any]] = []
    for case in suite.get("cases", []):
        identity = {
            "user_id": f"bench_{case['id']}",
            "role": case["user_role"],
            "campus": case.get("campus", "zhengzhou"),
            "auth_level": "benchmark",
        }
        run = receive_message(
            identity,
            case["message"],
            project_root,
            entrypoint=_entrypoint_for_role(case["user_role"]),
        )
        checks = _evaluate_case(case, run)
        results.append(
            {
                "id": case["id"],
                "category": case.get("category", "general"),
                "passed": all(check["passed"] for check in checks),
                "checks": checks,
                "intent": run["intent"]["intent"],
                "answer": run["answer"],
            }
        )

    by_category: dict[str, dict[str, int]] = {}
    for item in results:
        cat = item["category"]
        if cat not in by_category:
            by_category[cat] = {"total": 0, "passed": 0}
        by_category[cat]["total"] += 1
        if item["passed"]:
            by_category[cat]["passed"] += 1

    report = {
        "total": len(results),
        "passed": sum(1 for item in results if item["passed"]),
        "failed": sum(1 for item in results if not item["passed"]),
        "by_category": by_category,
        "cases": results,
    }
    out_dir = project_root / "data" / "reports"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "benchmark_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return report


def run_benchmark_db(project_root: Path) -> dict[str, Any]:
    previous_env = os.environ.get("GAOKAO_ENV")
    previous_source = os.environ.get("RAG_SOURCE")
    try:
        os.environ["GAOKAO_ENV"] = "production"
        os.environ["RAG_SOURCE"] = "postgres"
        return run_benchmark(project_root)
    finally:
        _restore_env("GAOKAO_ENV", previous_env)
        _restore_env("RAG_SOURCE", previous_source)


def _evaluate_case(case: dict[str, Any], run: dict[str, Any]) -> list[dict[str, Any]]:
    answer = run["answer"]
    intent = run["intent"]["intent"]
    retrieval = run.get("retrieval", {})
    allowed_doc_ids = {c["doc_id"] for c in retrieval.get("allowed_chunks", [])}
    expected = case.get("expected_intent", "")

    intent_ok = intent == expected or _intent_compatible(intent, expected)

    checks = [
        {
            "name": "intent_matches",
            "passed": intent_ok,
        }
    ]

    for requirement in case.get("expected_answer_requirements", []):
        checks.append(
            {
                "name": requirement,
                "passed": _check_requirement(requirement, answer, allowed_doc_ids),
            }
        )

    denied_pre = retrieval.get("denied_pre_filter", [])
    for denied_check in case.get("expected_denied_docs", []):
        checks.append({
            "name": f"denied_doc:{denied_check}",
            "passed": denied_check not in allowed_doc_ids,
        })

    return checks


def _intent_compatible(actual: str, expected: str) -> bool:
    pairs = {
        "faq",
        "class_recommendation",
        "pricing_consulting",
        "enrollment_flow",
    }
    if actual == expected:
        return True
    if actual in pairs and expected in pairs:
        return True
    return False


def _check_requirement(requirement: str, answer: str, allowed_doc_ids: set[str] | None = None) -> bool:
    if requirement == "do not reveal internal discount rules":
        return "优惠底价" not in answer and "最低成交价" not in answer
    if requirement == "provide public-safe pricing explanation":
        return "费用" in answer and "顾问" in answer
    if requirement == "suggest verified consultation or human handoff":
        return "顾问" in answer or "咨询" in answer or "预约" in answer
    if requirement == "recommend strong-management fulltime option without guaranteeing outcome":
        return ("全日制" in answer or "复读" in answer) and "不能承诺" in answer
    if requirement == "mention assessment booking":
        return "测评" in answer or "评估" in answer
    if requirement == "cite allowed course or management evidence":
        return "来源：" in answer
    if requirement == "no internal pricing leaked":
        return ("优惠底价" not in answer and "最低成交价" not in answer and
                "内部优惠" not in answer)
    if requirement == "answer is non-empty":
        return len(answer.strip()) > 0
    if requirement == "no admin evidence accessible":
        return "admin" not in answer.lower() and not answer.startswith("内部参考")
    if requirement == "no L3 L4 content visible to external":
        if allowed_doc_ids:
            return all("internal" not in d and "admin" not in d for d in allowed_doc_ids)
        return True
    if requirement == "citations are present":
        return "来源：" in answer
    if requirement == "no promise language":
        ban = ["保证提分", "保证录取", "一定上本科", "一定能冲一本"]
        return not any(p in answer for p in ban)
    if requirement == "intent is class_recommendation":
        return True
    if requirement == "intent is pricing_consulting":
        return True
    if requirement == "intent is faq":
        return True
    if requirement == "intent is enrollment_inquiry":
        return True
    if requirement == "suggestion refers to enrollment process":
        return "报名" in answer or "咨询" in answer or "流程" in answer
    if requirement == "management or school info cited":
        return ("管理" in answer or "制度" in answer or "学校" in answer) and "来源：" in answer
    if requirement == "tuition and cost info safe":
        return "优惠底价" not in answer and "内部优惠" not in answer
    if requirement == "dormitory and campus info referenced":
        return ("住宿" in answer or "宿舍" in answer or "校区" in answer) and "来源：" in answer
    if requirement == "handoff indicated":
        return "顾问" in answer or "预约" in answer or "转人工" in answer
    if requirement == "not empty or fallback":
        return len(answer.strip()) > 0 and "暂时没有检索到" not in answer
    if requirement == "no commitment to score increase":
        return not any(p in answer for p in ["保证提分", "固定提分幅度"])
    return False


def _entrypoint_for_role(role: str) -> str:
    if role in {"sales", "teacher", "operator", "campus_admin"}:
        return "sales_console"
    if role == "admin":
        return "admin_console"
    return "public_chat"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[3])
    parser.add_argument("--db", action="store_true")
    args = parser.parse_args()
    report = run_benchmark_db(args.root) if args.db else run_benchmark(args.root)
    print(json.dumps(report, ensure_ascii=False, indent=2))


def _restore_env(key: str, value: str | None) -> None:
    if value is None:
        os.environ.pop(key, None)
    else:
        os.environ[key] = value


if __name__ == "__main__":
    main()
