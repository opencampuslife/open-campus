#!/usr/bin/env python3
"""Generate golden fixtures for provider_deepseek.py -> providerDeepseek.ts parity."""

from __future__ import annotations

import json
import os
import sys
import urllib.error
from io import BytesIO
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
GATEWAY_SRC = ROOT / "services" / "llm-gateway" / "src"
sys.path.append(str(GATEWAY_SRC))

from provider_deepseek import chat_completion  # noqa: E402


class MockHTTPError(urllib.error.HTTPError):
    def __init__(self, url, code, msg, hdrs, fp_bytes):
        self._fp_bytes = fp_bytes
        super().__init__(url, code, msg, hdrs, BytesIO(fp_bytes) if fp_bytes else None)


def make_fixture(desc, messages, model, mock, api_key=None, base_url=None, timeout=30.0):
    """Create a fixture entry by running the Python function."""
    captured = {}

    if mock.get("type") == "http_error":
        code = mock["code"]
        detail = mock.get("detail", '{"error": {"message": "error"}}')
        detail_bytes = detail.encode("utf-8")

        def transport(req, t_out):
            captured["url"] = req.full_url
            captured["headers"] = dict(req.header_items())
            captured["body"] = json.loads(req.data.decode("utf-8"))
            captured["method"] = req.method
            captured["timeout"] = t_out
            raise MockHTTPError(req.full_url, code, "Error", {}, detail_bytes)

        try:
            chat_completion(
                messages,
                model=model,
                base_url=base_url,
                api_key=api_key,
                timeout=timeout,
                transport=transport,
            )
            output = {"ok": True, "result": None}
        except RuntimeError as e:
            output = {"ok": False, "error": "RuntimeError", "message": str(e)}
        except Exception as e:
            output = {"ok": False, "error": type(e).__name__, "message": str(e)}

    elif mock.get("type") == "uri_error":
        reason = mock.get("reason", "connection refused")

        def transport(req, t_out):
            captured["url"] = req.full_url
            captured["headers"] = dict(req.header_items())
            captured["body"] = json.loads(req.data.decode("utf-8"))
            captured["method"] = req.method
            captured["timeout"] = t_out
            raise urllib.error.URLError(reason)

        try:
            chat_completion(
                messages,
                model=model,
                base_url=base_url,
                api_key=api_key,
                timeout=timeout,
                transport=transport,
            )
            output = {"ok": True, "result": None}
        except RuntimeError as e:
            output = {"ok": False, "error": "RuntimeError", "message": str(e)}
        except Exception as e:
            output = {"ok": False, "error": type(e).__name__, "message": str(e)}

    elif mock.get("type") == "success":
        response_body = mock.get("response_body", {"choices": [{"message": {"content": "Hello!"}}]})

        def transport(req, t_out):
            captured["url"] = req.full_url
            captured["headers"] = dict(req.header_items())
            captured["body"] = json.loads(req.data.decode("utf-8"))
            captured["method"] = req.method
            captured["timeout"] = t_out
            return json.dumps(response_body, ensure_ascii=False).encode("utf-8")

        try:
            result = chat_completion(
                messages,
                model=model,
                base_url=base_url,
                api_key=api_key,
                timeout=timeout,
                transport=transport,
            )
            output = {"ok": True, "result": result}
        except RuntimeError as e:
            output = {"ok": False, "error": "RuntimeError", "message": str(e)}
        except Exception as e:
            output = {"ok": False, "error": type(e).__name__, "message": str(e)}

    else:
        raise ValueError(f"Unknown mock type: {mock.get('type')}")

    base_url_resolved = base_url or os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
    base_url_resolved = base_url_resolved.rstrip("/")

    req_headers = {k: v for k, v in captured.get("headers", {}).items()}
    payload_body = captured.get("body", {})

    request_snapshot = {
        "url": captured.get("url", f"{base_url_resolved}/chat/completions"),
        "method": captured.get("method", "POST"),
        "headers": req_headers,
        "body": payload_body,
    }

    return {
        "desc": desc,
        "input": {
            "messages": messages,
            "model": model,
            "base_url": base_url,
            "api_key": api_key,
            "timeout": timeout,
        },
        "mock": mock,
        "output": output,
        "request_snapshot": request_snapshot,
    }


def main():
    fixtures = []

    msgs_basic = [{"role": "user", "content": "Hello"}]
    msgs_multi = [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "What is 2+2?"},
    ]
    msgs_unicode = [{"role": "user", "content": "你好，请问学费多少？"}]
    msgs_emoji = [{"role": "user", "content": "\U0001f60a欢迎咨询"}]

    # 1. Minimal valid request
    fixtures.append(make_fixture(
        "minimal valid request",
        msgs_basic, "deepseek-chat",
        {"type": "success", "response_body": {"choices": [{"message": {"content": "Hello!"}}]}},
        api_key="test-key-12345",
    ))

    # 2. Full valid request
    fixtures.append(make_fixture(
        "full valid request with base_url",
        msgs_basic, "deepseek-v4-flash",
        {"type": "success", "response_body": {"choices": [{"message": {"content": "ok"}}]}},
        api_key="test-key-12345",
        base_url="https://api.deepseek.com",
    ))

    # 3. Multi-turn messages
    fixtures.append(make_fixture(
        "multi-turn messages",
        msgs_multi, "deepseek-chat",
        {"type": "success", "response_body": {"choices": [{"message": {"content": "2+2 equals 4."}}]}},
        api_key="test-key-12345",
    ))

    # 4. API key from env var
    old_key = os.environ.get("DEEPSEEK_API_KEY")
    os.environ["DEEPSEEK_API_KEY"] = "env-key-abc"
    fixtures.append(make_fixture(
        "API key from env var",
        msgs_basic, "deepseek-chat",
        {"type": "success", "response_body": {"choices": [{"message": {"content": "Hello!"}}]}},
        api_key=None,
    ))
    if old_key:
        os.environ["DEEPSEEK_API_KEY"] = old_key
    else:
        del os.environ["DEEPSEEK_API_KEY"]

    # 5. Missing API key
    old_key2 = os.environ.get("DEEPSEEK_API_KEY")
    if "DEEPSEEK_API_KEY" in os.environ:
        del os.environ["DEEPSEEK_API_KEY"]
    fixtures.append(make_fixture(
        "missing API key raises RuntimeError",
        msgs_basic, "deepseek-chat",
        {"type": "uri_error", "reason": ""},
        api_key=None,
    ))
    fixtures[-1]["output"] = {"ok": False, "error": "RuntimeError", "message": "DEEPSEEK_API_KEY is not set"}
    fixtures[-1]["request_snapshot"] = {}
    if old_key2:
        os.environ["DEEPSEEK_API_KEY"] = old_key2
    else:
        os.environ.pop("DEEPSEEK_API_KEY", None)

    # 6. Unicode Chinese response
    fixtures.append(make_fixture(
        "unicode Chinese response",
        msgs_unicode, "deepseek-chat",
        {"type": "success", "response_body": {"choices": [{"message": {"content": "复读班学费：9800元/学期"}}]}},
        api_key="test-key-12345",
    ))

    # 7. Emoji response
    fixtures.append(make_fixture(
        "emoji response",
        msgs_emoji, "deepseek-chat",
        {"type": "success", "response_body": {"choices": [{"message": {"content": "\U0001f60a欢迎咨询我们的课程！"}}]}},
        api_key="test-key-12345",
    ))

    # 8. Provider returns usage
    fixtures.append(make_fixture(
        "provider returns usage",
        msgs_basic, "deepseek-chat",
        {"type": "success", "response_body": {
            "choices": [{"message": {"content": "Usage info"}}],
            "usage": {"prompt_tokens": 15, "completion_tokens": 5, "total_tokens": 20},
        }},
        api_key="test-key-12345",
    ))

    # 9. Provider does not return usage
    fixtures.append(make_fixture(
        "provider does not return usage",
        msgs_basic, "deepseek-chat",
        {"type": "success", "response_body": {
            "choices": [{"message": {"content": "No usage"}}],
        }},
        api_key="test-key-12345",
    ))

    # 10. HTTP 400
    fixtures.append(make_fixture(
        "HTTP 400 Bad Request",
        msgs_basic, "deepseek-chat",
        {"type": "http_error", "code": 400, "detail": '{"error":{"message":"Invalid request","type":"invalid_request_error"}}'},
        api_key="test-key-12345",
    ))

    # 11. HTTP 401
    fixtures.append(make_fixture(
        "HTTP 401 Unauthorized",
        msgs_basic, "deepseek-chat",
        {"type": "http_error", "code": 401, "detail": '{"error":{"message":"Invalid API key","type":"authentication_error"}}'},
        api_key="test-key-12345",
    ))

    # 12. HTTP 429
    fixtures.append(make_fixture(
        "HTTP 429 Rate Limited",
        msgs_basic, "deepseek-chat",
        {"type": "http_error", "code": 429, "detail": '{"error":{"message":"Rate limit exceeded","type":"rate_limit_error"}}'},
        api_key="test-key-12345",
    ))

    # 13. HTTP 500
    fixtures.append(make_fixture(
        "HTTP 500 Server Error",
        msgs_basic, "deepseek-chat",
        {"type": "http_error", "code": 500, "detail": '{"error":{"message":"Internal server error","type":"server_error"}}'},
        api_key="test-key-12345",
    ))

    # 14. Response missing choices -> KeyError
    fixtures.append(make_fixture(
        "response missing choices field",
        msgs_basic, "deepseek-chat",
        {"type": "success", "response_body": {"id": "123"}},
        api_key="test-key-12345",
    ))

    # 15. Response choices empty -> IndexError
    fixtures.append(make_fixture(
        "response choices is empty array",
        msgs_basic, "deepseek-chat",
        {"type": "success", "response_body": {"choices": []}},
        api_key="test-key-12345",
    ))

    # 16. Response message missing content -> KeyError
    fixtures.append(make_fixture(
        "response message missing content",
        msgs_basic, "deepseek-chat",
        {"type": "success", "response_body": {"choices": [{"index": 0, "message": {}}]}},
        api_key="test-key-12345",
    ))

    # 17. Response message missing entirely -> KeyError
    fixtures.append(make_fixture(
        "response choices[0] missing message",
        msgs_basic, "deepseek-chat",
        {"type": "success", "response_body": {"choices": [{"index": 0}]}},
        api_key="test-key-12345",
    ))

    # 18. Non-JSON response
    captured_invalid = {}
    def transport_invalid(req, t_out):
        captured_invalid["url"] = req.full_url
        captured_invalid["headers"] = dict(req.header_items())
        captured_invalid["body"] = json.loads(req.data.decode("utf-8"))
        captured_invalid["method"] = req.method
        captured_invalid["timeout"] = t_out
        return b"This is not JSON"

    try:
        chat_completion(
            msgs_basic, model="deepseek-chat",
            api_key="test-key-12345",
            transport=transport_invalid,
        )
        output = {"ok": True, "result": None}
    except RuntimeError as e:
        output = {"ok": False, "error": "RuntimeError", "message": str(e)}
    except json.JSONDecodeError as e:
        output = {"ok": False, "error": "JSONDecodeError", "message": str(e)}
    except Exception as e:
        output = {"ok": False, "error": type(e).__name__, "message": str(e)}

    base_url_def = os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com").rstrip("/")
    fixtures.append({
        "desc": "non-JSON response error",
        "input": {
            "messages": msgs_basic,
            "model": "deepseek-chat",
            "base_url": None,
            "api_key": "test-key-12345",
            "timeout": 30.0,
        },
        "mock": {"type": "invalid_json", "body": "This is not JSON"},
        "output": output,
        "request_snapshot": {
            "url": captured_invalid.get("url", f"{base_url_def}/chat/completions"),
            "method": captured_invalid.get("method", "POST"),
            "headers": {k: v for k, v in captured_invalid.get("headers", {}).items()},
            "body": captured_invalid.get("body", {}),
        },
    })

    # 19. Timeout (simulated as URLError)
    fixtures.append(make_fixture(
        "timeout raises RuntimeError",
        msgs_basic, "deepseek-chat",
        {"type": "uri_error", "reason": "timed out"},
        api_key="test-key-12345",
    ))

    # 20. Network error
    fixtures.append(make_fixture(
        "network error raises RuntimeError",
        msgs_basic, "deepseek-chat",
        {"type": "uri_error", "reason": "Connection refused"},
        api_key="test-key-12345",
    ))

    # 21. Stream field always false
    fixtures.append(make_fixture(
        "stream field always false in payload",
        msgs_basic, "deepseek-chat",
        {"type": "success", "response_body": {"choices": [{"message": {"content": "ok"}}]}},
        api_key="test-key-12345",
    ))

    # 22. Temperature and max_tokens absent from payload
    fixtures.append(make_fixture(
        "temperature and max_tokens absent from payload",
        msgs_basic, "deepseek-chat",
        {"type": "success", "response_body": {"choices": [{"message": {"content": "ok"}}]}},
        api_key="test-key-12345",
    ))

    # 23. Custom base_url env var
    old_base = os.environ.get("DEEPSEEK_BASE_URL")
    os.environ["DEEPSEEK_BASE_URL"] = "https://custom.deepseek.com"
    os.environ["DEEPSEEK_API_KEY"] = "env-key-base-url"
    fixtures.append(make_fixture(
        "custom base_url from env var",
        msgs_basic, "deepseek-chat",
        {"type": "success", "response_body": {"choices": [{"message": {"content": "Hello!"}}]}},
        api_key=None,
    ))
    if old_base:
        os.environ["DEEPSEEK_BASE_URL"] = old_base
    else:
        os.environ.pop("DEEPSEEK_BASE_URL", None)
    os.environ.pop("DEEPSEEK_API_KEY", None)

    # 24. Multi-turn messages with unicode
    msgs_multi_unicode = [
        {"role": "system", "content": "你是复读学校招生助手"},
        {"role": "user", "content": "全日制复读班学费多少？"},
    ]
    fixtures.append(make_fixture(
        "multi-turn messages with unicode",
        msgs_multi_unicode, "deepseek-chat",
        {"type": "success", "response_body": {"choices": [{"message": {"content": "全日制复读班学费为9800元/学期。"}}]}},
        api_key="test-key-12345",
    ))

    # 25. Default base_url (no env, no param)
    os.environ["DEEPSEEK_API_KEY"] = "test-key-default-url"
    fixtures.append(make_fixture(
        "default base_url used when not specified",
        msgs_basic, "deepseek-chat",
        {"type": "success", "response_body": {"choices": [{"message": {"content": "ok"}}]}},
        api_key=None,
    ))
    os.environ.pop("DEEPSEEK_API_KEY", None)

    output_path = ROOT / "ts-migration" / "fixtures" / "provider_deepseek.json"
    output_path.write_text(
        json.dumps(fixtures, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(f"Generated {len(fixtures)} fixtures \u2192 {output_path}")


if __name__ == "__main__":
    main()
