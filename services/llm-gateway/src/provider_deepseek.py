from __future__ import annotations

import json
import os
import ssl
import urllib.error
import urllib.request
from typing import Any, Callable

try:
    import certifi
    _CAFILE: str | None = certifi.where()
except ImportError:
    _CAFILE = None

Transport = Callable[[urllib.request.Request, float], bytes]


def chat_completion(
    messages: list[dict[str, str]],
    *,
    model: str,
    base_url: str | None = None,
    api_key: str | None = None,
    timeout: float = 30.0,
    transport: Transport | None = None,
) -> str:
    api_key = api_key or os.environ.get("DEEPSEEK_API_KEY")
    if not api_key:
        raise RuntimeError("DEEPSEEK_API_KEY is not set")

    base_url = (base_url or os.environ.get("DEEPSEEK_BASE_URL") or "https://api.deepseek.com").rstrip("/")
    payload = {
        "model": model,
        "messages": messages,
        "stream": False,
    }
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        f"{base_url}/chat/completions",
        data=body,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        method="POST",
    )

    try:
        raw = (transport or _default_transport)(request, timeout)
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"DeepSeek API error {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"DeepSeek API network error: {exc.reason}") from exc

    data: dict[str, Any] = json.loads(raw.decode("utf-8"))
    return data["choices"][0]["message"]["content"]


def _default_transport(request: urllib.request.Request, timeout: float) -> bytes:
    ctx = None
    if _CAFILE:
        ctx = ssl.create_default_context(cafile=_CAFILE)
    with urllib.request.urlopen(request, timeout=timeout, context=ctx) as response:
        return response.read()

