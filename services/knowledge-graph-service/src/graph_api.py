from __future__ import annotations

import json
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from graph_store import GraphStore


class GraphAPI:
    def __init__(self, project_root: Path) -> None:
        self._project_root = project_root
        self._store = GraphStore(project_root)
        self._audit_dir = project_root / "data" / "audit_logs"
        self._audit_dir.mkdir(parents=True, exist_ok=True)

    def _audit(self, action: str, detail: dict) -> None:
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "action": action,
            "detail": detail,
        }
        log_path = self._audit_dir / "graph_api_audit.jsonl"
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    @property
    def store(self) -> GraphStore:
        return self._store

    def _parse_frontmatter(self, text: str) -> dict:
        match = re.match(r"^---\s*\n(.*?)\n(?:---|\.\.\.)", text, re.DOTALL)
        if not match:
            return {}
        raw = match.group(1)
        frontmatter: dict = {}
        current_key = None
        current_list: list[str] = []
        for line in raw.split("\n"):
            stripped = line.strip()
            if not stripped or stripped == "---":
                continue
            if stripped.startswith("- "):
                if current_key is not None:
                    current_list.append(stripped[2:].strip().strip('"').strip("'"))
                continue
            if current_key is not None and current_list:
                frontmatter[current_key] = current_list
                current_list = []
                current_key = None
            if ":" in stripped:
                key, _, value = stripped.partition(":")
                current_key = key.strip()
                value = value.strip()
                if value == "":
                    current_list = []
                elif value.startswith("[") and value.endswith("]"):
                    try:
                        frontmatter[current_key] = json.loads(value)
                    except (json.JSONDecodeError, ValueError):
                        frontmatter[current_key] = [
                            v.strip().strip('"').strip("'")
                            for v in value[1:-1].split(",")
                        ]
                    current_key = None
                elif value.startswith('"') and value.endswith('"'):
                    frontmatter[current_key] = value[1:-1]
                    current_key = None
                elif value.startswith("'") and value.endswith("'"):
                    frontmatter[current_key] = value[1:-1]
                    current_key = None
                else:
                    frontmatter[current_key] = value
                    current_key = None
        if current_key is not None and current_list:
            frontmatter[current_key] = current_list
        return frontmatter

    def _load_md_doc(self, path: Path) -> dict | None:
        if not path.is_file():
            return None
        text = path.read_text(encoding="utf-8")
        frontmatter = self._parse_frontmatter(text)
        doc_id = frontmatter.get("doc_id", path.stem)
        title = frontmatter.get("title", path.stem)
        return {
            "doc_id": doc_id,
            "title": title,
            "frontmatter": frontmatter,
            "source_path": str(path.relative_to(self._project_root)),
            "visibility": frontmatter.get("visibility", "public"),
        }

    def build_graph_from_knowledge_vault(
        self, project_root: Path, created_by: str
    ) -> dict:
        run = self._store.create_run("knowledge_vault", "all")
        graph_run_id = run["graph_run_id"]

        try:
            vault_dir = project_root / "knowledge_vault"
            md_files = sorted(vault_dir.rglob("*.md"))

            docs: list[dict] = []
            topics: dict[str, dict] = {}

            for md_path in md_files:
                doc = self._load_md_doc(md_path)
                if doc is None:
                    continue
                docs.append(doc)

                self._store.add_node(
                    graph_run_id=graph_run_id,
                    node_id=doc["doc_id"],
                    node_type="document",
                    label=doc["title"],
                    source_doc_id=doc["doc_id"],
                    metadata={
                        "visibility": doc["visibility"],
                        "source_path": doc["source_path"],
                        "frontmatter": doc["frontmatter"],
                    },
                )

                tags = doc["frontmatter"].get("business_tags", [])
                if isinstance(tags, str):
                    tags = [tags]
                for tag in tags:
                    tag_key = tag.strip()
                    if tag_key not in topics:
                        topic_id = "topic_{}".format(uuid.uuid4().hex[:8])
                        topics[tag_key] = {
                            "node_id": topic_id,
                            "label": tag_key,
                        }
                        self._store.add_node(
                            graph_run_id=graph_run_id,
                            node_id=topic_id,
                            node_type="topic",
                            label=tag_key,
                            source_doc_id="",
                            metadata={"tag": tag_key},
                        )
                    self._store.add_edge(
                        graph_run_id=graph_run_id,
                        edge_id=uuid.uuid4().hex,
                        source_node_id=doc["doc_id"],
                        target_node_id=topics[tag_key]["node_id"],
                        edge_type="has_topic",
                        metadata={"tag": tag_key},
                    )

            doc_ids = [d["doc_id"] for d in docs]
            for i in range(len(doc_ids)):
                for j in range(i + 1, len(doc_ids)):
                    di = docs[i]
                    dj = docs[j]
                    ti = set(di["frontmatter"].get("business_tags", []))
                    tj = set(dj["frontmatter"].get("business_tags", []))
                    shared = ti & tj
                    if shared:
                        self._store.add_edge(
                            graph_run_id=graph_run_id,
                            edge_id=uuid.uuid4().hex,
                            source_node_id=doc_ids[i],
                            target_node_id=doc_ids[j],
                            edge_type="related_to",
                            metadata={"shared_tags": list(shared)},
                        )

            summary = {
                "total_docs": len(docs),
                "total_topics": len(topics),
                "created_by": created_by,
            }

            result = self._store.complete_run(graph_run_id, summary)
            self._audit("build_graph_from_knowledge_vault", {
                "graph_run_id": graph_run_id,
                "doc_count": len(docs),
                "topic_count": len(topics),
                "created_by": created_by,
            })
            return result

        except Exception as e:
            self._store.fail_run(graph_run_id, str(e))
            self._audit("build_graph_from_knowledge_vault_failed", {
                "graph_run_id": graph_run_id,
                "error": str(e),
                "created_by": created_by,
            })
            raise

    def build_graph_from_staging(
        self, project_root: Path, staging_doc_id: str, created_by: str
    ) -> dict:
        run = self._store.create_run("staging_doc", staging_doc_id)
        graph_run_id = run["graph_run_id"]

        try:
            staging_path = project_root / "data" / "staging" / "{}.json".format(staging_doc_id)
            if not staging_path.is_file():
                raise FileNotFoundError(
                    "staging doc not found: {}".format(staging_doc_id)
                )

            staging_doc = json.loads(staging_path.read_text(encoding="utf-8"))
            doc_id = staging_doc.get("doc_id", staging_doc_id)
            title = staging_doc.get("title", doc_id)
            frontmatter = staging_doc.get("frontmatter", {})

            self._store.add_node(
                graph_run_id=graph_run_id,
                node_id=doc_id,
                node_type="document",
                label=title,
                source_doc_id=doc_id,
                metadata={
                    "staging_doc_id": staging_doc_id,
                    "frontmatter": frontmatter,
                },
            )

            tags = frontmatter.get("business_tags", [])
            if isinstance(tags, str):
                tags = [tags]
            topics: dict[str, str] = {}
            for tag in tags:
                tag_key = tag.strip()
                if tag_key not in topics:
                    topic_id = "topic_{}".format(uuid.uuid4().hex[:8])
                    topics[tag_key] = topic_id
                    self._store.add_node(
                        graph_run_id=graph_run_id,
                        node_id=topic_id,
                        node_type="topic",
                        label=tag_key,
                        source_doc_id="",
                        metadata={"tag": tag_key},
                    )
                self._store.add_edge(
                    graph_run_id=graph_run_id,
                    edge_id=uuid.uuid4().hex,
                    source_node_id=doc_id,
                    target_node_id=topics[tag_key],
                    edge_type="has_topic",
                    metadata={"tag": tag_key},
                )

            summary = {
                "staging_doc_id": staging_doc_id,
                "doc_id": doc_id,
                "topic_count": len(topics),
                "created_by": created_by,
            }

            result = self._store.complete_run(graph_run_id, summary)
            self._audit("build_graph_from_staging", {
                "graph_run_id": graph_run_id,
                "staging_doc_id": staging_doc_id,
                "doc_id": doc_id,
                "topic_count": len(topics),
                "created_by": created_by,
            })
            return result

        except Exception as e:
            self._store.fail_run(graph_run_id, str(e))
            self._audit("build_graph_from_staging_failed", {
                "graph_run_id": graph_run_id,
                "staging_doc_id": staging_doc_id,
                "error": str(e),
                "created_by": created_by,
            })
            raise
