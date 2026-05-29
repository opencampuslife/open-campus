#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURES_DIR = REPO_ROOT / "ts-migration" / "fixtures"


@dataclass
class FixtureCase:
    input: Any
    output: Any


def _serialize(obj: Any) -> Any:
    if hasattr(obj, "__dict__"):
        return {k: _serialize(v) for k, v in obj.__dict__.items() if not k.startswith("_")}
    if isinstance(obj, list):
        return [_serialize(item) for item in obj]
    if isinstance(obj, dict):
        return {k: _serialize(v) for k, v in obj.items()}
    if isinstance(obj, (Path,)):
        return str(obj)
    return obj


def generate_markdown_normalizer() -> list[dict]:
    sys.path.insert(0, str(REPO_ROOT / "services" / "source-ingestion-service" / "src"))
    from markdown_normalizer import normalize_markdown

    cases = [
        {"input": "Hello\nWorld", "desc": "simple_two_lines"},
        {"input": "Hello\r\nWorld", "desc": "windows_line_endings"},
        {"input": "Hello\rWorld", "desc": "old_mac_line_endings"},
        {"input": "\ufeff# Title\nContent", "desc": "bom_removal"},
        {"input": "#Heading\nContent", "desc": "missing_space_after_hash"},
        {"input": "Line1  \nLine2  \n\n\n\nLine3", "desc": "trailing_spaces_and_collapse_newlines"},
        {"input": "##  Already Spaced", "desc": "already_correct_heading"},
        {"input": "Text with  trailing spaces   \n\n\n\n\nMore text", "desc": "extreme_newline_collapse"},
        {"input": "", "desc": "empty_string"},
        {"input": "No newline at end", "desc": "no_final_newline"},
    ]
    return [{"input": c["input"], "output": _serialize(normalize_markdown(c["input"]))} for c in cases]


def generate_citation_builder() -> list[dict]:
    sys.path.insert(0, str(REPO_ROOT / "services" / "rag-service" / "src"))
    from citation_builder import build_citations

    cases: list[dict] = [
        {
            "desc": "normal_multiple_docs",
            "input": [
                {"doc_id": "d1", "title": "Title 1", "source_uri": "https://a.com/1", "chunk_id": "c1"},
                {"doc_id": "d2", "title": "Title 2", "source_uri": "https://a.com/2", "chunk_id": "c2"},
                {"doc_id": "d1", "title": "Title 1", "source_uri": "https://a.com/1", "chunk_id": "c3"},
            ],
        },
        {
            "desc": "single_doc",
            "input": [
                {"doc_id": "d1", "title": "Only Doc", "source_uri": "https://x.com", "chunk_id": "c1"},
                {"doc_id": "d1", "title": "Only Doc", "source_uri": "https://x.com", "chunk_id": "c2"},
            ],
        },
        {"desc": "empty_list", "input": []},
        {
            "desc": "all_unique",
            "input": [
                {"doc_id": "a", "title": "A", "source_uri": "u1", "chunk_id": "c1"},
                {"doc_id": "b", "title": "B", "source_uri": "u2", "chunk_id": "c2"},
                {"doc_id": "c", "title": "C", "source_uri": "u3", "chunk_id": "c3"},
            ],
        },
        {
            "desc": "all_duplicates",
            "input": [
                {"doc_id": "x", "title": "X", "source_uri": "u", "chunk_id": "c1"},
                {"doc_id": "x", "title": "X", "source_uri": "u", "chunk_id": "c2"},
                {"doc_id": "x", "title": "X", "source_uri": "u", "chunk_id": "c3"},
            ],
        },
    ]
    return [{"input": c["input"], "output": _serialize(build_citations(c["input"]))} for c in cases]


def generate_recommendation_model() -> list[dict]:
    sys.path.insert(0, str(REPO_ROOT / "services" / "recommendation-service" / "src"))
    from recommendation_model import ClassRecommendation, RecommendationInput

    cases = [
        {
            "desc": "default_values",
            "input": {"profile": {}, "allowed_evidence": [], "campus": None, "role": "parent", "consultation_stage": "NEEDS_ASSESSMENT"},
        },
        {
            "desc": "full_small_class",
            "input": {
                "profile": {"current_score": 370, "weak_subjects": ["math", "english"], "self_discipline_level": "low", "target_school_level": "本科"},
                "allowed_evidence": [{"chunk_id": "e1", "content": "小班强化课程"}],
            },
        },
        {
            "desc": "boarder_scenario",
            "input": {
                "profile": {"current_score": 320, "self_discipline_level": "low", "boarding_preference": "boarding"},
                "allowed_evidence": [{"chunk_id": "e2", "content": "全日制封闭式管理"}],
            },
        },
        {
            "desc": "single_subject",
            "input": {
                "profile": {"current_score": 400, "weak_subjects": ["physics"], "self_discipline_level": "high"},
                "allowed_evidence": [],
            },
        },
        {
            "desc": "sprint_class",
            "input": {
                "profile": {"current_score": 520, "target_score": 550},
                "allowed_evidence": [{"chunk_id": "e3", "content": "高考冲刺应试技巧"}],
            },
        },
        {
            "desc": "no_match_fallback",
            "input": {
                "profile": {"current_score": 250},
                "allowed_evidence": [],
            },
        },
    ]
    results = []
    for c in cases:
        inp = RecommendationInput(**c["input"])  # type: ignore[arg-type]
        from class_rules import recommend
        rec = recommend(inp)
        from recommendation_engine import generate_recommendation
        rec = generate_recommendation(**c["input"])  # type: ignore[arg-type]
        results.append({"input": c["input"], "output": _serialize(rec)})
    return results


def generate_compliance_checker() -> list[dict]:
    sys.path.insert(0, str(REPO_ROOT / "services" / "compliance-service" / "src"))
    from checker import evaluate_answer
    from pathlib import Path

    cases = [
        {"desc": "normal_text", "answer": "根据你的分数和目标，建议选择冲刺班。", "scope": {"role": "visitor"}},
        {"desc": "blocked_phrase_guarantee", "answer": "我们保证录取，请放心。", "scope": {"role": "visitor"}},
        {"desc": "absolute_claim_100", "answer": "这个课程100%能提分。", "scope": {"role": "visitor"}},
        {"desc": "internal_reference_leak", "answer": "这是内部参考的话术，对外不要说。", "scope": {"role": "visitor"}},
        {"desc": "privacy_phone", "answer": "请联系13812345678获取优惠。", "scope": {"role": "visitor"}},
        {"desc": "multi_violation", "answer": "保证录取，内部规则是100%成功。联系13900001111。", "scope": {"role": "visitor"}},
        {"desc": "empty_answer", "answer": "", "scope": {"role": "visitor"}},
        {"desc": "mixed_text", "answer": "Hello 保证录取 this is 100% guarantee", "scope": {"role": "visitor"}},
        {"desc": "internal_role_sees_pricing", "answer": "优惠底价是5000元。", "scope": {"role": "sales"}},
        {"desc": "student_role_blocks_pricing", "answer": "优惠底价是5000元。", "scope": {"role": "student"}},
    ]
    project_root = REPO_ROOT
    return [
        {"input": {"answer": c["answer"], "scope": c["scope"]}, "output": _serialize(evaluate_answer(c["answer"], c["scope"], project_root))}
        for c in cases
    ]


def generate_metadata_filter() -> list[dict]:
    sys.path.insert(0, str(REPO_ROOT / "services" / "permission-service" / "src"))
    from access_checker import can_access

    sys.path.insert(0, str(REPO_ROOT / "services" / "rag-service" / "src"))
    from metadata_filter import filter_allowed

    scope = {
        "role": "visitor",
        "campus": "all",
        "auth_level": "public",
        "allowed_visibility": ["public"],
        "allowed_data_levels": ["public"],
        "allowed_roles": ["visitor"],
        "forbidden_tags": ["internal_pricing", "sales_script"],
    }
    cases = [
        {
            "desc": "all_allowed",
            "chunks": [
                {"chunk_id": "c1", "doc_id": "d1", "review_status": "approved", "visibility": "public",
                 "data_level": "public", "allowed_roles": ["visitor"], "campus_scope": ["all"], "business_tags": [],
                 "effective_date": "2020-01-01", "expiry_date": "9999-12-31"},
            ],
        },
        {
            "desc": "forbidden_tag",
            "chunks": [
                {"chunk_id": "c1", "doc_id": "d1", "review_status": "approved", "visibility": "public",
                 "data_level": "public", "allowed_roles": ["visitor"], "campus_scope": ["all"], "business_tags": ["internal_pricing"],
                 "effective_date": "2020-01-01", "expiry_date": "9999-12-31"},
            ],
        },
        {
            "desc": "mixed_allowed_and_denied",
            "chunks": [
                {"chunk_id": "c1", "doc_id": "d1", "review_status": "approved", "visibility": "public",
                 "data_level": "public", "allowed_roles": ["visitor"], "campus_scope": ["all"], "business_tags": [],
                 "effective_date": "2020-01-01", "expiry_date": "9999-12-31"},
                {"chunk_id": "c2", "doc_id": "d2", "review_status": "approved", "visibility": "internal",
                 "data_level": "internal", "allowed_roles": ["sales"], "campus_scope": ["all"], "business_tags": [],
                 "effective_date": "2020-01-01", "expiry_date": "9999-12-31"},
                {"chunk_id": "c3", "doc_id": "d3", "review_status": "approved", "visibility": "public",
                 "data_level": "public", "allowed_roles": ["visitor"], "campus_scope": ["all"], "business_tags": ["sales_script"],
                 "effective_date": "2020-01-01", "expiry_date": "9999-12-31"},
            ],
        },
        {
            "desc": "not_approved",
            "chunks": [
                {"chunk_id": "c1", "doc_id": "d1", "review_status": "pending", "visibility": "public",
                 "data_level": "public", "allowed_roles": ["visitor"], "campus_scope": ["all"], "business_tags": [],
                 "effective_date": "2020-01-01", "expiry_date": "9999-12-31"},
            ],
        },
        {"desc": "empty_chunks", "chunks": []},
    ]
    return [{"input": {"chunks": c["chunks"], "scope": scope}, "output": _serialize(filter_allowed(c["chunks"], scope))} for c in cases]


def generate_permission_service() -> list[dict]:
    sys.path.insert(0, str(REPO_ROOT / "services" / "permission-service" / "src"))
    import scope_builder
    import access_checker

    project_root = REPO_ROOT

    # scope_builder cases
    scope_cases = [
        {"desc": "visitor_identity", "identity": {"user_id": "u1", "role": "visitor", "campus": "all", "auth_level": "anonymous"}},
        {"desc": "parent_identity", "identity": {"user_id": "u2", "role": "parent", "campus": "bj-campus", "auth_level": "authenticated"}},
        {"desc": "sales_identity", "identity": {"user_id": "u3", "role": "sales", "campus": "sh-campus", "auth_level": "authenticated"}},
        {"desc": "admin_identity", "identity": {"user_id": "u4", "role": "super_admin", "campus": "all", "auth_level": "admin"}},
        {"desc": "student_identity", "identity": {"user_id": "u5", "role": "student", "campus": "gz-campus", "auth_level": "authenticated"}},
    ]
    scope_fixtures = []
    for c in scope_cases:
        try:
            result = scope_builder.build_scope(c["identity"], project_root)
            scope_fixtures.append({"input": c["identity"], "output": _serialize(result)})
        except Exception as e:
            scope_fixtures.append({"input": c["identity"], "output": {"error": str(e)}})

    # access_checker cases
    parent_scope = scope_builder.build_scope({"user_id": "u2", "role": "parent", "campus": "all", "auth_level": "authenticated"}, project_root)
    access_cases = [
        {
            "desc": "allowed_public_item",
            "item": {"review_status": "approved", "visibility": "public", "data_level": "public",
                     "allowed_roles": ["visitor", "student", "parent", "customer"],
                     "campus_scope": ["all"], "business_tags": [],
                     "effective_date": "2020-01-01", "expiry_date": "9999-12-31"},
            "scope": parent_scope,
        },
        {
            "desc": "visibility_denied",
            "item": {"review_status": "approved", "visibility": "internal", "data_level": "public",
                     "allowed_roles": ["visitor", "student", "parent", "customer"],
                     "campus_scope": ["all"], "business_tags": [],
                     "effective_date": "2020-01-01", "expiry_date": "9999-12-31"},
            "scope": parent_scope,
        },
        {
            "desc": "campus_denied",
            "item": {"review_status": "approved", "visibility": "public", "data_level": "public",
                     "allowed_roles": ["visitor", "student", "parent", "customer"],
                     "campus_scope": ["bj-campus"], "business_tags": [],
                     "effective_date": "2020-01-01", "expiry_date": "9999-12-31"},
            "scope": parent_scope,
        },
        {
            "desc": "forbidden_tag",
            "item": {"review_status": "approved", "visibility": "public", "data_level": "public",
                     "allowed_roles": ["visitor", "student", "parent", "customer"],
                     "campus_scope": ["all"], "business_tags": ["internal_pricing"],
                     "effective_date": "2020-01-01", "expiry_date": "9999-12-31"},
            "scope": parent_scope,
        },
        {
            "desc": "not_yet_effective",
            "item": {"review_status": "approved", "visibility": "public", "data_level": "public",
                     "allowed_roles": ["visitor", "student", "parent", "customer"],
                     "campus_scope": ["all"], "business_tags": [],
                     "effective_date": "2099-01-01", "expiry_date": "9999-12-31"},
            "scope": parent_scope,
        },
    ]
    access_fixtures = []
    for c in access_cases:
        ok, reason = access_checker.can_access(c["item"], c["scope"])
        access_fixtures.append({"input": {"item": c["item"], "scope_role": parent_scope.get("role")},
                                "output": {"ok": ok, "reason": reason}})

    return scope_fixtures + access_fixtures


GENERATORS = {
    "markdown_normalizer": generate_markdown_normalizer,
    "citation_builder": generate_citation_builder,
    "recommendation_model": generate_recommendation_model,
    "compliance_checker": generate_compliance_checker,
    "metadata_filter": generate_metadata_filter,
    "permission_service": generate_permission_service,
}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=REPO_ROOT)
    parser.add_argument("--module", type=str, default=None, help="Generate only one module")
    args = parser.parse_args()

    FIXTURES_DIR.mkdir(parents=True, exist_ok=True)

    modules = [args.module] if args.module else list(GENERATORS.keys())

    for name in modules:
        if name not in GENERATORS:
            print(f"Unknown module: {name}")
            continue
        print(f"Generating fixtures for: {name}")
        try:
            cases = GENERATORS[name]()
            out_path = FIXTURES_DIR / f"{name}.json"
            out_path.write_text(json.dumps(cases, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
            print(f"  Wrote {len(cases)} cases → {out_path}")
        except Exception as e:
            print(f"  ERROR: {e}")
            import traceback
            traceback.print_exc()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
