from __future__ import annotations

import re
from typing import Any


PHONE_RE = re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)")
KEY_RE = re.compile(r"sk-[A-Za-z0-9]{8,}")


def redact_text(text: str) -> str:
    text = PHONE_RE.sub("[REDACTED_PHONE]", text)
    text = KEY_RE.sub("[REDACTED_API_KEY]", text)
    return text


def redact_payload(payload: Any) -> Any:
    if isinstance(payload, str):
        return redact_text(payload)
    if isinstance(payload, list):
        return [redact_payload(item) for item in payload]
    if isinstance(payload, dict):
        return {key: redact_payload(value) for key, value in payload.items()}
    return payload

