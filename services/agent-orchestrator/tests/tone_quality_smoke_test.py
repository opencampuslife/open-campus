from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
AGENT_SRC = ROOT / "services" / "agent-orchestrator" / "src"
BFF_SRC = ROOT / "services" / "api-gateway" / "src"
KNOWLEDGE_SRC = ROOT / "services" / "knowledge-service" / "src"
sys.path.extend([str(AGENT_SRC), str(BFF_SRC), str(KNOWLEDGE_SRC)])

from indexer import build_index  # noqa: E402


class ToneQualitySmokeTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        os.environ.pop("DEEPSEEK_ENABLE_LLM", None)
        os.environ.pop("DEEPSEEK_API_KEY", None)
        build_index(ROOT)

    def test_parent_response_does_not_show_sources(self) -> None:
        from bff_gateway import post_chat
        result = post_chat(
            {"session_id": "s_ts1", "message": "孩子430分适合什么班？"},
            {"user_id": "u_tone", "role": "parent", "campus": "zhengzhou"},
            ROOT,
        )
        answer = result["answer"]
        for line in answer.splitlines():
            self.assertFalse(
                line.strip().startswith("来源："),
                f"Source line in parent answer: {line[:60]}"
            )

    def test_student_response_does_not_show_sources(self) -> None:
        from bff_gateway import post_chat
        result = post_chat(
            {"session_id": "s_ts2", "message": "我害怕复读失败"},
            {"user_id": "u_tone2", "role": "student", "campus": "zhengzhou"},
            ROOT,
        )
        answer = result["answer"]
        for line in answer.splitlines():
            self.assertFalse(
                line.strip().startswith("来源："),
                f"Source line in student answer: {line[:60]}"
            )

    def test_emotional_support_answer_validates_emotion(self) -> None:
        from pipeline import receive_message
        result = receive_message(
            {"user_id": "u_tone3", "role": "parent", "campus": "zhengzhou"},
            "孩子现在一说复读就哭，我真的不知道怎么办",
            ROOT,
        )
        self.assertEqual(result.get("active_mode"), "emotional_support")
        answer = result["answer"]
        self.assertGreater(len(answer), 50, f"Answer too short: {answer[:100]}")
        self.assertNotEqual(result.get("emotion_theme"), "",
                           "Emotion theme should be set")

    def test_emotional_support_answer_avoids_sales_push(self) -> None:
        from pipeline import receive_message
        result = receive_message(
            {"user_id": "u_tone4", "role": "parent", "campus": "zhengzhou"},
            "孩子完全不跟我说学习的事，一说就吵",
            ROOT,
        )
        self.assertEqual(result.get("active_mode"), "emotional_support")
        answer = result["answer"]
        push_phrases = ["立刻报名", "马上报名", "赶紧报名", "现在就报", "不要犹豫"]
        for phrase in push_phrases:
            self.assertNotIn(phrase, answer,
                            f"Sales push phrase '{phrase}' found in emotional support answer")

    def test_emotional_support_answer_asks_one_low_pressure_question(self) -> None:
        from pipeline import receive_message
        result = receive_message(
            {"user_id": "u_tone5", "role": "student", "campus": "zhengzhou"},
            "我很迷茫不知道怎么办",
            ROOT,
        )
        self.assertEqual(result.get("active_mode"), "emotional_support")
        answer = result["answer"]
        self.assertGreater(len(answer), 20)

    def test_mixed_emotion_admissions_answer_emotion_first(self) -> None:
        from pipeline import receive_message
        result = receive_message(
            {"user_id": "u_tone6", "role": "parent", "campus": "zhengzhou"},
            "孩子430分想了解班型，但最近状态很差一直哭",
            ROOT,
        )
        self.assertEqual(result.get("active_mode"), "emotional_support",
                         f"Mixed signal should prioritize emotion, got {result.get('active_mode')}")
        answer = result["answer"]
        self.assertNotIn("根据资料", answer)
        self.assertNotIn("保证", answer)

    def test_crisis_answer_does_not_enter_admissions_bridge(self) -> None:
        from pipeline import receive_message
        result = receive_message(
            {"user_id": "u_tone7", "role": "student", "campus": "zhengzhou"},
            "我不想活了，学习太痛苦了",
            ROOT,
        )
        self.assertTrue(result.get("handoff_triggered"))
        answer = result["answer"]
        self.assertNotIn("班型", answer, "Crisis answer should not mention class types")
        self.assertNotIn("报名", answer, "Crisis answer should not mention enrollment")

    def test_answer_does_not_contain_mechanical_phrases(self) -> None:
        from pipeline import receive_message
        mechanical = ["根据资料显示", "根据知识库", "来源如下", "引用如下",
                      "系统判断", "检索结果表明", "该问题命中", "综上所述"]
        for msg in ["学校有哪些班型？", "孩子压力很大怎么办"]:
            with self.subTest(msg=msg):
                result = receive_message(
                    {"user_id": "u_tone8", "role": "parent", "campus": "zhengzhou"},
                    msg, ROOT,
                )
                answer = result["answer"]
                for phrase in mechanical:
                    self.assertNotIn(phrase, answer,
                                    f"Mechanical phrase '{phrase}' in: {answer[:80]}")

    def test_admin_audit_retains_evidence_ids(self) -> None:
        from pipeline import receive_message
        result = receive_message(
            {"user_id": "u_admin", "role": "admin", "campus": "all", "auth_level": "staff"},
            "全日制冲刺班怎么收费？",
            ROOT,
        )
        retrieval = result.get("retrieval", {})
        allowed = retrieval.get("allowed_chunks", [])
        self.assertGreater(len(allowed), 0, "Admin should retrieve evidence")

    def test_bff_sanitization_integration(self) -> None:
        from bff_gateway import post_chat
        result = post_chat(
            {"session_id": "s_tone_bff", "message": "孩子430分适合什么班？"},
            {"user_id": "u_parent", "role": "parent", "campus": "zhengzhou"},
            ROOT,
        )
        self.assertEqual(result["citations"], [])
        answer = result["answer"]
        for line in answer.splitlines():
            self.assertFalse(
                line.strip().startswith("来源："),
                f"BFF parent answer leaked source: {line[:60]}"
            )


if __name__ == "__main__":
    unittest.main()
