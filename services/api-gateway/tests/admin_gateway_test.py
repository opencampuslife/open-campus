from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SERVICE_SRC = ROOT / "services" / "api-gateway" / "src"
sys.path.append(str(SERVICE_SRC))

from admin_gateway import (  # noqa: E402
    admin_approve_staging_doc,
    admin_cancel_ingestion_run,
    admin_create_graph_run,
    admin_create_ingestion_run,
    admin_get_graph_run,
    admin_get_ingestion_run,
    admin_get_latest_graph,
    admin_get_staging_doc,
    admin_health,
    admin_list_audit_logs,
    admin_list_graph_runs,
    admin_list_ingestion_runs,
    admin_list_sources,
    admin_list_staging_docs,
    admin_publish_staging_doc,
    admin_reject_staging_doc,
    admin_sources_upload,
    admin_update_staging_doc,
    admin_validate_staging_doc,
)


def _admin_identity() -> dict[str, str]:
    return {"user_id": "u_admin", "role": "admin", "campus": "all", "auth_level": "admin"}


def _sales_identity() -> dict[str, str]:
    return {"user_id": "u_sales", "role": "sales", "campus": "zhengzhou", "auth_level": "sales"}


class AdminGatewayTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        (self.root / "data").mkdir(parents=True, exist_ok=True)
        (self.root / "data" / "ingestion").mkdir(exist_ok=True)
        (self.root / "data" / "staging").mkdir(exist_ok=True)
        (self.root / "data" / "graph-runs").mkdir(exist_ok=True)
        (self.root / "data" / "audit_logs").mkdir(exist_ok=True)
        (self.root / "data" / "published").mkdir(exist_ok=True)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    # --- Health ---

    def test_admin_health_returns_ok(self) -> None:
        result = admin_health(_admin_identity(), self.root)
        self.assertEqual(result["status"], "ok")
        self.assertIn("services", result)
        self.assertIn("version", result)

    # --- Sources ---

    def test_admin_list_sources_returns_list(self) -> None:
        result = admin_list_sources(_admin_identity(), self.root)
        self.assertIn("sources", result)
        self.assertIsInstance(result["sources"], list)

    def test_admin_sources_upload_creates_ingestion_run_and_staging_doc(self) -> None:
        upload_file = self.root / "data" / "test_upload.md"
        upload_file.write_text("# Test Document\n\nThis is test content.", encoding="utf-8")
        files = [{"path": str(upload_file), "filename": "test_upload.md"}]
        result = admin_sources_upload({}, files, _admin_identity(), self.root)
        self.assertIn("run_id", result)
        self.assertIn("staging_doc_id", result)
        self.assertEqual(result["status"], "ingested")
        run_path = self.root / "data" / "ingestion" / f"{result['run_id']}.json"
        self.assertTrue(run_path.exists())
        staging_path = self.root / "data" / "staging" / f"{result['staging_doc_id']}.json"
        self.assertTrue(staging_path.exists())

    def test_upload_missing_file_raises(self) -> None:
        with self.assertRaisesRegex(ValueError, "Uploaded file not found"):
            admin_sources_upload({}, [{"path": "/nonexistent/file.md", "filename": "nope.md"}], _admin_identity(), self.root)

    # --- Non-admin role gets 403 ---

    def test_non_admin_cannot_list_sources(self) -> None:
        with self.assertRaisesRegex(ValueError, "denied"):
            admin_list_sources(_sales_identity(), self.root)

    def test_non_admin_cannot_list_staging_docs(self) -> None:
        with self.assertRaisesRegex(ValueError, "denied"):
            admin_list_staging_docs(_sales_identity(), self.root)

    def test_non_admin_cannot_access_ingestion(self) -> None:
        with self.assertRaisesRegex(ValueError, "denied"):
            admin_list_ingestion_runs(_sales_identity(), self.root)

    def test_non_admin_cannot_access_graph(self) -> None:
        with self.assertRaisesRegex(ValueError, "denied"):
            admin_list_graph_runs(_sales_identity(), self.root)

    def test_non_admin_cannot_access_audit(self) -> None:
        with self.assertRaisesRegex(ValueError, "denied"):
            admin_list_audit_logs(_sales_identity(), self.root)

    # --- Ingestion Runs ---

    def test_create_ingestion_run(self) -> None:
        result = admin_create_ingestion_run(
            {"source_type": "manual", "source_path": "/tmp/test.md"},
            _admin_identity(), self.root,
        )
        self.assertIn("run_id", result)
        self.assertEqual(result["status"], "pending")
        self.assertEqual(result["source_type"], "manual")

    def test_list_ingestion_runs(self) -> None:
        admin_create_ingestion_run({"source_type": "test"}, _admin_identity(), self.root)
        result = admin_list_ingestion_runs(_admin_identity(), self.root)
        self.assertIn("runs", result)
        self.assertGreaterEqual(len(result["runs"]), 1)

    def test_get_ingestion_run_not_found(self) -> None:
        with self.assertRaisesRegex(ValueError, "not found"):
            admin_get_ingestion_run("nonexistent", _admin_identity(), self.root)

    def test_cancel_ingestion_run(self) -> None:
        created = admin_create_ingestion_run({"source_type": "test"}, _admin_identity(), self.root)
        result = admin_cancel_ingestion_run(created["run_id"], _admin_identity(), self.root)
        self.assertEqual(result["status"], "cancelled")

    def test_cancel_completed_run_raises(self) -> None:
        created = admin_create_ingestion_run({"source_type": "test"}, _admin_identity(), self.root)
        run_path = self.root / "data" / "ingestion" / f"{created['run_id']}.json"
        run = json.loads(run_path.read_text(encoding="utf-8"))
        run["status"] = "completed"
        run_path.write_text(json.dumps(run, ensure_ascii=False), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "Cannot cancel"):
            admin_cancel_ingestion_run(created["run_id"], _admin_identity(), self.root)

    # --- Staging Docs ---

    def test_list_staging_docs_returns_list(self) -> None:
        result = admin_list_staging_docs(_admin_identity(), self.root)
        self.assertIn("docs", result)
        self.assertIsInstance(result["docs"], list)

    def test_get_staging_doc_not_found(self) -> None:
        with self.assertRaisesRegex(ValueError, "not found"):
            admin_get_staging_doc("nonexistent", _admin_identity(), self.root)

    def test_update_staging_doc_updates_title(self) -> None:
        upload_file = self.root / "data" / "update_test.md"
        upload_file.write_text("# Update Test", encoding="utf-8")
        uploaded = admin_sources_upload({}, [{"path": str(upload_file), "filename": "update_test.md"}], _admin_identity(), self.root)
        result = admin_update_staging_doc(uploaded["staging_doc_id"], {"title": "New Title"}, _admin_identity(), self.root)
        self.assertEqual(result["title"], "New Title")

    def test_validate_staging_doc_checks_frontmatter(self) -> None:
        upload_file = self.root / "data" / "validate_test.md"
        upload_file.write_text("# Validate Test\n\nContent here.", encoding="utf-8")
        uploaded = admin_sources_upload({}, [{"path": str(upload_file), "filename": "validate_test.md"}], _admin_identity(), self.root)
        result = admin_validate_staging_doc(uploaded["staging_doc_id"], _admin_identity(), self.root)
        self.assertEqual(result["validation_status"], "failed")
        self.assertIn("Missing frontmatter", result["issues"])

    def test_validate_staging_doc_with_good_frontmatter(self) -> None:
        upload_file = self.root / "data" / "good_fm.md"
        upload_file.write_text("# Good FM\n\nContent.", encoding="utf-8")
        payload = {
            "frontmatter": {
                "title": "Good FM",
                "doc_id": "doc_good_001",
                "visibility": "public",
                "allowed_roles": ["public"],
                "data_level": "public",
                "data_level_int": 0,
                "status": "active",
                "effective_date": "2026-01-01",
                "expiry_date": "2027-01-01",
            }
        }
        uploaded = admin_sources_upload(payload, [{"path": str(upload_file), "filename": "good_fm.md"}], _admin_identity(), self.root)
        result = admin_validate_staging_doc(uploaded["staging_doc_id"], _admin_identity(), self.root)
        self.assertEqual(result["validation_status"], "passed")
        self.assertEqual(result["compliance_status"], "passed")

    # --- Approve / Reject / Publish ---

    def test_approve_requires_validation_passed(self) -> None:
        upload_file = self.root / "data" / "approve_no_val.md"
        upload_file.write_text("# No Val", encoding="utf-8")
        uploaded = admin_sources_upload({}, [{"path": str(upload_file), "filename": "approve_no_val.md"}], _admin_identity(), self.root)
        with self.assertRaisesRegex(ValueError, "validation has not passed"):
            admin_approve_staging_doc(uploaded["staging_doc_id"], _admin_identity(), self.root)

    def test_approve_staging_doc_sets_reviewer(self) -> None:
        upload_file = self.root / "data" / "approve_ok.md"
        upload_file.write_text("# Approve OK", encoding="utf-8")
        payload = {
            "frontmatter": {
                "title": "Approve OK",
                "doc_id": "doc_approve_001",
                "visibility": "public",
                "allowed_roles": ["public"],
                "data_level": "public",
                "data_level_int": 0,
                "status": "active",
                "effective_date": "2026-01-01",
                "expiry_date": "2027-01-01",
            }
        }
        uploaded = admin_sources_upload(payload, [{"path": str(upload_file), "filename": "approve_ok.md"}], _admin_identity(), self.root)
        admin_validate_staging_doc(uploaded["staging_doc_id"], _admin_identity(), self.root)
        result = admin_approve_staging_doc(uploaded["staging_doc_id"], _admin_identity(), self.root)
        self.assertEqual(result["review_status"], "approved")
        self.assertEqual(result["reviewer"], "u_admin")

    def test_reject_staging_doc_sets_reason(self) -> None:
        upload_file = self.root / "data" / "reject_test.md"
        upload_file.write_text("# Reject Test", encoding="utf-8")
        uploaded = admin_sources_upload({}, [{"path": str(upload_file), "filename": "reject_test.md"}], _admin_identity(), self.root)
        result = admin_reject_staging_doc(uploaded["staging_doc_id"], {"reason": "Incomplete content"}, _admin_identity(), self.root)
        self.assertEqual(result["review_status"], "rejected")
        self.assertEqual(result["reason"], "Incomplete content")

    def test_publish_requires_approved_status(self) -> None:
        upload_file = self.root / "data" / "publish_no_approve.md"
        upload_file.write_text("# Publish No Approve", encoding="utf-8")
        uploaded = admin_sources_upload({}, [{"path": str(upload_file), "filename": "publish_no_approve.md"}], _admin_identity(), self.root)
        with self.assertRaisesRegex(ValueError, "review status is 'draft'"):
            admin_publish_staging_doc(uploaded["staging_doc_id"], _admin_identity(), self.root)

    def test_publish_staging_doc_sets_published(self) -> None:
        upload_file = self.root / "data" / "publish_ok.md"
        upload_file.write_text("# Publish OK", encoding="utf-8")
        payload = {
            "frontmatter": {
                "title": "Publish OK",
                "doc_id": "doc_pub_001",
                "visibility": "public",
                "allowed_roles": ["public"],
                "data_level": "public",
                "data_level_int": 0,
                "status": "active",
                "effective_date": "2026-01-01",
                "expiry_date": "2027-01-01",
            }
        }
        uploaded = admin_sources_upload(payload, [{"path": str(upload_file), "filename": "publish_ok.md"}], _admin_identity(), self.root)
        admin_validate_staging_doc(uploaded["staging_doc_id"], _admin_identity(), self.root)
        admin_approve_staging_doc(uploaded["staging_doc_id"], _admin_identity(), self.root)
        result = admin_publish_staging_doc(uploaded["staging_doc_id"], _admin_identity(), self.root)
        self.assertEqual(result["review_status"], "published")
        self.assertIn("published_at", result)

    # --- Graph Runs ---

    def test_list_graph_runs_returns_list(self) -> None:
        result = admin_list_graph_runs(_admin_identity(), self.root)
        self.assertIn("runs", result)
        self.assertIsInstance(result["runs"], list)

    def test_create_graph_run(self) -> None:
        result = admin_create_graph_run({"target_type": "knowledge_vault"}, _admin_identity(), self.root)
        self.assertIn("graph_run_id", result)
        self.assertEqual(result["status"], "pending")
        self.assertEqual(result["target_type"], "knowledge_vault")

    def test_get_graph_run_not_found(self) -> None:
        with self.assertRaisesRegex(ValueError, "not found"):
            admin_get_graph_run("nonexistent", _admin_identity(), self.root)

    def test_get_latest_graph_returns_empty_when_no_runs(self) -> None:
        result = admin_get_latest_graph(_admin_identity(), self.root)
        self.assertIsNone(result["graph_run_id"])
        self.assertEqual(result["nodes"], [])
        self.assertEqual(result["edges"], [])

    def test_get_latest_graph_prefers_latest_finished_at_over_filename(self) -> None:
        older = {
            "graph_run_id": "graph_run_mock_pilot_001",
            "finished_at": "2026-05-24T08:13:00+09:00",
            "started_at": "2026-05-24T08:10:00+09:00",
            "summary": {},
        }
        newer = {
            "graph_run_id": "graph_run_mock_005",
            "finished_at": "2026-05-24T09:21:45+09:00+09:00",
            "started_at": "2026-05-24T09:20:00+09:00+09:00",
            "summary": {},
        }
        (self.root / "data" / "graph-runs" / "graph_run_mock_pilot_001.json").write_text(
            json.dumps(older, ensure_ascii=False),
            encoding="utf-8",
        )
        (self.root / "data" / "graph-runs" / "graph_run_mock_005.json").write_text(
            json.dumps(newer, ensure_ascii=False),
            encoding="utf-8",
        )
        graph_run_dir = self.root / "data" / "graph-runs" / "graph_run_mock_005"
        (graph_run_dir / "nodes").mkdir(parents=True, exist_ok=True)
        (graph_run_dir / "edges").mkdir(parents=True, exist_ok=True)
        (graph_run_dir / "nodes" / "nodes_005.json").write_text(
            json.dumps({"graph_run_id": "graph_run_mock_005", "nodes": [{"node_id": "n1", "label": "Node 1"}]}, ensure_ascii=False),
            encoding="utf-8",
        )
        (graph_run_dir / "edges" / "edges_005.json").write_text(
            json.dumps({"graph_run_id": "graph_run_mock_005", "edges": [{"source_node_id": "n1", "target_node_id": "n1"}]}, ensure_ascii=False),
            encoding="utf-8",
        )

        result = admin_get_latest_graph(_admin_identity(), self.root)
        self.assertEqual(result["graph_run_id"], "graph_run_mock_005")
        self.assertEqual(len(result["nodes"]), 1)

    def test_get_graph_run_loads_composite_from_run_directory(self) -> None:
        run = {
            "graph_run_id": "graph_run_mock_pilot_001",
            "finished_at": "2026-05-24T08:13:00+09:00",
            "started_at": "2026-05-24T08:10:00+09:00",
            "summary": {},
        }
        run_dir = self.root / "data" / "graph-runs" / "graph_run_mock_pilot_001"
        run_dir.mkdir(parents=True, exist_ok=True)
        (self.root / "data" / "graph-runs" / "graph_run_mock_pilot_001.json").write_text(
            json.dumps(run, ensure_ascii=False),
            encoding="utf-8",
        )
        (run_dir / "graph_comprehensive_mock_pilot_001.json").write_text(
            json.dumps(
                {
                    "graph_run": run,
                    "nodes": [{"node_id": "pilot-node", "label": "Pilot Node"}],
                    "edges": [{"source_node_id": "pilot-node", "target_node_id": "pilot-node"}],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        result = admin_get_graph_run("graph_run_mock_pilot_001", _admin_identity(), self.root)
        self.assertEqual(len(result["nodes"]), 1)
        self.assertEqual(len(result["edges"]), 1)

    # --- Audit Logs ---

    def test_list_audit_logs_returns_list(self) -> None:
        import json as _json
        log_dir = self.root / "data" / "audit_logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        (log_dir / "audit.jsonl").write_text(
            _json.dumps({"action": "test", "user_id": "u_admin", "role": "admin", "created_at": "2026-01-01T00:00:00"}) + "\n",
            encoding="utf-8",
        )
        result = admin_list_audit_logs(_admin_identity(), self.root)
        self.assertIn("entries", result)
        self.assertGreaterEqual(len(result["entries"]), 1)
        self.assertEqual(result["entries"][0]["action"], "test")


if __name__ == "__main__":
    unittest.main()
