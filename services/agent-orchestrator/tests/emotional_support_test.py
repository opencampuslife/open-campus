from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
KNOWLEDGE_SRC = ROOT / "services" / "knowledge-service" / "src"
AGENT_SRC = ROOT / "services" / "agent-orchestrator" / "src"
BFF_SRC = ROOT / "services" / "api-gateway" / "src"
sys.path.extend([str(KNOWLEDGE_SRC), str(AGENT_SRC), str(BFF_SRC)])
sys.path.extend([str(AGENT_SRC / "bt"), str(AGENT_SRC / "fsm"), str(AGENT_SRC / "trees"), str(AGENT_SRC / "nodes")])

from indexer import build_index  # noqa: E402


class ModeRouterTest(unittest.TestCase):
    def setUp(self) -> None:
        from mode_router import route_mode
        self.route = route_mode

    def test_crisis_keywords_route_to_emotional_support(self) -> None:
        for msg in ["我不想活了", "想死的心都有了", "活着没意思了"]:
            with self.subTest(msg=msg):
                self.assertEqual(self.route(msg), "emotional_support")

    def test_emotion_keywords_route_to_emotional_support(self) -> None:
        for msg in ["我压力好大", "最近特别焦虑", "感觉很迷茫不知道怎么办", "害怕考不好"]:
            with self.subTest(msg=msg):
                self.assertEqual(self.route(msg), "emotional_support")

    def test_normal_admission_keywords_route_to_consultation(self) -> None:
        for msg in ["学校有哪些班型？", "学费多少钱？", "怎么报名？"]:
            with self.subTest(msg=msg):
                self.assertEqual(self.route(msg), "admissions_consultation")

    def test_intent_emotional_support_overrides(self) -> None:
        msg = "我最近状态不太好"
        self.assertEqual(self.route(msg, intent="emotional_support"), "emotional_support")


class EmotionalSupportFSMTest(unittest.TestCase):
    def setUp(self) -> None:
        from emotional_support_machine import EmotionalSupportMachine, EmotionalSupportEvent
        self.Machine = EmotionalSupportMachine
        self.Event = EmotionalSupportEvent

    def test_initial_state_is_emotion_detected(self) -> None:
        fsm = self.Machine()
        self.assertEqual(fsm.state.value, "EMOTION_DETECTED")

    def test_emotion_validated_transitions_to_validating(self) -> None:
        fsm = self.Machine()
        fsm.transition(self.Event.VALIDATED)
        self.assertEqual(fsm.state.value, "VALIDATING")

    def test_crisis_detected_transitions_to_escalation(self) -> None:
        fsm = self.Machine()
        fsm.transition(self.Event.CRISIS_DETECTED)
        self.assertEqual(fsm.state.value, "CRISIS_ESCALATION")
        self.assertTrue(fsm.is_crisis())

    def test_full_sequence_to_problem_solving(self) -> None:
        fsm = self.Machine()
        fsm.transition(self.Event.VALIDATED)
        self.assertEqual(fsm.state.value, "VALIDATING")
        fsm.transition(self.Event.NORMALIZED)
        self.assertEqual(fsm.state.value, "NORMALIZING")
        fsm.transition(self.Event.CLARIFIED)
        self.assertEqual(fsm.state.value, "CLARIFYING")
        fsm.transition(self.Event.REAPPRAISED)
        self.assertEqual(fsm.state.value, "REAPPRAISING")
        fsm.transition(self.Event.SOLUTION_FOUND)
        self.assertEqual(fsm.state.value, "PROBLEM_SOLVING")

    def test_problem_solving_to_motivation(self) -> None:
        fsm = self.Machine()
        for evt in [self.Event.VALIDATED, self.Event.NORMALIZED, self.Event.CLARIFIED,
                     self.Event.REAPPRAISED, self.Event.SOLUTION_FOUND]:
            fsm.transition(evt)
        fsm.transition(self.Event.MOTIVATED)
        self.assertEqual(fsm.state.value, "MOTIVATION_SUPPORT")
        self.assertTrue(fsm.can_bridge_back())

    def test_motivation_to_boundary_setting(self) -> None:
        fsm = self.Machine()
        for evt in [self.Event.VALIDATED, self.Event.NORMALIZED, self.Event.CLARIFIED,
                     self.Event.REAPPRAISED, self.Event.SOLUTION_FOUND, self.Event.MOTIVATED]:
            fsm.transition(evt)
        fsm.transition(self.Event.BRIDGE_SAFE)
        self.assertEqual(fsm.state.value, "BOUNDARY_SETTING")

    def test_crisis_from_any_state(self) -> None:
        fsm = self.Machine()
        fsm.transition(self.Event.VALIDATED)
        fsm.transition(self.Event.NORMALIZED)
        fsm.transition(self.Event.CRISIS_DETECTED)
        self.assertTrue(fsm.is_crisis())


class EmotionalSupportBTTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        os.environ.pop("DEEPSEEK_ENABLE_LLM", None)
        os.environ.pop("DEEPSEEK_API_KEY", None)
        build_index(ROOT)

    def setUp(self) -> None:
        from base import AgentContext
        from emotional_support_tree import build_emotional_support_tree
        self.ctx_cls = AgentContext
        self.build_es_tree = build_emotional_support_tree

    def test_crisis_imminent_triggers_handoff(self) -> None:
        from base import run_tree
        ctx = self.ctx_cls(
            user_id="u_parent",
            role="parent",
            campus="zhengzhou",
            message="我不想活了，这个世界没有希望了",
            project_root=ROOT,
        )
        tree = self.build_es_tree()
        result = run_tree(tree, ctx)
        self.assertEqual(ctx.crisis_risk, "imminent")
        self.assertTrue(ctx.handoff_triggered)
        self.assertEqual(ctx.risk_level, "high")
        self.assertIn("400-161-9995", ctx.answer_draft)

    def test_crisis_high_produces_support_message(self) -> None:
        from base import run_tree
        ctx = self.ctx_cls(
            user_id="u_student",
            role="student",
            campus="zhengzhou",
            message="我崩溃了，撑不住了",
            project_root=ROOT,
        )
        tree = self.build_es_tree()
        result = run_tree(tree, ctx)
        self.assertEqual(ctx.crisis_risk, "high")
        self.assertTrue(ctx.risk_level in ("high", "medium"))
        self.assertGreater(len(ctx.answer_draft), 10)

    def test_emotion_signal_produces_validating_response(self) -> None:
        from base import run_tree
        ctx = self.ctx_cls(
            user_id="u_parent",
            role="parent",
            campus="zhengzhou",
            message="孩子考试压力太大了，我最近一直失眠焦虑",
            project_root=ROOT,
        )
        tree = self.build_es_tree()
        result = run_tree(tree, ctx)
        self.assertNotEqual(ctx.emotion_theme, "",
                           f"Emotion theme should be set, got empty. Audit: {ctx.audit_events}")
        self.assertGreater(len(ctx.answer_draft), 20)
        self.assertFalse(ctx.handoff_triggered)

    def test_emotion_theme_classified_correctly(self) -> None:
        from base import run_tree
        cases = [
            ("我很焦虑很紧张", "anxiety"),
            ("我很难过很伤心", "sadness"),
            ("我很害怕不敢考试", "fear"),
            ("我特别生气这不公平", "anger"),
            ("我对不起父母辜负了期望", "guilt"),
            ("我很迷茫不知道怎么办", "confusion"),
        ]
        for msg, expected_theme in cases:
            with self.subTest(msg=msg):
                ctx = self.ctx_cls(
                    user_id="u_student",
                    role="student",
                    campus="zhengzhou",
                    message=msg,
                    project_root=ROOT,
                )
                tree = self.build_es_tree()
                run_tree(tree, ctx)
                self.assertEqual(ctx.emotion_theme, expected_theme,
                                f"Expected {expected_theme} for '{msg}', got '{ctx.emotion_theme}'")

    def test_admissions_bridge_safe_when_not_crisis(self) -> None:
        from base import run_tree
        ctx = self.ctx_cls(
            user_id="u_parent",
            role="parent",
            campus="zhengzhou",
            message="压力很大，但想了解适合什么班",
            project_root=ROOT,
        )
        tree = self.build_es_tree()
        run_tree(tree, ctx)
        self.assertTrue(ctx.safe_for_bridge,
                        f"Should be safe for bridge. crisis_risk={ctx.crisis_risk}, theme={ctx.emotion_theme}")

    def test_admissions_bridge_blocked_during_crisis(self) -> None:
        from base import run_tree
        ctx = self.ctx_cls(
            user_id="u_student",
            role="student",
            campus="zhengzhou",
            message="我想死了，什么班都没用",
            project_root=ROOT,
        )
        tree = self.build_es_tree()
        run_tree(tree, ctx)
        self.assertFalse(ctx.safe_for_bridge)
        self.assertNotIn("聊聊具体的班型", ctx.answer_draft)


class SourceHidingTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        os.environ.pop("DEEPSEEK_ENABLE_LLM", None)
        os.environ.pop("DEEPSEEK_API_KEY", None)
        build_index(ROOT)

    def test_should_hide_sources_for_visitor(self) -> None:
        from bff_gateway import _should_hide_sources
        self.assertTrue(_should_hide_sources({"role": "visitor"}))
        self.assertTrue(_should_hide_sources({"role": "parent"}))
        self.assertTrue(_should_hide_sources({"role": "student"}))

    def test_should_not_hide_sources_for_admin(self) -> None:
        from bff_gateway import _should_hide_sources
        self.assertFalse(_should_hide_sources({"role": "admin"}))
        self.assertFalse(_should_hide_sources({"role": "sales"}))
        self.assertFalse(_should_hide_sources({"role": "campus_admin"}))

    def test_strip_source_lines_removes_sources(self) -> None:
        from bff_gateway import _strip_source_lines
        answer = "这是答案内容\n来源：参考文档A、文档B\n更多内容"
        stripped = _strip_source_lines(answer)
        self.assertNotIn("来源：", stripped)
        self.assertIn("这是答案内容", stripped)
        self.assertIn("更多内容", stripped)

    def test_strip_source_lines_preserves_normal_lines(self) -> None:
        from bff_gateway import _strip_source_lines
        answer = "第一段\n来源：某文档\n第二段\n参考资料：某书\n第三段"
        stripped = _strip_source_lines(answer)
        self.assertNotIn("来源：", stripped)
        self.assertNotIn("参考资料：", stripped)
        self.assertIn("第一段", stripped)
        self.assertIn("第二段", stripped)
        self.assertIn("第三段", stripped)

    def test_bff_parent_answer_hides_citations(self) -> None:
        from bff_gateway import post_chat
        result = post_chat(
            {"session_id": "s_test_cit", "message": "学费多少钱？"},
            {"user_id": "u_parent", "role": "parent", "campus": "zhengzhou"},
            ROOT,
        )
        self.assertEqual(result["citations"], [],
                         f"Parent citations should be empty, got: {result['citations']}")
        answer = result["answer"]
        for line in answer.splitlines():
            self.assertFalse(
                line.strip().startswith("来源："),
                f"Source line found in BFF parent answer: {line[:60]}"
            )

    def test_bff_sales_answer_keeps_citations(self) -> None:
        from bff_gateway import post_chat
        result = post_chat(
            {"session_id": "s_test_cit2", "message": "全日制冲刺班怎么收费？"},
            {"user_id": "u_sales", "role": "sales", "campus": "zhengzhou", "auth_level": "staff"},
            ROOT,
        )
        citations = result.get("citations", [])
        self.assertGreater(len(citations), 0,
                           f"Sales citations should not be empty, got: {citations}")


class EmotionalSupportIntegrationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        os.environ.pop("DEEPSEEK_ENABLE_LLM", None)
        os.environ.pop("DEEPSEEK_API_KEY", None)
        build_index(ROOT)

    def test_emotional_message_routes_to_emotional_mode(self) -> None:
        from pipeline import receive_message
        result = receive_message(
            {"user_id": "u_parent", "role": "parent", "campus": "zhengzhou"},
            "孩子焦虑得睡不着，我真的很担心他",
            ROOT,
        )
        self.assertEqual(result.get("active_mode"), "emotional_support")

    def test_normal_admission_message_stays_in_consultation_mode(self) -> None:
        from pipeline import receive_message
        result = receive_message(
            {"user_id": "u_parent", "role": "parent", "campus": "zhengzhou"},
            "学校有哪些班型？",
            ROOT,
        )
        self.assertNotEqual(result.get("active_mode"), "emotional_support")

    def test_emotional_response_is_warm_and_validating(self) -> None:
        from pipeline import receive_message
        result = receive_message(
            {"user_id": "u_student", "role": "student", "campus": "zhengzhou"},
            "我很迷茫不知道怎么办，数学也学不进去",
            ROOT,
        )
        answer = result["answer"]
        self.assertGreater(len(answer), 10)
        self.assertFalse(answer.strip().startswith("根据资料"))

    def test_emotion_theme_preserved_in_response(self) -> None:
        from pipeline import receive_message
        result = receive_message(
            {"user_id": "u_parent", "role": "parent", "campus": "zhengzhou"},
            "我对不起孩子，感觉自己没做好",
            ROOT,
        )
        self.assertEqual(result.get("emotion_theme"), "guilt",
                         f"Expected guilt, got '{result.get('emotion_theme')}', answer: {result['answer'][:100]}")

    def test_crisis_integration_flow(self) -> None:
        from pipeline import receive_message
        result = receive_message(
            {"user_id": "u_student", "role": "student", "campus": "zhengzhou"},
            "我不想活了，考试太痛苦了",
            ROOT,
        )
        self.assertTrue(result.get("handoff_triggered"))
        self.assertEqual(result.get("active_mode"), "emotional_support")
        self.assertGreater(len(result["answer"]), 10)

    def test_parent_bff_chat_hides_sources_end_to_end(self) -> None:
        from bff_gateway import post_chat
        result = post_chat(
            {"session_id": "s_e2e_hide", "message": "学校有哪些班型？"},
            {"user_id": "u_parent", "role": "parent", "campus": "zhengzhou"},
            ROOT,
        )
        answer = result["answer"]
        for line in answer.splitlines():
            self.assertFalse(
                line.strip().startswith("来源："),
                f"Source line leaked to parent: {line[:60]}"
            )
        self.assertEqual(result["citations"], [])


if __name__ == "__main__":
    unittest.main()
