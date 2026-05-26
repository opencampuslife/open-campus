from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
AGENT_SRC = ROOT / "services" / "agent-orchestrator" / "src"
sys.path.insert(0, str(AGENT_SRC))

from consultation.stage import determine_stage, ConsultationStage  # noqa: E402


class ConsultationStageTest(unittest.TestCase):
    def test_low_profile_completeness_routes_to_profile_collecting(self):
        profile: dict = {}
        stage = determine_stage(profile, 0.1, "你好")
        self.assertEqual(stage, ConsultationStage.PROFILE_COLLECTING)

    def test_missing_score_routes_to_profile_collecting(self):
        profile = {"subject_type": "physics", "target_school_level": "undergraduate"}
        stage = determine_stage(profile, 0.3, "你好")
        self.assertEqual(stage, ConsultationStage.PROFILE_COLLECTING)

    def test_basic_profile_routes_to_needs_assessment(self):
        profile = {"current_score": 430, "subject_type": "physics", "target_school_level": "undergraduate"}
        stage = determine_stage(profile, 0.5, "你好，想了解下")
        self.assertEqual(stage, ConsultationStage.NEEDS_ASSESSMENT)

    def test_class_query_routes_to_class_recommending(self):
        profile = {"current_score": 430, "subject_type": "physics", "target_school_level": "undergraduate"}
        stage = determine_stage(profile, 0.55, "你们有什么班型可以推荐吗")
        self.assertEqual(stage, ConsultationStage.CLASS_RECOMMENDING)

    def test_followup_question_routes_to_plan_explaining(self):
        profile = {"current_score": 430, "subject_type": "physics", "target_school_level": "undergraduate"}
        stage = determine_stage(profile, 0.55, "为什么这个班比较好")
        self.assertEqual(stage, ConsultationStage.PLAN_EXPLAINING)

    def test_price_objection_routes_to_objection_handling(self):
        profile = {"current_score": 430, "subject_type": "physics", "target_school_level": "undergraduate"}
        stage = determine_stage(profile, 0.55, "太贵了吧，不值这个价")
        self.assertEqual(stage, ConsultationStage.OBJECTION_HANDLING)

    def test_handoff_request_routes_to_ready_for_handoff(self):
        profile = {"current_score": 430, "subject_type": "physics", "target_school_level": "undergraduate"}
        stage = determine_stage(profile, 0.55, "能转人工吗，我想打电话咨询")
        self.assertEqual(stage, ConsultationStage.READY_FOR_HANDOFF)

    def test_human_taken_over_routes_to_followup_pending(self):
        profile = {"current_score": 430, "subject_type": "physics", "target_school_level": "undergraduate"}
        stage = determine_stage(profile, 0.55, "你好", session_has_handoff=True)
        self.assertEqual(stage, ConsultationStage.FOLLOWUP_PENDING)


if __name__ == "__main__":
    unittest.main()
