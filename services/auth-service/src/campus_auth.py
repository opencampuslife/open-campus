from __future__ import annotations

import json
import re
import secrets
from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from campus_domain import (
    create_wecom_mapping_state,
    consume_wecom_state,
    resolve_local_identity_for_wecom,
)

SESSION_TTL = timedelta(hours=8)
SESSION_ID_PATTERN = re.compile(r"^wecom_[A-Za-z0-9_-]{16,128}$")


def issue_wecom_state(project_root: Path, redirect_path: str = "/h5") -> dict[str, Any]:
    payload = create_wecom_mapping_state(project_root, redirect_path=redirect_path)
    return {
        "state": payload["state"],
        "redirect_path": payload["redirect_path"],
        "expires_at": payload["expires_at"],
    }


def handle_wecom_callback(
    project_root: Path,
    code: str,
    state: str,
    wecom_adapter: Any,
    identity_resolver: Callable[[str], dict[str, Any] | None] | None = None,
) -> dict[str, Any]:
    if not code:
        raise ValueError("wecom oauth code is required")
    if not state:
        raise ValueError("wecom oauth state is required")
    state_payload = consume_wecom_state(project_root, state)
    userinfo = wecom_adapter.getuserinfo(code)
    wecom_userid = str(userinfo.get("UserId", ""))
    if not wecom_userid:
        raise ValueError("wecom callback missing UserId")

    identity = identity_resolver(wecom_userid) if identity_resolver else None
    if not identity:
        identity = resolve_local_identity_for_wecom(project_root, wecom_userid)
    session_id = f"wecom_{secrets.token_urlsafe(16)}"
    session_payload = {
        "session_id": session_id,
        "identity": identity,
        "redirect_path": state_payload["redirect_path"],
        "wecom_userid": wecom_userid,
        "expires_at": (datetime.now(timezone.utc) + SESSION_TTL).isoformat(),
    }

    session_dir = project_root / "data" / "campus" / "sessions"
    session_dir.mkdir(parents=True, exist_ok=True)
    (session_dir / f"{session_id}.json").write_text(
        json.dumps(session_payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return session_payload


def load_wecom_session_identity(project_root: Path, session_id: str) -> dict[str, Any] | None:
    """Return a server-issued OAuth identity or fail closed for invalid sessions."""
    if not SESSION_ID_PATTERN.fullmatch(session_id):
        return None
    session_path = project_root / "data" / "campus" / "sessions" / f"{session_id}.json"
    if not session_path.exists():
        return None
    try:
        payload = json.loads(session_path.read_text(encoding="utf-8"))
        expires_at = datetime.fromisoformat(str(payload["expires_at"]))
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        if expires_at <= datetime.now(timezone.utc):
            session_path.unlink(missing_ok=True)
            return None
        identity = payload.get("identity")
        if not isinstance(identity, dict) or not identity.get("role") or not identity.get("school_id"):
            return None
        return dict(identity)
    except (KeyError, TypeError, ValueError, json.JSONDecodeError, OSError):
        return None
