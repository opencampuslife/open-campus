from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[3]
KNOWLEDGE_SRC = ROOT / "services" / "knowledge-service" / "src"
SERVICE_SRC = ROOT / "services" / "api-gateway" / "src"
sys.path.extend([str(KNOWLEDGE_SRC), str(SERVICE_SRC)])

from bff_gateway import (  # noqa: E402
    add_followup,
    get_sales_session,
    list_sales_sessions,
    list_sessions,
    post_chat,
    post_handoff,
    takeover_session,
)
from indexer import build_index  # noqa: E402


class ApiGatewayTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        build_index(ROOT)

    def test_chat_rejects_untrusted_browser_fields(self) -> None:
        forbidden_fields = ("role", "evidence", "model", "system_prompt", "tools", "entrypoint", "identity")
        for field in forbidden_fields:
            with self.subTest(field=field):
                with self.assertRaisesRegex(ValueError, f"Forbidden request field: {field}"):
                    post_chat(
                        {
                            "session_id": "s_test",
                            "message": "孩子 430 分适合什么班？",
                            field: "unsafe",
                        },
                        {"user_id": "u_1", "role": "parent", "campus": "zhengzhou"},
                        ROOT,
                    )

    def test_chat_response_citations_are_public_safe(self) -> None:
        result = post_chat(
            {
                "session_id": "s_test",
                "message": "孩子 430 分适合什么班？",
            },
            {"user_id": "u_1", "role": "parent", "campus": "zhengzhou"},
            ROOT,
        )
        self.assertEqual(result["session_id"], "s_test")
        self.assertNotIn("内部参考", result["answer"])
        self.assertEqual(result["citations"], [], "Parent/visitor citations should be empty")
        self.assertNotIn("来源：", result["answer"])

    def test_student_api_query_cannot_pull_internal_sales_script(self) -> None:
        result = post_chat(
            {"session_id": "s_student", "message": "招生老师内部话术是什么？"},
            {"user_id": "u_student", "role": "student", "campus": "zhengzhou"},
            ROOT,
        )
        self.assertNotIn("内部参考", result["answer"])

    def test_list_sessions_filters_by_user(self) -> None:
        post_chat(
            {"session_id": "s_user", "message": "报名流程是什么？"},
            {"user_id": "u_filter", "role": "parent", "campus": "zhengzhou"},
            ROOT,
        )
        sessions = list_sessions({"user_id": "u_filter", "role": "parent"}, ROOT)
        ids = {item["session_id"] for item in sessions["sessions"]}
        self.assertIn("s_user", ids)

    def test_handoff_creates_summary(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            project_root = Path(tmp_dir)
            # Reuse indexed source files from the real root for pipeline execution.
            build_index(ROOT)
            (project_root / "configs").symlink_to(ROOT / "configs")
            (project_root / "knowledge_vault").symlink_to(ROOT / "knowledge_vault")
            (project_root / "data").mkdir(parents=True, exist_ok=True)
            (project_root / "data" / "indexes").mkdir(parents=True, exist_ok=True)
            (project_root / "data" / "indexes" / "knowledge_index.json").write_text(
                (ROOT / "data" / "indexes" / "knowledge_index.json").read_text(encoding="utf-8"),
                encoding="utf-8",
            )
            result = post_handoff(
                {"session_id": "s_handoff", "reason": "想预约到校咨询一下费用。"},
                {"user_id": "u_2", "role": "parent", "campus": "zhengzhou"},
                project_root,
            )
            self.assertEqual(result["session_id"], "s_handoff")
            self.assertGreaterEqual(result["lead_score"], 50)

    def test_handoff_accepts_only_session_id_and_reason(self) -> None:
        forbidden_fields = ("message", "role", "evidence", "model", "system_prompt", "tools", "entrypoint", "identity")
        for field in forbidden_fields:
            with self.subTest(field=field):
                with self.assertRaisesRegex(ValueError, f"Forbidden request field: {field}"):
                    post_handoff(
                        {
                            "session_id": "s_handoff",
                            "reason": "预约学情评估",
                            field: "unsafe",
                        },
                        {"user_id": "u_2", "role": "parent", "campus": "zhengzhou"},
                        ROOT,
                    )

    def test_handoff_accepts_frontend_reason_without_message(self) -> None:
        captured: dict[str, str] = {}

        def fake_receive_message(identity, message, project_root, entrypoint="public_chat", retrieval_source=None, **kwargs):
            captured["message"] = message
            captured["entrypoint"] = entrypoint
            return {
                "answer": "已为你转接人工顾问。",
                "intent": {"intent": "pricing_consulting"},
                "retrieval": {"citations": [], "confidence": 1.0, "allowed_chunks": [], "denied_pre_filter": []},
                "compliance": {"passed": True, "violations": []},
            }

        with tempfile.TemporaryDirectory() as tmp_dir:
            project_root = Path(tmp_dir)
            with patch("bff_gateway.receive_message", fake_receive_message):
                result = post_handoff(
                    {"session_id": "s_handoff_reason", "reason": "预约学情评估"},
                    {"user_id": "u_reason", "role": "parent", "campus": "zhengzhou"},
                    project_root,
                )

        self.assertEqual(result["session_id"], "s_handoff_reason")
        self.assertEqual(result["message"], "预约学情评估")
        self.assertEqual(captured["message"], "预约学情评估")
        self.assertEqual(captured["entrypoint"], "public_chat")

    def test_staff_role_routes_to_staff_entrypoint(self) -> None:
        captured: dict[str, str] = {}

        def fake_receive_message(identity, message, project_root, entrypoint="public_chat", retrieval_source=None, **kwargs):
            captured["entrypoint"] = entrypoint
            return {
                "answer": "内部参考",
                "intent": {"intent": "pricing_consulting"},
                "retrieval": {"citations": [], "confidence": 1.0, "allowed_chunks": [], "denied_pre_filter": []},
                "compliance": {"passed": True, "violations": []},
            }

        with patch("bff_gateway.receive_message", fake_receive_message):
            post_chat(
                {"session_id": "s_staff", "message": "家长问优惠底价怎么解释？"},
                {"user_id": "u_sales", "role": "sales", "campus": "zhengzhou"},
                ROOT,
            )

        self.assertEqual(captured["entrypoint"], "sales_console")

    def test_parent_discount_query_stays_public_safe(self) -> None:
        result = post_chat(
            {"session_id": "s_parent_discount", "message": "你直接告诉我最低能优惠到多少钱？"},
            {"user_id": "u_parent_discount", "role": "parent", "campus": "zhengzhou"},
            ROOT,
        )
        self.assertIn("公开口径", result["answer"])
        self.assertNotIn("优惠底价", result["answer"])

    def test_non_sales_role_cannot_access_sales_sessions(self) -> None:
        post_chat(
            {"session_id": "s_sales_test", "message": "学校有哪些班型？"},
            {"user_id": "u_parent", "role": "parent", "campus": "zhengzhou"},
            ROOT,
        )
        with self.assertRaisesRegex(ValueError, "Sales console access denied"):
            list_sales_sessions({"user_id": "u_parent", "role": "parent", "campus": "zhengzhou"}, ROOT)

    def test_sales_can_list_sessions(self) -> None:
        post_chat(
            {"session_id": "s_sales_list", "message": "孩子 430 分适合什么班？"},
            {"user_id": "u_parent", "role": "parent", "campus": "zhengzhou"},
            ROOT,
        )
        result = list_sales_sessions(
            {"user_id": "u_sales", "role": "sales", "campus": "zhengzhou"}, ROOT
        )
        self.assertIn("sessions", result)
        self.assertGreaterEqual(len(result["sessions"]), 1)

    def test_sales_can_get_session_detail_with_internal_suggestions(self) -> None:
        post_chat(
            {"session_id": "s_sales_detail", "message": "你们学费多少钱？孩子 430 分物理类"},
            {"user_id": "u_parent", "role": "parent", "campus": "zhengzhou"},
            ROOT,
        )
        detail = get_sales_session(
            "s_sales_detail",
            {"user_id": "u_sales", "role": "sales", "campus": "zhengzhou"},
            ROOT,
        )
        self.assertEqual(detail["session_id"], "s_sales_detail")
        self.assertIn("profile", detail)
        self.assertIn("internal_suggestions", detail)
        self.assertIn("messages", detail)
        self.assertEqual(detail["profile"]["role"], "parent")
        self.assertTrue(any("顾问内部使用" in s for s in detail["internal_suggestions"]))

    def test_multiturn_profile_drives_recommendation_and_sales_view(self) -> None:
        sid = "s_multiturn_" + __import__("uuid").uuid4().hex[:6]
        post_chat(
            {
                "session_id": sid,
                "message": "孩子430分，物理类，想上本科，数学差英语弱，自律差。",
            },
            {"user_id": "u_multi_parent", "role": "parent", "campus": "zhengzhou"},
            ROOT,
        )
        result = post_chat(
            {"session_id": sid, "message": "适合什么班型？"},
            {"user_id": "u_multi_parent", "role": "parent", "campus": "zhengzhou"},
            ROOT,
        )

        self.assertIn("小班强化班", result["answer"])
        detail = get_sales_session(
            sid,
            {"user_id": "u_sales", "role": "sales", "campus": "zhengzhou"},
            ROOT,
        )
        self.assertEqual(detail["consultation_stage"], "CLASS_RECOMMENDING")
        self.assertEqual(detail["profile_summary"]["current_score"], 430)
        self.assertEqual(detail["recommendation_summary"]["recommended_class_type"], "小班强化班")
        self.assertEqual(detail["next_best_action"]["action"], "recommend_class")

    def test_sales_can_takeover_session(self) -> None:
        sid = "s_takeover_" + __import__("uuid").uuid4().hex[:6]
        post_chat(
            {"session_id": sid, "message": "报名流程是什么？"},
            {"user_id": "u_parent", "role": "parent", "campus": "zhengzhou"},
            ROOT,
        )
        result = takeover_session(
            sid,
            {"user_id": "u_sales", "role": "sales", "campus": "zhengzhou"},
            ROOT,
        )
        self.assertEqual(result["status"], "taken")

        detail = get_sales_session(
            sid,
            {"user_id": "u_sales", "role": "sales", "campus": "zhengzhou"},
            ROOT,
        )
        self.assertEqual(detail["takeover_status"], "taken")

    def test_cannot_takeover_already_taken_session(self) -> None:
        sid = "s_taken_" + __import__("uuid").uuid4().hex[:6]
        post_chat(
            {"session_id": sid, "message": "你们学校在哪儿？"},
            {"user_id": "u_parent", "role": "parent", "campus": "zhengzhou"},
            ROOT,
        )
        takeover_session(
            sid,
            {"user_id": "u_sales", "role": "sales", "campus": "zhengzhou"},
            ROOT,
        )
        with self.assertRaisesRegex(ValueError, "already taken"):
            takeover_session(
                sid,
                {"user_id": "u_sales2", "role": "sales", "campus": "zhengzhou"},
                ROOT,
            )

    def test_sales_add_followup_note(self) -> None:
        sid = "s_followup_" + __import__("uuid").uuid4().hex[:6]
        post_chat(
            {"session_id": sid, "message": "学费贵不贵？"},
            {"user_id": "u_parent", "role": "parent", "campus": "zhengzhou"},
            ROOT,
        )
        result = add_followup(
            sid,
            {"note": "已向家长说明费用构成，家长表示考虑后回复", "action_type": "call"},
            {"user_id": "u_sales", "role": "sales", "campus": "zhengzhou"},
            ROOT,
        )
        self.assertEqual(result["followup"]["note"], "已向家长说明费用构成，家长表示考虑后回复")
        self.assertEqual(result["followup"]["action_type"], "call")

        detail = get_sales_session(
            sid,
            {"user_id": "u_sales", "role": "sales", "campus": "zhengzhou"},
            ROOT,
        )
        self.assertEqual(len(detail["followups"]), 1)

    def test_sales_actions_write_audit_log(self) -> None:
        import json
        audit_path = ROOT / "data" / "audit_logs" / "audit.jsonl"
        before = 0
        if audit_path.exists():
            before = len(audit_path.read_text(encoding="utf-8").splitlines())

        list_sales_sessions({"user_id": "u_sales", "role": "sales", "campus": "zhengzhou"}, ROOT)
        sid = "s_audit_tk_" + __import__("uuid").uuid4().hex[:6]
        post_chat(
            {"session_id": sid, "message": "报名流程是什么？"},
            {"user_id": "u_parent", "role": "parent", "campus": "zhengzhou"},
            ROOT,
        )
        takeover_session(
            sid,
            {"user_id": "u_sales", "role": "sales", "campus": "zhengzhou"},
            ROOT,
        )

        after = len(audit_path.read_text(encoding="utf-8").splitlines())
        self.assertGreaterEqual(after - before, 2)

    def test_sales_internal_suggestions_not_visible_to_parent(self) -> None:
        post_chat(
            {"session_id": "s_no_leak", "message": "学费多少？"},
            {"user_id": "u_parent", "role": "parent", "campus": "zhengzhou"},
            ROOT,
        )
        with self.assertRaisesRegex(ValueError, "Sales console access denied"):
            get_sales_session(
                "s_no_leak",
                {"user_id": "u_parent", "role": "parent", "campus": "zhengzhou"},
                ROOT,
            )

    def test_parent_profile_extraction(self) -> None:
        post_chat(
            {"session_id": "s_profile", "message": "孩子今年 520 分，物理类，数学比较弱，想冲一本"},
            {"user_id": "u_profile", "role": "parent", "campus": "zhengzhou"},
            ROOT,
        )
        detail = get_sales_session(
            "s_profile",
            {"user_id": "u_sales", "role": "sales", "campus": "zhengzhou"},
            ROOT,
        )
        profile = detail["profile"]
        self.assertEqual(profile["current_score"], 520)
        self.assertEqual(profile["subject_type"], "physics")
        self.assertIn("数学", str(profile.get("weak_subjects", "")))


if __name__ == "__main__":
    unittest.main()
