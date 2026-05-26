from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

# ── Required fields for basic consultation ──────────────────────────

REQUIRED_FIELDS = [
    "subject_type",
    "current_score",
    "target_school_level",
]

# ── All recognized profile fields ───────────────────────────────────

PROFILE_FIELDS = [
    "identity_type",
    "province",
    "city",
    "subject_type",
    "current_score",
    "target_score",
    "target_school_level",
    "weak_subjects",
    "strong_subjects",
    "self_discipline_level",
    "budget_range",
    "preferred_campus",
    "preferred_class_type",
    "boarding_preference",
    "parent_concerns",
    "student_concerns",
    "exam_year",
    "repeat_year_count",
    "intent_level",
    "risk_tags",
    "last_updated_at",
]

# ── Subject type normalization ──────────────────────────────────────

SUBJECT_TYPE_MAP = {
    "物理类": "physics",
    "物化生": "physics",
    "物化地": "physics",
    "物生政": "physics",
    "历史类": "history",
    "史地政": "history",
    "文科": "arts",
    "理科": "science",
    "文理": "mixed",
}

TARGET_SCHOOL_LEVEL_MAP = {
    "985": "985_211",
    "211": "985_211",
    "双一流": "985_211",
    "一本": "undergraduate",
    "本科": "undergraduate",
    "二本": "undergraduate",
    "专科": "vocational",
    "大专": "vocational",
    "高职": "vocational",
    "重点": "key_university",
}

DISCIPLINE_LEVEL_MAP = {
    "自律强": "high",
    "自觉": "high",
    "自律差": "low",
    "不自觉": "low",
    "管不住": "low",
    "还行": "medium",
    "一般": "medium",
}

BUDGET_RANGE_MAP = {
    "经济": "low",
    "贵": "high",
    "便宜": "low",
}

# ── Data classes ────────────────────────────────────────────────────

@dataclass
class ProfilePatch:
    updates: dict[str, Any] = field(default_factory=dict)
    confidence: dict[str, float] = field(default_factory=dict)
    missing_required_fields: list[str] = field(default_factory=list)
    profile_completeness: float = 0.0

# ── Extraction ──────────────────────────────────────────────────────

def extract_profile_from_message(message: str, current: dict[str, Any] | None = None) -> ProfilePatch:
    if current is None:
        current = {}

    updates: dict[str, Any] = {}
    confidence: dict[str, float] = {}

    # Score: "430分", "430 分", "考了430"
    m = re.search(r"(\d{3})\s*分|(?:考了?|成绩(?:是|为)?|分数(?:是|为)?)\s*(\d{3})(?!\d)", message)
    if m:
        score = int(m.group(1) or m.group(2))
        if 100 <= score <= 750:
            updates["current_score"] = score
            confidence["current_score"] = 0.95

    # Target score: "目标500分", "想冲550"
    m = re.search(r"目标.*?(\d{3})\s*分|冲.*?(\d{3})", message)
    if m:
        target = int(m.group(1) or m.group(2))
        if 100 <= target <= 750:
            updates["target_score"] = target
            confidence["target_score"] = 0.9

    # Subject type: scan known types in message
    for keyword, normalized in SUBJECT_TYPE_MAP.items():
        if keyword in message:
            updates["subject_type"] = normalized
            confidence["subject_type"] = 0.9
            break

    # Target school level
    for keyword, normalized in TARGET_SCHOOL_LEVEL_MAP.items():
        if keyword in message:
            updates["target_school_level"] = normalized
            confidence["target_school_level"] = 0.85
            break

    # Weak subjects
    ALL_SUBJECTS = ["数学", "英语", "语文", "物理", "化学", "生物", "历史", "地理", "政治"]
    weak: list[str] = []
    strong: list[str] = []
    for subj in ALL_SUBJECTS:
        if subj in message:
            pos = message.index(subj)
            context = message[pos:pos + len(subj) + 12]
            weak_kws = ["差", "弱", "不好", "不行", "偏科", "拉分", "拖后腿"]
            strong_kws = ["好", "强", "优势", "擅长", "不错"]
            if any(kw in context for kw in weak_kws):
                weak.append(subj)
            elif any(kw in context for kw in strong_kws):
                strong.append(subj)

    if weak:
        updates["weak_subjects"] = weak
        confidence["weak_subjects"] = 0.8
    if strong:
        updates["strong_subjects"] = strong
        confidence["strong_subjects"] = 0.75

    # Self-discipline
    for keyword, level in DISCIPLINE_LEVEL_MAP.items():
        if keyword in {"还行", "一般"} and not any(anchor in message for anchor in ["自律", "学习习惯", "管自己"]):
            continue
        if keyword in message:
            updates["self_discipline_level"] = level
            confidence["self_discipline_level"] = 0.7
            break

    # Province / city (simple: match known names)
    PROVINCES = ["河南", "河北", "山东", "山西", "陕西", "江苏", "浙江", "安徽",
                  "湖北", "湖南", "广东", "广西", "四川", "贵州", "云南", "福建",
                  "北京", "上海", "天津", "重庆"]
    for prov in PROVINCES:
        if prov in message:
            updates["province"] = prov
            confidence["province"] = 0.85
            break

    # Budget
    for keyword, level in BUDGET_RANGE_MAP.items():
        if keyword in message:
            updates["budget_range"] = level
            confidence["budget_range"] = 0.5  # low confidence, needs confirmation
            break

    # Identity type: "孩子" → parent, "我今年" → student
    if any(kw in message for kw in ["孩子", "我家", "儿子", "女儿", "小孩"]):
        updates["identity_type"] = "parent"
        confidence["identity_type"] = 0.85
    elif any(kw in message for kw in ["我今年", "我考了", "我的成绩", "我的分数", "我是学生", "学生本人"]):
        updates["identity_type"] = "student"
        confidence["identity_type"] = 0.8

    repeat_match = re.search(r"复读第?([一二两三四五六七八九\d]+)年", message)
    if repeat_match:
        repeat_text = repeat_match.group(1)
        chinese_numbers = {"一": 1, "二": 2, "两": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}
        repeat_year_count = int(repeat_text) if repeat_text.isdigit() else chinese_numbers.get(repeat_text)
        if repeat_year_count:
            updates["repeat_year_count"] = repeat_year_count
            confidence["repeat_year_count"] = 0.9

    # Exam year: "今年高考", "2026届", "明年高考"
    m = re.search(r"(\d{4})届", message)
    if m:
        updates["exam_year"] = int(m.group(1))
        confidence["exam_year"] = 0.9

    # Boarding preference
    if any(kw in message for kw in ["走读", "不住校", "回家住"]):
        updates["boarding_preference"] = "day"
        confidence["boarding_preference"] = 0.7
    elif any(kw in message for kw in ["住宿", "住校", "封闭", "寄宿"]):
        updates["boarding_preference"] = "boarding"
        confidence["boarding_preference"] = 0.7

    # Preferred campus
    CAMPUSES = ["郑州", "新郑", "开封", "洛阳", "南阳", "信阳", "周口", "商丘", "许昌", "驻马店"]
    for campus in CAMPUSES:
        if campus in message:
            updates["preferred_campus"] = campus
            confidence["preferred_campus"] = 0.75
            break

    # Class type preference
    if any(kw in message for kw in ["冲刺班", "培优班", "全日制"]):
        updates["preferred_class_type"] = "冲刺班" if "冲刺" in message else "全日制"
        confidence["preferred_class_type"] = 0.6

    # Parent/student concerns
    concerns: list[str] = []
    if any(kw in message for kw in ["学费", "费用", "价格"]):
        concerns.append("费用")
    if any(kw in message for kw in ["管理", "管教", "纪律"]):
        concerns.append("管理")
    if any(kw in message for kw in ["效果", "提分", "提高"]):
        concerns.append("效果")
    if any(kw in message for kw in ["安全", "环境"]):
        concerns.append("安全")
    if concerns:
        if "孩子" in message or "家长" in message:
            updates["parent_concerns"] = concerns
        else:
            updates["student_concerns"] = concerns
        confidence["parent_concerns" if "孩子" in message else "student_concerns"] = 0.6

    # Compute completeness based on current + updates merged
    merged = dict(current)
    merged.update(updates)
    completeness = compute_completeness(merged)

    # Determine missing required fields
    missing = [f for f in REQUIRED_FIELDS if not merged.get(f)]

    return ProfilePatch(
        updates=updates,
        confidence=confidence,
        missing_required_fields=missing,
        profile_completeness=completeness,
    )


def merge_profile(existing: dict[str, Any], patch: ProfilePatch) -> dict[str, Any]:
    merged = dict(existing)
    for key, value in patch.updates.items():
        if key == "weak_subjects" and isinstance(value, list):
            current_weak = merged.get(key, [])
            if isinstance(current_weak, list):
                merged[key] = sorted(set(current_weak + value))
            else:
                merged[key] = value
        elif key == "strong_subjects" and isinstance(value, list):
            current_strong = merged.get(key, [])
            if isinstance(current_strong, list):
                merged[key] = sorted(set(current_strong + value))
            else:
                merged[key] = value
        elif key == "current_score":
            existing_score = merged.get(key, 0)
            if isinstance(existing_score, int) and existing_score > 0:
                # If new score differs significantly, use the new one (correction)
                if abs(value - existing_score) <= 5:
                    pass  # minor difference, keep old
                else:
                    merged[key] = value
            else:
                merged[key] = value
        else:
            merged[key] = value

    merged["last_updated_at"] = datetime.now(timezone.utc).isoformat()
    return merged


def compute_completeness(profile: dict[str, Any]) -> float:
    """Compute profile completeness score 0.0-1.0"""
    scored_fields = {
        "identity_type": 0.10,
        "province": 0.05,
        "city": 0.02,
        "subject_type": 0.15,
        "current_score": 0.15,
        "target_score": 0.05,
        "target_school_level": 0.10,
        "weak_subjects": 0.10,
        "strong_subjects": 0.03,
        "self_discipline_level": 0.05,
        "budget_range": 0.05,
        "preferred_campus": 0.05,
        "preferred_class_type": 0.05,
        "boarding_preference": 0.03,
        "parent_concerns": 0.01,
        "student_concerns": 0.01,
    }
    total = 0.0
    for field, weight in scored_fields.items():
        val = profile.get(field)
        if val and val != "" and val != 0 and val != []:
            total += weight
    return round(min(total, 1.0), 2)


def profile_summary(profile: dict[str, Any]) -> dict[str, Any]:
    """Return a safe, de-identified summary suitable for CRM lead."""
    return {
        "identity_type": profile.get("identity_type", ""),
        "province": profile.get("province", ""),
        "subject_type": profile.get("subject_type", ""),
        "current_score": profile.get("current_score"),
        "target_school_level": profile.get("target_school_level", ""),
        "weak_subjects": profile.get("weak_subjects", []),
        "budget_range": profile.get("budget_range", ""),
        "self_discipline_level": profile.get("self_discipline_level", ""),
        "preferred_class_type": profile.get("preferred_class_type", ""),
        "completeness": compute_completeness(profile),
    }


def profile_to_dict(profile: dict[str, Any]) -> dict[str, Any]:
    """Export profile for JSON storage, filtering sensitive fields."""
    safe: dict[str, Any] = {}
    for key in PROFILE_FIELDS:
        if key in profile:
            safe[key] = profile[key]
    return safe
