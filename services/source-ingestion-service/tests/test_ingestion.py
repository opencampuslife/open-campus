from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

TEST_DIR = Path(__file__).resolve().parent
SRC_DIR = TEST_DIR.parent / "src"
sys.path.insert(0, str(SRC_DIR))

from markdown_normalizer import normalize_markdown
from docling_adapter import parse_file_to_markdown, is_docling_available
from frontmatter_validator import validate_frontmatter, parse_frontmatter_from_md
from compliance_precheck import compliance_precheck
from staging_store import (
    write_staging_doc,
    load_staging_doc,
    list_staging_docs,
    update_staging_doc,
    delete_staging_doc,
)
from publisher import publish_staging_doc
from url_validator import validate_url
from pipeline import IngestionPipeline


class TestMarkdownNormalizer(unittest.TestCase):

    def test_normalize_line_endings(self):
        result = normalize_markdown("line1\r\nline2\rline3\n")
        self.assertEqual(result, "line1\nline2\nline3\n")

    def test_remove_bom(self):
        result = normalize_markdown("\ufeff# Hello\n")
        self.assertEqual(result, "# Hello\n")

    def test_trailing_whitespace_removed(self):
        result = normalize_markdown("hello   \nworld  \n")
        self.assertEqual(result, "hello\nworld\n")

    def test_heading_spacing(self):
        result = normalize_markdown("#Title\n")
        self.assertEqual(result, "# Title\n")

    def test_single_trailing_newline(self):
        result = normalize_markdown("hello\n\n\n\n")
        self.assertEqual(result, "hello\n")


class TestDoclingAdapter(unittest.TestCase):

    def test_md_file_read_directly(self):
        with tempfile.NamedTemporaryFile(suffix=".md", mode="w", delete=False) as f:
            f.write("# Test\ncontent\n")
            tmp = f.name
        try:
            result = parse_file_to_markdown(Path(tmp))
            self.assertIn("content", result)
            self.assertIn("# Test", result["content"])
            self.assertIn("content", result["content"])
        finally:
            os.unlink(tmp)

    def test_txt_file_read_directly(self):
        with tempfile.NamedTemporaryFile(suffix=".txt", mode="w", delete=False) as f:
            f.write("plain text\n")
            tmp = f.name
        try:
            result = parse_file_to_markdown(Path(tmp))
            self.assertEqual(result["content"], "plain text\n")
        finally:
            os.unlink(tmp)

    def test_unsupported_file_type_returns_warning(self):
        with tempfile.NamedTemporaryFile(suffix=".xyz", mode="w", delete=False) as f:
            f.write("data")
            tmp = f.name
        try:
            result = parse_file_to_markdown(Path(tmp))
            self.assertTrue(len(result["warnings"]) > 0)
            self.assertTrue(any("unsupported" in w for w in result["warnings"]))
        finally:
            os.unlink(tmp)

    def test_is_docling_available(self):
        self.assertIsInstance(is_docling_available(), bool)


class TestFrontmatterValidator(unittest.TestCase):

    def setUp(self):
        self.valid_fm = {
            "title": "Test Doc",
            "doc_id": "test_doc_001",
            "visibility": "public",
            "allowed_roles": ["student", "parent"],
            "data_level": "L1",
            "data_level_int": 1,
            "campus_scope": ["all"],
            "business_tags": ["FAQ"],
            "effective_date": "2026-01-01",
            "expiry_date": "2099-12-31",
            "owner": "Test Dept",
            "review_status": "approved",
            "source_type": "wiki",
            "version": 1,
        }

    def test_valid_frontmatter_passes(self):
        result = validate_frontmatter(self.valid_fm)
        self.assertTrue(result["valid"])
        self.assertEqual(len(result["errors"]), 0)

    def test_missing_frontmatter_rejected(self):
        result = validate_frontmatter({})
        self.assertFalse(result["valid"])
        self.assertTrue(len(result["errors"]) > 0)
        self.assertTrue(any("missing required field" in e for e in result["errors"]))

    def test_invalid_visibility_rejected(self):
        fm = dict(self.valid_fm)
        fm["visibility"] = "secret"
        result = validate_frontmatter(fm)
        self.assertFalse(result["valid"])
        self.assertTrue(any("invalid visibility" in e for e in result["errors"]))

    def test_invalid_data_level_int_rejected(self):
        fm = dict(self.valid_fm)
        fm["data_level_int"] = 99
        result = validate_frontmatter(fm)
        self.assertFalse(result["valid"])
        self.assertTrue(any("invalid data_level_int" in e for e in result["errors"]))

    def test_invalid_review_status_rejected(self):
        fm = dict(self.valid_fm)
        fm["review_status"] = "published"
        result = validate_frontmatter(fm)
        self.assertFalse(result["valid"])
        self.assertTrue(any("invalid review_status" in e for e in result["errors"]))

    def test_expired_doc_rejected(self):
        fm = dict(self.valid_fm)
        fm["expiry_date"] = "2020-01-01"
        result = validate_frontmatter(fm)
        self.assertFalse(result["valid"])
        self.assertTrue(any("expiry_date" in e and "past" in e for e in result["errors"]))

    def test_draft_doc_not_publishable(self):
        fm = dict(self.valid_fm)
        fm["review_status"] = "draft"
        result = validate_frontmatter(fm)
        self.assertFalse(result["valid"])
        self.assertTrue(any("draft" in e and "cannot be published" in e for e in result["errors"]))

    def test_invalid_allowed_roles_rejected(self):
        fm = dict(self.valid_fm)
        fm["allowed_roles"] = ["superadmin"]
        result = validate_frontmatter(fm)
        self.assertFalse(result["valid"])
        self.assertTrue(any("invalid allowed_roles" in e for e in result["errors"]))

    def test_empty_campus_scope_rejected(self):
        fm = dict(self.valid_fm)
        fm["campus_scope"] = []
        result = validate_frontmatter(fm)
        self.assertFalse(result["valid"])
        self.assertTrue(any("campus_scope" in e for e in result["errors"]))

    def test_public_doc_with_promise_word(self):
        fm = dict(self.valid_fm)
        fm["title"] = "保证提分方案"
        result = validate_frontmatter(fm)
        self.assertTrue(result["valid"])
        self.assertTrue(len(result["warnings"]) > 0)


class TestFrontmatterParsing(unittest.TestCase):

    def test_parse_valid_frontmatter(self):
        md = "---\ntitle: Test\ndoc_id: t1\nvisibility: public\n---\n\nBody text\n"
        fm, body = parse_frontmatter_from_md(md)
        self.assertIsNotNone(fm)
        self.assertEqual(fm["title"], "Test")
        self.assertEqual(fm["doc_id"], "t1")
        self.assertEqual(body, "Body text")

    def test_parse_missing_frontmatter(self):
        md = "# No frontmatter\ncontent\n"
        fm, body = parse_frontmatter_from_md(md)
        self.assertIsNone(fm)
        self.assertEqual(body, md)


class TestCompliancePrecheck(unittest.TestCase):

    def test_pii_detected_public_doc(self):
        fm = {"visibility": "public", "data_level_int": 1}
        content = "Call me at 13800138000 for details"
        result = compliance_precheck(fm, content)
        self.assertFalse(result["passed"])
        self.assertTrue(any(i["type"] == "pii_phone" for i in result["issues"]))
        self.assertEqual(result["risk_level"], "high")

    def test_id_card_detected_public_doc(self):
        fm = {"visibility": "public", "data_level_int": 1}
        content = "ID: 110101199001011234"
        result = compliance_precheck(fm, content)
        self.assertFalse(result["passed"])
        self.assertTrue(any(i["type"] == "pii_id_card" for i in result["issues"]))

    def test_competitive_claim_detected(self):
        fm = {"visibility": "public", "data_level_int": 1}
        content = "我们是最好培训机构"
        result = compliance_precheck(fm, content)
        self.assertTrue(any(i["type"] == "competitive_claim" for i in result["issues"]))
        self.assertEqual(result["risk_level"], "medium")

    def test_promise_language_detected(self):
        fm = {"visibility": "public", "data_level_int": 1}
        content = "我们保证提分"
        result = compliance_precheck(fm, content)
        self.assertFalse(result["passed"])
        self.assertTrue(any(i["type"] == "promise_language" for i in result["issues"]))

    def test_clean_public_doc_passes(self):
        fm = {"visibility": "public", "data_level_int": 1}
        content = "Welcome to our school for more information."
        result = compliance_precheck(fm, content)
        self.assertTrue(result["passed"])
        self.assertEqual(result["risk_level"], "low")

    def test_internal_doc_no_pii_check(self):
        fm = {"visibility": "internal", "data_level_int": 2}
        content = "Call 13800138000"
        result = compliance_precheck(fm, content)
        self.assertTrue(result["passed"])


class TestStagingStore(unittest.TestCase):

    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp())
        (self.tmpdir / "data" / "staging").mkdir(parents=True, exist_ok=True)

    def tearDown(self):
        import shutil
        shutil.rmtree(str(self.tmpdir), ignore_errors=True)

    def test_write_and_load_staging_doc(self):
        doc_data = {
            "run_id": "run_001",
            "doc_id": "doc_001",
            "title": "Test Document",
            "canonical_markdown": "# Hello",
            "frontmatter": {"title": "Test"},
            "created_by": "tester",
        }
        sid = write_staging_doc(self.tmpdir, doc_data)
        self.assertTrue(len(sid) > 0)

        loaded = load_staging_doc(self.tmpdir, sid)
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded["title"], "Test Document")
        self.assertEqual(loaded["run_id"], "run_001")

    def test_list_staging_docs(self):
        write_staging_doc(self.tmpdir, {"run_id": "r1", "doc_id": "d1", "title": "T1",
                                        "canonical_markdown": "a", "created_by": "u"})
        write_staging_doc(self.tmpdir, {"run_id": "r2", "doc_id": "d2", "title": "T2",
                                        "canonical_markdown": "b", "created_by": "u"})
        docs = list_staging_docs(self.tmpdir)
        self.assertEqual(len(docs), 2)

    def test_update_staging_doc(self):
        sid = write_staging_doc(self.tmpdir, {
            "run_id": "r1", "doc_id": "d1", "title": "Original",
            "canonical_markdown": "text", "created_by": "u"
        })
        updated = update_staging_doc(self.tmpdir, sid, {"title": "Updated"})
        self.assertEqual(updated["title"], "Updated")

        loaded = load_staging_doc(self.tmpdir, sid)
        self.assertEqual(loaded["title"], "Updated")

    def test_delete_staging_doc(self):
        sid = write_staging_doc(self.tmpdir, {
            "run_id": "r1", "doc_id": "d1", "title": "T",
            "canonical_markdown": "text", "created_by": "u"
        })
        self.assertTrue(delete_staging_doc(self.tmpdir, sid))
        self.assertFalse(delete_staging_doc(self.tmpdir, "nonexistent"))
        self.assertIsNone(load_staging_doc(self.tmpdir, sid))


class TestUrlValidator(unittest.TestCase):

    def setUp(self):
        self._prev = os.environ.get("ENABLE_REMOTE_URL_INGESTION")
        os.environ["ENABLE_REMOTE_URL_INGESTION"] = "1"

    def tearDown(self):
        if self._prev is None:
            os.environ.pop("ENABLE_REMOTE_URL_INGESTION", None)
        else:
            os.environ["ENABLE_REMOTE_URL_INGESTION"] = self._prev

    @patch("url_validator._resolve_dns", return_value=["93.184.215.14"])
    def test_valid_url(self, _mock_dns):
        result = validate_url("https://example.com/path")
        self.assertTrue(result["valid"])

    def test_invalid_url(self):
        result = validate_url("")
        self.assertFalse(result["valid"])


class TestIngestionPipeline(unittest.TestCase):

    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp())
        (self.tmpdir / "data" / "ingestion").mkdir(parents=True, exist_ok=True)
        (self.tmpdir / "data" / "staging").mkdir(parents=True, exist_ok=True)
        self.pipeline = IngestionPipeline(self.tmpdir)

    def tearDown(self):
        import shutil
        shutil.rmtree(str(self.tmpdir), ignore_errors=True)

    def _write_md_with_frontmatter(self, name: str, doc_id: str, **overrides) -> str:
        fm = {
            "title": overrides.get("title", "Test Doc"),
            "doc_id": doc_id,
            "visibility": overrides.get("visibility", "public"),
            "allowed_roles": overrides.get("allowed_roles", ["student", "parent"]),
            "data_level": "L1",
            "data_level_int": 1,
            "campus_scope": ["all"],
            "business_tags": ["test"],
            "effective_date": "2026-01-01",
            "expiry_date": "2099-12-31",
            "owner": "Test",
            "review_status": "approved",
            "source_type": "wiki",
            "version": 1,
        }
        lines = ["---"]
        for k, v in fm.items():
            if isinstance(v, list):
                lines.append("{}:".format(k))
                for item in v:
                    lines.append("  - {}".format(item))
            else:
                lines.append("{}: {}".format(k, v))
        lines.append("---")
        lines.append("")
        lines.append("# {}".format(fm["title"]))
        lines.append("")
        lines.append("Content body")
        path = self.tmpdir / name
        path.write_text("\n".join(lines), encoding="utf-8")
        return str(path)

    def test_upload_markdown_creates_staging(self):
        src = self._write_md_with_frontmatter("test_doc.md", "test_staging_doc")
        result = self.pipeline.run(src, "md", "tester", "admin", "beijing")
        self.assertEqual(result["status"], "success")
        self.assertTrue(len(result["staging_doc_id"]) > 0)
        self.assertEqual(result["doc_id"], "test_staging_doc")

    def test_upload_txt_creates_staging(self):
        path = self.tmpdir / "plain.txt"
        path.write_text("---\ntitle: Plain\ndoc_id: plain_txt\nvisibility: public\n"
                        "allowed_roles:\n  - student\ndata_level: L1\ndata_level_int: 1\n"
                        "campus_scope:\n  - all\nbusiness_tags:\n  - test\n"
                        "effective_date: 2026-01-01\nexpiry_date: 2099-12-31\n"
                        "owner: Test\nreview_status: approved\nsource_type: wiki\n"
                        "version: 1\n---\n\nPlain text content\n",
                        encoding="utf-8")
        result = self.pipeline.run(str(path), "txt", "tester", "admin")
        self.assertEqual(result["status"], "success")
        self.assertTrue(len(result["staging_doc_id"]) > 0)

    def test_invalid_file_type_rejected(self):
        path = self.tmpdir / "test.xyz"
        path.write_text("data", encoding="utf-8")
        result = self.pipeline.run(str(path), "xyz", "tester", "admin")
        self.assertEqual(result["status"], "failed")

    def test_source_hash_recorded(self):
        src = self._write_md_with_frontmatter("hash_doc.md", "hash_doc_001")
        result = self.pipeline.run(src, "md", "tester", "admin")
        self.assertEqual(result["status"], "success")
        run_path = self.tmpdir / "data" / "ingestion" / "{}.json".format(result["run_id"])
        self.assertTrue(run_path.is_file())
        run_data = json.loads(run_path.read_text(encoding="utf-8"))
        self.assertIn("run_id", run_data)

    def test_ingestion_run_status_success(self):
        src = self._write_md_with_frontmatter("success_doc.md", "success_001")
        result = self.pipeline.run(src, "md", "tester", "admin")
        self.assertEqual(result["status"], "success")

    def test_ingestion_run_status_failed(self):
        result = self.pipeline.run("/nonexistent/path.md", "md", "tester", "admin")
        self.assertEqual(result["status"], "failed")

    def test_missing_frontmatter_rejected(self):
        path = self.tmpdir / "no_fm.md"
        path.write_text("# No Frontmatter\n", encoding="utf-8")
        result = self.pipeline.run(str(path), "md", "tester", "admin")
        self.assertEqual(result["status"], "failed")


class TestPublisher(unittest.TestCase):

    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp())
        (self.tmpdir / "data" / "staging").mkdir(parents=True, exist_ok=True)
        (self.tmpdir / "knowledge_vault").mkdir(parents=True, exist_ok=True)

    def tearDown(self):
        import shutil
        shutil.rmtree(str(self.tmpdir), ignore_errors=True)

    def _create_staging_doc(self, review_status="approved", compliance_status="passed",
                            doc_id="pub_test_doc") -> str:
        from staging_store import write_staging_doc
        sid = write_staging_doc(self.tmpdir, {
            "run_id": "pub_run",
            "doc_id": doc_id,
            "title": "Publishable Doc",
            "canonical_markdown": "# Content\n",
            "frontmatter": {
                "title": "Publishable Doc",
                "doc_id": doc_id,
                "visibility": "public",
                "allowed_roles": ["student", "parent"],
                "data_level": "L1",
                "data_level_int": 1,
                "campus_scope": ["all"],
                "business_tags": ["test"],
                "effective_date": "2026-01-01",
                "expiry_date": "2099-12-31",
                "owner": "Test",
                "review_status": review_status,
                "source_type": "wiki",
                "version": 1,
            },
            "validation_status": "passed",
            "compliance_status": compliance_status,
            "review_status": review_status,
            "created_by": "tester",
        })
        return sid

    def test_publish_requires_approved_status(self):
        sid = self._create_staging_doc(review_status="draft")
        result = publish_staging_doc(self.tmpdir, sid, "publisher", "admin")
        self.assertFalse(result["success"])
        self.assertIn("review_status", result.get("error", ""))

    def test_publish_requires_compliance_passed(self):
        sid = self._create_staging_doc(compliance_status="failed")
        result = publish_staging_doc(self.tmpdir, sid, "publisher", "admin")
        self.assertFalse(result["success"])
        self.assertIn("compliance_status", result.get("error", ""))

    def test_publish_success_creates_vault_file(self):
        sid = self._create_staging_doc()
        result = publish_staging_doc(self.tmpdir, sid, "publisher", "admin")
        self.assertTrue(result["success"])
        self.assertEqual(result["doc_id"], "pub_test_doc")
        self.assertEqual(result["version"], 1)
        vault_path = self.tmpdir / "knowledge_vault" / "public" / "pub_test_doc.md"
        self.assertTrue(vault_path.is_file())

    def test_publish_nonexistent_doc(self):
        result = publish_staging_doc(self.tmpdir, "nonexistent", "publisher", "admin")
        self.assertFalse(result["success"])
        self.assertIn("not found", result.get("error", ""))

    def test_publish_to_postgres_skipped_when_no_db(self):
        from publisher import publish_to_postgres
        result = publish_to_postgres({}, self.tmpdir, "2026-01-01", "test", 1)
        self.assertTrue(result.get("skipped", False))
        self.assertIn("DATABASE_URL_ADMIN", result.get("reason", ""))


if __name__ == "__main__":
    unittest.main()
