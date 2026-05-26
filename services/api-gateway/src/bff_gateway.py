from __future__ import annotations

import json
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

AGENT_SRC = Path(__file__).resolve().parents[2] / "agent-orchestrator" / "src"
CRM_SRC = Path(__file__).resolve().parents[2] / "crm-service" / "src"
sys.path.extend([str(AGENT_SRC), str(CRM_SRC)])

from audit_logger import audit_log  # noqa: E402
from handoff import create_handoff  # noqa: E402
from leads import (  # noqa: E402
    add_followup_to_lead,
    assign_lead,
    list_leads,
    load_lead,
    update_lead_status,
    upsert_lead,
)
from next_best_action import determine_next_best_action  # noqa: E402
from pipeline import receive_message  # noqa: E402
from structured_logger import RequestLogger  # noqa: E402
from event_schema import EventType, make_event  # noqa: E402
from audit_store import write_audit_event  # noqa: E402

CHAT_FIELDS = {"session_id", "message"}
HANDOFF_FIELDS = {"session_id", "reason"}
SALES_ROLES = {"sales", "campus_admin", "admin"}
PRIVILEGED_ROLES = {"sales", "admin", "campus_admin", "teacher", "operator", "content_operator", "reviewer"}


def post_chat(payload: dict[str, Any], auth_identity: dict[str, Any], project_root: Path) -> dict[str, Any]:
    _reject_untrusted_fields(payload, CHAT_FIELDS)
    _reject_missing_message(payload)
    identity = _trusted_identity(auth_identity)
    entrypoint = _entrypoint_for(identity["role"])
    session_id = str(payload.get("session_id") or _new_session_id())
    session = _load_session(project_root, session_id, identity)
    log = RequestLogger(project_root, identity)
    log.chat_request(session_id=session_id, message_len=len(str(payload["message"])))
    result = receive_message(
        identity,
        str(payload["message"]),
        project_root,
        entrypoint=entrypoint,
        initial_profile=session.get("profile", {}),
        initial_recommendation=session.get("recommendation_result"),
    )
    session["messages"].append({"role": "user", "content": str(payload["message"])})
    session["messages"].append({"role": "assistant", "content": result["answer"]})
    session["intent"] = result["intent"]
    _apply_consultation_result(session, result)
    session["updated_at"] = _now_iso()
    _save_session(project_root, session_id, session)
    log.chat_response(session_id=session_id, answer_len=len(result["answer"]),
                      intent=result["intent"].get("intent", ""),
                      consultation_stage=session.get("consultation_stage", ""))
    log.flush()

    write_audit_event(project_root, make_event(EventType.CHAT_RECEIVED,
        trace_id=log.trace_id, request_id=log.request_id,
        session_id=session_id, user_id=str(identity.get("user_id", "")),
        role=str(identity.get("role", "")), campus=str(identity.get("campus", "")),
        entrypoint=entrypoint, status="ok", latency_ms=int((log.t0 - log.t0) * 1000) or 1,
        metadata={"message_len": len(str(payload["message"]))},
    ))
    write_audit_event(project_root, make_event(EventType.CHAT_ANSWERED,
        trace_id=log.trace_id, request_id=log.request_id,
        session_id=session_id, user_id=str(identity.get("user_id", "")),
        role=str(identity.get("role", "")), campus=str(identity.get("campus", "")),
        entrypoint=entrypoint, status="ok",
        metadata={
            "intent": result["intent"].get("intent", ""),
            "answer_len": len(result["answer"]),
            "consultation_stage": session.get("consultation_stage", ""),
            "profile_completeness": session.get("profile_completeness", 0.0),
        },
    ))

    hide_sources = _should_hide_sources(identity)
    answer = result["answer"]
    if hide_sources:
        answer = _strip_source_lines(answer)
        answer = _sanitize_mechanical_phrases(answer)

    return {
        "session_id": session_id,
        "answer": answer,
        "citations": [] if hide_sources else _public_citations(result["retrieval"].get("citations", [])),
        "recommended_actions": _recommended_actions(payload["message"], result),
        "handoff_triggered": result.get("handoff_triggered", False),
        "active_mode": result.get("active_mode", "admissions_consultation"),
    }


def list_sessions(auth_identity: dict[str, Any], project_root: Path) -> dict[str, Any]:
    identity = _trusted_identity(auth_identity)
    session_dir = project_root / "data" / "sessions"
    items: list[dict[str, Any]] = []
    if session_dir.exists():
        for path in sorted(session_dir.glob("*.json")):
            session = json.loads(path.read_text(encoding="utf-8"))
            if session.get("user_id") == identity.get("user_id"):
                items.append(_session_summary(session))
    return {"sessions": items}


def post_handoff(payload: dict[str, Any], auth_identity: dict[str, Any], project_root: Path) -> dict[str, Any]:
    _reject_untrusted_fields(payload, HANDOFF_FIELDS)
    identity = _trusted_identity(auth_identity)
    entrypoint = _entrypoint_for(identity["role"])
    session_id = str(payload.get("session_id") or _new_session_id())
    message = _handoff_message(payload)
    session = _load_session(project_root, session_id, identity)
    log = RequestLogger(project_root, identity)
    chat_result = receive_message(
        identity,
        message,
        project_root,
        entrypoint=entrypoint,
        initial_profile=session.get("profile", {}),
        initial_recommendation=session.get("recommendation_result"),
    )
    session["intent"] = chat_result["intent"]
    _apply_consultation_result(session, chat_result)
    _save_session(project_root, session_id, session)
    handoff = create_handoff(
        project_root=project_root,
        session_id=session_id,
        identity=identity,
        message=message,
        answer=chat_result["answer"],
        intent=str(chat_result["intent"]["intent"]),
        retrieval=chat_result["retrieval"],
    )
    _session_apply_fsm_event(session, project_root, session_id, "handoff_requested")
    lead = upsert_lead(
        project_root,
        session_id=session_id,
        identity=identity,
        message=message,
        intent=str(chat_result["intent"]["intent"]),
        profile=_extract_profile(session),
        campus_id=identity.get("campus", "all"),
    )
    log.handoff(session_id=session_id, lead_id=str(lead.get("lead_id", "")))
    log.flush()
    write_audit_event(project_root, make_event(EventType.HANDOFF_REQUESTED,
        trace_id=log.trace_id, request_id=log.request_id,
        session_id=session_id, lead_id=str(lead.get("lead_id", "")),
        user_id=str(identity.get("user_id", "")),
        role=str(identity.get("role", "")), campus=str(identity.get("campus", "")),
        entrypoint=entrypoint, status="ok",
        metadata={"intent": str(chat_result["intent"]["intent"]),
                  "consultation_stage": session.get("consultation_stage", "")},
    ))
    handoff["lead"] = _lead_summary(lead)
    return handoff


def list_sales_sessions(auth_identity: dict[str, Any], project_root: Path) -> dict[str, Any]:
    identity = _trusted_identity(auth_identity)
    _require_sales_role(identity)
    session_dir = project_root / "data" / "sessions"
    items: list[dict[str, Any]] = []

    if session_dir.exists():
        for path in sorted(session_dir.glob("*.json")):
            session = json.loads(path.read_text(encoding="utf-8"))
            if not _visible_to_sales(session, identity):
                continue
            items.append(_session_summary(session))

    items.sort(key=lambda s: s["updated_at"], reverse=True)
    audit_log(project_root, {
        "action": "list_sales_sessions",
        "user_id": identity["user_id"],
        "role": identity["role"],
        "count": len(items),
    })
    return {"sessions": items}


def get_sales_session(session_id: str, auth_identity: dict[str, Any], project_root: Path) -> dict[str, Any]:
    identity = _trusted_identity(auth_identity)
    _require_sales_role(identity)
    session = _load_session(project_root, session_id, identity)
    if not _visible_to_sales(session, identity):
        raise ValueError("session not found or not accessible")

    return {
        "session_id": session["session_id"],
        "user_id": session.get("user_id"),
        "role": session.get("role"),
        "campus": session.get("campus"),
        "created_at": session.get("created_at"),
        "updated_at": session.get("updated_at"),
        "messages": session.get("messages", []),
        "intent": session.get("intent", {}),
        "profile": _extract_profile(session),
        "internal_suggestions": _build_internal_suggestions(session, identity),
        "takeover_status": session.get("takeover_status", "open"),
        "assigned_to": session.get("assigned_to"),
        "followups": session.get("followups", []),
        "consultation_stage": session.get("consultation_stage", ""),
        "profile_summary": _build_profile_summary_card(session),
        "recommendation_summary": _build_recommendation_card(session),
        "next_best_action": _build_next_best_action_card(session),
        "risk_tags": _extract_risk_tags(session),
    }


def takeover_session(
    session_id: str, auth_identity: dict[str, Any], project_root: Path
) -> dict[str, Any]:
    identity = _trusted_identity(auth_identity)
    _require_sales_role(identity)
    session = _load_session(project_root, session_id, identity)
    if not _visible_to_sales(session, identity):
        raise ValueError("session not found or not accessible")

    if session.get("takeover_status") == "taken":
        raise ValueError("session already taken by another consultant")

    session["takeover_status"] = "taken"
    session["assigned_to"] = identity["user_id"]
    session["assigned_at"] = _now_iso()
    _save_session(project_root, session_id, session)

    _session_apply_fsm_event(session, project_root, session_id, "human_accepted")

    result = {"session_id": session_id, "status": "taken"}
    try:
        lead = upsert_lead(
            project_root,
            session_id=session_id,
            identity=identity,
            message="",
            intent=session.get("intent", {}).get("intent", ""),
            profile=_extract_profile(session),
            campus_id=identity.get("campus", "all"),
        )
        lead = assign_lead(project_root, lead["lead_id"], identity["user_id"], identity)
        result["lead"] = _lead_summary(lead)
    except Exception:
        pass

    audit_log(project_root, {
        "action": "takeover_session",
        "user_id": identity["user_id"],
        "role": identity["role"],
        "session_id": session_id,
        "session_user_id": session.get("user_id"),
    })
    return result


def add_followup(
    session_id: str, payload: dict[str, Any], auth_identity: dict[str, Any], project_root: Path
) -> dict[str, Any]:
    identity = _trusted_identity(auth_identity)
    _require_sales_role(identity)
    session = _load_session(project_root, session_id, identity)
    if not _visible_to_sales(session, identity):
        raise ValueError("session not found or not accessible")

    note = str(payload.get("note", "")).strip()
    if not note:
        raise ValueError("followup note is required")

    action = payload.get("action_type", "general")

    followup = {
        "consultant_id": identity["user_id"],
        "note": note,
        "action_type": action,
        "created_at": _now_iso(),
    }

    followups = session.get("followups", [])
    followups.append(followup)
    session["followups"] = followups
    session["updated_at"] = _now_iso()
    _save_session(project_root, session_id, session)

    _session_apply_fsm_event(session, project_root, session_id, "followup_created")

    result = {"session_id": session_id, "followup": followup}
    try:
        lead_id = _find_lead_id_for_session(project_root, session_id)
        if lead_id:
            lr = add_followup_to_lead(
                project_root, lead_id,
                consultant_id=identity["user_id"],
                note=note,
                followup_type=action,
                next_followup_at=str(payload.get("next_followup_at", "")),
                identity=identity,
            )
            result["lead"] = lr
    except Exception:
        pass

    audit_log(project_root, {
        "action": "add_followup",
        "user_id": identity["user_id"],
        "role": identity["role"],
        "session_id": session_id,
        "action_type": action,
    })
    return result


def list_sales_leads(auth_identity: dict[str, Any], project_root: Path) -> dict[str, Any]:
    identity = _trusted_identity(auth_identity)
    _require_sales_role(identity)
    items = list_leads(project_root, identity)
    audit_log(project_root, {
        "action": "list_crm_leads",
        "user_id": identity["user_id"],
        "role": identity["role"],
        "count": len(items),
    })
    return {"leads": items}


def get_crm_lead(lead_id: str, auth_identity: dict[str, Any], project_root: Path) -> dict[str, Any]:
    identity = _trusted_identity(auth_identity)
    _require_sales_role(identity)
    lead = load_lead(project_root, lead_id)
    if lead is None:
        raise ValueError(f"lead not found: {lead_id}")
    if not _crm_lead_visible_to(lead, identity):
        raise ValueError(f"lead not found or not accessible")
    audit_log(project_root, {
        "action": "get_crm_lead",
        "user_id": identity["user_id"],
        "role": identity["role"],
        "lead_id": lead_id,
    })
    return lead


def create_crm_lead(payload: dict[str, Any], auth_identity: dict[str, Any], project_root: Path) -> dict[str, Any]:
    identity = _trusted_identity(auth_identity)
    _require_sales_role(identity)
    session_id = str(payload.get("session_id") or _new_session_id())
    lead = upsert_lead(
        project_root,
        session_id=session_id,
        identity=identity,
        message=str(payload.get("message", "")),
        intent=str(payload.get("intent", "")),
        profile=_extract_profile_from_payload(payload),
        campus_id=str(payload.get("campus_id", identity.get("campus", "all"))),
        phone=str(payload.get("phone", "")),
        lead_id=str(payload.get("lead_id", "")),
    )
    audit_log(project_root, {
        "action": "create_crm_lead",
        "user_id": identity["user_id"],
        "role": identity["role"],
        "lead_id": lead["lead_id"],
    })
    return lead


def patch_crm_lead(lead_id: str, payload: dict[str, Any], auth_identity: dict[str, Any], project_root: Path) -> dict[str, Any]:
    identity = _trusted_identity(auth_identity)
    _require_sales_role(identity)
    lead = load_lead(project_root, lead_id)
    if lead is None:
        raise ValueError(f"lead not found: {lead_id}")
    if not _crm_lead_visible_to(lead, identity):
        raise ValueError(f"lead not found or not accessible")

    updatable = {"next_followup_at", "assigned_consultant_id", "weak_subjects", "budget_range",
                  "current_score", "subject_type", "target_school_level"}
    for key in updatable:
        if key in payload:
            lead[key] = payload[key]

    from leads import _save_lead
    _save_lead(project_root, lead)
    return lead


def add_crm_lead_followup(
    lead_id: str, payload: dict[str, Any], auth_identity: dict[str, Any], project_root: Path
) -> dict[str, Any]:
    identity = _trusted_identity(auth_identity)
    _require_sales_role(identity)
    lead = load_lead(project_root, lead_id)
    if lead is None:
        raise ValueError(f"lead not found: {lead_id}")
    if not _crm_lead_visible_to(lead, identity):
        raise ValueError(f"lead not found or not accessible")

    note = str(payload.get("note", "")).strip()
    if not note:
        raise ValueError("followup note is required")

    result = add_followup_to_lead(
        project_root, lead_id,
        consultant_id=identity["user_id"],
        note=note,
        followup_type=str(payload.get("followup_type", "general")),
        next_followup_at=str(payload.get("next_followup_at", "")),
        identity=identity,
    )
    audit_log(project_root, {
        "action": "add_crm_lead_followup",
        "user_id": identity["user_id"],
        "role": identity["role"],
        "lead_id": lead_id,
        "followup_type": payload.get("followup_type", "general"),
    })
    return result


def assign_crm_lead(lead_id: str, payload: dict[str, Any], auth_identity: dict[str, Any], project_root: Path) -> dict[str, Any]:
    identity = _trusted_identity(auth_identity)
    _require_sales_role(identity)
    consultant_id = str(payload.get("consultant_id", identity["user_id"]))
    lead = assign_lead(project_root, lead_id, consultant_id, identity)
    audit_log(project_root, {
        "action": "assign_crm_lead",
        "user_id": identity["user_id"],
        "role": identity["role"],
        "lead_id": lead_id,
        "consultant_id": consultant_id,
    })
    return lead


def update_crm_lead_status(
    lead_id: str, payload: dict[str, Any], auth_identity: dict[str, Any], project_root: Path
) -> dict[str, Any]:
    identity = _trusted_identity(auth_identity)
    _require_sales_role(identity)
    lead = load_lead(project_root, lead_id)
    if lead is None:
        raise ValueError(f"lead not found: {lead_id}")
    if not _crm_lead_visible_to(lead, identity):
        raise ValueError(f"lead not found or not accessible")

    new_status = str(payload.get("status", ""))
    if not new_status:
        raise ValueError("status is required")

    lead = update_lead_status(project_root, lead_id, new_status, identity)
    audit_log(project_root, {
        "action": "update_crm_lead_status",
        "user_id": identity["user_id"],
        "role": identity["role"],
        "lead_id": lead_id,
        "status": new_status,
    })
    return lead


def _apply_consultation_result(session: dict[str, Any], result: dict[str, Any]) -> None:
    profile = dict(result.get("profile") or session.get("profile") or {})
    completeness = float(result.get("profile_completeness") or 0)
    stage = str(result.get("consultation_stage") or "")
    recommendation = result.get("recommendation_result") or session.get("recommendation_result") or {}

    profile["_completeness"] = completeness
    profile["consultation_stage"] = stage
    session["profile"] = profile
    session["profile_completeness"] = completeness
    session["consultation_stage"] = stage
    session["recommendation_result"] = recommendation
    session["risk_level"] = result.get("risk_level", "low")
    session["next_best_action"] = determine_next_best_action(
        profile=profile,
        profile_completeness=completeness,
        consultation_stage=stage,
        recommendation=recommendation,
    )
    session["risk_tags"] = _extract_risk_tags(session)


def _find_lead_id_for_session(project_root: Path, session_id: str) -> str:
    from leads import _leads_dir
    import json as _json
    leads_dir = _leads_dir(project_root)
    if leads_dir.exists():
        for path in leads_dir.glob("*.json"):
            lead = _json.loads(path.read_text(encoding="utf-8"))
            if lead.get("session_id") == session_id:
                return lead["lead_id"]
    return ""


def _lead_summary(lead: dict[str, Any]) -> dict[str, Any]:
    return {
        "lead_id": lead["lead_id"],
        "session_id": lead.get("session_id"),
        "status": lead.get("status"),
        "intent_level": lead.get("intent_level"),
        "score": lead.get("score"),
        "assigned_consultant_id": lead.get("assigned_consultant_id"),
        "created_at": lead.get("created_at"),
    }


def _crm_lead_visible_to(lead: dict[str, Any], identity: dict[str, Any]) -> bool:
    from leads import _visible_to
    return _visible_to(lead, identity)


def _extract_profile_from_payload(payload: dict[str, Any]) -> dict[str, Any]:
    profile: dict[str, Any] = {}
    for key in ("current_score", "subject_type", "target_school_level", "weak_subjects", "budget_range"):
        if key in payload and payload[key]:
            profile[key] = payload[key]
    return profile


def _session_apply_fsm_event(session: dict[str, Any], project_root: Path, session_id: str, event_name: str) -> None:
    try:
        import sys
        fsm_src = str(project_root / "services" / "agent-orchestrator" / "src")
        if fsm_src not in sys.path:
            sys.path.insert(0, fsm_src)
        from fsm.machine import SessionEvent, SessionMachine
        current = session.get("fsm_state", "CONSULTING")
        machine = SessionMachine(current)
        event_map: dict[str, str] = {
            "handoff_requested": SessionEvent.HANDOFF_REQUESTED,
            "human_accepted": SessionEvent.HUMAN_ACCEPTED,
            "followup_created": SessionEvent.FOLLOWUP_CREATED,
        }
        if event_name in event_map:
            machine.transition(event_map[event_name])
            session["fsm_state"] = machine.state.value
            _save_session(project_root, session_id, session)
    except Exception:
        pass


def _build_profile_summary_card(session: dict[str, Any]) -> dict[str, Any]:
    profile = session.get("profile", {})
    missing = []
    if not profile.get("subject_type"):
        missing.append("subject_type")
    if not profile.get("current_score"):
        missing.append("current_score")
    if not profile.get("target_school_level"):
        missing.append("target_school_level")

    return {
        "identity_type": profile.get("identity_type", "unknown"),
        "province": profile.get("province", ""),
        "subject_type": profile.get("subject_type", ""),
        "current_score": profile.get("current_score"),
        "target_score": profile.get("target_score"),
        "target_school_level": profile.get("target_school_level", ""),
        "weak_subjects": profile.get("weak_subjects", []),
        "strong_subjects": profile.get("strong_subjects", []),
        "self_discipline_level": profile.get("self_discipline_level", ""),
        "budget_range": profile.get("budget_range", ""),
        "preferred_campus": profile.get("preferred_campus", ""),
        "preferred_class_type": profile.get("preferred_class_type", ""),
        "boarding_preference": profile.get("boarding_preference", ""),
        "parent_concerns": profile.get("parent_concerns", []),
        "student_concerns": profile.get("student_concerns", []),
        "completeness": profile.get("_completeness", 0),
        "missing_fields": missing,
    }


def _build_recommendation_card(session: dict[str, Any]) -> dict[str, Any]:
    rec = session.get("recommendation_result", {})
    if not isinstance(rec, dict):
        rec = {}
    return {
        "recommended_class_type": rec.get("recommended_class_type", ""),
        "confidence": rec.get("confidence", "low"),
        "reasons": rec.get("reasons", []),
        "not_suitable_if": rec.get("not_suitable_if", []),
        "missing_info": rec.get("missing_info", []),
        "next_questions": rec.get("next_questions", []),
    }


def _build_next_best_action_card(session: dict[str, Any]) -> dict[str, Any]:
    nba = session.get("next_best_action", {})
    if not isinstance(nba, dict):
        nba = {}
    return {
        "action": nba.get("action", "continue_conversation"),
        "description": nba.get("description", ""),
        "priority": nba.get("priority", "medium"),
    }


def _extract_risk_tags(session: dict[str, Any]) -> list[str]:
    risks: list[str] = []
    profile = session.get("profile", {})
    if not profile.get("current_score"):
        risks.append("missing_score")
    if not profile.get("subject_type"):
        risks.append("missing_subject_type")
    if session.get("intent", {}).get("intent") == "promise_risk":
        risks.append("promise_seeking")
    if session.get("risk_level") == "high":
        risks.append("high_risk_session")
    if profile.get("self_discipline_level") == "low":
        risks.append("low_discipline")
    if not profile.get("target_school_level"):
        risks.append("missing_school_level")
    return risks


def _session_summary(session: dict[str, Any]) -> dict[str, Any]:
    return {
        "session_id": session["session_id"],
        "user_id": session.get("user_id"),
        "role": session.get("role"),
        "campus": session.get("campus"),
        "updated_at": session.get("updated_at"),
        "message_count": len(session.get("messages", [])),
        "intent": session.get("intent", {}).get("intent", ""),
        "takeover_status": session.get("takeover_status", "open"),
        "assigned_to": session.get("assigned_to"),
    }


def _extract_profile(session: dict[str, Any]) -> dict[str, Any]:
    stored_profile = session.get("profile", {})
    profile: dict[str, Any] = dict(stored_profile) if isinstance(stored_profile, dict) else {}
    profile.update({
        "user_id": session.get("user_id"),
        "role": session.get("role"),
        "campus": session.get("campus"),
    })

    all_text = " ".join(
        m["content"] for m in session.get("messages", [])
        if isinstance(m, dict) and m.get("role") == "user"
    )

    from profile_model import extract_profile_from_message
    patch = extract_profile_from_message(all_text, profile)
    for key, value in patch.updates.items():
        if key not in profile and value:
            profile[key] = value

    import re
    score_match = re.search(r"(\d{3})\s*分", all_text)
    if score_match and not profile.get("current_score"):
        profile["current_score"] = int(score_match.group(1))

    for key, pattern in [
        ("target_score", r"目标.*?(\d{3})\s*分"),
        ("subject_type", r"(物理类|历史类|文理)"),
    ]:
        m = re.search(pattern, all_text)
        if m and not profile.get(key):
            profile[key] = m.group(1)

    subjects = ["数学", "英语", "语文", "物理", "化学", "生物", "历史", "地理", "政治"]
    best_subject = ""
    best_dist = 999
    for subj in subjects:
        subj_pos = all_text.find(subj)
        if subj_pos < 0:
            continue
        for kw in ["差", "弱", "不好", "不行"]:
            kw_pos = all_text.find(kw, subj_pos)
            if kw_pos < 0:
                continue
            dist = kw_pos - subj_pos
            if dist < best_dist and dist < 30:
                best_dist = dist
                best_subject = subj
    if best_subject and not profile.get("weak_subjects"):
        profile["weak_subjects"] = best_subject

    profile["_completeness"] = session.get("profile_completeness", profile.get("_completeness", 0))
    profile["consultation_stage"] = session.get("consultation_stage", profile.get("consultation_stage", ""))
    profile["recommendation_summary"] = session.get("recommendation_result", {})
    profile["next_best_action"] = session.get("next_best_action", {})
    profile["risk_tags"] = session.get("risk_tags", [])

    return profile


def _build_internal_suggestions(session: dict[str, Any], identity: dict[str, Any]) -> list[str]:
    suggestions: list[str] = []
    profile = _extract_profile(session)
    intent = session.get("intent", {}).get("intent", "")
    user_messages = [
        m["content"] for m in session.get("messages", [])
        if m.get("role") == "user"
    ]

    if profile.get("current_score"):
        suggestions.append(f"学生当前成绩约{profile['current_score']}分，建议了解目标院校及分数线")

    if profile.get("weak_subjects"):
        suggestions.append(f"检测到薄弱科目：{profile['weak_subjects']}，可推荐专项补弱方案")

    if intent == "pricing_consulting":
        suggestions.append("用户关注费用，优先引导到校或预约顾问说明费用构成")

    if len(user_messages) <= 1:
        suggestions.append("用户信息不足，建议继续收集分数、科类、目标和薄弱科目")

    if "报名" in str(user_messages) or "入学" in str(user_messages):
        suggestions.append("用户有报名意向，建议尽快跟进确认并邀请到校测评")

    suggestions.append("注意：以上建议仅供顾问内部使用，不应原样发送给家长或学生")
    return suggestions


def _visible_to_sales(session: dict[str, Any], identity: dict[str, Any]) -> bool:
    if identity["role"] in {"admin", "campus_admin"}:
        return identity.get("campus") in (
            session.get("campus", "all"), "all", session.get("assign_campus")
        )
    if identity.get("campus", "zh") == session.get("campus", "zh"):
        return True
    if identity.get("campus") in ("all", None) or session.get("campus") in ("all", None):
        return True
    return False


def _lead_visible_to(lead: dict[str, Any], identity: dict[str, Any]) -> bool:
    if identity["role"] in {"admin", "campus_admin"}:
        return True
    if identity.get("campus", "zh") == lead.get("campus", "zh"):
        return True
    return False


def _require_sales_role(identity: dict[str, Any]) -> None:
    if identity.get("role") not in SALES_ROLES:
        raise ValueError(f"Sales console access denied for role: {identity.get('role')}")


def _trusted_identity(auth_identity: dict[str, Any]) -> dict[str, Any]:
    return {
        "user_id": auth_identity.get("user_id", "anonymous"),
        "role": auth_identity.get("role", "visitor"),
        "campus": auth_identity.get("campus", "all"),
        "auth_level": auth_identity.get("auth_level", "anonymous"),
    }


def _reject_missing_message(payload: dict[str, Any]) -> None:
    message = str(payload.get("message", "")).strip()
    if not message:
        raise ValueError("message is required")


def _reject_untrusted_fields(payload: dict[str, Any], allowed_fields: set[str]) -> None:
    forbidden = sorted(set(payload) - allowed_fields)
    if forbidden:
        raise ValueError(f"Forbidden request field: {forbidden[0]}")


def _handoff_message(payload: dict[str, Any]) -> str:
    message = str(payload.get("reason") or "").strip()
    if message:
        return message
    return "请求人工顾问跟进"


def _public_citations(citations: list[dict[str, Any]]) -> list[dict[str, str]]:
    safe: list[dict[str, str]] = []
    for citation in citations:
        item = {
            "title": str(citation.get("title") or "来源资料"),
            "source_type": str(citation.get("source_type") or _source_type(citation)),
        }
        section = str(citation.get("section") or "").strip()
        if section:
            item["section"] = section
        safe.append(item)
    return safe


def _source_type(citation: dict[str, Any]) -> str:
    source_uri = str(citation.get("source_uri") or "")
    if "/internal/" in source_uri:
        return "internal_knowledge"
    if "/admin/" in source_uri:
        return "admin_knowledge"
    return "public_knowledge"


def _entrypoint_for(role: str) -> str:
    if role in {"sales", "teacher", "operator", "campus_admin"}:
        return "sales_console"
    if role == "admin":
        return "admin_console"
    return "public_chat"


def _load_session(project_root: Path, session_id: str, identity: dict[str, Any]) -> dict[str, Any]:
    session_path = project_root / "data" / "sessions" / f"{session_id}.json"
    if session_path.exists():
        return json.loads(session_path.read_text(encoding="utf-8"))
    return {
        "session_id": session_id,
        "user_id": identity["user_id"],
        "role": identity["role"],
        "campus": identity["campus"],
        "created_at": _now_iso(),
        "updated_at": _now_iso(),
        "messages": [],
    }


def _save_session(project_root: Path, session_id: str, session: dict[str, Any]) -> None:
    session_dir = project_root / "data" / "sessions"
    session_dir.mkdir(parents=True, exist_ok=True)
    (session_dir / f"{session_id}.json").write_text(
        json.dumps(session, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _new_session_id() -> str:
    return f"s_{uuid.uuid4().hex[:12]}"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _recommended_actions(message: str, result: dict[str, Any]) -> list[str]:
    actions: list[str] = []
    if result.get("handoff_triggered"):
        actions.append("high_risk_crisis: 系统检测到高风险情绪信号，建议立即人工跟进")
    if result["intent"]["intent"] == "class_recommendation":
        actions.append("建议预约学情评估")
    if "学费" in message or "优惠" in message or result["intent"]["intent"] == "pricing_consulting":
        actions.append("建议转顾问进一步说明费用口径")
    if result["retrieval"]["confidence"] < 0.3:
        actions.append("当前资料命中较弱，建议人工跟进")
    return actions


def _should_hide_sources(identity: dict[str, Any]) -> bool:
    role = identity.get("role", "visitor")
    return role not in PRIVILEGED_ROLES


def _strip_source_lines(answer: str) -> str:
    lines = answer.splitlines()
    cleaned: list[str] = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("来源：") or stripped.startswith("参考资料") or stripped.startswith("引用来源"):
            continue
        cleaned.append(line)
    return "\n".join(cleaned)


_MECHANICAL_PHRASES = [
    "根据资料显示",
    "根据知识库",
    "来源如下",
    "引用如下",
    "系统判断",
    "检索结果表明",
    "该问题命中",
    "以下是标准答案",
    "综上所述",
    "您可以参考如下信息",
]


def _sanitize_mechanical_phrases(answer: str) -> str:
    result = answer
    for phrase in _MECHANICAL_PHRASES:
        result = result.replace(phrase, "")
    result = result.replace("\n\n\n", "\n\n")
    return result.strip()
