from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from event_schema import AuditEvent, EventType


def _audit_dir(project_root: Path) -> Path:
    d = project_root / "data" / "audit" / "events"
    d.mkdir(parents=True, exist_ok=True)
    return d


def write_audit_event(project_root: Path, event: AuditEvent) -> str:
    d = _audit_dir(project_root)
    event_dict = event.to_dict()
    event_dict.pop("SENSITIVE_FIELDS", None)

    timestamp = event.timestamp or datetime.now(timezone.utc).isoformat()
    date_prefix = timestamp[:10].replace("-", "")
    file_path = d / "events_{}.jsonl".format(date_prefix)

    with file_path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(event_dict, ensure_ascii=False, default=str) + "\n")

    return event.event_id


def query_audit_events(
    project_root: Path,
    *,
    trace_id: str = "",
    session_id: str = "",
    lead_id: str = "",
    event_id: str = "",
    user_id: str = "",
    role: str = "",
    event_type: str = "",
    action: str = "",
    status: str = "",
    campus: str = "",
    since: str = "",
    until: str = "",
    limit: int = 100,
    offset: int = 0,
) -> dict[str, Any]:
    d = _audit_dir(project_root)
    results: list[dict[str, Any]] = []

    event_files = sorted(d.glob("events_*.jsonl"), reverse=True)
    for fpath in event_files:
        try:
            for line in fpath.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    ev = json.loads(line)
                except json.JSONDecodeError:
                    continue

                if event_id and ev.get("event_id", "") != event_id:
                    continue
                if trace_id and ev.get("trace_id", "") != trace_id:
                    continue
                if session_id and ev.get("session_id", "") != session_id:
                    continue
                if lead_id and ev.get("lead_id", "") != lead_id:
                    continue
                if user_id and ev.get("user_id", "") != user_id:
                    continue
                if role and ev.get("role", "") != role:
                    continue
                if campus and ev.get("campus", "") != campus and ev.get("campus", "") != "all":
                    continue
                if event_type and ev.get("event_type", "") != event_type:
                    continue
                if action and ev.get("action", "") != action:
                    continue
                if status and ev.get("status", "") != status:
                    continue
                if since and ev.get("timestamp", "") < since:
                    continue
                if until and ev.get("timestamp", "") > until:
                    continue

                results.append(ev)
                if len(results) >= limit + offset:
                    break
            if len(results) >= limit + offset:
                break
        except Exception:
            continue

    total = len(results)
    results = results[offset:offset + limit]

    return {
        "events": results,
        "total": total,
        "limit": limit,
        "offset": offset,
        "count": len(results),
    }


def get_event_by_id(project_root: Path, event_id: str) -> dict[str, Any] | None:
    result = query_audit_events(project_root, event_id=event_id, limit=1)
    events = result.get("events", [])
    return events[0] if events else None


def query_by_trace(project_root: Path, trace_id: str, **kw: Any) -> dict[str, Any]:
    return query_audit_events(project_root, trace_id=trace_id, **kw)


def query_by_session(project_root: Path, session_id: str, **kw: Any) -> dict[str, Any]:
    return query_audit_events(project_root, session_id=session_id, **kw)


def query_by_lead(project_root: Path, lead_id: str, **kw: Any) -> dict[str, Any]:
    return query_audit_events(project_root, lead_id=lead_id, **kw)
