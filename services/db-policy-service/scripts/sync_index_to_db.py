from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from textwrap import dedent

ROOT = Path(__file__).resolve().parents[3]
SERVICE = ROOT / "services" / "db-policy-service"
PSQL = SERVICE / "scripts" / "psql.sh"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args()

    db_url = os.environ.get("DATABASE_URL_ADMIN")
    if not db_url:
        print("DATABASE_URL_ADMIN is required", file=sys.stderr)
        return 1

    index_path = args.root / "data" / "indexes" / "knowledge_index.json"
    if not index_path.exists():
        print(f"Index not found at {index_path}", file=sys.stderr)
        return 1

    index = json.loads(index_path.read_text(encoding="utf-8"))

    sql_docs = _build_doc_upsert_sql(index)
    sql_chunks = _build_chunk_upsert_sql(index)

    for sql in (sql_docs, sql_chunks):
        try:
            subprocess.run(
                [str(PSQL), db_url, "-v", "ON_ERROR_STOP=1", "-c", sql],
                check=True,
                text=True,
            )
        except subprocess.CalledProcessError as e:
            print(f"Sync failed: {e.stderr or e.stdout}", file=sys.stderr)
            return 1

    print(f"synced {len(index['docs'])} docs, {len(index['chunks'])} chunks to postgres")
    return 0


def _build_doc_upsert_sql(index: dict) -> str:
    rows = []
    for doc in index.get("docs", []):
        doc_id = _escape(doc.get("doc_id", ""))
        title = _escape(doc.get("title", ""))
        source_uri = _escape(doc.get("source_uri", ""))
        visibility = _escape(doc.get("visibility", ""))
        data_level = _escape(doc.get("data_level", ""))
        dli = doc.get("data_level_int", 1)
        roles = _escape_list(doc.get("allowed_roles", []))
        campus = _escape_list(doc.get("campus_scope", []))
        tags = _escape_list(doc.get("business_tags", []))
        review = _escape(doc.get("review_status", ""))
        effective = _escape(doc.get("effective_date", ""))
        expiry = _escape(doc.get("expiry_date", ""))
        owner = _escape(doc.get("owner", ""))
        version = doc.get("version", 1)

        rows.append(
            f"({doc_id}, {title}, {source_uri}, {visibility}, {data_level}, {dli}, "
            f"{roles}, {campus}, {tags}, {review}, {effective}, {expiry}, {owner}, {version})"
        )

    values = ",\n".join(rows)

    return dedent(f"""\
    INSERT INTO knowledge_docs (
        doc_id, title, source_uri,
        visibility, data_level, data_level_int,
        allowed_roles, campus_scope, business_tags,
        review_status, effective_date, expiry_date,
        owner, version
    )
    VALUES
    {values}
    ON CONFLICT (doc_id) DO NOTHING;
    """)


def _build_chunk_upsert_sql(index: dict) -> str:
    rows = []
    for chunk in index.get("chunks", []):
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

        rows.append(
            f"({chunk_id}, (SELECT id FROM knowledge_docs WHERE doc_id = {doc_id}), "
            f"{title}, {content}, {visibility}, {data_level}, {dli}, "
            f"{roles}, {campus}, {tags}, {source_uri}, {review}, "
            f"{effective}, {expiry})"
        )

    values = ",\n".join(rows)

    return dedent(f"""\
    INSERT INTO knowledge_chunks (
        chunk_id, doc_id,
        title, content,
        visibility, data_level, data_level_int,
        allowed_roles, campus_scope, business_tags,
        source_uri, review_status,
        effective_date, expiry_date
    )
    VALUES
    {values}
    ON CONFLICT (chunk_id) DO NOTHING;
    """)


def _escape(value: str) -> str:
    return f"'{value.replace(chr(39), chr(39) + chr(39))}'"


def _escape_list(values: list[str]) -> str:
    if not values:
        return "'{}'"
    escaped = ", ".join(f'"{v}"' for v in values)
    return f"'{{{escaped}}}'::text[]"


if __name__ == "__main__":
    raise SystemExit(main())
