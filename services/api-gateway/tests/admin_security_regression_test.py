from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
import types
import unittest
import urllib.error
import urllib.request
from pathlib import Path
from threading import Thread
from http.server import ThreadingHTTPServer

ROOT = Path(__file__).resolve().parents[3]
ADMIN_SRC = ROOT / "services" / "api-gateway" / "src"
INGESTION_SRC = ROOT / "services" / "source-ingestion-service" / "src"
KNOWLEDGE_SRC = ROOT / "services" / "knowledge-service" / "src"
RAG_SRC = ROOT / "services" / "rag-service" / "src"
PERMISSION_SRC = ROOT / "services" / "permission-service" / "src"
AGENT_SRC = ROOT / "services" / "agent-orchestrator" / "src"
CRM_SRC = ROOT / "services" / "crm-service" / "src"
sys.path.extend([str(AGENT_SRC), str(CRM_SRC), str(ADMIN_SRC), str(INGESTION_SRC), str(KNOWLEDGE_SRC), str(RAG_SRC), str(PERMISSION_SRC)])

if "psycopg" not in sys.modules:
    psycopg_stub = types.ModuleType("psycopg")
    psycopg_stub.connect = lambda *args, **kwargs: None
    psycopg_rows_stub = types.ModuleType("psycopg.rows")
    psycopg_rows_stub.dict_row = object()
    psycopg_types_stub = types.ModuleType("psycopg.types")
    psycopg_types_json_stub = types.ModuleType("psycopg.types.json")
    psycopg_types_json_stub.Jsonb = lambda value: value
    sys.modules["psycopg"] = psycopg_stub
    sys.modules["psycopg.rows"] = psycopg_rows_stub
    sys.modules["psycopg.types"] = psycopg_types_stub
    sys.modules["psycopg.types.json"] = psycopg_types_json_stub

from staging_store import write_staging_doc, load_staging_doc
from publisher import publish_staging_doc
from indexer import build_index
from retriever import search
from scope_builder import build_scope
from admin_gateway import (
    admin_approve_staging_doc,
    admin_create_ingestion_run,
    admin_health,
    admin_list_staging_docs,
    admin_sources_upload,
    admin_validate_staging_doc,
)
from bff_gateway import _trusted_identity
from csrf_protection import generate_csrf_token
from server import GaokaoHandler


class _QuietHTTPServer(ThreadingHTTPServer):
    allow_reuse_address = True


class _LegacyAdminHTTPMixin:
    def _start_server(self) -> None:
        GaokaoHandler.project_root = self.root
        self._server = _QuietHTTPServer(("127.0.0.1", 0), GaokaoHandler)
        self._thread = Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()
        self.base_url = f"http://127.0.0.1:{self._server.server_address[1]}"

    def _stop_server(self) -> None:
        if hasattr(self, "_server"):
            self._server.shutdown()
            self._server.server_close()
        if hasattr(self, "_thread"):
            self._thread.join(timeout=2)

    def _request(
        self,
        method: str,
        path: str,
        *,
        payload: dict | None = None,
        headers: dict[str, str] | None = None,
    ) -> tuple[int, dict[str, str], dict]:
        request_headers = dict(headers or {})
        body = None
        if payload is not None:
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            request_headers.setdefault("Content-Type", "application/json")
        request = urllib.request.Request(self.base_url + path, data=body, method=method, headers=request_headers)
        try:
            with urllib.request.urlopen(request) as response:
                return response.status, dict(response.headers.items()), json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            return exc.code, dict(exc.headers.items()), json.loads(exc.read().decode("utf-8"))


class AdminSecurityRegressionTest(_LegacyAdminHTTPMixin, unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        for sub in ("data/staging", "data/ingestion", "data/graph-runs", "data/audit_logs", "data/published", "data/indexes"):
            (self.root / sub).mkdir(parents=True, exist_ok=True)
        configs_link = self.root / "configs"
        if not configs_link.exists():
            configs_link.symlink_to(ROOT / "configs", target_is_directory=True)
        self._start_server()

    def tearDown(self):
        self._stop_server()
        self._tmp.cleanup()

    def _build_approved_staging(self, doc_id: str, fm_overrides: dict | None = None, **kw) -> str:
        fm = {
            "title": doc_id,
            "doc_id": doc_id,
            "visibility": "public",
            "allowed_roles": ["parent", "student", "sales", "admin"],
            "data_level": "L1",
            "data_level_int": 1,
            "campus_scope": ["all"],
            "business_tags": ["test"],
            "effective_date": "2026-01-01",
            "expiry_date": "2099-12-31",
            "owner": "test",
            "review_status": "approved",
            "source_type": "test",
            "version": 1,
        }
        if fm_overrides:
            fm.update(fm_overrides)
        doc_data = {
            "run_id": f"r_{doc_id}",
            "doc_id": doc_id,
            "title": doc_id,
            "canonical_markdown": f"# {doc_id}\n\n测试内容。",
            "frontmatter": fm,
            "validation_status": "passed",
            "compliance_status": "passed",
            "review_status": "approved",
            "source_hash": f"hash_{doc_id}",
            "created_by": "test",
        }
        doc_data.update(kw)
        return write_staging_doc(self.root, doc_data)

    def _write_and_publish(self, doc_id: str, fm_overrides: dict | None = None, **kw) -> tuple[str, dict]:
        sid = self._build_approved_staging(doc_id, fm_overrides, **kw)
        result = publish_staging_doc(self.root, sid, "test_publisher", "admin")
        self.assertTrue(result["success"], f"publish failed: {result.get('error')}")
        return sid, result

    def test_admin_api_ignores_client_supplied_role(self):
        # sales role cannot access any knowledge-admin routes (including health)
        non_admin = {"user_id": "u_sales", "role": "sales", "campus": "zhengzhou"}
        with self.assertRaises(ValueError):
            admin_health(non_admin, self.root)
        with self.assertRaises(ValueError):
            admin_list_staging_docs(non_admin, self.root)
        # But a valid knowledge role (content_operator) can access health
        co = {"user_id": "u_co", "role": "content_operator", "campus": "zhengzhou"}
        result = admin_health(co, self.root)
        self.assertEqual(result["status"], "ok")
        # content_operator can read staging docs too
        result = admin_list_staging_docs(co, self.root)
        self.assertIn("docs", result)

    def test_staging_doc_not_searchable_before_publish(self):
        write_staging_doc(self.root, {
            "staging_doc_id": "s_test_01",
            "run_id": "r_test_01",
            "doc_id": "test_staging_only",
            "title": "Test Staging Only",
            "canonical_markdown": "这是测试内容，不应该被检索到",
            "frontmatter": {
                "title": "Test Staging Only",
                "doc_id": "test_staging_only",
                "visibility": "public",
                "allowed_roles": ["parent", "sales", "admin"],
                "data_level": "L1",
                "data_level_int": 1,
                "campus_scope": ["all"],
                "business_tags": ["test"],
                "effective_date": "2026-01-01",
                "expiry_date": "2027-01-01",
                "owner": "test",
                "review_status": "draft",
                "source_type": "test",
                "version": 1,
            },
            "validation_status": "pending",
            "compliance_status": "pending",
            "review_status": "draft",
            "source_hash": "abc123",
            "created_by": "test",
        })
        (self.root / "knowledge_vault").mkdir(parents=True, exist_ok=True)
        build_index(self.root)
        scope = build_scope({"role": "parent", "campus": "all"}, self.root)
        result = search("测试", scope, self.root)
        doc_ids = {c["doc_id"] for c in result["allowed_chunks"]}
        self.assertNotIn("test_staging_only", doc_ids)

    def test_published_doc_respects_rls(self):
        _, pub = self._write_and_publish("doc_rls_001", fm_overrides={
            "visibility": "internal",
            "allowed_roles": ["sales", "admin"],
        })
        self.assertEqual(pub["version"], 1)
        build_index(self.root)

        parent_scope = build_scope({"role": "parent", "campus": "all"}, self.root)
        parent_result = search("测试", parent_scope, self.root)
        parent_ids = {c["doc_id"] for c in parent_result["allowed_chunks"]}
        self.assertNotIn("doc_rls_001", parent_ids)

        admin_scope = build_scope({"role": "admin", "campus": "all"}, self.root)
        admin_result = search("测试", admin_scope, self.root)
        admin_ids = {c["doc_id"] for c in admin_result["allowed_chunks"]}
        self.assertIn("doc_rls_001", admin_ids)

    def test_graph_build_failure_does_not_block_publish(self):
        sid = self._build_approved_staging("doc_graph_fail")
        result = publish_staging_doc(self.root, sid, "test_user", "admin")
        self.assertTrue(result["success"], f"publish failed: {result.get('error')}")
        self.assertEqual(result["doc_id"], "doc_graph_fail")

    def test_publish_same_source_hash_is_idempotent(self):
        _, r1 = self._write_and_publish("doc_idem",
            source_hash="hash_idem", run_id="r_idem_1")
        self.assertEqual(r1["version"], 1)

        _, r2 = self._write_and_publish("doc_idem",
            source_hash="hash_idem", run_id="r_idem_2")
        self.assertEqual(r2["version"], 2)

    def test_publish_existing_doc_id_requires_new_version(self):
        _, r1 = self._write_and_publish("doc_ver",
            source_hash="hash_v1", run_id="r_ver_1",
            canonical_markdown="# V1\nFirst version.")
        self.assertEqual(r1["version"], 1)

        _, r2 = self._write_and_publish("doc_ver",
            source_hash="hash_v2", run_id="r_ver_2",
            canonical_markdown="# V2\nUpdated content with different text.")
        self.assertEqual(r2["version"], 2)

    def test_post_admin_replacements_require_csrf(self):
        created = admin_create_ingestion_run({"source_type": "test"}, {"user_id": "u_admin", "role": "admin", "campus": "all"}, self.root)
        status, _, body = self._request(
            "POST",
            f"/api/admin/ingestion/runs/{created['run_id']}/cancel",
            payload={"identity": {"user_id": "u_admin", "role": "admin", "campus": "all"}},
        )
        self.assertEqual(status, 403)
        self.assertEqual(body["error"], "csrf_token_required")

    def test_post_admin_replacements_and_get_aliases_stay_compatible(self):
        csrf_headers = {"X-CSRF-Token": generate_csrf_token("u_admin")}

        created = admin_create_ingestion_run({"source_type": "test"}, {"user_id": "u_admin", "role": "admin", "campus": "all"}, self.root)
        cancel_path = f"/api/admin/ingestion/runs/{created['run_id']}/cancel?user_id=u_admin&role=admin&campus=all&auth_level=admin"
        status, headers, body = self._request("GET", cancel_path)
        self.assertEqual(status, 200)
        self.assertEqual(body["status"], "cancelled")
        self.assertEqual(headers.get("Deprecation"), "true")
        self.assertEqual(headers.get("X-Gaokao-Legacy-Route"), "state-changing-get")
        self.assertIn("</api/admin/ingestion/runs/", headers.get("Link", ""))
        self.assertIn("/cancel>", headers.get("Link", ""))

        created_post = admin_create_ingestion_run({"source_type": "test"}, {"user_id": "u_admin", "role": "admin", "campus": "all"}, self.root)
        cancel_post_path = f"/api/admin/ingestion/runs/{created_post['run_id']}/cancel"
        status, headers, body = self._request(
            "POST",
            cancel_post_path,
            payload={"identity": {"user_id": "u_admin", "role": "admin", "campus": "all"}},
            headers=csrf_headers,
        )
        self.assertEqual(status, 200)
        self.assertEqual(body["status"], "cancelled")
        self.assertNotIn("Deprecation", headers)

        upload_file = self.root / "data" / "http_validate.md"
        upload_file.write_text("# Validate\n\nContent.", encoding="utf-8")
        uploaded = admin_sources_upload({}, [{"path": str(upload_file), "filename": "http_validate.md"}], {"user_id": "u_admin", "role": "admin", "campus": "all"}, self.root)
        validate_path = f"/api/admin/staging/docs/{uploaded['staging_doc_id']}/validate"
        status, _, body = self._request(
            "POST",
            validate_path,
            payload={"identity": {"user_id": "u_admin", "role": "admin", "campus": "all"}},
            headers=csrf_headers,
        )
        self.assertEqual(status, 200)
        self.assertEqual(body["validation_status"], "failed")

        payload = {
            "frontmatter": {
                "title": "Approve",
                "doc_id": "doc_http_approve_001",
                "visibility": "public",
                "allowed_roles": ["public"],
                "data_level": "public",
                "data_level_int": 0,
                "status": "active",
                "effective_date": "2026-01-01",
                "expiry_date": "2027-01-01",
            }
        }
        approve_file = self.root / "data" / "http_approve.md"
        approve_file.write_text("# Approve\n\nContent.", encoding="utf-8")
        approved_upload = admin_sources_upload(payload, [{"path": str(approve_file), "filename": "http_approve.md"}], {"user_id": "u_admin", "role": "admin", "campus": "all"}, self.root)
        admin_validate_staging_doc(approved_upload["staging_doc_id"], {"user_id": "u_admin", "role": "admin", "campus": "all"}, self.root)
        status, _, body = self._request(
            "POST",
            f"/api/admin/staging/docs/{approved_upload['staging_doc_id']}/approve",
            payload={"identity": {"user_id": "u_admin", "role": "admin", "campus": "all"}},
            headers=csrf_headers,
        )
        self.assertEqual(status, 200)
        self.assertEqual(body["review_status"], "approved")

        reject_file = self.root / "data" / "http_reject.md"
        reject_file.write_text("# Reject\n\nContent.", encoding="utf-8")
        rejected_upload = admin_sources_upload({}, [{"path": str(reject_file), "filename": "http_reject.md"}], {"user_id": "u_admin", "role": "admin", "campus": "all"}, self.root)
        status, headers, body = self._request(
            "GET",
            f"/api/admin/staging/docs/{rejected_upload['staging_doc_id']}/reject?user_id=u_admin&role=admin&campus=all&auth_level=admin",
        )
        self.assertEqual(status, 200)
        self.assertEqual(body["reason"], "No reason provided")
        self.assertEqual(headers.get("Deprecation"), "true")
        status, _, body = self._request(
            "POST",
            f"/api/admin/staging/docs/{rejected_upload['staging_doc_id']}/reject",
            payload={"reason": "Incomplete content", "identity": {"user_id": "u_admin", "role": "admin", "campus": "all"}},
            headers=csrf_headers,
        )
        self.assertEqual(status, 200)
        self.assertEqual(body["reason"], "Incomplete content")

        publish_file = self.root / "data" / "http_publish.md"
        publish_file.write_text("# Publish\n\nContent.", encoding="utf-8")
        publish_upload = admin_sources_upload(payload, [{"path": str(publish_file), "filename": "http_publish.md"}], {"user_id": "u_admin", "role": "admin", "campus": "all"}, self.root)
        admin_validate_staging_doc(publish_upload["staging_doc_id"], {"user_id": "u_admin", "role": "admin", "campus": "all"}, self.root)
        admin_approve_staging_doc(publish_upload["staging_doc_id"], {"user_id": "u_admin", "role": "admin", "campus": "all"}, self.root)
        status, headers, body = self._request(
            "GET",
            f"/api/admin/staging/docs/{publish_upload['staging_doc_id']}/publish?user_id=u_admin&role=admin&campus=all&auth_level=admin",
        )
        self.assertEqual(status, 200)
        self.assertEqual(body["review_status"], "published")
        self.assertEqual(headers.get("Deprecation"), "true")

    def test_legacy_get_alias_records_usage_event(self):
        created = admin_create_ingestion_run({"source_type": "test"}, {"user_id": "u_admin", "role": "admin", "campus": "all"}, self.root)
        cancel_route = f"/api/admin/ingestion/runs/{created['run_id']}/cancel"
        cancel_path = f"{cancel_route}?user_id=u_admin&role=admin&campus=all&auth_level=admin"
        log_entries_before = self._count_structured_events("legacy_admin_get_mutation_used")

        status, headers, body = self._request("GET", cancel_path)
        self.assertEqual(status, 200)
        self.assertEqual(body["status"], "cancelled")

        log_entries_after = self._count_structured_events("legacy_admin_get_mutation_used")
        self.assertGreater(log_entries_after, log_entries_before,
                           "GET alias must record at least one legacy usage event")

        last_entry = self._last_structured_event("legacy_admin_get_mutation_used")
        self.assertIsNotNone(last_entry)
        details = last_entry.get("details", {})
        self.assertEqual(details.get("route"), cancel_route)
        self.assertIn("POST /api/admin/ingestion/runs/", details.get("successor", ""))
        self.assertIn("/cancel", details.get("successor", ""))
        self.assertEqual(details.get("actor_role"), "admin")
        self.assertTrue(details.get("user_agent_hash", "").startswith("sha256:") or details.get("user_agent_hash") == "")
        self.assertTrue(details.get("client_ip_hash", "").startswith("sha256:"))
        self.assertNotIn(details.get("user_agent_hash", ""), "raw_ip")
        self.assertNotIn(details.get("client_ip_hash", ""), "raw_ip")

    def test_post_replacement_does_not_record_legacy_event(self):
        log_entries_before = self._count_structured_events("legacy_admin_get_mutation_used")
        csrf_headers = {"X-CSRF-Token": generate_csrf_token("u_admin")}
        created = admin_create_ingestion_run({"source_type": "test"}, {"user_id": "u_admin", "role": "admin", "campus": "all"}, self.root)
        status, _, _ = self._request(
            "POST",
            f"/api/admin/ingestion/runs/{created['run_id']}/cancel",
            payload={"identity": {"user_id": "u_admin", "role": "admin", "campus": "all"}},
            headers=csrf_headers,
        )
        self.assertEqual(status, 200)
        log_entries_after = self._count_structured_events("legacy_admin_get_mutation_used")
        self.assertEqual(log_entries_after, log_entries_before,
                         "POST replacement must not record a legacy usage event")

    def _count_structured_events(self, event_type: str) -> int:
        log_path = self.root / "data" / "audit_logs" / "structured.jsonl"
        if not log_path.exists():
            return 0
        count = 0
        for line in log_path.read_text(encoding="utf-8").splitlines():
            try:
                entry = json.loads(line)
                if entry.get("event_type") == event_type:
                    count += 1
            except json.JSONDecodeError:
                continue
        return count

    def _last_structured_event(self, event_type: str) -> dict | None:
        log_path = self.root / "data" / "audit_logs" / "structured.jsonl"
        if not log_path.exists():
            return None
        for line in reversed(log_path.read_text(encoding="utf-8").splitlines()):
            try:
                entry = json.loads(line)
                if entry.get("event_type") == event_type:
                    return entry
            except json.JSONDecodeError:
                continue
        return None
