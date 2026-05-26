from __future__ import annotations

from typing import Any
from recommendation_model import ClassRecommendation, RecommendationInput


def recommend(input: RecommendationInput) -> ClassRecommendation:
    profile = input.profile
    all_rules = [_small_class_rule, _closed_boarding_rule, _single_subject_rule, _sprint_class_rule]
    
    for rule in all_rules:
        result = rule(profile, input.allowed_evidence)
        if result:
            return result
    
    return _no_recommendation(profile)


def _small_class_rule(profile: dict, evidence: list[dict]) -> ClassRecommendation | None:
    score = profile.get("current_score", 0)
    weak = profile.get("weak_subjects", [])
    discipline = profile.get("self_discipline_level", "")
    target = profile.get("target_school_level", "")
    
    if score >= 350 and len(weak) >= 2 and discipline in ("medium", "low"):
        evidence_ids = [e.get("chunk_id","") for e in evidence if any(kw in str(e.get("content","")).lower() for kw in ["小班","强化","分层","管理"])][:3]
        return ClassRecommendation(
            recommended_class_type="小班强化班",
            confidence="medium",
            reasons=[
                f"当前分数{score}分，目标为{target or '本科'}，存在提升空间",
                f"检测到{len(weak)}个薄弱科目：{'、'.join(weak)}",
                f"自律水平为{'中等偏低' if discipline=='low' else '中等'}，需要稳定管理与反馈"
            ],
            not_suitable_if=["学生自律性极强且只需单科补弱", "预算明显低于该班型区间"],
            missing_info=_missing_from_profile(profile, ["budget_range", "preferred_campus", "boarding_preference"]),
            next_questions=["孩子更倾向走读还是住宿？", "预算方面有什么考虑？"],
            risk_warnings=["不承诺提分幅度，最终录取以高考实际表现为准"],
            evidence_ids=evidence_ids,
        )
    return None


def _closed_boarding_rule(profile: dict, evidence: list[dict]) -> ClassRecommendation | None:
    discipline = profile.get("self_discipline_level", "")
    concerns = profile.get("parent_concerns", [])
    boarding = profile.get("boarding_preference", "")
    score = profile.get("current_score", 0)
    
    conditions = discipline == "low" or "管理" in str(concerns) or boarding == "boarding"
    if conditions and score >= 300:
        evidence_ids = [e.get("chunk_id","") for e in evidence if any(kw in str(e.get("content","")).lower() for kw in ["封闭","全日制","住宿","管理"])][:3]
        return ClassRecommendation(
            recommended_class_type="全日制封闭班",
            confidence="medium",
            reasons=[
                "自律性较低或家长关注管理",
                "需要封闭式学习环境以确保学习纪律",
                "适合需要全天候管理支持的学生"
            ],
            not_suitable_if=["学生不住校且家庭可提供稳定监督", "走读需求明确"],
            missing_info=_missing_from_profile(profile, ["preferred_campus", "budget_range"]),
            next_questions=["是否接受住宿式管理？", "离哪个校区比较方便？"],
            risk_warnings=["封闭式环境适应期是个体化的，建议试听确认"],
            evidence_ids=evidence_ids,
        )
    return None


def _single_subject_rule(profile: dict, evidence: list[dict]) -> ClassRecommendation | None:
    weak = profile.get("weak_subjects", [])
    strong = profile.get("strong_subjects", [])
    discipline = profile.get("self_discipline_level", "")
    score = profile.get("current_score", 0)
    
    if len(weak) == 1 and discipline in ("high", "medium") and score >= 380:
        evidence_ids = [e.get("chunk_id","") for e in evidence if any(kw in str(e.get("content","")).lower() for kw in ["单科","专项","突破","一对一"])][:3]
        return ClassRecommendation(
            recommended_class_type="单科突破班",
            confidence="medium",
            reasons=[
                f"只有一个主要薄弱科目：{weak[0]}",
                f"自律水平{'较高' if discipline=='high' else '中等'}，可独立完成大部分学习",
                "总分相对稳定，建议集中突破薄弱科目",
            ],
            not_suitable_if=["多科薄弱（≥2科）", "自律性明显偏低"],
            missing_info=_missing_from_profile(profile, ["target_school_level"]),
            next_questions=[f"对于{weak[0]}，目前主要问题是基础不牢还是解题技巧？"],
            risk_warnings=["单科突破通常需要配合整体学习节奏，建议先做学情诊断"],
            evidence_ids=evidence_ids,
        )
    return None


def _sprint_class_rule(profile: dict, evidence: list[dict]) -> ClassRecommendation | None:
    score = profile.get("current_score", 0)
    target_score = profile.get("target_score", 0)
    exam_year = profile.get("exam_year", 0)
    target_level = profile.get("target_school_level", "")
    
    close_to_target = target_score > 0 and abs(target_score - score) <= 40
    if close_to_target:
        evidence_ids = [e.get("chunk_id","") for e in evidence if any(kw in str(e.get("content","")).lower() for kw in ["冲刺","应试","真题","技巧"])][:3]
        return ClassRecommendation(
            recommended_class_type="冲刺班",
            confidence="medium",
            reasons=[
                f"当前{score}分，目标{target_score}分，差距适中",
                "距离考试较近，侧重查漏补缺和应试技巧",
                "适合有明确目标且基础较好的学生"
            ],
            not_suitable_if=["基础差距过大（≥80分）", "需要长期系统补课"],
            missing_info=_missing_from_profile(profile, ["weak_subjects", "exam_year"]),
            next_questions=["距离高考还有多少时间？", "主要想加强哪些题型的训练？"],
            risk_warnings=["冲刺班以提分效率为导向，需要学生已有较强基础"],
            evidence_ids=evidence_ids,
        )
    return None


def _no_recommendation(profile: dict) -> ClassRecommendation:
    missing = _missing_from_profile(profile, ["current_score", "subject_type", "target_school_level"])
    return ClassRecommendation(
        recommended_class_type=None,
        confidence="low",
        reasons=["当前画像信息不足以做出班型推荐"],
        missing_info=missing,
        next_questions=[f"请问{'您的' if profile.get('identity_type')=='parent' else ''}孩子是物理类还是历史类？", "目前考试成绩大概在多少分？"],
        risk_warnings=["信息不足时不做班型推荐，以免误导"],
        evidence_ids=[],
    )


def _missing_from_profile(profile: dict, fields: list[str]) -> list[str]:
    missing: list[str] = []
    for f in fields:
        val = profile.get(f)
        if not val or val == "" or val == 0 or val == []:
            missing.append(f)
    return missing
