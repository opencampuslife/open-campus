from __future__ import annotations

import json
import os
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SENSITIVE_LOG_KEYS = ("token", "secret", "password", "api_key", "access_token", "encoding_aes")


def _redact_log_payload(payload: Any, key: str = "") -> Any:
    if any(part in key.lower() for part in SENSITIVE_LOG_KEYS):
        return "[REDACTED]"
    if isinstance(payload, dict):
        return {name: _redact_log_payload(value, str(name)) for name, value in payload.items()}
    if isinstance(payload, list):
        return [_redact_log_payload(item) for item in payload]
    return payload

TRACE_ID_HEADER = "x-trace-id"
REQUEST_ID_HEADER = "x-request-id"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_trace_id() -> str:
    return uuid.uuid4().hex


def extract_request_id(headers: dict[str, str]) -> str:
    for key in (REQUEST_ID_HEADER, "x-request-id", "x-request-id"):
        val = headers.get(key, "")
        if val:
            return val
    return uuid.uuid4().hex[:16]


def structured_log(
    project_root: Path,
    event_type: str,
    *,
    trace_id: str = "",
    request_id: str = "",
    session_id: str = "",
    lead_id: str = "",
    user_id: str = "",
    role: str = "",
    campus: str = "",
    entrypoint: str = "",
    action: str = "",
    status: str = "ok",
    latency_ms: int = 0,
    details: dict[str, Any] | None = None,
    error: str = "",
) -> dict[str, Any]:
    entry: dict[str, Any] = {
        "timestamp": _now_iso(),
        "event_type": event_type,
        "trace_id": trace_id or new_trace_id(),
        "request_id": request_id,
        "session_id": session_id,
        "lead_id": lead_id,
        "user_id": user_id,
        "role": role,
        "campus": campus,
        "entrypoint": entrypoint,
        "action": action or event_type,
        "status": status,
        "latency_ms": latency_ms,
        "app_env": os.environ.get("GAOKAO_ENV", "development"),
    }

    if details:
        entry["details"] = _redact_log_payload(details)
    if error:
        entry["error"] = error

    log_dir = project_root / "data" / "audit_logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / "structured.jsonl"

    with log_path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry, ensure_ascii=False, default=str) + "\n")

    return entry


class RequestLogger:
    def __init__(self, project_root: Path, identity: dict[str, Any]):
        self.project_root = project_root
        self.trace_id = new_trace_id()
        self.request_id = str(uuid.uuid4().hex)[:16]
        self.identity = identity
        self.t0 = time.monotonic()
        self.events: list[dict[str, Any]] = []

    def _base(self, event_type: str, **kw: Any) -> dict[str, Any]:
        return {
            "timestamp": _now_iso(),
            "event_type": event_type,
            "trace_id": self.trace_id,
            "request_id": self.request_id,
            "user_id": self.identity.get("user_id", "anonymous"),
            "role": self.identity.get("role", "visitor"),
            "campus": self.identity.get("campus", "all"),
            "entrypoint": self.identity.get("entrypoint", ""),
            "latency_ms": int((time.monotonic() - self.t0) * 1000),
            "app_env": os.environ.get("GAOKAO_ENV", "development"),
            **kw,
        }

    def log(self, event_type: str, **kw: Any) -> dict[str, Any]:
        entry = self._base(event_type, **_redact_log_payload(kw))
        self.events.append(entry)
        return entry

    def chat_request(self, session_id: str = "", message_len: int = 0, **kw: Any) -> dict[str, Any]:
        return self.log("chat_request", session_id=session_id, message_length=message_len, **kw)

    def chat_response(self, session_id: str = "", answer_len: int = 0, **kw: Any) -> dict[str, Any]:
        return self.log("chat_response", session_id=session_id, answer_length=answer_len, **kw)

    def handoff(self, session_id: str = "", lead_id: str = "", **kw: Any) -> dict[str, Any]:
        return self.log("handoff", session_id=session_id, lead_id=lead_id, **kw)

    def lead_update(self, lead_id: str = "", **kw: Any) -> dict[str, Any]:
        return self.log("lead_update", lead_id=lead_id, **kw)

    def admin_mutation(self, action: str = "", resource_id: str = "", **kw: Any) -> dict[str, Any]:
        return self.log("admin_mutation", action=action, resource_id=resource_id, **kw)

    def publish(self, doc_id: str = "", **kw: Any) -> dict[str, Any]:
        return self.log("publish", doc_id=doc_id, **kw)

    def recommendation(self, class_type: str = "", confidence: float = 0.0, **kw: Any) -> dict[str, Any]:
        return self.log("recommendation", class_type=class_type, confidence=confidence, **kw)

    def security_event(self, event_type: str = "", **kw: Any) -> dict[str, Any]:
        return self.log(event_type, status="blocked", **kw)

    def flush(self) -> None:
        log_dir = self.project_root / "data" / "audit_logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        log_path = log_dir / "structured.jsonl"
        with log_path.open("a", encoding="utf-8") as fh:
            for entry in self.events:
                fh.write(json.dumps(entry, ensure_ascii=False, default=str) + "\n")
        self.events.clear()
