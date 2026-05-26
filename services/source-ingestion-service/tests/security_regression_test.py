from __future__ import annotations

import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

TEST_DIR = Path(__file__).resolve().parent
SRC_DIR = TEST_DIR.parent / "src"
sys.path.insert(0, str(SRC_DIR))

from staging_store import write_staging_doc, load_staging_doc
from publisher import publish_staging_doc
from frontmatter_validator import validate_frontmatter


class PublisherSecurityRegressionTest(unittest.TestCase):
    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp())
        (self.tmpdir / "data" / "staging").mkdir(parents=True, exist_ok=True)
        (self.tmpdir / "knowledge_vault").mkdir(parents=True, exist_ok=True)

    def tearDown(self):
        shutil.rmtree(str(self.tmpdir), ignore_errors=True)

    def _create_staging(self, review_status="approved", compliance_status="passed",
                        doc_id="sec_test_doc", expiry_date="2099-12-31", **kw) -> str:
        data = {
            "run_id": "sec_run",
            "doc_id": doc_id,
            "title": "Security Test Doc",
            "canonical_markdown": "# Security\n测试内容。",
            "frontmatter": {
                "title": "Security Test Doc",
                "doc_id": doc_id,
                "visibility": "public",
                "allowed_roles": ["student", "parent"],
                "data_level": "L1",
                "data_level_int": 1,
                "campus_scope": ["all"],
                "business_tags": ["test"],
                "effective_date": "2026-01-01",
                "expiry_date": expiry_date,
                "owner": "Test",
                "review_status": review_status,
                "source_type": "wiki",
                "version": 1,
            },
            "validation_status": "passed",
            "compliance_status": compliance_status,
            "review_status": review_status,
            "source_hash": kw.pop("source_hash", f"hash_{doc_id}"),
            "created_by": "tester",
        }
        data.update(kw)
        return write_staging_doc(self.tmpdir, data)

    def test_publisher_rejects_draft_doc(self):
        sid = self._create_staging(review_status="draft")
        result = publish_staging_doc(self.tmpdir, sid, "publisher", "admin")
        self.assertFalse(result["success"])
        self.assertIn("review_status", result.get("error", ""))

    def test_publisher_rejects_expired_doc(self):
        fm = {
            "title": "Expired Doc",
            "doc_id": "expired_doc",
            "visibility": "public",
            "allowed_roles": ["public"],
            "data_level": "public",
            "data_level_int": 0,
            "campus_scope": ["all"],
            "business_tags": ["test"],
            "effective_date": "2020-01-01",
            "expiry_date": "2020-01-01",
            "owner": "Test",
            "review_status": "approved",
            "source_type": "test",
            "version": 1,
        }
        result = validate_frontmatter(fm)
        self.assertFalse(result["valid"])
        self.assertTrue(any("expiry_date" in e and "past" in e for e in result["errors"]))

    def test_publisher_requires_compliance_passed(self):
        sid = self._create_staging(compliance_status="failed")
        result = publish_staging_doc(self.tmpdir, sid, "publisher", "admin")
        self.assertFalse(result["success"])
        self.assertIn("compliance_status", result.get("error", ""))

    def test_publish_same_source_hash_is_idempotent(self):
        sid1 = self._create_staging(doc_id="idem_doc", source_hash="abc123")
        r1 = publish_staging_doc(self.tmpdir, sid1, "pub", "admin")
        self.assertTrue(r1["success"])
        self.assertEqual(r1["version"], 1)

        sid2 = self._create_staging(doc_id="idem_doc", source_hash="abc123",
                                    run_id="sec_run_2")
        r2 = publish_staging_doc(self.tmpdir, sid2, "pub", "admin")
        self.assertTrue(r2["success"])
        self.assertEqual(r2["version"], 2)

    def test_graph_build_failure_does_not_block_publish(self):
        sid = self._create_staging(doc_id="graph_fail_doc", source_hash="graph_fail")
        result = publish_staging_doc(self.tmpdir, sid, "test_user", "admin")
        self.assertTrue(result["success"], f"publish failed: {result.get('error')}")
        self.assertEqual(result["doc_id"], "graph_fail_doc")


if __name__ == "__main__":
    unittest.main()
