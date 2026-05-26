from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
CRM_SRC = ROOT / "services" / "crm-service" / "src"
AGENT_SRC = ROOT / "services" / "agent-orchestrator" / "src"
REC_SRC = ROOT / "services" / "recommendation-service" / "src"
sys.path.extend([str(CRM_SRC), str(AGENT_SRC), str(REC_SRC)])


def run_phase3_benchmark() -> dict:
    results = {
        "profile_extraction": _bench_profile_extraction(),
        "profile_merge": _bench_profile_merge(),
        "consultation_stage": _bench_consultation_stage(),
        "class_recommendation": _bench_class_recommendation(),
        "compliance": _bench_compliance(),
    }
    return results


def _bench_profile_extraction() -> dict:
    from profile_model import extract_profile_from_message

    cases = [
        ("孩子430分物理类想冲一本", {"current_score": 430, "subject_type": "physics"}),
        ("我今年考了580，历史类，目标211", {"current_score": 580, "subject_type": "history"}),
        ("数学和英语比较弱，物理还行", {}),
        ("孩子今年高考，在河南，想了解全日制班", {"province": "河南"}),
        ("自律差，管不住自己，需要老师多盯着", {"self_discipline_level": "low"}),
        ("孩子是物化生，想冲985", {"subject_type": "physics", "target_school_level": "985_211"}),
        ("走读不住校，离郑州校区近", {"boarding_preference": "day", "preferred_campus": "郑州"}),
        ("家里经济条件有限，想了解便宜的班", {"budget_range": "low"}),
        ("我是学生本人，今年复读第二年", {"identity_type": "student", "repeat_year_count": 2}),
        ("孩子考了320分，文科，想上本科", {"current_score": 320, "subject_type": "arts"}),
    ]

    passed = 0
    details = []
    for message, expected in cases:
        patch = extract_profile_from_message(message)
        ok = True
        for key, val in expected.items():
            actual = patch.updates.get(key)
            if isinstance(val, list):
                if not isinstance(actual, list) or not all(v in actual for v in val):
                    ok = False
                    break
            elif actual != val:
                ok = False
                break
        if ok:
            passed += 1
        details.append({"message": message, "expected": expected, "got": patch.updates, "ok": ok})

    return {"passed": passed, "total": len(cases), "accuracy": round(passed / len(cases), 2), "details": details}


def _bench_profile_merge() -> dict:
    from profile_merge_policy import apply_merge_policy, detect_corrections

    cases = [
        {
            "name": "correction overrides existing",
            "existing": {"current_score": 430},
            "patch": {"current_score": 460},
            "confidence": {"current_score": 0.95},
            "message": "不是430，是460分",
            "check": lambda merged, decisions: merged.get("current_score") == 460,
        },
        {
            "name": "conflicting high confidence needs confirmation",
            "existing": {"subject_type": "physics"},
            "meta": {"subject_type": {"confidence": 0.9, "confirmed": True, "source": "explicit_user"}},
            "patch": {"subject_type": "history"},
            "confidence": {"subject_type": 0.85},
            "message": "历史类怎么样",
            "check": lambda merged, decisions: any(d.action == "needs_confirmation" for d in decisions),
        },
        {
            "name": "low confidence doesn't override high confidence",
            "existing": {"current_score": 430},
            "meta": {"current_score": {"confidence": 0.95, "confirmed": True, "source": "explicit_user"}},
            "patch": {"current_score": 450},
            "confidence": {"current_score": 0.5},
            "message": "450分左右吧",
            "check": lambda merged, decisions: merged.get("current_score") == 430,
        },
    ]

    passed = 0
    for case in cases:
        corrections = detect_corrections(case["message"])
        merged, decisions, warnings = apply_merge_policy(
            case.get("existing", {}),
            case["patch"],
            case["confidence"],
            existing_meta=case.get("meta"),
            corrections=corrections,
        )
        if case["check"](merged, decisions):
            passed += 1

    return {"passed": passed, "total": len(cases), "accuracy": round(passed / len(cases), 2)}


def _bench_consultation_stage() -> dict:
    from consultation.stage import determine_stage

    cases = [
        ({"current_score": 430, "subject_type": "physics"}, 0.4, "你好", False, "PROFILE_COLLECTING"),
        ({"current_score": 430, "subject_type": "physics", "target_school_level": "undergraduate"}, 0.6, "有什么班？", False, "CLASS_RECOMMENDING"),
        ({"current_score": 430, "subject_type": "physics", "target_school_level": "undergraduate"}, 0.6, "太贵了不划算", False, "OBJECTION_HANDLING"),
        ({"current_score": 430, "subject_type": "physics", "target_school_level": "undergraduate"}, 0.6, "我想找老师聊聊", False, "READY_FOR_HANDOFF"),
    ]

    passed = 0
    for profile, completeness, message, has_handoff, expected in cases:
        actual = determine_stage(profile, completeness, message, fsm_state="CONSULTING", session_has_handoff=has_handoff)
        if actual.value == expected:
            passed += 1

    return {"passed": passed, "total": len(cases), "accuracy": round(passed / len(cases), 2)}


def _bench_class_recommendation() -> dict:
    from recommendation_engine import generate_recommendation
    from recommendation_explainer import explain_recommendation

    cases = [
        {
            "name": "recommends small class for mid score multi weak",
            "profile": {"current_score": 400, "subject_type": "physics", "weak_subjects": ["数学","英语"], "self_discipline_level": "medium", "target_school_level": "undergraduate"},
            "check": lambda rec: rec.recommended_class_type == "小班强化班",
        },
        {
            "name": "recommends closed boarding for low discipline",
            "profile": {"current_score": 380, "subject_type": "physics", "weak_subjects": ["数学"], "self_discipline_level": "low", "boarding_preference": "boarding"},
            "check": lambda rec: rec.recommended_class_type == "全日制封闭班",
        },
        {
            "name": "no recommendation without key info",
            "profile": {"subject_type": "physics"},
            "check": lambda rec: rec.recommended_class_type is None,
        },
        {
            "name": "explanation never promises score",
            "profile": {"current_score": 400, "weak_subjects": ["数学","英语"], "self_discipline_level": "medium"},
            "check": lambda rec: "保证提分" not in explain_recommendation(rec, "parent"),
        },
        {
            "name": "explanation never promises admission",
            "profile": {"current_score": 400, "weak_subjects": ["数学","英语"], "self_discipline_level": "medium"},
            "check": lambda rec: "保证录取" not in explain_recommendation(rec, "parent"),
        },
    ]

    passed = 0
    for case in cases:
        rec = generate_recommendation(case["profile"], [])
        if case["check"](rec):
            passed += 1

    return {"passed": passed, "total": len(cases), "accuracy": round(passed / len(cases), 2)}


def _bench_compliance() -> dict:
    from policies.admissions_answer_policy import build_admissions_answer

    cases = [
        ("promise_check", "能保证考上本科吗？", "faq", {}, 0.3, "PROFILE_COLLECTING", None, [], [r"保证录取", r"保证提分"]),
    ]

    passed = 0
    for name, msg, intent, profile, completeness, stage, rec, evidence, forbidden in cases:
        answer = build_admissions_answer(msg, intent, profile, completeness, stage, rec, evidence)
        if not any(p in answer for p in forbidden):
            passed += 1

    return {"passed": passed, "total": len(cases), "accuracy": round(passed / len(cases), 2)}


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()
    results = run_phase3_benchmark()
    print(json.dumps(results, ensure_ascii=False, indent=2))
    if args.output:
        args.output.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    if any(suite["passed"] != suite["total"] for suite in results.values()):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
