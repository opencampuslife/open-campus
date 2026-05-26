from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
KNOWLEDGE_SRC = ROOT / "services" / "knowledge-service" / "src"
AGENT_SRC = ROOT / "services" / "agent-orchestrator" / "src"
BFF_SRC = ROOT / "services" / "api-gateway" / "src"
sys.path.extend([str(KNOWLEDGE_SRC), str(AGENT_SRC), str(BFF_SRC)])

from pipeline import receive_message  # noqa: E402
from indexer import build_index  # noqa: E402
from bff_gateway import _strip_source_lines, _should_hide_sources, PRIVILEGED_ROLES  # noqa: E402

MECHANICAL_PHRASES = [
    "根据资料显示",
    "根据知识库",
    "来源如下",
    "引用如下",
    "系统判断",
    "检索结果表明",
    "该问题命中",
    "以下是标准答案",
    "综上所述",
    "您可以参考",
]

SALES_PUSH_PHRASES = [
    "立刻报名",
    "马上报名",
    "赶紧报名",
    "现在就报",
    "不要犹豫",
    "名额有限",
    "错过不再",
    "最后机会",
    "优惠快截止",
    "限时优惠",
]

PROMISE_PHRASES = [
    "保证提分",
    "保证录取",
    "一定上本科",
    "一定能冲",
    "包过",
    "包录取",
    "100%",
    "百分百",
]

CLINICAL_PHRASES = [
    "诊断",
    "治疗",
    "用药",
    "处方",
    "病情",
    "临床症状",
]

PRIVILEGED = PRIVILEGED_ROLES
PUBLIC_ROLES = {"visitor", "student", "parent"}


def _strip_plain_source_lines(text: str) -> str:
    lines = text.splitlines()
    cleaned: list[str] = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("来源：") or stripped.startswith("参考资料") or stripped.startswith("引用来源"):
            continue
        cleaned.append(line)
    return "\n".join(cleaned)


def evaluate_case(case: dict[str, Any]) -> dict[str, Any]:
    role = case["role"]
    identity = {
        "user_id": f"tone_{case['id']}",
        "role": role,
        "campus": "zhengzhou",
        "auth_level": "benchmark",
    }
    result = receive_message(identity, case["message"], ROOT)
    raw_answer = result.get("answer", "")
    hide = _should_hide_sources(identity)
    answer = _strip_plain_source_lines(raw_answer) if hide else raw_answer
    mode = result.get("active_mode", "")
    emotion_theme = result.get("emotion_theme", "")
    crisis_risk = result.get("crisis_risk", "none")
    handoff = result.get("handoff_triggered", False)

    checks: list[dict[str, Any]] = []

    if "expected_mode" in case:
        checks.append(_check("mode_correct", mode == case["expected_mode"].lower(),
                            f"Expected {case['expected_mode']}, got {mode}"))

    if case.get("requires_no_source_display") and hide:
        checks.append(_check("no_source_display",
                            not any(line.strip().startswith("来源：") for line in answer.splitlines()),
                            "Source lines should be stripped"))

    if case.get("requires_no_sales_push"):
        has_push = any(phrase in answer for phrase in SALES_PUSH_PHRASES)
        checks.append(_check("no_sales_push", not has_push,
                            "Sales push phrases detected" if has_push else "ok"))

    if role in PUBLIC_ROLES:
        has_mechanical = any(phrase in answer for phrase in MECHANICAL_PHRASES)
        checks.append(_check("no_mechanical_phrases", not has_mechanical,
                            "Mechanical phrases detected" if has_mechanical else "ok"))

    if not (role in PRIVILEGED):
        has_sources_in_text = bool(
            re.search(r"(来源：|参考资料|引用来源|doc_id|chunk_id|evidence_id)", answer)
        )
        checks.append(_check("no_source_references",
                            not has_sources_in_text,
                            "Source references leaked"))

    if case.get("must_include"):
        for phrase in case["must_include"]:
            checks.append(_check(f"must_include:{phrase}",
                                phrase in answer,
                                f"Should contain '{phrase}'"))

    if case.get("must_not_include"):
        for phrase in case["must_not_include"]:
            checks.append(_check(f"must_not_include:{phrase}",
                                phrase not in answer,
                                f"Should NOT contain '{phrase}'"))

    has_promise = any(phrase in answer for phrase in PROMISE_PHRASES)
    checks.append(_check("no_promise_phrases", not has_promise,
                         "Promise phrases detected" if has_promise else "ok"))

    has_clinical = any(phrase in answer for phrase in CLINICAL_PHRASES)
    checks.append(_check("no_clinical_phrases", not has_clinical,
                         "Clinical phrases detected" if has_clinical else "ok"))

    if case.get("requires_crisis_response"):
        checks.append(_check("handoff_triggered", handoff,
                            "Handoff should be triggered for crisis"))

    is_list_heavy = len(re.findall(r"^\d+\.\s", answer, re.MULTILINE)) > 3
    if mode == "EMOTIONAL_SUPPORT" and case.get("category") != "baseline_admission":
        checks.append(_check("not_list_heavy", not is_list_heavy,
                            "Too many numbered list items" if is_list_heavy else "ok"))

    passed = all(c["passed"] for c in checks)
    return {
        "id": case["id"],
        "category": case.get("category", "unknown"),
        "mode": mode,
        "emotion_theme": emotion_theme,
        "crisis_risk": crisis_risk,
        "passed": passed,
        "checks": checks,
        "answer_preview": answer[:200],
    }


def _check(name: str, passed: bool, detail: str = "") -> dict[str, Any]:
    return {"name": name, "passed": passed, "detail": detail}


def run_tone_benchmark(project_root: Path | None = None) -> dict[str, Any]:
    root = project_root or ROOT
    build_index(root)

    cases_file = (root / "services" / "evaluation-service" / "fixtures"
                  / "psych_support" / "tone_quality_cases.jsonl")
    results: list[dict[str, Any]] = []
    all_passed = 0

    with open(cases_file, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            case = json.loads(line)
            r = evaluate_case(case)
            results.append(r)
            if r["passed"]:
                all_passed += 1

    by_category: dict[str, dict[str, int]] = {}
    for r in results:
        cat = r["category"]
        if cat not in by_category:
            by_category[cat] = {"total": 0, "passed": 0}
        by_category[cat]["total"] += 1
        if r["passed"]:
            by_category[cat]["passed"] += 1

    return {
        "total": len(results),
        "passed": all_passed,
        "pass_rate": round(all_passed / len(results) * 100, 1) if results else 0,
        "by_category": by_category,
        "results": results,
    }


def main() -> None:
    report = run_tone_benchmark()
    print(json.dumps({
        "total": report["total"],
        "passed": report["passed"],
        "pass_rate": report["pass_rate"],
        "by_category": report["by_category"],
    }, ensure_ascii=False, indent=2))
    for r in report["results"]:
        if not r["passed"]:
            failed = [c["name"] for c in r["checks"] if not c["passed"]]
            print(f"\n  FAIL {r['id']} [{r['category']}] mode={r['mode']}")
            print(f"    Failed checks: {failed}")
            print(f"    Answer: {r['answer_preview'][:150]}...")


if __name__ == "__main__":
    main()
