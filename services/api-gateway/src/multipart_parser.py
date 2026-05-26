from __future__ import annotations

import re
from typing import Any


def parse_multipart(content_type: str, body: bytes) -> dict[str, Any]:
    boundary = _extract_boundary(content_type)
    if not boundary:
        raise ValueError("no boundary in Content-Type")

    boundary_bytes = boundary.encode("utf-8")

    fields: dict[str, Any] = {}
    parts = body.split(b"--" + boundary_bytes)

    for part in parts[1:]:
        if part.startswith(b"--"):
            break

        header_end = part.find(b"\r\n\r\n")
        if header_end == -1:
            continue

        headers_raw = part[2:header_end].decode("utf-8", errors="replace")
        content = part[header_end + 4:]

        if content.endswith(b"\r\n"):
            content = content[:-2]

        disp, filename = _parse_disposition(headers_raw)
        name = _extract_field_name(headers_raw)
        content_type_field = _extract_content_type(headers_raw)

        if name == "photo":
            fields["photo_bytes"] = content
            fields["photo_content_type"] = content_type_field or "image/jpeg"
            fields["photo_filename"] = filename or "upload.jpg"
        elif name == "file":
            fields["file_bytes"] = content
            fields["file_content_type"] = content_type_field or "application/octet-stream"
            fields["file_filename"] = filename or "upload.bin"
        elif name:
            fields[name] = content.decode("utf-8", errors="replace")

    return fields


def _extract_boundary(content_type: str) -> str:
    for part in content_type.split(";"):
        part = part.strip()
        if part.startswith("boundary="):
            return part.removeprefix("boundary=").strip('"').strip("'")
    return ""


def _parse_disposition(headers: str) -> tuple[str | None, str | None]:
    name = None
    filename = None
    for line in headers.splitlines():
        line = line.strip()
        if not line.lower().startswith("content-disposition:"):
            continue
        for part in line.split(";"):
            part = part.strip()
            if part.startswith("name="):
                name = part.removeprefix("name=").strip('"').strip("'")
            elif part.startswith("filename="):
                filename = part.removeprefix("filename=").strip('"').strip("'")
    return name, filename


def _extract_field_name(headers: str) -> str:
    name, _ = _parse_disposition(headers)
    return name or ""


def _extract_content_type(headers: str) -> str | None:
    for line in headers.splitlines():
        line = line.strip()
        if line.lower().startswith("content-type:"):
            return line.removeprefix("Content-Type:").removeprefix("content-type:").strip()
    return None
