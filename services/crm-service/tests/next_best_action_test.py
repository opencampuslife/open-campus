from __future__ import annotations
import sys
import unittest
from pathlib import Path

TEST_DIR = Path(__file__).resolve().parent
SRC_DIR = TEST_DIR.parent / "src"
sys.path.insert(0, str(SRC_DIR))

from next_best_action import determine_next_best_action  # noqa: E402


class NextBestActionTest(unittest.TestCase):
    def test_next_best_action_collect_profile(self) -> None:
        result = determine_next_best_action(
            profile={"current_score": 430},
            profile_completeness=0.3,
            consultation_stage="NEEDS_ASSESSMENT",
        )
        self.assertEqual(result["action"], "collect_profile")
        self.assertEqual(result["priority"], "high")

    def test_next_best_action_recommend_class(self) -> None:
        result = determine_next_best_action(
            profile={"current_score": 430, "subject_type": "physics", "target_school_level": "undergraduate"},
            profile_completeness=0.6,
            consultation_stage="CLASS_RECOMMENDING",
        )
        self.assertEqual(result["action"], "recommend_class")
        self.assertEqual(result["priority"], "high")

    def test_next_best_action_handoff_for_visit_request(self) -> None:
        result = determine_next_best_action(
            profile={"current_score": 430, "subject_type": "physics"},
            profile_completeness=0.5,
            consultation_stage="READY_FOR_HANDOFF",
        )
        self.assertEqual(result["action"], "handoff_to_consultant")
        self.assertEqual(result["priority"], "high")

    def test_next_best_action_assign_consultant_for_high_intent(self) -> None:
        result = determine_next_best_action(
            profile={"current_score": 430, "subject_type": "physics", "target_school_level": "undergraduate"},
            profile_completeness=0.7,
            consultation_stage="NEEDS_ASSESSMENT",
            has_contact=True,
            intent_level="high",
        )
        self.assertEqual(result["action"], "assign_consultant")
        self.assertEqual(result["priority"], "high")

    def test_sensitive_fields_not_in_output(self) -> None:
        result = determine_next_best_action(
            profile={"current_score": 430},
            profile_completeness=0.3,
            consultation_stage="NEEDS_ASSESSMENT",
        )
        self.assertNotIn("phone", result)
        self.assertNotIn("parent_phone", result)

    def test_action_priority_is_string(self) -> None:
        result = determine_next_best_action(
            profile={"current_score": 430},
            profile_completeness=0.5,
            consultation_stage="NEEDS_ASSESSMENT",
        )
        self.assertIsInstance(result["priority"], str)
        self.assertIsInstance(result["action"], str)


if __name__ == "__main__":
    unittest.main()
