from __future__ import annotations

import json
import os
import ssl
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import certifi


Transport = Callable[[str, str, dict[str, Any] | None, dict[str, Any] | None], dict[str, Any]]
TOKEN_QUERY = re.compile(r"([?&](?:t|token|access_token)=)[^&\s]+", re.IGNORECASE)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _ssl_context() -> ssl.SSLContext:
    return ssl.create_default_context(cafile=certifi.where())


def _campus_dir(project_root: Path) -> Path:
    path = project_root / "data" / "campus" / "wecom"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _redact(payload: dict[str, Any]) -> dict[str, Any]:
    cleaned: dict[str, Any] = {}
    for key, value in payload.items():
        low = key.lower()
        if any(token in low for token in ("secret", "token", "key", "password")):
            cleaned[key] = "[REDACTED]"
        elif isinstance(value, str):
            cleaned[key] = TOKEN_QUERY.sub(r"\1[REDACTED]", value)
        elif isinstance(value, dict):
            cleaned[key] = _redact(value)
        elif isinstance(value, list):
            cleaned[key] = [
                TOKEN_QUERY.sub(r"\1[REDACTED]", item) if isinstance(item, str) else item
                for item in value
            ]
        else:
            cleaned[key] = value
    return cleaned


class WeComAdapter:
    def __init__(self, project_root: Path, transport: Transport | None = None) -> None:
        self.project_root = project_root
        self.transport = transport or self._default_transport

    def _token_cache_path(self) -> Path:
        return _campus_dir(self.project_root) / "token_cache.json"

    def _audit_path(self) -> Path:
        return _campus_dir(self.project_root) / "wecom_audit.jsonl"

    def _write_audit(self, action: str, status: str, payload: dict[str, Any], response: dict[str, Any] | None = None) -> None:
        record = {
            "action": action,
            "status": status,
            "payload": _redact(payload),
            "response": _redact(response or {}),
            "created_at": _now().isoformat(),
        }
        with self._audit_path().open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")

    def _default_transport(
        self,
        method: str,
        endpoint: str,
        params: dict[str, Any] | None = None,
        body: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        mode = os.environ.get("WECOM_TRANSPORT_MODE", "stub").lower()
        if mode != "live":
            if endpoint == "/cgi-bin/gettoken":
                return {"errcode": 0, "access_token": "stub-access-token", "expires_in": 7200}
            if endpoint == "/cgi-bin/user/getuserinfo":
                code = str((params or {}).get("code", ""))
                user_id = code.replace("code_", "") or "teacher_001"
                return {"errcode": 0, "UserId": user_id, "DeviceId": "stub-device"}
            if endpoint.endswith("/send"):
                return {"errcode": 0, "msgid": "stub-msg"}
            if endpoint == "/cgi-bin/media/upload":
                return {"errcode": 0, "media_id": "stub-media", "created_at": int(_now().timestamp())}
            return {"errcode": 0}

        base = "https://qyapi.weixin.qq.com"
        params = params or {}
        url = f"{base}{endpoint}"
        if params:
            url += "?" + urlencode({key: value for key, value in params.items() if value is not None})
        data = None
        headers = {"Content-Type": "application/json"}
        if body is not None:
            data = json.dumps(body, ensure_ascii=False).encode("utf-8")
        request = Request(url, data=data, method=method.upper(), headers=headers)
        with urlopen(request, timeout=10, context=_ssl_context()) as response:
            return json.loads(response.read().decode("utf-8"))

    def get_access_token(self, force_refresh: bool = False) -> str:
        path = self._token_cache_path()
        if not force_refresh and path.exists():
            cached = json.loads(path.read_text(encoding="utf-8"))
            expires_at = datetime.fromisoformat(str(cached.get("expires_at")))
            if expires_at > _now():
                return str(cached["access_token"])

        payload = {
            "corpid": os.environ.get("WECOM_CORP_ID", "demo-corp"),
            "corpsecret": os.environ.get("WECOM_APP_SECRET", "demo-secret"),
        }
        response = self.transport("GET", "/cgi-bin/gettoken", payload, None)
        if int(response.get("errcode", 0)) != 0:
            self._write_audit("get_access_token", "failed", payload, response)
            raise ValueError(f"wecom gettoken failed: {response.get('errmsg', 'unknown')}")

        cache = {
            "access_token": response["access_token"],
            "expires_at": (_now() + timedelta(seconds=min(int(response.get("expires_in", 7200)), 7000))).isoformat(),
        }
        path.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")
        self._write_audit("get_access_token", "ok", payload, {"expires_in": response.get("expires_in", 7200)})
        return str(response["access_token"])

    def getuserinfo(self, code: str) -> dict[str, Any]:
        token = self.get_access_token()
        params = {"access_token": token, "code": code}
        response = self.transport("GET", "/cgi-bin/user/getuserinfo", params, None)
        if int(response.get("errcode", 0)) != 0:
            self._write_audit("getuserinfo", "failed", {"code": code}, response)
            raise ValueError(f"wecom getuserinfo failed: {response.get('errmsg', 'unknown')}")
        self._write_audit("getuserinfo", "ok", {"code": code}, {"UserId": response.get("UserId", "")})
        return response

    def send_app_message(self, payload: dict[str, Any]) -> dict[str, Any]:
        token = self.get_access_token()
        response = self.transport("POST", "/cgi-bin/message/send", {"access_token": token}, payload)
        status = "ok" if int(response.get("errcode", 0)) == 0 else "failed"
        self._write_audit("message.send", status, payload, response)
        if status != "ok":
            raise ValueError(f"wecom message send failed: {response.get('errmsg', 'unknown')}")
        return response

    def send_school_notification(self, payload: dict[str, Any]) -> dict[str, Any]:
        token = self.get_access_token()
        response = self.transport("POST", "/cgi-bin/externalcontact/message/send", {"access_token": token}, payload)
        status = "ok" if int(response.get("errcode", 0)) == 0 else "failed"
        self._write_audit("school_notice.send", status, payload, response)
        if status != "ok":
            raise ValueError(f"wecom school notification failed: {response.get('errmsg', 'unknown')}")
        return response

    def send_webhook(self, key: str, payload: dict[str, Any]) -> dict[str, Any]:
        response = self.transport("POST", "/cgi-bin/webhook/send", {"key": key}, payload)
        status = "ok" if int(response.get("errcode", 0)) == 0 else "failed"
        self._write_audit("webhook.send", status, {"key": key, **payload}, response)
        if status != "ok":
            raise ValueError(f"wecom webhook failed: {response.get('errmsg', 'unknown')}")
        return response

    def upload_media(self, media_type: str, filename: str) -> dict[str, Any]:
        token = self.get_access_token()
        payload = {"access_token": token, "type": media_type, "filename": filename}
        response = self.transport("POST", "/cgi-bin/media/upload", payload, None)
        status = "ok" if int(response.get("errcode", 0)) == 0 else "failed"
        self._write_audit("media.upload", status, payload, response)
        if status != "ok":
            raise ValueError(f"wecom media upload failed: {response.get('errmsg', 'unknown')}")
        return response
