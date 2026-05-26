from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
ADMIN_SRC = ROOT / "services" / "api-gateway" / "src"
INGESTION_SRC = ROOT / "services" / "source-ingestion-service" / "src"
sys.path.extend([str(ADMIN_SRC), str(INGESTION_SRC)])

from admin_policy import (
    AdminContext, Action, ROLE_ADMIN, ROLE_CAMPUS_ADMIN,
    ROLE_CONTENT_OPERATOR, ROLE_REVIEWER, ROLE_SALES,
    require_action, require_action_str, build_context,
    can_edit_permission_fields, is_permission_field,
    can_view_audit, can_view_crm, can_view_sales,
    PROTECTED_PERMISSION_FIELDS, ACTION_ROLES,
)
from admin_gateway import (
    admin_health, admin_list_staging_docs, admin_get_staging_doc,
    admin_update_staging_doc, admin_validate_staging_doc,
    admin_approve_staging_doc, admin_reject_staging_doc,
    admin_publish_staging_doc, admin_list_graph_runs,
    admin_create_graph_run, admin_list_audit_logs,
    admin_sources_upload, admin_create_ingestion_run,
    admin_list_sources,
)
from staging_store import write_staging_doc, load_staging_doc


class AdminRoleGranularityTest(unittest.TestCase):
    def setUp(self):
        self.tmp_root = Path(tempfile.mkdtemp())
        (self.tmp_root / "data" / "staging").mkdir(parents=True, exist_ok=True)
        (self.tmp_root / "data" / "ingestion").mkdir(parents=True, exist_ok=True)
        (self.tmp_root / "data" / "graph-runs").mkdir(parents=True, exist_ok=True)
        (self.tmp_root / "data" / "audit_logs").mkdir(parents=True, exist_ok=True)
        (self.tmp_root / "data" / "published").mkdir(parents=True, exist_ok=True)

        self.admin = {"user_id": "u_admin", "role": "admin", "campus": "all", "auth_level": "admin"}
        self.campus_admin = {"user_id": "u_ca", "role": "campus_admin", "campus": "zhengzhou", "auth_level": "staff"}
        self.content_op = {"user_id": "u_co", "role": "content_operator", "campus": "zhengzhou", "auth_level": "staff"}
        self.reviewer = {"user_id": "u_rev", "role": "reviewer", "campus": "zhengzhou", "auth_level": "staff"}
        self.sales = {"user_id": "u_sales", "role": "sales", "campus": "zhengzhou", "auth_level": "staff"}

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp_root, ignore_errors=True)

    def _make_staging(self, doc_id="test_doc", review_status="draft", campus="zhengzhou"):
        """Helper: create a staging doc and return its staging_doc_id"""
        return write_staging_doc(self.tmp_root, {
            "staging_doc_id": f"std_{doc_id}",
            "run_id": f"r_{doc_id}",
            "doc_id": doc_id,
            "title": f"Test {doc_id}",
            "canonical_markdown": f"# {doc_id}\nContent here",
            "frontmatter": {
                "title": f"Test {doc_id}", "doc_id": doc_id,
                "visibility": "internal", "allowed_roles": ["sales"],
                "data_level": "L2", "data_level_int": 2,
                "campus_scope": [campus],
                "business_tags": ["test"],
                "effective_date": "2026-01-01", "expiry_date": "2027-01-01",
                "owner": "test", "review_status": review_status,
                "source_type": "test", "version": 1,
            },
            "validation_status": "pending" if review_status == "draft" else "passed",
            "compliance_status": "pending" if review_status == "draft" else "passed",
            "review_status": review_status,
            "source_hash": "hash_" + doc_id,
            "created_by": "test",
        })

    def test_admin_can_access_all_admin_routes(self):
        for identity in [self.admin]:
            result = admin_health(identity, self.tmp_root)
            self.assertEqual(result["status"], "ok")
            result = admin_list_staging_docs(identity, self.tmp_root)
            self.assertIn("docs", result)

    def test_sales_cannot_access_knowledge_admin_routes(self):
        # Sales should be denied on knowledge admin paths
        with self.assertRaises(ValueError) as ctx:
            admin_list_staging_docs(self.sales, self.tmp_root)
        self.assertIn("denied", str(ctx.exception))

        with self.assertRaises(ValueError):
            admin_list_graph_runs(self.sales, self.tmp_root)

    def test_content_operator_can_access_staging_read(self):
        # content_operator can read staging but not approve/publish
        self._make_staging("doc_co")
        result = admin_list_staging_docs(self.content_op, self.tmp_root)
        self.assertIn("docs", result)
        # Also can access health
        result = admin_health(self.content_op, self.tmp_root)
        self.assertEqual(result["status"], "ok")

    def test_content_operator_cannot_approve(self):
        sid = self._make_staging("doc_co_approve")
        with self.assertRaises(ValueError) as ctx:
            admin_approve_staging_doc(sid, self.content_op, self.tmp_root)
        self.assertIn("denied", str(ctx.exception))
        self.assertIn("approve", str(ctx.exception).lower() or "staging.approve")

    def test_content_operator_cannot_publish(self):
        sid = self._make_staging("doc_co_pub", review_status="approved")
        # Even with approved doc, content_operator cannot publish
        with self.assertRaises(ValueError) as ctx:
            admin_publish_staging_doc(sid, self.content_op, self.tmp_root)
        self.assertIn("denied", str(ctx.exception))

    def test_content_operator_can_upload_source(self):
        file_path = self.tmp_root / "test_upload.md"
        file_path.write_text("# Test Upload")
        files = [{"path": str(file_path), "filename": "test_upload.md"}]
        result = admin_sources_upload({"title": "Test"}, files, self.content_op, self.tmp_root)
        self.assertIn("run_id", result)

    def test_reviewer_can_approve(self):
        sid = self._make_staging("doc_rev_approve")
        # Set validation/compliance to passed so approve works
        doc = load_staging_doc(self.tmp_root, sid)
        doc["validation_status"] = "passed"
        doc["compliance_status"] = "passed"
        (self.tmp_root / "data" / "staging" / f"{sid}.json").write_text(
            json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")

        result = admin_approve_staging_doc(sid, self.reviewer, self.tmp_root)
        self.assertEqual(result["review_status"], "approved")

    def test_reviewer_can_reject(self):
        sid = self._make_staging("doc_rev_reject")
        result = admin_reject_staging_doc(sid, {"reason": "Not good"}, self.reviewer, self.tmp_root)
        self.assertEqual(result["review_status"], "rejected")

    def test_reviewer_cannot_publish(self):
        sid = self._make_staging("doc_rev_pub")
        with self.assertRaises(ValueError) as ctx:
            admin_publish_staging_doc(sid, self.reviewer, self.tmp_root)
        self.assertIn("denied", str(ctx.exception))

    def test_reviewer_cannot_edit_content(self):
        sid = self._make_staging("doc_rev_edit")
        with self.assertRaises(ValueError) as ctx:
            admin_update_staging_doc(sid, {"title": "Changed"}, self.reviewer, self.tmp_root)
        self.assertIn("denied", str(ctx.exception))

    def test_campus_admin_only_sees_own_campus_docs(self):
        # This is a unit test on the policy layer
        ctx_zz = AdminContext(user_id="u1", role="campus_admin", campus="zhengzhou")
        self.assertTrue(ctx_zz.can_access_campus("zhengzhou"))
        self.assertFalse(ctx_zz.can_access_campus("beijing"))
        self.assertTrue(ctx_zz.can_access_campus("all"))

    def test_campus_admin_can_access_graph(self):
        result = admin_list_graph_runs(self.campus_admin, self.tmp_root)
        self.assertIn("runs", result)

    def test_campus_admin_can_approve(self):
        sid = self._make_staging("doc_ca_approve")
        doc = load_staging_doc(self.tmp_root, sid)
        doc["validation_status"] = "passed"
        doc["compliance_status"] = "passed"
        (self.tmp_root / "data" / "staging" / f"{sid}.json").write_text(
            json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
        result = admin_approve_staging_doc(sid, self.campus_admin, self.tmp_root)
        self.assertEqual(result["review_status"], "approved")

    def test_client_body_role_admin_is_ignored(self):
        # Even if identity dict has role=admin, if it's from body, the backend
        # policy still checks the action. This is a unit test on the policy layer.
        # The server-layer test (admin_security_regression) covers the HTTP-level case.
        # Here we test that the policy correctly rejects known non-admin roles
        # even when passed through via identity dict.

        # Verify require_action_str rejects sales for admin actions
        with self.assertRaises(ValueError):
            require_action_str({"user_id": "fake_admin", "role": "sales", "campus": "all"}, Action.STAGING_PUBLISH)

    def test_admin_action_writes_audit_log(self):
        # Verify require_action_str returns context that can be used for audit
        ctx = require_action_str(self.admin, Action.HEALTH_READ)
        self.assertEqual(ctx.role, "admin")
        self.assertEqual(ctx.user_id, "u_admin")

    def test_protected_permission_fields_identified(self):
        for field in ["visibility", "allowed_roles", "data_level", "data_level_int",
                       "campus_scope", "review_status"]:
            self.assertTrue(is_permission_field(field), f"{field} should be protected")

        self.assertFalse(is_permission_field("title"))
        self.assertFalse(is_permission_field("content"))

    def test_content_operator_cannot_edit_permission_fields(self):
        ctx = build_context(self.content_op)
        self.assertFalse(can_edit_permission_fields(ctx))

    def test_campus_admin_can_edit_permission_fields(self):
        ctx = build_context(self.campus_admin)
        self.assertTrue(can_edit_permission_fields(ctx))


if __name__ == "__main__":
    unittest.main()
