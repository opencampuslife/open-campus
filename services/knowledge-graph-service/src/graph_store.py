from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


TOOL_VERSION = "0.1.0"


class GraphStore:
    def __init__(self, project_root: Path) -> None:
        self._project_root = project_root
        self._runs_dir = project_root / "data" / "graph-runs"
        self._runs_dir.mkdir(parents=True, exist_ok=True)

    def _run_dir(self, graph_run_id: str) -> Path:
        return self._runs_dir / graph_run_id

    def _read_json(self, path: Path) -> dict | None:
        if not path.is_file():
            return None
        return json.loads(path.read_text(encoding="utf-8"))

    def _write_json(self, path: Path, data: Any) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def create_run(self, target_type: str, target_id: str) -> dict:
        graph_run_id = uuid.uuid4().hex
        now = datetime.now(timezone.utc).isoformat()
        run_data = {
            "graph_run_id": graph_run_id,
            "target_type": target_type,
            "target_id": target_id,
            "status": "running",
            "tool_version": TOOL_VERSION,
            "started_at": now,
            "finished_at": None,
            "error_message": None,
            "summary": {},
        }
        run_dir = self._run_dir(graph_run_id)
        run_dir.mkdir(parents=True, exist_ok=True)
        self._write_json(run_dir / "run.json", run_data)
        self._write_json(run_dir / "nodes.json", [])
        self._write_json(run_dir / "edges.json", [])
        return run_data

    def complete_run(self, graph_run_id: str, summary: dict) -> dict:
        run = self.get_run(graph_run_id)
        if run is None:
            raise ValueError(f"run not found: {graph_run_id}")
        run["status"] = "completed"
        run["finished_at"] = datetime.now(timezone.utc).isoformat()
        run["summary"] = summary
        self._write_json(self._run_dir(graph_run_id) / "run.json", run)
        return run

    def fail_run(self, graph_run_id: str, error_message: str) -> dict:
        run = self.get_run(graph_run_id)
        if run is None:
            raise ValueError(f"run not found: {graph_run_id}")
        run["status"] = "failed"
        run["finished_at"] = datetime.now(timezone.utc).isoformat()
        run["error_message"] = error_message
        self._write_json(self._run_dir(graph_run_id) / "run.json", run)
        return run

    def get_run(self, graph_run_id: str) -> dict | None:
        return self._read_json(self._run_dir(graph_run_id) / "run.json")

    def list_runs(self, limit: int = 20) -> list[dict]:
        if not self._runs_dir.is_dir():
            return []
        runs: list[dict] = []
        for entry in self._runs_dir.iterdir():
            if entry.is_dir():
                run = self.get_run(entry.name)
                if run is not None:
                    runs.append(run)
        runs.sort(key=lambda r: r.get("started_at", ""), reverse=True)
        return runs[:limit]

    def add_node(
        self,
        graph_run_id: str,
        node_id: str,
        node_type: str,
        label: str,
        source_doc_id: str,
        metadata: dict,
    ) -> dict:
        node = {
            "graph_run_id": graph_run_id,
            "node_id": node_id,
            "node_type": node_type,
            "label": label,
            "source_doc_id": source_doc_id,
            "metadata": metadata,
        }
        nodes_path = self._run_dir(graph_run_id) / "nodes.json"
        nodes = self._read_json(nodes_path) or []
        nodes.append(node)
        self._write_json(nodes_path, nodes)
        return node

    def add_edge(
        self,
        graph_run_id: str,
        edge_id: str,
        source_node_id: str,
        target_node_id: str,
        edge_type: str,
        metadata: dict,
    ) -> dict:
        edge = {
            "graph_run_id": graph_run_id,
            "edge_id": edge_id,
            "source_node_id": source_node_id,
            "target_node_id": target_node_id,
            "edge_type": edge_type,
            "metadata": metadata,
        }
        edges_path = self._run_dir(graph_run_id) / "edges.json"
        edges = self._read_json(edges_path) or []
        edges.append(edge)
        self._write_json(edges_path, edges)
        return edge

    def get_nodes(self, graph_run_id: str) -> list[dict]:
        nodes = self._read_json(self._run_dir(graph_run_id) / "nodes.json")
        return nodes or []

    def get_edges(self, graph_run_id: str) -> list[dict]:
        edges = self._read_json(self._run_dir(graph_run_id) / "edges.json")
        return edges or []

    def get_latest_run(self) -> dict | None:
        runs = self.list_runs(limit=1)
        if not runs:
            return None
        latest = runs[0]
        if latest["status"] != "completed":
            return None
        return latest

    def get_latest_graph(self) -> dict:
        run = self.get_latest_run()
        if run is None:
            return {"run": None, "nodes": [], "edges": []}
        graph_run_id = run["graph_run_id"]
        return {
            "run": run,
            "nodes": self.get_nodes(graph_run_id),
            "edges": self.get_edges(graph_run_id),
        }
