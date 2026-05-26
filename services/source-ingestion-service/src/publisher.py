from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from staging_store import load_staging_doc


def publish_staging_doc(
    project_root: Path,
    staging_doc_id: str,
    publisher: str,
    role: str,
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "success": False,
        "doc_id": "",
        "published_at": "",
        "version": 0,
        "error": "",
    }

    try:
        doc = load_staging_doc(project_root, staging_doc_id)
        if doc is None:
            result["error"] = "staging doc not found: {}".format(staging_doc_id)
            return result

        review_status = doc.get("review_status", "")
        if review_status != "approved":
            result["error"] = "cannot publish: review_status is '{}', must be 'approved'".format(
                review_status
            )
            return result

        compliance_status = doc.get("compliance_status", "")
        if compliance_status != "passed":
            result["error"] = "cannot publish: compliance_status is '{}', must be 'passed'".format(
                compliance_status
            )
            return result

        vault_dir = project_root / "knowledge_vault"
        vault_dir.mkdir(parents=True, exist_ok=True)

        frontmatter = doc.get("frontmatter", {})
        doc_id = doc.get("doc_id", "")
        visibility = frontmatter.get("visibility", "internal")
        sub_dir = vault_dir / visibility
        sub_dir.mkdir(parents=True, exist_ok=True)

        target_path = sub_dir / "{}.md".format(doc_id)
        version = _compute_next_version(target_path)

        markdown_content = _build_published_markdown(doc, version)
        target_path.write_text(markdown_content, encoding="utf-8")

        published_dir = project_root / "data" / "knowledge_published"
        published_dir.mkdir(parents=True, exist_ok=True)
        history = {
            "staging_doc_id": staging_doc_id,
            "doc_id": doc_id,
            "title": doc.get("title", ""),
            "version": version,
            "published_at": datetime.now(timezone.utc).isoformat(),
            "publisher": publisher,
            "publisher_role": role,
            "path": str(target_path.relative_to(project_root)),
        }
        history_path = published_dir / "{}.{}.json".format(doc_id, version)
        history_path.write_text(
            json.dumps(history, ensure_ascii=False, indent=2), encoding="utf-8"
        )

        result["success"] = True
        result["doc_id"] = doc_id
        result["published_at"] = history["published_at"]
        result["version"] = version

        db_result = publish_to_postgres(
            doc, project_root, result["published_at"], publisher, version
        )
        if "error" in db_result:
            result["db_warning"] = db_result["error"]
        else:
            result["db"] = db_result

    except Exception as exc:
        result["error"] = "publish failed: {}".format(str(exc))

    return result


def _compute_next_version(target_path: Path) -> int:
    if not target_path.is_file():
        return 1
    content = target_path.read_text(encoding="utf-8")
    import re
    m = re.search(r"^version:\s*(\d+)", content, re.MULTILINE)
    if m:
        return int(m.group(1)) + 1
    return 1


def _build_published_markdown(doc: dict[str, Any], version: int) -> str:
    frontmatter = dict(doc.get("frontmatter", {}))
    frontmatter["version"] = version
    parts = ["---"]
    for key, value in frontmatter.items():
        if isinstance(value, list):
            parts.append("{}:".format(key))
            for item in value:
                parts.append("  - {}".format(item))
        else:
            parts.append("{}: {}".format(key, value))
    parts.append("---")
    parts.append("")
    parts.append(doc.get("canonical_markdown", "").strip())
    return "\n".join(parts) + "\n"


def _escape(value: str) -> str:
    return f"'{value.replace(chr(39), chr(39) + chr(39))}'"


def _escape_list(values: list[str]) -> str:
    if not values:
        return "'{}'"
    escaped = ", ".join(f'"{v}"' for v in values)
    return f"'{{{escaped}}}'::text[]"


def _build_doc_insert_sql(metadata: dict, source_uri: str, version: int) -> str:
    from textwrap import dedent

    doc_id = _escape(metadata.get("doc_id", ""))
    title = _escape(metadata.get("title", ""))
    source_uri_esc = _escape(source_uri)
    visibility = _escape(metadata.get("visibility", ""))
    data_level = _escape(metadata.get("data_level", ""))
    dli = metadata.get("data_level_int", 1)
    roles = _escape_list(metadata.get("allowed_roles", []))
    campus = _escape_list(metadata.get("campus_scope", []))
    tags = _escape_list(metadata.get("business_tags", []))
    review = _escape(metadata.get("review_status", ""))
    effective = _escape(metadata.get("effective_date", ""))
    expiry = _escape(metadata.get("expiry_date", ""))
    owner = _escape(metadata.get("owner", ""))

    return dedent(f"""\
    INSERT INTO knowledge_docs (
        doc_id, title, source_uri,
        visibility, data_level, data_level_int,
        allowed_roles, campus_scope, business_tags,
        review_status, effective_date, expiry_date,
        owner, version
    )
    VALUES
    ({doc_id}, {title}, {source_uri_esc},
     {visibility}, {data_level}, {dli},
     {roles}, {campus}, {tags},
     {review}, {effective}, {expiry},
     {owner}, {version})
    ON CONFLICT (doc_id) DO UPDATE SET
        title = EXCLUDED.title,
        source_uri = EXCLUDED.source_uri,
        visibility = EXCLUDED.visibility,
        data_level = EXCLUDED.data_level,
        data_level_int = EXCLUDED.data_level_int,
        allowed_roles = EXCLUDED.allowed_roles,
        campus_scope = EXCLUDED.campus_scope,
        business_tags = EXCLUDED.business_tags,
        review_status = EXCLUDED.review_status,
        effective_date = EXCLUDED.effective_date,
        expiry_date = EXCLUDED.expiry_date,
        owner = EXCLUDED.owner,
        version = EXCLUDED.version,
        updated_at = now();
    """)


def _build_chunk_insert_sql(chunks: list[dict]) -> str:
    from textwrap import dedent

    rows = []
    for chunk in chunks:
        chunk_id = _escape(chunk.get("chunk_id", ""))
        doc_id = _escape(chunk.get("doc_id", ""))
        title = _escape(chunk.get("title", ""))
        content = _escape(chunk.get("content", ""))
        visibility = _escape(chunk.get("visibility", ""))
        data_level = _escape(chunk.get("data_level", ""))
        dli = chunk.get("data_level_int", 1)
        roles = _escape_list(chunk.get("allowed_roles", []))
        campus = _escape_list(chunk.get("campus_scope", []))
        tags = _escape_list(chunk.get("business_tags", []))
        source_uri = _escape(chunk.get("source_uri", ""))
        review = _escape(chunk.get("review_status", ""))
        effective = _escape(chunk.get("effective_date", ""))
        expiry = _escape(chunk.get("expiry_date", ""))
        source_page = _escape(str(chunk.get("source_page") or ""))

        rows.append(
            f"({chunk_id}, (SELECT id FROM knowledge_docs WHERE doc_id = {doc_id}), "
            f"{title}, {content}, {visibility}, {data_level}, {dli}, "
            f"{roles}, {campus}, {tags}, {source_uri}, "
            f"{review}, {effective}, {expiry}, {source_page})"
        )

    values = ",\n".join(rows)

    return dedent(f"""\
    INSERT INTO knowledge_chunks (
        chunk_id, doc_id,
        title, content,
        visibility, data_level, data_level_int,
        allowed_roles, campus_scope, business_tags,
        source_uri, review_status,
        effective_date, expiry_date,
        source_page
    )
    VALUES
    {values}
    ON CONFLICT (chunk_id) DO NOTHING;
    """)


def publish_to_postgres(
    doc: dict,
    project_root: Path,
    published_at: str,
    publisher: str,
    version: int,
) -> dict:
    db_url = os.environ.get("DATABASE_URL_ADMIN")
    if not db_url:
        return {"skipped": True, "reason": "DATABASE_URL_ADMIN not set"}

    try:
        KNOWLEDGE_SRC = (
            Path(__file__).resolve().parents[3]
            / "services"
            / "knowledge-service"
            / "src"
        )
        sys.path.insert(0, str(KNOWLEDGE_SRC))
        from chunker import chunk_markdown  # noqa: F811

        PSQL = (
            Path(__file__).resolve().parents[3]
            / "services"
            / "db-policy-service"
            / "scripts"
            / "psql.sh"
        )

        frontmatter = doc.get("frontmatter", {})
        doc_id = doc.get("doc_id", "")

        metadata = {
            "doc_id": doc_id,
            "title": doc.get("title", frontmatter.get("title", "")),
            "visibility": frontmatter.get("visibility", "internal"),
            "allowed_roles": frontmatter.get("allowed_roles", []),
            "data_level": frontmatter.get("data_level", "L1"),
            "data_level_int": frontmatter.get("data_level_int", 1),
            "campus_scope": frontmatter.get("campus_scope", ["all"]),
            "business_tags": frontmatter.get("business_tags", []),
            "effective_date": frontmatter.get("effective_date", ""),
            "expiry_date": frontmatter.get("expiry_date", ""),
            "review_status": frontmatter.get("review_status", "approved"),
            "owner": frontmatter.get("owner", ""),
        }

        source_uri = frontmatter.get("source_uri", "")
        body = doc.get("canonical_markdown", "")

        doc_sql = _build_doc_insert_sql(metadata, source_uri, version)
        chunks = chunk_markdown(metadata, body, source_uri)
        chunk_sql = _build_chunk_insert_sql(chunks)

        for sql in (doc_sql, chunk_sql):
            subprocess.run(
                [str(PSQL), db_url, "-v", "ON_ERROR_STOP=1", "-c", sql],
                check=True,
                text=True,
            )

        return {
            "success": True,
            "doc_id": doc_id,
            "chunks_count": len(chunks),
        }
    except Exception as exc:
        return {"error": "db publish failed: {}".format(str(exc))}
