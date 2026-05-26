from __future__ import annotations

from pathlib import Path
from typing import Any

from chunker import chunk_markdown
from frontmatter_parser import parse_markdown
from validator import (
    check_content_prohibited,
    check_doc_id_uniqueness,
    check_doc_is_retrievable,
    check_public_content_leak,
    check_visibility_directory_consistency,
    validate_doc,
)


def load_knowledge(
    vault_root: Path, *, strict: bool = True
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[str]]:
    docs: list[dict[str, Any]] = []
    chunks: list[dict[str, Any]] = []
    errors: list[str] = []
    doc_id_map: dict[str, str] = {}

    for path in sorted(vault_root.rglob("*.md")):
        if "metadata" in path.parts:
            continue
        metadata, body = parse_markdown(path)
        source_uri = str(path.relative_to(vault_root.parent))
        metadata["source_uri"] = source_uri

        frontmatter_errors = validate_doc(metadata, source_uri)
        dir_errors = check_visibility_directory_consistency(metadata, source_uri)

        all_file_errors = frontmatter_errors + dir_errors
        if all_file_errors:
            for err in all_file_errors:
                errors.append(f"{source_uri}: {err}")
            if strict:
                continue

        content_warnings = check_content_prohibited(body, metadata.get("visibility"))
        leak_warnings = check_public_content_leak(metadata, body, source_uri)
        for w in content_warnings + leak_warnings:
            errors.append(f"{source_uri}: [content] {w}")

        if not check_doc_is_retrievable(metadata):
            continue

        if not check_doc_is_retrievable(metadata):
            continue

        doc_id_map[metadata["doc_id"]] = source_uri

        doc = dict(metadata)
        doc["chunk_count"] = 0
        doc_chunks = chunk_markdown(metadata, body, source_uri)
        doc["chunk_count"] = len(doc_chunks)
        docs.append(doc)
        chunks.extend(doc_chunks)

    dup_errors = check_doc_id_uniqueness(doc_id_map)
    errors.extend(dup_errors)

    return docs, chunks, errors
