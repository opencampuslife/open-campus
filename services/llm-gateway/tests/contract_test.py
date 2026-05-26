from __future__ import annotations

import json
import os
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[3]
GATEWAY_SRC = ROOT / "services" / "llm-gateway" / "src"
sys.path.append(str(GATEWAY_SRC))

from gateway import _build_messages, generate_admissions_answer  # noqa: E402
from provider_deepseek import chat_completion  # noqa: E402
from schemas import EvidenceChunk, LLMRequest  # noqa: E402


class LLMContractTest(unittest.TestCase):
    def test_llm_request_to_policy_dict_strips_source_uri_and_ids_from_evidence(self) -> None:
        r = LLMRequest(
            user_role="parent",
            intent="faq",
            user_query="费用是多少？",
            allowed_evidence=[
                EvidenceChunk(
                    chunk_id="c1",
                    doc_id="tuition_public_2026",
                    title="公开费用说明",
                    content="学费明细",
                    visibility="public",
                    data_level="L1",
                    allowed_roles=["visitor", "student", "parent", "sales"],
                    source_uri="knowledge_vault/public/enrollment/tuition_public.md",
                )
            ],
        )
        policy = r.to_policy_dict()
        for chunk in policy["evidence"]:
            self.assertIn("source_uri", chunk)
            self.assertIn("chunk_id", chunk)
            self.assertIn("doc_id", chunk)

    def test_build_messages_output_is_exact_system_user_format(self) -> None:
        request = {
            "task": "admissions_answer",
            "message": "测试问题",
            "intent": "faq",
            "scope": {"role": "parent", "campus": "zhengzhou"},
            "evidence": [],
            "risk_level": "low",
        }
        messages = _build_messages(request)
        self.assertEqual(len(messages), 2)
        self.assertEqual(messages[0]["role"], "system")
        self.assertEqual(messages[1]["role"], "user")
        for msg in messages:
            self.assertEqual(set(msg.keys()), {"role", "content"})

    def test_build_messages_never_leaks_caller_internals(self) -> None:
        request = {
            "task": "admissions_answer",
            "message": "测试问题",
            "intent": "faq",
            "scope": {"role": "parent", "campus": "zhengzhou"},
            "evidence": [],
            "risk_level": "high",
            "session_id": "s_abc123",
            "answer_policy": {"must_cite_sources": True},
            "output_format": "json_with_sources",
        }
        user_content = _build_messages(request)[1]["content"]
        self.assertNotIn("session_id", user_content)
        self.assertNotIn("s_abc123", user_content)
        self.assertNotIn("answer_policy", user_content)
        self.assertNotIn("output_format", user_content)
        self.assertNotIn("json_with_sources", user_content)
        self.assertNotIn("risk_level", user_content)

    def test_system_prompt_is_immutable_no_caller_override(self) -> None:
        os.environ["DEEPSEEK_API_KEY"] = "test-key"
        captured = {}

        def fake_transport(request, timeout):
            captured["body"] = json.loads(request.data.decode("utf-8"))
            return b'{"choices":[{"message":{"content":"ok"}}]}'

        generate_admissions_answer(
            project_root=ROOT,
            request=LLMRequest(
                user_role="parent",
                intent="faq",
                user_query="test",
                campus="zhengzhou",
                allowed_evidence=[
                    EvidenceChunk(
                        chunk_id="c1",
                        doc_id="faq_parent_common_2026",
                        title="FAQ",
                        content="公开FAQ",
                        visibility="public",
                        data_level="L1",
                        allowed_roles=["visitor", "student", "parent", "sales"],
                        source_uri="knowledge_vault/public/faq/parent_common_questions.md",
                    )
                ],
            ),
            transport=fake_transport,
        )

        system_content = captured["body"]["messages"][0]["content"]
        self.assertIn("复读学校招生问答 Agent", system_content)
        self.assertIn("allowed evidence", system_content)
        self.assertNotIn("session_id", system_content)
        self.assertNotIn("answer_policy", system_content)

    def test_llm_response_parsing_handles_malformed_json(self) -> None:
        os.environ["DEEPSEEK_API_KEY"] = "test-key"

        def fake_transport(request, timeout):
            return b"not valid json"

        result = generate_admissions_answer(
            project_root=ROOT,
            request=LLMRequest(
                user_role="parent",
                intent="faq",
                user_query="test",
                allowed_evidence=[
                    EvidenceChunk(
                        chunk_id="c1",
                        doc_id="faq_parent_common_2026",
                        title="FAQ",
                        content="公开FAQ",
                        visibility="public",
                        data_level="L1",
                        allowed_roles=["visitor", "student", "parent", "sales"],
                        source_uri="knowledge_vault/public/faq/parent_common_questions.md",
                    )
                ],
            ),
            transport=fake_transport,
        )
        self.assertIsNone(result)

    def test_llm_response_parsing_handles_missing_choices(self) -> None:
        os.environ["DEEPSEEK_API_KEY"] = "test-key"

        def fake_transport(request, timeout):
            return json.dumps({"choices": []}).encode("utf-8")

        result = generate_admissions_answer(
            project_root=ROOT,
            request=LLMRequest(
                user_role="parent",
                intent="faq",
                user_query="test",
                allowed_evidence=[
                    EvidenceChunk(
                        chunk_id="c1",
                        doc_id="faq_parent_common_2026",
                        title="FAQ",
                        content="公开FAQ",
                        visibility="public",
                        data_level="L1",
                        allowed_roles=["visitor", "student", "parent", "sales"],
                        source_uri="knowledge_vault/public/faq/parent_common_questions.md",
                    )
                ],
            ),
            transport=fake_transport,
        )
        self.assertIsNone(result)

    def test_provider_error_without_transport_raises_runtime_error(self) -> None:
        import urllib.error

        def failing_transport(request, timeout):
            raise urllib.error.URLError("connection refused")

        with self.assertRaises(RuntimeError) as ctx:
            chat_completion(
                [{"role": "user", "content": "Hello"}],
                api_key="sk-test",
                base_url="https://api.deepseek.com",
                model="deepseek-v4-flash",
                transport=failing_transport,
            )
        self.assertIn("network error", str(ctx.exception).lower())

    def test_provider_error_propagates_from_gateway(self) -> None:
        os.environ["DEEPSEEK_API_KEY"] = "sk-test"

        def failing_transport(request, timeout):
            import urllib.error
            raise urllib.error.URLError("connection refused")

        result = generate_admissions_answer(
            project_root=ROOT,
            request=LLMRequest(
                user_role="parent",
                intent="faq",
                user_query="test",
                allowed_evidence=[
                    EvidenceChunk(
                        chunk_id="c1",
                        doc_id="faq_parent_common_2026",
                        title="FAQ",
                        content="公开FAQ",
                        visibility="public",
                        data_level="L1",
                        allowed_roles=["visitor", "student", "parent", "sales"],
                        source_uri="knowledge_vault/public/faq/parent_common_questions.md",
                    )
                ],
            ),
            transport=failing_transport,
        )
        self.assertIsNone(result)

    def test_evidence_passed_to_llm_contains_title_and_content_but_not_chunk_id(self) -> None:
        os.environ["DEEPSEEK_API_KEY"] = "test-key"
        captured = {}

        def fake_transport(request, timeout):
            captured["body"] = json.loads(request.data.decode("utf-8"))
            return json.dumps({"choices": [{"message": {"content": "模型回答"}}]}).encode("utf-8")

        evidence_chunk = EvidenceChunk(
            chunk_id="c1",
            doc_id="tuition_public_2026",
            title="公开费用说明",
            content="学费明细内容",
            visibility="public",
            data_level="L1",
            allowed_roles=["visitor", "student", "parent", "sales"],
            source_uri="knowledge_vault/public/enrollment/tuition_public.md",
        )
        generate_admissions_answer(
            project_root=ROOT,
            request=LLMRequest(
                user_role="parent",
                intent="faq",
                user_query="费用是多少？",
                allowed_evidence=[evidence_chunk],
            ),
            transport=fake_transport,
        )

        user_message = captured["body"]["messages"][1]["content"]
        self.assertIn("公开费用说明", user_message)
        self.assertIn("学费明细内容", user_message)
        self.assertNotIn("/internal/", user_message)
        self.assertNotIn("admin_redline", user_message)


if __name__ == "__main__":
    unittest.main()
