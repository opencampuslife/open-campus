from __future__ import annotations

import hashlib
import hmac
import os
import secrets
import time
from typing import Any


CSRF_TOKEN_SECRET = os.environ.get("CSRF_TOKEN_SECRET", secrets.token_hex(32))
CSRF_TOKEN_TTL = int(os.environ.get("CSRF_TOKEN_TTL", "3600"))


def _constant_time_compare(a: str, b: str) -> bool:
    return hmac.compare_digest(a.encode("utf-8"), b.encode("utf-8"))


def generate_csrf_token(session_id: str = "") -> str:
    timestamp = str(int(time.time()))
    nonce = secrets.token_hex(4)
    sid_part = session_id[:16] if session_id else "_"
    payload = "{}:{}:{}".format(timestamp, sid_part, nonce)
    mac = hmac.new(
        CSRF_TOKEN_SECRET.encode("utf-8"),
        payload.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return "{}.{}.{}.{}".format(timestamp, sid_part, nonce, mac)


def validate_csrf_token(token: str, session_id: str = "") -> bool:
    try:
        parts = token.split(".")
        if len(parts) != 4:
            return False

        ts_str, sid_part, nonce, mac = parts

        ts = int(ts_str)
        now = int(time.time())
        if now - ts > CSRF_TOKEN_TTL or ts > now + 60:
            return False

        if session_id and session_id[:16] != sid_part and sid_part != "_":
            return False

        payload = "{}:{}:{}".format(ts_str, sid_part, nonce)
        expected = hmac.new(
            CSRF_TOKEN_SECRET.encode("utf-8"),
            payload.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

        return _constant_time_compare(expected, mac)
    except Exception:
        return False


def verify_csrf(headers: dict[str, str], session_id: str = "") -> bool:
    token = headers.get("x-csrf-token", "")
    if not token:
        return False
    return validate_csrf_token(token, session_id)


def is_admin_path(path: str) -> bool:
    return path.startswith("/api/admin/")
