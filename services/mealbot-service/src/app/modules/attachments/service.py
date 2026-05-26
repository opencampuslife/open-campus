from __future__ import annotations

from typing import Any

from app.db.repositories import attachments as repo
from app.storage.local import save_image_bytes


def save_image_and_create_attachment(
    *,
    file_bytes: bytes,
    original_name: str | None,
    content_type: str,
    school_id: str,
    source: str = "h5_upload",
    biz_type: str | None = None,
    biz_id: str | None = None,
    created_by_wecom_userid: str | None = None,
) -> dict[str, Any]:
    stored = save_image_bytes(
        file_bytes=file_bytes,
        original_name=original_name,
        content_type=content_type,
        school_id=school_id,
    )

    from uuid import uuid4

    attachment = repo.create_attachment({
        "attachment_id": f"ATT-{uuid4().hex[:12]}",
        "school_id": school_id,
        "source": source,
        "biz_type": biz_type,
        "biz_id": biz_id,
        "file_path": stored["file_path"],
        "original_name": stored["original_name"],
        "content_type": stored["content_type"],
        "size_bytes": stored["size_bytes"],
        "sha256": stored["sha256"],
        "created_by_wecom_userid": created_by_wecom_userid,
    })
    return attachment
