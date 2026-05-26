from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
AGENT_SRC = ROOT / "services" / "agent-orchestrator" / "src"
API_SRC = ROOT / "services" / "api-gateway" / "src"
KNOWLEDGE_SRC = ROOT / "services" / "knowledge-service" / "src"
RAG_SRC = ROOT / "services" / "rag-service" / "src"
TOOLS_SRC = ROOT / "tools"
sys.path.extend([str(AGENT_SRC), str(API_SRC), str(KNOWLEDGE_SRC), str(RAG_SRC), str(TOOLS_SRC)])

from bff_gateway import post_chat, post_handoff  # noqa: E402
from ci_policy_check import check_database_urls  # noqa: E402
from indexer import build_index  # noqa: E402
from pipeline import receive_message  # noqa: E402
from search_router import resolve_retrieval_source  # noqa: E402
from source_policy import enforce_json_index_allowed  # noqa: E402


class ReleaseGateSecurityTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        build_index(ROOT)

    def setUp(self) -> None:
        for name in (
            "GAOKAO_ENV",
            "RAG_SOURCE",
            "DATABASE_URL_PUBLIC",
            "DATABASE_URL_STAFF",
            "DEEPSEEK_ENABLE_LLM",
            "DEEPSEEK_API_KEY",
        ):
            os.environ.pop(name, None)

    def test_frontend_gaokao_client_rejects_forbidden_fields_and_sends_minimal_payload(self) -> None:
        client = (ROOT.parent / "openhuman-main" / "app" / "src" / "api" / "gaokaoClient.ts").read_text(
            encoding="utf-8"
        )
        for field in ("role", "evidence", "model", "system_prompt"):
            self.assertIn(field, client)
        self.assertIn("Forbidden request field", client)
        self.assertIn("credentials: 'include'", client)
        self.assertIn("const body: Record<string, string> = { message: request.message }", client)
        self.assertIn("body.session_id = sessionId", client)
        self.assertNotIn("body.role", client)
        self.assertNotIn("body.evidence", client)
        self.assertNotIn("body.model", client)
        self.assertNotIn("body.system_prompt", client)

    def test_bff_rejects_browser_forged_chat_fields(self) -> None:
        for field in ("role", "evidence", "model", "system_prompt", "tools", "entrypoint", "identity"):
            with self.subTest(field=field):
                with self.assertRaisesRegex(ValueError, f"Forbidden request field: {field}"):
                    post_chat(
                        {"session_id": "s_gate", "message": "最低优惠是多少？", field: "unsafe"},
                        {"user_id": "u_parent", "role": "parent", "campus": "zhengzhou"},
                        ROOT,
                    )

    def test_handoff_accepts_only_session_id_and_reason(self) -> None:
        for field in ("message", "role", "evidence", "model", "system_prompt", "tools", "entrypoint", "identity"):
            with self.subTest(field=field):
                with self.assertRaisesRegex(ValueError, f"Forbidden request field: {field}"):
                    post_handoff(
                        {"session_id": "s_gate", "reason": "预约学情评估", field: "unsafe"},
                        {"user_id": "u_parent", "role": "parent", "campus": "zhengzhou"},
                        ROOT,
                    )

    def test_bff_citations_do_not_expose_internal_identifiers_or_paths(self) -> None:
        result = post_chat(
            {"session_id": "s_gate_citations", "message": "孩子 430 分适合什么班？"},
            {"user_id": "u_parent", "role": "parent", "campus": "zhengzhou"},
            ROOT,
        )
        self.assertEqual(result["citations"], [], "Parent/visitor citations should be empty")
        self.assertNotIn("来源：", result["answer"])
        self.assertNotIn("doc_id", result["answer"])
        self.assertNotIn("chunk_id", result["answer"])

    def test_public_roles_cannot_retrieve_internal_l3_evidence(self) -> None:
        for role in ("parent", "student", "visitor"):
            with self.subTest(role=role):
                result = receive_message(
                    {"user_id": f"u_{role}", "role": role, "campus": "zhengzhou"},
                    "招生老师内部话术和最低优惠是多少？",
                    ROOT,
                    entrypoint="public_chat",
                )
                doc_ids = {chunk["doc_id"] for chunk in result["retrieval"]["allowed_chunks"]}
                self.assertNotIn("sales_price_sensitive_2026", doc_ids)
                self.assertNotIn("内部参考", result["answer"])
                self.assertNotIn("优惠底价", result["answer"])

    def test_sales_can_retrieve_internal_l3_but_not_admin_l5(self) -> None:
        internal_result = receive_message(
            {"user_id": "u_sales", "role": "sales", "campus": "zhengzhou"},
            "家长嫌贵，价格敏感用户应该怎么解释？",
            ROOT,
            entrypoint="sales_console",
        )
        internal_doc_ids = {chunk["doc_id"] for chunk in internal_result["retrieval"]["allowed_chunks"]}
        self.assertIn("sales_price_sensitive_2026", internal_doc_ids)
        self.assertNotIn("admin_redline_rules_2026", internal_doc_ids)

        admin_result = receive_message(
            {"user_id": "u_sales", "role": "sales", "campus": "zhengzhou"},
            "后台策略和管理员红线是什么？",
            ROOT,
            entrypoint="sales_console",
        )
        admin_doc_ids = {chunk["doc_id"] for chunk in admin_result["retrieval"]["allowed_chunks"]}
        self.assertNotIn("admin_redline_rules_2026", admin_doc_ids)

    def test_production_requires_postgres_and_blocks_json_fallback(self) -> None:
        os.environ["GAOKAO_ENV"] = "production"
        self.assertEqual(resolve_retrieval_source(ROOT), "postgres")

        os.environ["RAG_SOURCE"] = "json"
        with self.assertRaisesRegex(RuntimeError, "JSON knowledge index is disabled in production"):
            enforce_json_index_allowed(ROOT)

    def test_public_and_staff_database_urls_must_not_use_admin_user(self) -> None:
        with patch.dict(
            os.environ,
            {
                "DATABASE_URL_PUBLIC": "postgresql://postgres:postgres@localhost:54329/gaokao_agent_test",
                "DATABASE_URL_STAFF": "postgresql://db_admin:postgres@localhost:54329/gaokao_agent_test",
            },
            clear=False,
        ):
            errors = check_database_urls()
        self.assertTrue(any("DATABASE_URL_PUBLIC" in error for error in errors))
        self.assertTrue(any("DATABASE_URL_STAFF" in error for error in errors))

    def test_chat_and_handoff_write_audit_log(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            project_root = _isolated_project_root(Path(tmp_dir))

            post_chat(
                {"session_id": "s_gate_audit", "message": "孩子 430 分适合什么班？"},
                {"user_id": "u_audit", "role": "parent", "campus": "zhengzhou"},
                project_root,
            )
            post_handoff(
                {"session_id": "s_gate_audit", "reason": "预约学情评估"},
                {"user_id": "u_audit", "role": "parent", "campus": "zhengzhou"},
                project_root,
            )

            audit_path = project_root / "data" / "audit_logs" / "audit.jsonl"
            events = [json.loads(line) for line in audit_path.read_text(encoding="utf-8").splitlines()]
            self.assertGreaterEqual(len(events), 2)
            self.assertEqual(events[-2]["message"], "孩子 430 分适合什么班？")
            self.assertEqual(events[-1]["message"], "预约学情评估")
            for event in events[-2:]:
                self.assertEqual(event["user_id"], "u_audit")
                self.assertEqual(event["role"], "parent")
                self.assertEqual(event["entrypoint"], "public_chat")
                self.assertIn("retrieved_chunk_ids", event)
                self.assertIn("compliance", event)


def _isolated_project_root(tmp_root: Path) -> Path:
    (tmp_root / "configs").symlink_to(ROOT / "configs")
    (tmp_root / "knowledge_vault").symlink_to(ROOT / "knowledge_vault")
    (tmp_root / "data" / "indexes").mkdir(parents=True, exist_ok=True)
    index_path = ROOT / "data" / "indexes" / "knowledge_index.json"
    (tmp_root / "data" / "indexes" / "knowledge_index.json").write_text(
        index_path.read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    return tmp_root


if __name__ == "__main__":
    unittest.main()
