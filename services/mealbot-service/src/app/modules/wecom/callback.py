from __future__ import annotations

import os
from pathlib import Path

from app.db.repositories import inbound_messages as inbound_repo
from app.db.repositories.operation_logs import write_operation_log
from app.modules.wecom.message_parser import extract_encrypted_payload, parse_message
from app.services.wecom_crypto import decrypt_message, verify_signature


def _callback_settings() -> dict[str, str]:
    values = {
        "token": os.environ.get("WECOM_TOKEN", ""),
        "encoding_aes_key": os.environ.get("WECOM_ENCODING_AES_KEY", ""),
        "corp_id": os.environ.get("WECOM_CORP_ID", ""),
        "school_id": os.environ.get("WECOM_SCHOOL_ID", "school_demo"),
    }
    if not values["token"] or not values["encoding_aes_key"] or not values["corp_id"]:
        raise ValueError("WECOM_CALLBACK_NOT_CONFIGURED")
    return values


def verify_callback_url(query: dict[str, str]) -> str:
    settings = _callback_settings()
    encrypted_echo = query.get("echostr", "")
    try:
        verify_signature(
            token=settings["token"],
            timestamp=query.get("timestamp", ""),
            nonce=query.get("nonce", ""),
            encrypted=encrypted_echo,
            msg_signature=query.get("msg_signature", ""),
        )
    except Exception:
        _audit_callback(settings["school_id"], "wecom_callback.invalid_signature")
        raise
    _audit_callback(settings["school_id"], "wecom_callback.verified")
    return decrypt_message(
        encrypted=encrypted_echo,
        encoding_aes_key=settings["encoding_aes_key"],
        corp_id=settings["corp_id"],
    )


def receive_callback_message(query: dict[str, str], raw_xml: str, project_root: Path) -> dict[str, object]:
    del project_root
    settings = _callback_settings()
    encrypted = extract_encrypted_payload(raw_xml)
    try:
        verify_signature(
            token=settings["token"],
            timestamp=query.get("timestamp", ""),
            nonce=query.get("nonce", ""),
            encrypted=encrypted,
            msg_signature=query.get("msg_signature", ""),
        )
    except Exception:
        _audit_callback(settings["school_id"], "wecom_callback.invalid_signature")
        raise
    decrypted_xml = decrypt_message(
        encrypted=encrypted,
        encoding_aes_key=settings["encoding_aes_key"],
        corp_id=settings["corp_id"],
    )
    message = parse_message(decrypted_xml)
    msg_id = str(message["msg_id"])
    if not msg_id or not message["from_user_name"]:
        raise ValueError("INVALID_WECOM_MESSAGE")

    is_image = message["msg_type"] == "image" and bool(message["media_id"])
    environment = os.environ.get("ENVIRONMENT", os.environ.get("GAOKAO_ENV", "dev")).lower()
    row, created = inbound_repo.create_inbound_message_idempotent({
        "msg_id": msg_id,
        "school_id": settings["school_id"],
        "from_wecom_userid": message["from_user_name"],
        "msg_type": message["msg_type"],
        "agent_id": message["agent_id"] or None,
        "media_id": message["media_id"] or None,
        "pic_url": message["pic_url"] or None,
        "raw_xml": None if environment in {"prod", "production"} else decrypted_xml,
        "status": "download_pending" if is_image else "ignored",
    })
    _audit_callback(
        settings["school_id"],
        "wecom_callback.image_received" if created and is_image else
        "wecom_callback.duplicate_msg" if not created else "wecom_callback.ignored",
        msg_id=msg_id,
    )
    return {
        "created": created,
        "status": (row or {}).get("status", "ignored"),
        "msg_id": msg_id,
        "msg_type": message["msg_type"],
    }


def _audit_callback(school_id: str, action: str, msg_id: str = "callback") -> None:
    write_operation_log(
        school_id=school_id,
        actor_user_id="wecom",
        actor_type="wecom_callback",
        biz_type="inbound_message",
        biz_id=msg_id,
        action=action,
    )
