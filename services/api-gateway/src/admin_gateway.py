from __future__ import annotations

import json
import os
import re
import shutil
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

AGENT_SRC = Path(__file__).resolve().parents[2] / "agent-orchestrator" / "src"
sys.path.append(str(AGENT_SRC))

from audit_logger import audit_log  # noqa: E402
from admin_policy import Action, require_action_str, can_edit_permission_fields, is_permission_field

KNOWN_GRAPH_RUN_STATUSES = {"pending", "running", "completed", "failed", "cancelled"}


def _require_admin_action(identity: dict[str, Any], action: str, resource: dict[str, Any] | None = None) -> dict[str, Any]:
    ctx = require_action_str(identity, action, resource)
    return {"user_id": ctx.user_id, "role": ctx.role, "campus": ctx.campus}


def _admin_audit_log(
    project_root: Path, action: str, identity: dict[str, Any], details: dict[str, Any] | None = None
) -> None:
    event: dict[str, Any] = {
        "action": action,
        "user_id": identity.get("user_id", "anonymous"),
        "role": identity.get("role", "visitor"),
    }
    if details:
        event["details"] = details
    audit_log(project_root, event)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _trusted_identity(auth_identity: dict[str, Any]) -> dict[str, Any]:
    return {
        "user_id": auth_identity.get("user_id", "anonymous"),
        "role": auth_identity.get("role", "visitor"),
        "campus": auth_identity.get("campus", "all"),
        "auth_level": auth_identity.get("auth_level", "anonymous"),
    }


def _admin_visible_to(lead: dict[str, Any], identity: dict[str, Any]) -> bool:
    if identity.get("role") in {"admin", "campus_admin"}:
        return True
    if identity.get("campus", "zh") == lead.get("campus", "zh"):
        return True
    return False


def admin_health(identity: dict[str, Any], project_root: Path) -> dict[str, Any]:
    _trusted_identity(identity)
    _require_admin_action(identity, Action.HEALTH_READ)
    services: dict[str, str] = {}
    candidate_services = [
        ("api-gateway", "services/api-gateway/src/server.py"),
        ("agent-orchestrator", "services/agent-orchestrator/src/pipeline.py"),
        ("crm-service", "services/crm-service/src/leads.py"),
    ]
    for name, rel_path in candidate_services:
        svc_path = project_root / rel_path
        services[name] = "ok" if svc_path.exists() else "unavailable"
    return {
        "status": "ok",
        "services": services,
        "version": "0.1.0",
    }


def admin_sources_upload(payload: dict[str, Any], files: list[dict[str, Any]], identity: dict[str, Any], project_root: Path) -> dict[str, Any]:
    identity = _trusted_identity(identity)
    _require_admin_action(identity, Action.SOURCE_UPLOAD)

    if not files:
        raise ValueError("No files provided for upload")

    file_info = files[0]
    file_path = file_info.get("path", "")
    filename = file_info.get("filename", "unknown")
    if not file_path or not Path(file_path).exists():
        raise ValueError(f"Uploaded file not found: {file_path}")

    source_path = Path(file_path)
    run_id = f"ing_{uuid.uuid4().hex[:12]}"
    staging_doc_id = f"std_{uuid.uuid4().hex[:12]}"

    content = source_path.read_bytes()
    import hashlib
    source_hash = hashlib.sha256(content).hexdigest()[:16]

    ingestion_dir = project_root / "data" / "ingestion" / run_id
    ingestion_dir.mkdir(parents=True, exist_ok=True)
    saved_path = ingestion_dir / filename
    saved_path.write_bytes(content)

    source_type = "markdown"
    ext = Path(filename).suffix.lower()
    if ext == ".pdf":
        source_type = "pdf"
    elif ext == ".docx":
        source_type = "docx"
    elif ext == ".txt":
        source_type = "text"

    run_record = {
        "run_id": run_id,
        "status": "pending",
        "source_type": source_type,
        "source_path": str(saved_path),
        "source_hash": source_hash,
        "created_by": identity["user_id"],
        "role": identity["role"],
        "campus": identity["campus"],
        "started_at": _now_iso(),
        "finished_at": None,
        "error_message": None,
        "metadata": {},
    }
    _write_json(project_root / "data" / "ingestion", f"{run_id}.json", run_record)

    canonical_markdown = content.decode("utf-8", errors="replace")
    staging_doc = {
        "staging_doc_id": staging_doc_id,
        "run_id": run_id,
        "doc_id": None,
        "title": payload.get("title", filename),
        "source_type": source_type,
        "canonical_markdown": canonical_markdown,
        "frontmatter": payload.get("frontmatter", {}),
        "validation_status": "pending",
        "compliance_status": "pending",
        "review_status": "draft",
        "source_hash": source_hash,
        "created_by": identity["user_id"],
        "reviewer": None,
        "created_at": _now_iso(),
        "updated_at": _now_iso(),
    }
    _write_json(project_root / "data" / "staging", f"{staging_doc_id}.json", staging_doc)

    _admin_audit_log(project_root, "sources_upload", identity, {
        "run_id": run_id, "filename": filename, "staging_doc_id": staging_doc_id, "source_type": source_type,
    })

    run_record["status"] = "ingested"
    _write_json(project_root / "data" / "ingestion", f"{run_id}.json", run_record)

    validation_result = {"frontmatter": "pending", "compliance": "pending"}

    return {
        "run_id": run_id,
        "staging_doc_id": staging_doc_id,
        "status": "ingested",
        "validation_result": validation_result,
    }


def admin_list_sources(identity: dict[str, Any], project_root: Path) -> dict[str, Any]:
    identity = _trusted_identity(identity)
    _require_admin_action(identity, Action.SOURCE_UPLOAD)
    sources: list[dict[str, Any]] = []

    ingestion_dir = project_root / "data" / "ingestion"
    if ingestion_dir.exists():
        seen_dirs: set[str] = set()
        for entry in sorted(ingestion_dir.iterdir()):
            if entry.is_file() and entry.suffix.lower() in (".md", ".txt", ".pdf", ".docx"):
                run_id = entry.stem
                if run_id in seen_dirs:
                    continue
                seen_dirs.add(run_id)
                sources.append({
                    "id": run_id,
                    "title": entry.name,
                    "source_type": entry.suffix.lstrip("."),
                    "created_at": _now_iso(),
                    "status": "available",
                })

    knowledge_vault = project_root / "knowledge_vault"
    if knowledge_vault.exists():
        for entry in sorted(knowledge_vault.iterdir()):
            if entry.is_file():
                sources.append({
                    "id": entry.stem,
                    "title": entry.name,
                    "source_type": entry.suffix.lstrip("."),
                    "created_at": _now_iso(),
                    "status": "indexed",
                })

    _admin_audit_log(project_root, "list_sources", identity, {"count": len(sources)})
    return {"sources": sources}


def admin_create_ingestion_run(payload: dict[str, Any], identity: dict[str, Any], project_root: Path) -> dict[str, Any]:
    identity = _trusted_identity(identity)
    _require_admin_action(identity, Action.INGESTION_RUN)
    run_id = f"ing_{uuid.uuid4().hex[:12]}"
    run_record = {
        "run_id": run_id,
        "status": "pending",
        "source_type": payload.get("source_type", "manual"),
        "source_path": payload.get("source_path"),
        "source_hash": payload.get("source_hash"),
        "created_by": identity["user_id"],
        "role": identity["role"],
        "campus": identity["campus"],
        "started_at": _now_iso(),
        "finished_at": None,
        "error_message": None,
        "metadata": payload.get("metadata", {}),
    }
    _write_json(project_root / "data" / "ingestion", f"{run_id}.json", run_record)
    _admin_audit_log(project_root, "create_ingestion_run", identity, {"run_id": run_id})
    return run_record


def _write_json(directory: Path, filename: str, data: dict[str, Any]) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / filename).write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def _read_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def admin_list_ingestion_runs(identity: dict[str, Any], project_root: Path) -> dict[str, Any]:
    identity = _trusted_identity(identity)
    _require_admin_action(identity, Action.INGESTION_READ)
    runs: list[dict[str, Any]] = []
    runs_dir = project_root / "data" / "ingestion"
    if runs_dir.exists():
        for path in sorted(runs_dir.glob("*.json")):
            run = _read_json(path)
            if run:
                runs.append({
                    "run_id": run.get("run_id", path.stem),
                    "status": run.get("status", "unknown"),
                    "source_type": run.get("source_type", "unknown"),
                    "started_at": run.get("started_at"),
                    "finished_at": run.get("finished_at"),
                })
    _admin_audit_log(project_root, "list_ingestion_runs", identity, {"count": len(runs)})
    return {"runs": runs}


def admin_get_ingestion_run(run_id: str, identity: dict[str, Any], project_root: Path) -> dict[str, Any]:
    identity = _trusted_identity(identity)
    _require_admin_action(identity, Action.INGESTION_READ)
    run = _read_json(project_root / "data" / "ingestion" / f"{run_id}.json")
    if run is None:
        raise ValueError(f"Ingestion run not found: {run_id}")
    return run


def admin_cancel_ingestion_run(run_id: str, identity: dict[str, Any], project_root: Path) -> dict[str, Any]:
    identity = _trusted_identity(identity)
    _require_admin_action(identity, Action.INGESTION_RUN)
    run_path = project_root / "data" / "ingestion" / f"{run_id}.json"
    run = _read_json(run_path)
    if run is None:
        raise ValueError(f"Ingestion run not found: {run_id}")
    if run.get("status") in ("completed", "cancelled"):
        raise ValueError(f"Cannot cancel run with status: {run['status']}")
    run["status"] = "cancelled"
    run["finished_at"] = _now_iso()
    _write_json(run_path.parent, run_path.name, run)
    _admin_audit_log(project_root, "cancel_ingestion_run", identity, {"run_id": run_id})
    return run


def admin_list_staging_docs(identity: dict[str, Any], project_root: Path) -> dict[str, Any]:
    identity = _trusted_identity(identity)
    _require_admin_action(identity, Action.STAGING_READ)
    docs: list[dict[str, Any]] = []
    staging_dir = project_root / "data" / "staging"
    if staging_dir.exists():
        for path in sorted(staging_dir.glob("*.json")):
            doc = _read_json(path)
            if doc:
                docs.append({
                    "staging_doc_id": doc.get("staging_doc_id") or doc.get("staging_id", path.stem),
                    "title": doc.get("title", "Untitled"),
                    "status": doc.get("review_status") or doc.get("status", "draft"),
                    "created_at": doc.get("created_at"),
                })
    _admin_audit_log(project_root, "list_staging_docs", identity, {"count": len(docs)})
    return {"docs": docs}


def admin_get_staging_doc(staging_doc_id: str, identity: dict[str, Any], project_root: Path) -> dict[str, Any]:
    identity = _trusted_identity(identity)
    _require_admin_action(identity, Action.STAGING_READ)
    doc = _read_json(project_root / "data" / "staging" / f"{staging_doc_id}.json")
    if doc is None:
        raise ValueError(f"Staging doc not found: {staging_doc_id}")
    return doc


def admin_update_staging_doc(staging_doc_id: str, payload: dict[str, Any], identity: dict[str, Any], project_root: Path) -> dict[str, Any]:
    identity = _trusted_identity(identity)
    _require_admin_action(identity, Action.STAGING_EDIT)
    doc_path = project_root / "data" / "staging" / f"{staging_doc_id}.json"
    doc = _read_json(doc_path)
    if doc is None:
        raise ValueError(f"Staging doc not found: {staging_doc_id}")
    updatable = {"title", "frontmatter", "doc_id"}
    for key in updatable:
        if key in payload:
            doc[key] = payload[key]
    doc["updated_at"] = _now_iso()
    _write_json(doc_path.parent, doc_path.name, doc)
    _admin_audit_log(project_root, "update_staging_doc", identity, {"staging_doc_id": staging_doc_id, "updated_fields": sorted(set(payload) & updatable)})
    return doc


def admin_validate_staging_doc(staging_doc_id: str, identity: dict[str, Any], project_root: Path) -> dict[str, Any]:
    identity = _trusted_identity(identity)
    _require_admin_action(identity, Action.STAGING_VALIDATE)
    doc_path = project_root / "data" / "staging" / f"{staging_doc_id}.json"
    doc = _read_json(doc_path)
    if doc is None:
        raise ValueError(f"Staging doc not found: {staging_doc_id}")

    issues: list[str] = []
    frontmatter = doc.get("frontmatter", {})
    if not frontmatter:
        issues.append("Missing frontmatter")
    if not frontmatter.get("title") and not doc.get("title"):
        issues.append("Missing title")
    if not frontmatter.get("doc_id"):
        issues.append("Missing doc_id in frontmatter")
    if not frontmatter.get("visibility"):
        issues.append("Missing visibility in frontmatter")

    visibility = frontmatter.get("visibility", "")
    allowed_roles = frontmatter.get("allowed_roles", [])
    if visibility == "public" and "public" not in allowed_roles:
        issues.append("Public visibility requires 'public' in allowed_roles")
    if visibility == "internal" and not any(r in allowed_roles for r in ("sales", "teacher", "operator")):
        issues.append("Internal visibility requires sales/teacher/operator in allowed_roles")
    if visibility == "admin" and "admin" not in allowed_roles:
        issues.append("Admin visibility requires 'admin' in allowed_roles")

    compliance_issues: list[str] = []
    if frontmatter.get("status") == "draft":
        compliance_issues.append("Document is in draft status")

    effective = frontmatter.get("effective_date")
    expiry = frontmatter.get("expiry_date")
    if expiry and effective and expiry < effective:
        compliance_issues.append("Expiry date is before effective date")

    canonical = doc.get("canonical_markdown", "")
    promise_patterns = [r"保证.*(?:提分|录取|提高)", r"承诺.*(?:提分|录取|提高)"]
    for pattern in promise_patterns:
        if re.search(pattern, canonical):
            compliance_issues.append(f"Contains promise/guarantee language matching: {pattern}")
            break

    validation_status = "passed" if not issues else "failed"
    compliance_status = "passed" if not compliance_issues else "failed"
    doc["validation_status"] = validation_status
    doc["compliance_status"] = compliance_status
    doc["updated_at"] = _now_iso()
    _write_json(doc_path.parent, doc_path.name, doc)

    _admin_audit_log(project_root, "validate_staging_doc", identity, {
        "staging_doc_id": staging_doc_id,
        "validation_status": validation_status,
        "compliance_status": compliance_status,
        "issues": issues,
        "compliance_issues": compliance_issues,
    })

    return {
        "staging_doc_id": staging_doc_id,
        "validation_status": validation_status,
        "compliance_status": compliance_status,
        "issues": issues,
        "compliance_issues": compliance_issues,
    }


def _emit_admin_event(project_root: Path, event_type: str, identity: dict[str, Any], metadata: dict[str, Any] | None = None) -> None:
    try:
        from event_schema import EventType, make_event
        from audit_store import write_audit_event
        write_audit_event(project_root, make_event(event_type,
            user_id=str(identity.get("user_id", "")),
            role=str(identity.get("role", "")),
            campus=str(identity.get("campus", "")),
            status="ok",
            metadata=metadata or {},
        ))
    except Exception:
        pass


def admin_approve_staging_doc(staging_doc_id: str, identity: dict[str, Any], project_root: Path) -> dict[str, Any]:
    identity = _trusted_identity(identity)
    _require_admin_action(identity, Action.STAGING_APPROVE)
    doc_path = project_root / "data" / "staging" / f"{staging_doc_id}.json"
    doc = _read_json(doc_path)
    if doc is None:
        raise ValueError(f"Staging doc not found: {staging_doc_id}")
    if doc.get("validation_status") != "passed":
        raise ValueError("Cannot approve: validation has not passed")
    if doc.get("compliance_status") != "passed":
        raise ValueError("Cannot approve: compliance check has not passed")
    doc["review_status"] = "approved"
    doc["reviewer"] = identity["user_id"]
    doc["updated_at"] = _now_iso()
    _write_json(doc_path.parent, doc_path.name, doc)
    _admin_audit_log(project_root, "approve_staging_doc", identity, {"staging_doc_id": staging_doc_id})
    _emit_admin_event(project_root, "admin.staging.approved", identity, {"staging_doc_id": staging_doc_id})
    return {"staging_doc_id": staging_doc_id, "review_status": "approved", "reviewer": identity["user_id"]}


def admin_reject_staging_doc(staging_doc_id: str, payload: dict[str, Any], identity: dict[str, Any], project_root: Path) -> dict[str, Any]:
    identity = _trusted_identity(identity)
    _require_admin_action(identity, Action.STAGING_REJECT)
    doc_path = project_root / "data" / "staging" / f"{staging_doc_id}.json"
    doc = _read_json(doc_path)
    if doc is None:
        raise ValueError(f"Staging doc not found: {staging_doc_id}")
    reason = str(payload.get("reason", "No reason provided")).strip()
    doc["review_status"] = "rejected"
    doc["reviewer"] = identity["user_id"]
    doc["rejection_reason"] = reason
    doc["updated_at"] = _now_iso()
    _write_json(doc_path.parent, doc_path.name, doc)
    _admin_audit_log(project_root, "reject_staging_doc", identity, {"staging_doc_id": staging_doc_id, "reason": reason})
    _emit_admin_event(project_root, "admin.staging.rejected", identity, {"staging_doc_id": staging_doc_id, "reason": reason})
    return {"staging_doc_id": staging_doc_id, "review_status": "rejected", "reason": reason}


def admin_publish_staging_doc(staging_doc_id: str, identity: dict[str, Any], project_root: Path) -> dict[str, Any]:
    identity = _trusted_identity(identity)
    _require_admin_action(identity, Action.STAGING_PUBLISH)
    doc_path = project_root / "data" / "staging" / f"{staging_doc_id}.json"
    doc = _read_json(doc_path)
    if doc is None:
        raise ValueError(f"Staging doc not found: {staging_doc_id}")
    if doc.get("review_status") != "approved":
        raise ValueError(f"Cannot publish: review status is '{doc.get('review_status')}', expected 'approved'")
    doc["review_status"] = "published"
    doc["updated_at"] = _now_iso()
    doc["published_at"] = _now_iso()
    doc["published_by"] = identity["user_id"]
    _write_json(doc_path.parent, doc_path.name, doc)

    published_dir = project_root / "data" / "published"
    published_dir.mkdir(parents=True, exist_ok=True)
    pub_record = {
        "staging_doc_id": staging_doc_id,
        "doc_id": doc.get("doc_id"),
        "title": doc.get("title"),
        "version": doc.get("frontmatter", {}).get("version", "1.0"),
        "source_hash": doc.get("source_hash"),
        "published_at": doc["published_at"],
        "published_by": identity["user_id"],
    }
    _write_json(published_dir, f"{staging_doc_id}.json", pub_record)

    _admin_audit_log(project_root, "publish_staging_doc", identity, {"staging_doc_id": staging_doc_id})
    _emit_admin_event(project_root, "admin.doc.published", identity, {"staging_doc_id": staging_doc_id, "doc_id": str(doc.get("doc_id", "")), "title": str(doc.get("title", ""))})
    return {
        "staging_doc_id": staging_doc_id,
        "review_status": "published",
        "published_at": doc["published_at"],
    }


def admin_list_graph_runs(identity: dict[str, Any], project_root: Path) -> dict[str, Any]:
    identity = _trusted_identity(identity)
    _require_admin_action(identity, Action.GRAPH_READ)
    runs: list[dict[str, Any]] = []
    runs_dir = project_root / "data" / "graph-runs"
    if runs_dir.exists():
        for path in sorted(runs_dir.glob("*.json")):
            run = _read_json(path)
            if run:
                runs.append({
                    "graph_run_id": run.get("graph_run_id", path.stem),
                    "status": run.get("status", "unknown"),
                    "target_type": run.get("target_type", "unknown"),
                    "started_at": run.get("started_at"),
                    "finished_at": run.get("finished_at"),
                    "summary": run.get("summary", {}),
                })
    _admin_audit_log(project_root, "list_graph_runs", identity, {"count": len(runs)})
    return {"runs": runs}


def _load_graph_run(project_root: Path, graph_run_id: str) -> dict[str, Any]:
    run = _read_json(project_root / "data" / "graph-runs" / f"{graph_run_id}.json")
    if run is None:
        raise ValueError(f"Graph run not found: {graph_run_id}")
    return run


def admin_get_graph_run(graph_run_id: str, identity: dict[str, Any], project_root: Path) -> dict[str, Any]:
    identity = _trusted_identity(identity)
    _require_admin_action(identity, Action.GRAPH_READ)
    run = _load_graph_run(project_root, graph_run_id)
    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []

    gdir = project_root / "data" / "graph-runs"

    if run.get("nodes") and isinstance(run["nodes"], list):
        nodes = run["nodes"]
    else:
        nodes_dir = gdir / graph_run_id / "nodes"
        if nodes_dir.exists():
            for path in sorted(nodes_dir.glob("*.json")):
                data = _read_json(path)
                if data:
                    _collect_graph_items(data, "nodes", nodes)

    if run.get("edges") and isinstance(run["edges"], list):
        edges = run["edges"]
    else:
        edges_dir = gdir / graph_run_id / "edges"
        if edges_dir.exists():
            for path in sorted(edges_dir.glob("*.json")):
                data = _read_json(path)
                if data:
                    _collect_graph_items(data, "edges", edges)

    flat_edges_dir = gdir / "edges"
    if not edges and flat_edges_dir.exists():
        for path in sorted(flat_edges_dir.glob("*.json")):
            data = _read_json(path)
            if data and _graph_file_matches_run(data, graph_run_id):
                _collect_graph_items(data, "edges", edges)

    flat_nodes_dir = gdir / "nodes"
    if not nodes and flat_nodes_dir.exists():
        for path in sorted(flat_nodes_dir.glob("*.json")):
            data = _read_json(path)
            if data and _graph_file_matches_run(data, graph_run_id):
                _collect_graph_items(data, "nodes", nodes)

    if not nodes and not edges:
        for candidate in _graph_composite_candidates(gdir, graph_run_id):
            composite = _read_json(candidate)
            if composite:
                _collect_graph_items(composite, "nodes", nodes)
                _collect_graph_items(composite, "edges", edges)
                break

    run["nodes"] = nodes
    run["edges"] = edges
    return run


def _collect_graph_items(data: dict[str, Any] | list[Any], key: str, target: list[dict[str, Any]]) -> None:
    if isinstance(data, list):
        for item in data:
            if isinstance(item, dict):
                target.append(item)
    elif isinstance(data, dict):
        if key in data and isinstance(data[key], list):
            for item in data[key]:
                if isinstance(item, dict):
                    target.append(item)
        elif isinstance(data, list):
            for item in data:
                if isinstance(item, dict):
                    target.append(item)


def admin_get_latest_graph(identity: dict[str, Any], project_root: Path) -> dict[str, Any]:
    identity = _trusted_identity(identity)
    _require_admin_action(identity, Action.GRAPH_READ)
    runs_dir = project_root / "data" / "graph-runs"
    if not runs_dir.exists():
        return {"graph_run_id": None, "nodes": [], "edges": []}
    runs: list[dict[str, Any]] = []
    for path in sorted(runs_dir.glob("*.json")):
        run = _read_json(path)
        if run:
            runs.append(run)
    if not runs:
        return {"graph_run_id": None, "nodes": [], "edges": []}
    latest = max(
        runs,
        key=lambda run: (
            _parse_graph_run_timestamp(run.get("finished_at")),
            _parse_graph_run_timestamp(run.get("started_at")),
            str(run.get("graph_run_id", "")),
        ),
    )
    graph_run_id = latest.get("graph_run_id")
    if not graph_run_id:
        return {"graph_run_id": None, "nodes": [], "edges": []}
    return admin_get_graph_run(graph_run_id, identity, project_root)


def _graph_file_matches_run(data: dict[str, Any] | list[Any], graph_run_id: str) -> bool:
    if not isinstance(data, dict):
        return False
    return str(data.get("graph_run_id", "")) == graph_run_id


def _graph_composite_candidates(graph_root: Path, graph_run_id: str) -> list[Path]:
    run_dir = graph_root / graph_run_id
    suffix = graph_run_id.removeprefix("graph_run_")
    candidates = [
        run_dir / f"graph_comprehensive_{graph_run_id}.json",
        run_dir / f"graph_comprehensive_{suffix}.json",
        graph_root / f"graph_comprehensive_{graph_run_id}.json",
        graph_root / f"graph_comprehensive_{suffix}.json",
    ]
    return [path for path in candidates if path.exists()]


def _parse_graph_run_timestamp(raw: Any) -> datetime:
    if not raw:
        return datetime.min.replace(tzinfo=timezone.utc)
    value = str(raw).strip()
    if not value:
        return datetime.min.replace(tzinfo=timezone.utc)
    value = re.sub(r"([+-]\d{2}:\d{2})([+-]\d{2}:\d{2})$", r"\1", value)
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return datetime.min.replace(tzinfo=timezone.utc)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def admin_create_graph_run(payload: dict[str, Any], identity: dict[str, Any], project_root: Path) -> dict[str, Any]:
    identity = _trusted_identity(identity)
    _require_admin_action(identity, Action.GRAPH_RUN)
    graph_run_id = f"gr_{uuid.uuid4().hex[:12]}"
    target_type = payload.get("target_type", "knowledge_vault")
    target_id = payload.get("target_id")
    run_record: dict[str, Any] = {
        "graph_run_id": graph_run_id,
        "target_type": target_type,
        "target_id": target_id,
        "status": "pending",
        "tool_version": payload.get("tool_version", "0.1.0"),
        "started_at": _now_iso(),
        "finished_at": None,
        "error_message": None,
        "summary": {},
    }
    _write_json(project_root / "data" / "graph-runs", f"{graph_run_id}.json", run_record)
    _admin_audit_log(project_root, "create_graph_run", identity, {
        "graph_run_id": graph_run_id, "target_type": target_type,
    })
    return run_record


def admin_list_audit_logs(identity: dict[str, Any], project_root: Path, limit: int = 50) -> dict[str, Any]:
    identity = _trusted_identity(identity)
    _require_admin_action(identity, Action.AUDIT_READ)
    entries: list[dict[str, Any]] = []
    audit_path = project_root / "data" / "audit_logs" / "audit.jsonl"
    if audit_path.exists():
        lines = audit_path.read_text(encoding="utf-8").splitlines()
        for line in reversed(lines):
            if len(entries) >= limit:
                break
            try:
                entry = json.loads(line)
                entries.append({
                    "timestamp": entry.get("created_at", ""),
                    "action": entry.get("action", ""),
                    "user_id": entry.get("user_id", ""),
                    "role": entry.get("role", ""),
                    "details": entry.get("details", {}),
                })
            except json.JSONDecodeError:
                continue
    return {"entries": entries}


def admin_get_audit_event(event_id: str, identity: dict[str, Any], project_root: Path) -> dict[str, Any]:
    _require_admin_action(identity, Action.AUDIT_READ)
    from audit_store import get_event_by_id
    event = get_event_by_id(project_root, event_id)
    if not event:
        raise ValueError("event not found: {}".format(event_id))
    _filter_by_visibility(event, identity)
    return {"event": event}


def admin_query_audit_by_trace(trace_id: str, identity: dict[str, Any], project_root: Path, **kw: Any) -> dict[str, Any]:
    _require_admin_action(identity, Action.AUDIT_READ)
    from audit_store import query_by_trace
    from event_schema import EventType
    result = query_by_trace(project_root, trace_id, **kw)
    result["events"] = _filter_events_by_role(result["events"], identity)
    return result


def admin_query_audit_by_session(session_id: str, identity: dict[str, Any], project_root: Path, **kw: Any) -> dict[str, Any]:
    _require_admin_action(identity, Action.AUDIT_READ)
    from audit_store import query_by_session
    result = query_by_session(project_root, session_id, **kw)
    result["events"] = _filter_events_by_role(result["events"], identity)
    return result


def admin_query_audit_by_lead(lead_id: str, identity: dict[str, Any], project_root: Path, **kw: Any) -> dict[str, Any]:
    _require_admin_action(identity, Action.AUDIT_READ)
    from audit_store import query_by_lead
    result = query_by_lead(project_root, lead_id, **kw)
    result["events"] = _filter_events_by_role(result["events"], identity)
    return result


def admin_list_audit_events(identity: dict[str, Any], project_root: Path, **kw: Any) -> dict[str, Any]:
    _require_admin_action(identity, Action.AUDIT_READ)
    from audit_store import query_audit_events
    result = query_audit_events(project_root, **kw)
    result["events"] = _filter_events_by_role(result["events"], identity)
    return result


def _filter_events_by_role(events: list[dict[str, Any]], identity: dict[str, Any]) -> list[dict[str, Any]]:
    role = str(identity.get("role", "visitor"))
    campus = str(identity.get("campus", "all"))
    from event_schema import EventType
    allowed_types = EventType.ROLE_VISIBILITY.get(role, frozenset())

    filtered: list[dict[str, Any]] = []
    for ev in events:
        ev_type = ev.get("event_type", "")
        if ev_type not in allowed_types:
            continue
        ev_campus = ev.get("campus", "all")
        if ev_campus not in ("all", campus) and role not in ("admin",):
            continue
        filtered.append(ev)
    return filtered


def _filter_by_visibility(event: dict[str, Any], identity: dict[str, Any]) -> None:
    role = str(identity.get("role", "visitor"))
    campus = str(identity.get("campus", "all"))
    from event_schema import EventType
    allowed_types = EventType.ROLE_VISIBILITY.get(role, frozenset())
    ev_type = event.get("event_type", "")
    if ev_type not in allowed_types:
        raise ValueError("event type not visible to role '{}'".format(role))
    ev_campus = event.get("campus", "all")
    if ev_campus not in ("all", campus) and role not in ("admin",):
        raise ValueError("campus not accessible: {}".format(ev_campus))
