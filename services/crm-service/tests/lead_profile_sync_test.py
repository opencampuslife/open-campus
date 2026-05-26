from __future__ import annotations
import sys
import tempfile
import unittest
from pathlib import Path

TEST_DIR = Path(__file__).resolve().parent
SRC_DIR = TEST_DIR.parent / "src"
sys.path.insert(0, str(SRC_DIR))

from leads import upsert_lead  # noqa: E402


class LeadProfileSyncTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.project_root = Path(self.tmp_dir.name)

    def tearDown(self) -> None:
        self.tmp_dir.cleanup()

    def test_lead_profile_summary_created_on_upsert(self) -> None:
        lead = upsert_lead(
            self.project_root,
            session_id="s_sync_001",
            identity={"user_id": "u_parent", "role": "parent", "campus": "zhengzhou"},
            message="孩子430分想报名",
            intent="class_recommendation",
            profile={"current_score": 430, "subject_type": "physics", "target_school_level": "undergraduate"},
            campus_id="zhengzhou",
        )
        self.assertIn("profile_summary", lead)
        self.assertGreater(len(lead["profile_summary"]), 0)
        self.assertEqual(lead["profile_summary"]["subject_type"], "physics")

    def test_lead_profile_completeness_stored(self) -> None:
        lead = upsert_lead(
            self.project_root,
            session_id="s_sync_002",
            identity={"user_id": "u_parent", "role": "parent", "campus": "zhengzhou"},
            message="孩子430分，物理类",
            intent="class_recommendation",
            profile={
                "current_score": 430,
                "subject_type": "physics",
                "target_school_level": "undergraduate",
                "_completeness": 0.65,
            },
            campus_id="zhengzhou",
        )
        self.assertEqual(lead.get("profile_completeness"), 0.65)

    def test_lead_consultation_stage_updated(self) -> None:
        lead = upsert_lead(
            self.project_root,
            session_id="s_sync_003",
            identity={"user_id": "u_parent", "role": "parent", "campus": "zhengzhou"},
            message="孩子430分想报名",
            intent="class_recommendation",
            profile={
                "current_score": 430,
                "consultation_stage": "CLASS_RECOMMENDING",
                "recommendation_summary": {"recommended_class_type": "小班强化班"},
                "next_best_action": {"action": "recommend_class", "priority": "high"},
                "risk_tags": ["low_discipline"],
            },
            campus_id="zhengzhou",
        )
        self.assertEqual(lead["consultation_stage"], "CLASS_RECOMMENDING")
        self.assertEqual(lead["recommendation_summary"]["recommended_class_type"], "小班强化班")
        self.assertEqual(lead["next_best_action"]["action"], "recommend_class")
        self.assertIn("low_discipline", lead["risk_tags"])

    def test_sensitive_profile_fields_not_logged_plaintext(self) -> None:
        lead = upsert_lead(
            self.project_root,
            session_id="s_sync_004",
            identity={"user_id": "u_parent", "role": "parent", "campus": "zhengzhou"},
            message="孩子430分想报名",
            intent="class_recommendation",
            profile={"current_score": 430, "phone": "13800138000", "id_card": "410123456789012345"},
            campus_id="zhengzhou",
        )
        self.assertNotIn("13800138000", str(lead))
        self.assertNotIn("410123456789012345", str(lead))


if __name__ == "__main__":
    unittest.main()
