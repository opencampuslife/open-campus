from __future__ import annotations

import json
import logging
import sys
from pathlib import Path
from typing import Any

log = logging.getLogger("message_adapters")
ROOT = Path(__file__).resolve().parents[5]
WECOM_SRC = ROOT / "services" / "wecom-adapter" / "src"
if str(WECOM_SRC) not in sys.path:
    sys.path.insert(0, str(WECOM_SRC))

from wecom_adapter import WeComAdapter  # noqa: E402


class NoopAdapter:
    def send(self, task: dict[str, Any]) -> dict[str, Any]:
        payload = task.get("payload_json", {})
        if isinstance(payload, str):
            payload = json.loads(payload)
        log.info("noop send: channel=%s template=%s receiver=%s",
                 task.get("channel"), task.get("template_id"), task.get("receiver_id"))
        return {"ok": True, "channel": task.get("channel")}


class WeComAppAdapter:
    def __init__(self, base_url: str = "https://qyapi.weixin.qq.com", agent_id: str = ""):
        self.base_url = base_url
        self.agent_id = agent_id
        self.project_root = ROOT
        self._adapter = WeComAdapter(self.project_root)

    def _normalize_payload(self, task: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
        if payload.get("msgtype"):
            return payload
        content = str(payload.get("content", "")).strip()
        return {
            "touser": payload.get("touser") or task.get("receiver_id"),
            "msgtype": "text",
            "agentid": payload.get("agentid") or self.agent_id,
            "text": {"content": content},
            "safe": int(payload.get("safe", 0) or 0),
        }

    def send(self, task: dict[str, Any]) -> dict[str, Any]:
        payload = task.get("payload_json", {})
        if isinstance(payload, str):
            payload = json.loads(payload)
        normalized = self._normalize_payload(task, payload)

        log.info("wecom_app send: agent=%s receiver=%s template=%s",
                 self.agent_id, task.get("receiver_id"), task.get("template_id"))
        response = self._adapter.send_app_message(normalized)
        return {"ok": True, "channel": "wecom_app_message", "response": response}


class WeComGroupBotAdapter:
    def __init__(self, webhook_url: str = ""):
        self.webhook_url = webhook_url

    def send(self, task: dict[str, Any]) -> dict[str, Any]:
        payload = task.get("payload_json", {})
        if isinstance(payload, str):
            payload = json.loads(payload)

        masked_url = self.webhook_url[:30] + "..." if len(self.webhook_url) > 30 else self.webhook_url
        log.info("group_bot send: webhook=%s template=%s", masked_url, task.get("template_id"))
        return {"ok": True, "channel": "group_bot"}


_ADAPTER_REGISTRY: dict[str, Any] = {}


def get_adapter(channel: str) -> Any:
    if channel not in _ADAPTER_REGISTRY:
        if channel == "wecom_app_message":
            _ADAPTER_REGISTRY[channel] = WeComAppAdapter()
        elif channel == "group_bot":
            _ADAPTER_REGISTRY[channel] = WeComGroupBotAdapter()
        else:
            _ADAPTER_REGISTRY[channel] = NoopAdapter()
    return _ADAPTER_REGISTRY[channel]
