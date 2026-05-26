from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timezone, timedelta

CST = timezone(timedelta(hours=8))


def generate_raw_token() -> tuple[str, str]:
    raw_token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
    return raw_token, token_hash


def token_to_hash(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode()).hexdigest()


def expires_at(minutes: int = 180) -> datetime:
    return datetime.now(CST) + timedelta(minutes=minutes)
