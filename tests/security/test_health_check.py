from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ADMIN_SRC = ROOT / "services" / "api-gateway" / "src"
sys.path.insert(0, str(ADMIN_SRC))

from health_checks import (
    db_health,
    filesystem_health,
    full_health_check,
    llm_health,
    public_health,
    rag_health,
    security_health,
)


class HealthCheckTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        for sub in (
            "knowledge_vault",
            "data/crm/leads",
            "data/staging",
            "data/ingestion",
            "data/graph-runs",
            "data/audit_logs",
            "data/published",
            "configs",
        ):
            (self.root / sub).mkdir(parents=True, exist_ok=True)

    def tearDown(self):
        self._tmp.cleanup()

    def test_public_health_returns_ok(self):
        result = public_health(self.root)
        self.assertEqual(result["status"], "ok")
        self.assertIn("version", result)
        self.assertIn("timestamp", result)

    def test_db_health_no_url_configured(self):
        old = os.environ.pop("DATABASE_URL_ADMIN", None)
        os.environ.pop("DATABASE_URL_PUBLIC", None)
        try:
            result = db_health(self.root)
            self.assertEqual(result["status"], "unavailable")
        finally:
            if old:
                os.environ["DATABASE_URL_ADMIN"] = old

    def test_filesystem_health_ok(self):
        result = filesystem_health(self.root)
        self.assertEqual(result["status"], "ok")

    def test_filesystem_missing_dir(self):
        import shutil
        shutil.rmtree(self.root / "knowledge_vault")
        result = filesystem_health(self.root)
        self.assertEqual(result["status"], "degraded")
        self.assertIn("knowledge_vault directory missing", result["errors"])

    def test_llm_health_no_key(self):
        old_key = os.environ.pop("DEEPSEEK_API_KEY", None)
        try:
            result = llm_health(self.root)
            self.assertIn("DEEPSEEK_API_KEY not configured", result["errors"])
        finally:
            if old_key:
                os.environ["DEEPSEEK_API_KEY"] = old_key

    def test_llm_health_with_key(self):
        os.environ["DEEPSEEK_API_KEY"] = "sk-test-key-12345"
        (self.root / "configs" / "llm_config.json").write_text("{}")
        try:
            result = llm_health(self.root)
            self.assertEqual(result["status"], "ok")
        finally:
            os.environ.pop("DEEPSEEK_API_KEY", None)

    def test_security_health_csrf_warning(self):
        old_secret = os.environ.pop("CSRF_TOKEN_SECRET", None)
        try:
            result = security_health(self.root)
            self.assertIn("CSRF_TOKEN_SECRET not properly configured", result["errors"])
        finally:
            if old_secret:
                os.environ["CSRF_TOKEN_SECRET"] = old_secret

    def test_security_health_csrf_ok(self):
        os.environ["CSRF_TOKEN_SECRET"] = "a" * 32
        os.environ["GAOKAO_ENV"] = "development"
        try:
            result = security_health(self.root)
            self.assertNotIn("CSRF_TOKEN_SECRET not properly configured", result["errors"])
            self.assertIn("csrf_secret", result["checks"])
        finally:
            os.environ.pop("CSRF_TOKEN_SECRET", None)
            os.environ.pop("GAOKAO_ENV", None)

    def test_security_health_remote_ingestion_warning(self):
        os.environ["ENABLE_REMOTE_URL_INGESTION"] = "1"
        os.environ["CSRF_TOKEN_SECRET"] = "a" * 32
        try:
            result = security_health(self.root)
            self.assertIn("ENABLE_REMOTE_URL_INGESTION is enabled in production", result["errors"])
        finally:
            os.environ.pop("ENABLE_REMOTE_URL_INGESTION", None)
            os.environ.pop("CSRF_TOKEN_SECRET", None)

    def test_full_health_check_aggregates(self):
        os.environ["DEEPSEEK_API_KEY"] = "sk-test"
        os.environ["CSRF_TOKEN_SECRET"] = "a" * 32
        try:
            result = full_health_check(self.root)
            self.assertIn(result["status"], ("ok", "degraded"))
            self.assertIn("db", result["checks"])
            self.assertIn("rag", result["checks"])
            self.assertIn("llm", result["checks"])
            self.assertIn("security", result["checks"])
            self.assertIn("filesystem", result["checks"])
            self.assertIn("request_id", result)
        finally:
            os.environ.pop("DEEPSEEK_API_KEY", None)
            os.environ.pop("CSRF_TOKEN_SECRET", None)


if __name__ == "__main__":
    unittest.main()
