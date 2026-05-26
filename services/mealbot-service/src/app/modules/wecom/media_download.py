from __future__ import annotations

import json
import os
import ssl
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable
from urllib.parse import urlencode
from urllib.request import urlopen
from uuid import uuid4

import certifi
from app.config import APP_BASE_URL, WECOM_AGENT_ID
from app.db.repositories import attachments as attachments_repo
from app.db.repositories import inbound_messages as inbound_repo
from app.db.repositories import reminder_tasks as tasks_repo
from app.db.repositories.operation_logs import write_operation_log
from app.storage.local import save_image_bytes


Download = Callable[[str], tuple[bytes, str]]


def _ssl_context() -> ssl.SSLContext:
    return ssl.create_default_context(cafile=certifi.where())


def _get_access_token() -> str:
    override = os.environ.get("WECOM_ACCESS_TOKEN", "")
    if override:
        return override
    corp_id = os.environ.get("WECOM_CORP_ID", "")
    secret = os.environ.get("WECOM_SECRET", "") or os.environ.get("WECOM_APP_SECRET", "")
    if not corp_id or not secret:
        raise ValueError("WECOM_MEDIA_CREDENTIALS_REQUIRED")
    url = "https://qyapi.weixin.qq.com/cgi-bin/gettoken?" + urlencode({
        "corpid": corp_id,
        "corpsecret": secret,
    })
    with urlopen(url, timeout=10, context=_ssl_context()) as response:
        result = json.loads(response.read().decode("utf-8"))
    if int(result.get("errcode", 0)) != 0 or not result.get("access_token"):
        raise ValueError(f"WECOM_GETTOKEN_FAILED:{result.get('errcode', 'unknown')}")
    return str(result["access_token"])


def _download_wecom_image(media_id: str) -> tuple[bytes, str]:
    access_token = _get_access_token()
    url = "https://qyapi.weixin.qq.com/cgi-bin/media/get?" + urlencode({
        "access_token": access_token,
        "media_id": media_id,
    })
    with urlopen(url, timeout=15, context=_ssl_context()) as response:
        content_type = response.headers.get_content_type()
        content = response.read()
    if content_type == "application/json":
        error = json.loads(content.decode("utf-8"))
        raise ValueError(f"WECOM_MEDIA_DOWNLOAD_FAILED:{error.get('errcode', 'unknown')}")
    return content, content_type


def _create_confirmation_task(message: dict[str, object], attachment_id: str) -> None:
    confirm_url = f"{APP_BASE_URL}/h5/meal/cancel?attachment_id={attachment_id}"
    tasks_repo.create_reminder_task({
        "reminder_id": f"RT-{uuid4().hex[:12]}",
        "school_id": message["school_id"],
        "biz_type": "inbound_message",
        "biz_id": message["msg_id"],
        "receiver_type": "wecom_user",
        "receiver_id": message["from_wecom_userid"],
        "channel": "wecom_app_message",
        "template_id": "wecom_image_confirm_link",
        "payload_json": {
            "touser": message["from_wecom_userid"],
            "agentid": WECOM_AGENT_ID,
            "content": f"已收到你上传的图片。\n\n是否用于提交退餐申请？\n点击确认：{confirm_url}",
            "confirm_url": confirm_url,
            "attachment_id": attachment_id,
        },
        "scheduled_at": datetime.now(timezone.utc),
        "idempotency_key": f"wecom_image_confirm_{message['msg_id']}",
    })


def process_pending_media_downloads(
    project_root: Path,
    *,
    downloader: Download | None = None,
    limit: int = 20,
    school_id: str | None = None,
) -> dict[str, int]:
    del project_root
    download = downloader or _download_wecom_image
    pending = inbound_repo.claim_pending_downloads(limit, school_id)
    counts = {"processed": len(pending), "downloaded": 0, "failed": 0}
    for message in pending:
        try:
            content, content_type = download(str(message["media_id"]))
            stored = save_image_bytes(
                file_bytes=content,
                original_name=f"{message['media_id']}.jpg",
                content_type=content_type,
                school_id=str(message["school_id"]),
            )
            attachment_id = f"ATT-{uuid4().hex[:12]}"
            attachments_repo.create_attachment({
                "attachment_id": attachment_id,
                "school_id": message["school_id"],
                "source": "wecom_callback",
                "biz_type": "inbound_message",
                "biz_id": message["msg_id"],
                "file_path": stored["file_path"],
                "original_name": stored.get("original_name"),
                "content_type": stored.get("content_type"),
                "size_bytes": stored.get("size_bytes"),
                "sha256": stored.get("sha256"),
                "created_by_wecom_userid": message["from_wecom_userid"],
            })
            inbound_repo.mark_downloaded(str(message["msg_id"]), attachment_id)
            _create_confirmation_task(message, attachment_id)
            write_operation_log(
                school_id=str(message["school_id"]),
                actor_user_id="wecom_media_worker",
                actor_type="worker",
                biz_type="attachment",
                biz_id=attachment_id,
                action="wecom_media.downloaded",
                after={"msg_id": message["msg_id"], "source": "wecom_callback"},
            )
            counts["downloaded"] += 1
        except Exception as exc:
            inbound_repo.update_inbound_message_status(str(message["msg_id"]), "failed", str(exc))
            write_operation_log(
                school_id=str(message["school_id"]),
                actor_user_id="wecom_media_worker",
                actor_type="worker",
                biz_type="inbound_message",
                biz_id=str(message["msg_id"]),
                action="wecom_media.failed",
                after={"error": "download_failed"},
            )
            counts["failed"] += 1
    return counts
