from __future__ import annotations

import json
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[3]
RAG_SRC = ROOT / "services" / "rag-service" / "src"
sys.path.append(str(RAG_SRC))

from db_retriever import get_database_url_for_entrypoint, search_db  # noqa: E402
from search_router import resolve_retrieval_source  # noqa: E402
from retriever import search  # noqa: E402


class DbRetrieverPolicyTest(unittest.TestCase):
    def tearDown(self) -> None:
        for key in (
            "GAOKAO_ENV",
            "RAG_SOURCE",
            "DATABASE_URL_PUBLIC",
            "DATABASE_URL_STAFF",
            "DATABASE_URL_ADMIN_APP",
        ):
            os.environ.pop(key, None)

    def test_production_forbids_json_index(self) -> None:
        os.environ["GAOKAO_ENV"] = "production"
        os.environ["RAG_SOURCE"] = "json"
        with self.assertRaisesRegex(RuntimeError, "JSON knowledge index is disabled"):
            search("学费", {"role": "parent"}, ROOT)

    def test_entrypoint_cannot_use_admin_postgres_connection(self) -> None:
        os.environ["DATABASE_URL_PUBLIC"] = "postgresql://postgres:postgres@localhost:54329/gaokao_agent_test"
        with self.assertRaisesRegex(RuntimeError, "must not use the admin postgres connection"):
            get_database_url_for_entrypoint("public_chat")

    def test_db_retriever_uses_transaction_and_set_local(self) -> None:
        os.environ["DATABASE_URL_PUBLIC"] = "postgresql://gaokao_api_public:postgres@localhost:54329/gaokao_agent_test"
        fake_rows = [
            {
                "chunk_id": "tuition_public_2026::chunk_001",
                "id": "tuition_public_2026::chunk_001",
                "doc_id": "tuition_public_2026",
                "title": "公开费用说明",
                "content": "公开费用口径",
                "source_uri": "knowledge_vault/public/enrollment/tuition_public.md",
                "source_page": None,
                "visibility": "public",
                "data_level": "L1",
                "data_level_int": 1,
                "business_tags": ["费用政策"],
                "allowed_roles": [],
                "campus_scope": [],
            }
        ]

        def fake_run(cmd, check, text, stdout, stderr=None):
            sql = cmd[-1]
            self.assertIn("BEGIN;", sql)
            self.assertIn("SET LOCAL app.role = 'parent';", sql)
            self.assertIn("SET LOCAL app.campus = 'zhengzhou';", sql)
            self.assertNotIn("SET app.role", sql)
            self.assertIn("search_accessible_chunks('学费 ", sql)
            self.assertIn("费用", sql)

            class Result:
                stdout = "BEGIN\n" + json.dumps(fake_rows, ensure_ascii=False) + "\nROLLBACK\n"

            return Result()

        with patch("subprocess.run", fake_run):
            result = search_db(
                "学费",
                {"user_id": "u_1", "role": "parent", "campus": "zhengzhou", "auth_level": "phone_verified"},
                ROOT,
                entrypoint="public_chat",
            )

        self.assertEqual(result["source"], "postgres")
        self.assertEqual(result["allowed_chunks"][0]["chunk_id"], "tuition_public_2026::chunk_001")

    def test_production_defaults_to_postgres_source(self) -> None:
        os.environ["GAOKAO_ENV"] = "production"
        os.environ.pop("RAG_SOURCE", None)
        self.assertEqual(resolve_retrieval_source(ROOT), "postgres")


if __name__ == "__main__":
    unittest.main()
