from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

TEST_DIR = Path(__file__).resolve().parent
SRC_DIR = TEST_DIR.parent / "src"
sys.path.insert(0, str(SRC_DIR))

from graph_store import GraphStore
from graph_findings import analyze_graph, find_connected_docs


def _make_staging_doc(staging_dir: Path, staging_doc_id: str, doc_id: str, title: str, tags: list[str]):
    path = staging_dir / "{}.json".format(staging_doc_id)
    path.write_text(json.dumps({
        "staging_doc_id": staging_doc_id,
        "doc_id": doc_id,
        "title": title,
        "frontmatter": {"business_tags": tags},
        "canonical_markdown": "# Test",
    }, ensure_ascii=False, indent=2), encoding="utf-8")


def _make_vault_doc(vault_dir: Path, rel_path: str, doc_id: str, title: str, tags: list[str]):
    full_path = vault_dir / rel_path
    full_path.parent.mkdir(parents=True, exist_ok=True)
    tags_yaml = "\n".join("    - {}".format(t) for t in tags)
    full_path.write_text(
        "---\ntitle: {}\ndoc_id: {}\nvisibility: public\nbusiness_tags:\n{}\n---\n\n# {}".format(
            title, doc_id, tags_yaml, title
        ),
        encoding="utf-8",
    )


class TestGraphStore(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tmpdir.name)
        self.store = GraphStore(self.root)

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_create_run(self):
        run = self.store.create_run("knowledge_vault", "test_id")
        self.assertIn("graph_run_id", run)
        self.assertEqual(run["target_type"], "knowledge_vault")
        self.assertEqual(run["target_id"], "test_id")
        self.assertEqual(run["status"], "running")
        self.assertIsNone(run["finished_at"])
        self.assertIsNone(run["error_message"])
        self.assertEqual(run["summary"], {})

    def test_complete_run(self):
        run = self.store.create_run("knowledge_vault", "test_id")
        result = self.store.complete_run(run["graph_run_id"], {"total": 5})
        self.assertEqual(result["status"], "completed")
        self.assertIsNotNone(result["finished_at"])
        self.assertEqual(result["summary"], {"total": 5})

    def test_fail_run(self):
        run = self.store.create_run("knowledge_vault", "test_id")
        result = self.store.fail_run(run["graph_run_id"], "something went wrong")
        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["error_message"], "something went wrong")
        self.assertIsNotNone(result["finished_at"])

    def test_get_run_nonexistent(self):
        result = self.store.get_run("nonexistent")
        self.assertIsNone(result)

    def test_add_node(self):
        run = self.store.create_run("knowledge_vault", "test_id")
        node = self.store.add_node(
            run["graph_run_id"], "doc_1", "document", "Test Doc", "doc_1", {"visibility": "public"}
        )
        self.assertEqual(node["node_id"], "doc_1")
        self.assertEqual(node["node_type"], "document")
        self.assertEqual(node["label"], "Test Doc")
        self.assertEqual(node["source_doc_id"], "doc_1")
        self.assertEqual(node["metadata"]["visibility"], "public")

    def test_add_edge(self):
        run = self.store.create_run("knowledge_vault", "test_id")
        self.store.add_node(run["graph_run_id"], "doc_1", "document", "Doc A", "doc_1", {})
        self.store.add_node(run["graph_run_id"], "doc_2", "document", "Doc B", "doc_2", {})
        edge = self.store.add_edge(
            run["graph_run_id"], "edge_1", "doc_1", "doc_2", "related_to", {"shared_tags": ["tag1"]}
        )
        self.assertEqual(edge["edge_id"], "edge_1")
        self.assertEqual(edge["source_node_id"], "doc_1")
        self.assertEqual(edge["target_node_id"], "doc_2")
        self.assertEqual(edge["edge_type"], "related_to")

    def test_get_nodes_edges(self):
        run = self.store.create_run("knowledge_vault", "test_id")
        self.store.add_node(run["graph_run_id"], "n1", "document", "N1", "n1", {})
        self.store.add_node(run["graph_run_id"], "n2", "topic", "N2", "", {})
        self.store.add_edge(run["graph_run_id"], "e1", "n1", "n2", "has_topic", {})
        nodes = self.store.get_nodes(run["graph_run_id"])
        edges = self.store.get_edges(run["graph_run_id"])
        self.assertEqual(len(nodes), 2)
        self.assertEqual(len(edges), 1)

    def test_list_runs(self):
        r1 = self.store.create_run("knowledge_vault", "a")
        r2 = self.store.create_run("knowledge_vault", "b")
        runs = self.store.list_runs(limit=10)
        self.assertEqual(len(runs), 2)
        self.assertEqual(runs[0]["graph_run_id"], r2["graph_run_id"])
        self.assertEqual(runs[1]["graph_run_id"], r1["graph_run_id"])

    def test_latest_run(self):
        self.assertIsNone(self.store.get_latest_run())
        r1 = self.store.create_run("knowledge_vault", "a")
        self.store.complete_run(r1["graph_run_id"], {})
        latest = self.store.get_latest_run()
        self.assertEqual(latest["graph_run_id"], r1["graph_run_id"])

    def test_latest_graph(self):
        graph = self.store.get_latest_graph()
        self.assertIsNone(graph["run"])
        self.assertEqual(graph["nodes"], [])
        self.assertEqual(graph["edges"], [])
        run = self.store.create_run("knowledge_vault", "a")
        self.store.add_node(run["graph_run_id"], "n1", "document", "N1", "n1", {})
        self.store.complete_run(run["graph_run_id"], {})
        graph = self.store.get_latest_graph()
        self.assertEqual(graph["run"]["graph_run_id"], run["graph_run_id"])
        self.assertEqual(len(graph["nodes"]), 1)


class TestGraphAPI(unittest.TestCase):
    def test_build_from_vault(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            vault_dir = root / "knowledge_vault"
            _make_vault_doc(vault_dir, "public/doc_a.md", "doc_a", "Doc A", ["tag1", "tag2"])
            _make_vault_doc(vault_dir, "public/doc_b.md", "doc_b", "Doc B", ["tag2", "tag3"])
            _make_vault_doc(vault_dir, "internal/doc_c.md", "doc_c", "Doc C", ["tag1"])

            from graph_api import GraphAPI
            api = GraphAPI(root)
            result = api.build_graph_from_knowledge_vault(root, "tester")

            self.assertEqual(result["status"], "completed")
            self.assertEqual(result["summary"]["total_docs"], 3)
            self.assertEqual(result["summary"]["total_topics"], 3)

            nodes = api.store.get_nodes(result["graph_run_id"])
            edges = api.store.get_edges(result["graph_run_id"])
            doc_nodes = [n for n in nodes if n["node_type"] == "document"]
            topic_nodes = [n for n in nodes if n["node_type"] == "topic"]
            self.assertEqual(len(doc_nodes), 3)
            self.assertEqual(len(topic_nodes), 3)

            has_topic_edges = [e for e in edges if e["edge_type"] == "has_topic"]
            related_edges = [e for e in edges if e["edge_type"] == "related_to"]
            self.assertEqual(len(has_topic_edges), 5)
            self.assertEqual(len(related_edges), 2)

    def test_build_from_staging(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            staging_dir = root / "data" / "staging"
            staging_dir.mkdir(parents=True, exist_ok=True)
            _make_staging_doc(staging_dir, "stg_001", "doc_x", "Doc X", ["招生信息", "报名流程"])

            from graph_api import GraphAPI
            api = GraphAPI(root)
            result = api.build_graph_from_staging(root, "stg_001", "tester")

            self.assertEqual(result["status"], "completed")
            self.assertEqual(result["summary"]["topic_count"], 2)

            nodes = api.store.get_nodes(result["graph_run_id"])
            topic_nodes = [n for n in nodes if n["node_type"] == "topic"]
            self.assertEqual(len(topic_nodes), 2)
            labels = {n["label"] for n in topic_nodes}
            self.assertEqual(labels, {"招生信息", "报名流程"})

    def test_build_from_staging_not_found(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            from graph_api import GraphAPI
            api = GraphAPI(root)
            with self.assertRaises(FileNotFoundError):
                api.build_graph_from_staging(root, "nonexistent", "tester")


class TestGraphFindings(unittest.TestCase):
    def test_basic_analysis(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            store = GraphStore(root)
            run = store.create_run("knowledge_vault", "test")
            rid = run["graph_run_id"]

            store.add_node(rid, "d1", "document", "Doc 1", "d1", {})
            store.add_node(rid, "d2", "document", "Doc 2", "d2", {})
            store.add_node(rid, "d3", "document", "Doc 3", "d3", {})
            store.add_node(rid, "t1", "topic", "Tag A", "", {})
            store.add_node(rid, "t2", "topic", "Tag B", "", {})
            store.add_node(rid, "isolated_doc", "document", "Isolated", "isolated", {})

            store.add_edge(rid, "e1", "d1", "t1", "has_topic", {})
            store.add_edge(rid, "e2", "d2", "t1", "has_topic", {})
            store.add_edge(rid, "e3", "d2", "t2", "has_topic", {})
            store.add_edge(rid, "e4", "d3", "t2", "has_topic", {})
            store.add_edge(rid, "e5", "d1", "d2", "related_to", {"shared_tags": ["Tag A"]})

            store.complete_run(rid, {})

            analysis = analyze_graph(rid, store)
            self.assertEqual(analysis["node_count"], 6)
            self.assertEqual(analysis["edge_count"], 5)
            self.assertEqual(analysis["node_types"]["document"], 4)
            self.assertEqual(analysis["node_types"]["topic"], 2)
            self.assertEqual(len(analysis["isolated_nodes"]), 1)
            self.assertEqual(analysis["isolated_nodes"][0]["node_id"], "isolated_doc")

    def test_find_connected(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            store = GraphStore(root)
            run = store.create_run("knowledge_vault", "test")
            rid = run["graph_run_id"]

            store.add_node(rid, "d1", "document", "Doc 1", "d1", {})
            store.add_node(rid, "d2", "document", "Doc 2", "d2", {})
            store.add_node(rid, "d3", "document", "Doc 3", "d3", {})
            store.add_node(rid, "t1", "topic", "Tag A", "", {})
            store.add_node(rid, "t2", "topic", "Tag B", "", {})

            store.add_edge(rid, "e1", "d1", "t1", "has_topic", {})
            store.add_edge(rid, "e2", "d2", "t1", "has_topic", {})
            store.add_edge(rid, "e3", "d2", "t2", "has_topic", {})
            store.add_edge(rid, "e4", "d3", "t2", "has_topic", {})

            connected = find_connected_docs(rid, "d1", store)
            self.assertEqual(len(connected), 1)
            self.assertEqual(connected[0]["doc_node_id"], "d2")
            self.assertIn("Tag A", connected[0]["shared_topics"])

            connected_d3 = find_connected_docs(rid, "d3", store)
            self.assertEqual(len(connected_d3), 1)
            self.assertEqual(connected_d3[0]["doc_node_id"], "d2")

            no_conn = find_connected_docs(rid, "nonexistent", store)
            self.assertEqual(no_conn, [])


if __name__ == "__main__":
    unittest.main()
