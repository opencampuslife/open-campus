from __future__ import annotations

import hashlib
import json
import re
import uuid
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any


class LeadStatus(str, Enum):
    NEW = "NEW"
    ASSIGNED = "ASSIGNED"
    CONTACTED = "CONTACTED"
    ASSESSMENT_BOOKED = "ASSESSMENT_BOOKED"
    VISIT_BOOKED = "VISIT_BOOKED"
    ENROLLED = "ENROLLED"
    LOST = "LOST"


VALID_TRANSITIONS: dict[LeadStatus, set[LeadStatus]] = {
    LeadStatus.NEW: {LeadStatus.ASSIGNED, LeadStatus.LOST},
    LeadStatus.ASSIGNED: {LeadStatus.CONTACTED, LeadStatus.LOST},
    LeadStatus.CONTACTED: {LeadStatus.ASSESSMENT_BOOKED, LeadStatus.VISIT_BOOKED, LeadStatus.LOST},
    LeadStatus.ASSESSMENT_BOOKED: {LeadStatus.VISIT_BOOKED, LeadStatus.ENROLLED, LeadStatus.LOST},
    LeadStatus.VISIT_BOOKED: {LeadStatus.ASSESSMENT_BOOKED, LeadStatus.ENROLLED, LeadStatus.LOST},
    LeadStatus.ENROLLED: {LeadStatus.LOST},
    LeadStatus.LOST: set(),
}


class LeadEventType(str, Enum):
    CREATED = "created"
    ASSIGNED = "assigned"
    FOLLOWUP_ADDED = "followup_added"
    STATUS_CHANGED = "status_changed"
    SCORE_UPDATED = "score_updated"
    PROFILE_UPDATED = "profile_updated"


SALES_ROLES = {"sales", "campus_admin", "admin"}


def score_lead(messages: list[str], intent: str, profile: dict[str, Any] | None = None) -> dict[str, Any]:
    score = 30
    reasons: list[str] = []
    all_text = " ".join(messages)

    if profile is None:
        profile = {}

    if profile.get("current_score") or re.search(r"\d{3}\s*分", all_text):
        score += 20
        reasons.append("已提供分数 (+20)")

    if any(token in all_text for token in ["学费", "学费", "费用", "价格", "优惠", "多少钱"]):
        score += 15
        reasons.append("咨询费用/价格 (+15)")

    if any(token in all_text for token in ["报名", "入学", "报到", "怎么报"]):
        score += 15
        reasons.append("咨询报名流程 (+15)")

    if any(token in all_text for token in ["转人工", "人工顾问", "打电话", "联系我", "微信"]):
        score += 15
        reasons.append("请求转人工 (+15)")

    if any(token in all_text for token in ["一本", "二本", "211", "985", "双一流", "本科"]) or profile.get("target_school_level"):
        score += 10
        reasons.append("提供目标院校/层次 (+10)")

    if profile.get("weak_subjects"):
        score += 10
        reasons.append("提供薄弱科目 (+10)")

    if any(token in all_text for token in ["班型", "全日制", "小班", "冲刺班", "适合什么班"]):
        score += 10
        reasons.append("咨询班型 (+10)")

    if any(token in all_text for token in ["住宿", "宿舍", "管理", "伙食", "封闭"]):
        score += 10
        reasons.append("咨询住宿/管理 (+10)")

    if any(token in all_text for token in ["预约", "测评", "学情评估", "到校", "试听", "参观"]):
        score += 20
        reasons.append("预约测评/到校 (+20)")

    if intent == "general_query":
        score -= 10
        reasons.append("泛泛提问 (-10)")

    if any(token in all_text for token in ["不感兴趣", "再看看", "不需要", "算了", "不考虑"]):
        score -= 20
        reasons.append("明确无意向 (-20)")

    if intent in {"class_recommendation", "pricing_consulting"}:
        score += 5
        reasons.append("意向明确 (+5)")

    score = max(0, min(100, score))

    if score >= 70:
        intent_level = "high"
    elif score >= 40:
        intent_level = "medium"
    else:
        intent_level = "low"

    return {
        "score": score,
        "intent_level": intent_level,
        "reasons": reasons,
    }


def _hash_phone(phone: str) -> str:
    return hashlib.sha256(f"gaokao_salt_{phone}".encode()).hexdigest()[:16]


def _new_lead_id() -> str:
    return f"lead_{uuid.uuid4().hex[:12]}"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _leads_dir(project_root: Path) -> Path:
    d = project_root / "data" / "crm" / "leads"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _lead_path(project_root: Path, lead_id: str) -> Path:
    return _leads_dir(project_root) / f"{lead_id}.json"


def load_lead(project_root: Path, lead_id: str) -> dict[str, Any] | None:
    path = _lead_path(project_root, lead_id)
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _save_lead(project_root: Path, lead: dict[str, Any]) -> None:
    lead["updated_at"] = _now_iso()
    _lead_path(project_root, lead["lead_id"]).write_text(
        json.dumps(lead, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _append_event(lead: dict[str, Any], event_type: str, actor_id: str, payload: dict[str, Any] | None = None) -> None:
    events = lead.setdefault("events", [])
    events.append({
        "event_id": f"evt_{uuid.uuid4().hex[:12]}",
        "event_type": event_type,
        "actor_id": actor_id,
        "payload": payload or {},
        "created_at": _now_iso(),
    })


def _visible_to(lead: dict[str, Any], identity: dict[str, Any]) -> bool:
    role = identity.get("role", "")
    if role == "admin":
        return True
    if role == "campus_admin":
        return identity.get("campus") in (lead.get("campus_id"), "all")
    if role == "sales":
        campus_match = identity.get("campus") in (lead.get("campus_id"), "all", lead.get("campus"))
        assigned_match = lead.get("assigned_consultant_id") == identity.get("user_id")
        return campus_match or assigned_match
    return False


def _require_sales_role(identity: dict[str, Any]) -> None:
    if identity.get("role") not in SALES_ROLES:
        raise ValueError(f"CRM access denied for role: {identity.get('role')}")


def upsert_lead(
    project_root: Path,
    *,
    session_id: str,
    identity: dict[str, Any],
    message: str = "",
    intent: str = "",
    profile: dict[str, Any] | None = None,
    campus_id: str = "",
    phone: str = "",
    lead_id: str = "",
) -> dict[str, Any]:
    existing: dict[str, Any] | None = None
    if lead_id:
        existing = load_lead(project_root, lead_id)
    if existing is None:
        for path in _leads_dir(project_root).glob("*.json"):
            candidate = json.loads(path.read_text(encoding="utf-8"))
            if candidate.get("session_id") == session_id:
                existing = candidate
                lead_id = candidate["lead_id"]
                break

    if existing is not None:
        lead = existing
        is_new = False
    else:
        lead_id = lead_id or _new_lead_id()
        lead = {
            "lead_id": lead_id,
            "session_id": session_id,
            "status": LeadStatus.NEW.value,
            "channel": "openhuman",
            "campus_id": campus_id or identity.get("campus", "all"),
            "identity_type": identity.get("role", "visitor"),
            "created_at": _now_iso(),
            "updated_at": _now_iso(),
            "followups": [],
            "events": [],
            "profile_summary": {},
            "consultation_stage": "",
            "recommendation_summary": {},
            "intent_reason": [],
            "next_best_action": {},
            "risk_tags": [],
            "last_consultation_at": _now_iso(),
        }
        is_new = True

    if phone:
        lead["parent_phone_hash"] = _hash_phone(phone)

    scoring = score_lead([message] if message else [], intent, profile or {})
    lead["intent"] = intent
    lead["intent_level"] = scoring["intent_level"]
    lead["score"] = scoring["score"]
    lead["score_reasons"] = scoring["reasons"]
    lead["message"] = message or lead.get("message", "")

    if profile:
        for key in ("current_score", "subject_type", "target_school_level",
                     "weak_subjects", "strong_subjects", "budget_range",
                     "self_discipline_level", "province", "preferred_class_type",
                     "identity_type", "target_score"):
            if profile.get(key):
                lead[key] = profile[key]
        from profile_model import profile_summary as _profile_summary
        lead["profile_summary"] = _profile_summary(profile)
        completeness = profile.get("_completeness") or 0
        if completeness:
            lead["profile_completeness"] = completeness
        if profile.get("consultation_stage"):
            lead["consultation_stage"] = profile["consultation_stage"]
        if isinstance(profile.get("recommendation_summary"), dict):
            lead["recommendation_summary"] = profile["recommendation_summary"]
        if isinstance(profile.get("next_best_action"), dict):
            lead["next_best_action"] = profile["next_best_action"]
        if isinstance(profile.get("risk_tags"), list):
            lead["risk_tags"] = profile["risk_tags"]
        lead["last_consultation_at"] = _now_iso()

    if is_new:
        _append_event(lead, LeadEventType.CREATED.value, identity.get("user_id", "system"),
                      {"session_id": session_id, "intent": intent, "score": scoring["score"]})

    _save_lead(project_root, lead)
    return lead


def assign_lead(project_root: Path, lead_id: str, consultant_id: str, identity: dict[str, Any]) -> dict[str, Any]:
    lead = load_lead(project_root, lead_id)
    if lead is None:
        raise ValueError(f"lead not found: {lead_id}")

    lead["assigned_consultant_id"] = consultant_id
    lead["assigned_at"] = _now_iso()
    if lead["status"] in {LeadStatus.NEW.value}:
        lead["status"] = LeadStatus.ASSIGNED.value

    _append_event(lead, LeadEventType.ASSIGNED.value, identity.get("user_id", "system"),
                  {"consultant_id": consultant_id})
    _save_lead(project_root, lead)
    return lead


def update_lead_status(project_root: Path, lead_id: str, new_status: str, identity: dict[str, Any]) -> dict[str, Any]:
    lead = load_lead(project_root, lead_id)
    if lead is None:
        raise ValueError(f"lead not found: {lead_id}")

    current = LeadStatus(lead["status"])
    target = LeadStatus(new_status)

    if target not in VALID_TRANSITIONS.get(current, set()):
        raise ValueError(f"Invalid status transition: {current.value} -> {target.value}")

    old_status = lead["status"]
    lead["status"] = target.value

    _append_event(lead, LeadEventType.STATUS_CHANGED.value, identity.get("user_id", "system"),
                  {"from_status": old_status, "to_status": target.value})
    _save_lead(project_root, lead)
    return lead


def add_followup_to_lead(
    project_root: Path,
    lead_id: str,
    *,
    consultant_id: str,
    note: str,
    followup_type: str = "general",
    next_followup_at: str = "",
    identity: dict[str, Any] | None = None,
) -> dict[str, Any]:
    lead = load_lead(project_root, lead_id)
    if lead is None:
        raise ValueError(f"lead not found: {lead_id}")

    followup = {
        "followup_id": f"fup_{uuid.uuid4().hex[:12]}",
        "consultant_id": consultant_id,
        "note": note,
        "followup_type": followup_type,
        "created_at": _now_iso(),
    }
    if next_followup_at:
        followup["next_followup_at"] = next_followup_at
        lead["next_followup_at"] = next_followup_at

    followups = lead.setdefault("followups", [])
    followups.append(followup)

    actor_id = identity.get("user_id", "system") if identity else "system"
    _append_event(lead, LeadEventType.FOLLOWUP_ADDED.value, actor_id,
                  {"followup_id": followup["followup_id"], "followup_type": followup_type})
    _save_lead(project_root, lead)
    return {"lead_id": lead_id, "followup": followup}


def list_leads(project_root: Path, identity: dict[str, Any]) -> list[dict[str, Any]]:
    _require_sales_role(identity)
    items: list[dict[str, Any]] = []
    leads_dir = _leads_dir(project_root)
    if leads_dir.exists():
        for path in sorted(leads_dir.glob("*.json")):
            lead = json.loads(path.read_text(encoding="utf-8"))
            if _visible_to(lead, identity):
                items.append(_lead_summary(lead))
    items.sort(key=lambda l: l.get("updated_at", ""), reverse=True)
    return items


def _lead_summary(lead: dict[str, Any]) -> dict[str, Any]:
    profile = lead.get("profile") or {}
    name = profile.get("name") or profile.get("student_name")
    campus = lead.get("campus") or lead.get("campus_id", "")
    return {
        "id": lead.get("lead_id") or lead.get("id"),
        "lead_id": lead["lead_id"],
        "name": name,
        "session_id": lead.get("session_id"),
        "channel": lead.get("channel"),
        "campus": campus,
        "campus_id": lead.get("campus_id") or campus,
        "identity_type": lead.get("identity_type"),
        "current_score": profile.get("current_score") or lead.get("current_score"),
        "subject_type": profile.get("subject_type") or lead.get("subject_type"),
        "target_school_level": profile.get("target_school_level") or lead.get("target_school_level"),
        "intent": lead.get("intent"),
        "intent_level": lead.get("intent_level"),
        "score": lead.get("score"),
        "score_reasons": lead.get("score_reasons", []),
        "status": lead.get("status"),
        "assigned_to": lead.get("assigned_to") or lead.get("assigned_consultant_id"),
        "assigned_consultant_id": lead.get("assigned_consultant_id") or lead.get("assigned_to"),
        "phone": lead.get("phone") or lead.get("phone_hash"),
        "followup_count": len(lead.get("followups", [])),
        "followups": lead.get("followups", []),
        "next_followup_at": lead.get("next_followup_at"),
        "message": lead.get("message", ""),
        "profile_completeness": lead.get("profile_completeness", 0),
        "consultation_stage": lead.get("consultation_stage", ""),
        "recommendation_summary": lead.get("recommendation_summary", {}),
        "next_best_action": lead.get("next_best_action", {}),
        "risk_tags": lead.get("risk_tags", []),
        "created_at": lead.get("created_at"),
        "updated_at": lead.get("updated_at"),
        "last_contacted": lead.get("last_contacted") or lead.get("updated_at"),
    }
