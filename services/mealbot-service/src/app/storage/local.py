from __future__ import annotations

import hashlib
from pathlib import Path
from uuid import uuid4

from app.config import ALLOWED_IMAGE_TYPES, ALLOWED_UPLOAD_TYPES, MAX_IMAGE_BYTES, MAX_UPLOAD_BYTES, UPLOAD_DIR

_upload_dir = Path(UPLOAD_DIR)


def save_image_bytes(
    *,
    file_bytes: bytes,
    original_name: str | None,
    content_type: str,
    school_id: str,
) -> dict:
    if content_type not in ALLOWED_IMAGE_TYPES:
        raise ValueError("INVALID_IMAGE_TYPE")

    if len(file_bytes) > MAX_IMAGE_BYTES:
        raise ValueError("IMAGE_TOO_LARGE")

    sha256 = hashlib.sha256(file_bytes).hexdigest()
    ext = ALLOWED_IMAGE_TYPES[content_type]

    folder = _upload_dir / school_id
    folder.mkdir(parents=True, exist_ok=True)

    filename = f"{uuid4()}{ext}"
    path = folder / filename
    path.write_bytes(file_bytes)

    return {
        "file_path": str(path),
        "original_name": original_name,
        "content_type": content_type,
        "size_bytes": len(file_bytes),
        "sha256": sha256,
    }


def save_upload_bytes(
    *,
    file_bytes: bytes,
    original_name: str | None,
    content_type: str,
    school_id: str,
) -> dict:
    if content_type not in ALLOWED_UPLOAD_TYPES:
        raise ValueError("INVALID_UPLOAD_TYPE")
    if len(file_bytes) > MAX_UPLOAD_BYTES:
        raise ValueError("UPLOAD_TOO_LARGE")
    sha256 = hashlib.sha256(file_bytes).hexdigest()
    folder = _upload_dir / school_id
    folder.mkdir(parents=True, exist_ok=True)
    filename = f"{uuid4()}{ALLOWED_UPLOAD_TYPES[content_type]}"
    path = folder / filename
    path.write_bytes(file_bytes)
    return {
        "file_path": str(path),
        "original_name": original_name,
        "content_type": content_type,
        "size_bytes": len(file_bytes),
        "sha256": sha256,
    }
