from __future__ import annotations

import re
from typing import Any

SENSITIVE_KEYS = ("secret", "token", "key", "password", "encoding_aes", "access_token")
TOKEN_QUERY = re.compile(r"([?&](?:t|token|access_token)=)[^&\s]+", re.IGNORECASE)


def redact(value: Any, key: str = "") -> Any:
    if any(item in key.lower() for item in SENSITIVE_KEYS):
        return "[REDACTED]"
    if isinstance(value, dict):
        return {str(k): redact(v, str(k)) for k, v in value.items()}
    if isinstance(value, list):
        return [redact(item) for item in value]
    if isinstance(value, str):
        return TOKEN_QUERY.sub(r"\1[REDACTED]", value)
    return value
