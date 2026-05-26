from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def write_staging_doc(project_root: Path, doc_data: dict[str, Any]) -> str:
    staging_dir = project_root / "data" / "staging"
    staging_dir.mkdir(parents=True, exist_ok=True)

    import uuid
    staging_doc_id = doc_data.get("staging_doc_id", uuid.uuid4().hex)

    now = datetime.now(timezone.utc).isoformat()
    staging_doc = {
        "staging_doc_id": staging_doc_id,
        "run_id": doc_data.get("run_id", ""),
        "doc_id": doc_data.get("doc_id", ""),
        "title": doc_data.get("title", ""),
        "canonical_markdown": doc_data.get("canonical_markdown", ""),
        "frontmatter": doc_data.get("frontmatter", {}),
        "validation_status": doc_data.get("validation_status", "pending"),
        "compliance_status": doc_data.get("compliance_status", "pending"),
        "review_status": doc_data.get("review_status", "draft"),
        "source_hash": doc_data.get(
            "source_hash",
            hashlib.sha256(doc_data.get("canonical_markdown", "").encode("utf-8")).hexdigest(),
        ),
        "created_by": doc_data.get("created_by", ""),
        "reviewer": doc_data.get("reviewer", ""),
        "created_at": doc_data.get("created_at", now),
        "updated_at": now,
    }

    path = staging_dir / "{}.json".format(staging_doc_id)
    path.write_text(json.dumps(staging_doc, ensure_ascii=False, indent=2), encoding="utf-8")
    return staging_doc_id


def load_staging_doc(project_root: Path, staging_doc_id: str) -> dict[str, Any] | None:
    path = project_root / "data" / "staging" / "{}.json".format(staging_doc_id)
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def list_staging_docs(project_root: Path) -> list[dict[str, Any]]:
    staging_dir = project_root / "data" / "staging"
    if not staging_dir.is_dir():
        return []
    docs: list[dict[str, Any]] = []
    for p in sorted(staging_dir.glob("*.json")):
        doc = load_staging_doc(project_root, p.stem)
        if doc is not None:
            docs.append(doc)
    return docs


def update_staging_doc(
    project_root: Path,
    staging_doc_id: str,
    updates: dict[str, Any],
) -> dict[str, Any]:
    doc = load_staging_doc(project_root, staging_doc_id)
    if doc is None:
        raise ValueError("staging doc not found: {}".format(staging_doc_id))
    doc.update(updates)
    doc["updated_at"] = datetime.now(timezone.utc).isoformat()
    path = project_root / "data" / "staging" / "{}.json".format(staging_doc_id)
    path.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
    return doc


def delete_staging_doc(project_root: Path, staging_doc_id: str) -> bool:
    path = project_root / "data" / "staging" / "{}.json".format(staging_doc_id)
    if not path.is_file():
        return False
    path.unlink()
    return True
