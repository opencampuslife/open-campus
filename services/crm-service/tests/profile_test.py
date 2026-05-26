from __future__ import annotations

import sys
import unittest
from pathlib import Path

TEST_DIR = Path(__file__).resolve().parent
SRC_DIR = TEST_DIR.parent / "src"
sys.path.insert(0, str(SRC_DIR))

from profile_model import (  # noqa: E402
    ProfilePatch,
    extract_profile_from_message,
    merge_profile,
    compute_completeness,
    profile_summary,
    REQUIRED_FIELDS,
)


class ProfileExtractionTest(unittest.TestCase):
    def test_extract_score_from_message(self):
        patch = extract_profile_from_message("孩子考了430分，物理类")
        self.assertIn("current_score", patch.updates)
        self.assertEqual(patch.updates["current_score"], 430)
        self.assertAlmostEqual(patch.confidence["current_score"], 0.95)

    def test_extract_score_without_fen_suffix(self):
        patch = extract_profile_from_message("我今年考了580，历史类，目标211")
        self.assertEqual(patch.updates["current_score"], 580)

    def test_extract_subject_type_from_message(self):
        patch = extract_profile_from_message("孩子是物理类，今年考了430")
        self.assertIn("subject_type", patch.updates)
        self.assertEqual(patch.updates["subject_type"], "physics")

        patch2 = extract_profile_from_message("孩子历史类")
        self.assertEqual(patch2.updates.get("subject_type"), "history")

    def test_extract_weak_subjects_from_message(self):
        patch = extract_profile_from_message("孩子数学和英语比较弱，物理也不行")
        self.assertIn("weak_subjects", patch.updates)
        weak = patch.updates["weak_subjects"]
        self.assertIn("数学", weak)
        self.assertIn("英语", weak)

    def test_subject_performance_does_not_imply_exam_track_or_discipline(self):
        patch = extract_profile_from_message("数学和英语比较弱，物理还行")
        self.assertEqual(patch.updates["weak_subjects"], ["数学", "英语"])
        self.assertNotIn("subject_type", patch.updates)
        self.assertNotIn("self_discipline_level", patch.updates)

    def test_profile_merge_preserves_existing_fields(self):
        existing = {"current_score": 430, "province": "河南", "subject_type": "physics"}
        patch = extract_profile_from_message("想冲一本", existing)
        merged = merge_profile(existing, patch)
        self.assertEqual(merged["current_score"], 430)
        self.assertEqual(merged["province"], "河南")
        self.assertEqual(merged["subject_type"], "physics")
        self.assertIn("target_school_level", merged)

    def test_user_correction_overrides_old_profile(self):
        existing = {"current_score": 430}
        # User says a significantly different score
        patch = extract_profile_from_message("不对，是460分")
        merged = merge_profile(existing, patch)
        self.assertEqual(merged["current_score"], 460)

    def test_profile_missing_fields_detected(self):
        empty = {}
        patch = extract_profile_from_message("想了解一下有什么班", empty)
        missing = patch.missing_required_fields
        self.assertIn("subject_type", missing)
        self.assertIn("current_score", missing)

    def test_day_student_and_repeat_year_are_extracted_without_substring_collision(self):
        commute = extract_profile_from_message("走读不住校，离郑州校区近")
        self.assertEqual(commute.updates["boarding_preference"], "day")

        student = extract_profile_from_message("我是学生本人，今年复读第二年")
        self.assertEqual(student.updates["identity_type"], "student")
        self.assertEqual(student.updates["repeat_year_count"], 2)

    def test_profile_completeness_scoring(self):
        full_profile = {
            "identity_type": "parent",
            "subject_type": "physics",
            "current_score": 430,
            "target_school_level": "undergraduate",
            "weak_subjects": ["数学", "英语"],
            "self_discipline_level": "low",
            "preferred_class_type": "全日制",
            "preferred_campus": "郑州",
        }
        score = compute_completeness(full_profile)
        self.assertGreater(score, 0.5)
        self.assertLessEqual(score, 1.0)

        empty_score = compute_completeness({})
        self.assertAlmostEqual(empty_score, 0.0)

    def test_profile_summary_generates_safe_dict(self):
        profile = {
            "identity_type": "parent",
            "province": "河南",
            "subject_type": "physics",
            "current_score": 430,
            "target_school_level": "undergraduate",
            "weak_subjects": ["数学", "英语"],
            "self_discipline_level": "low",
            "budget_range": "medium",
            "preferred_class_type": "全日制",
            "secret_field": "should_not_appear",
        }
        summary = profile_summary(profile)
        self.assertEqual(summary["identity_type"], "parent")
        self.assertEqual(summary["current_score"], 430)
        self.assertIn("completeness", summary)
        self.assertNotIn("secret_field", summary)


if __name__ == "__main__":
    unittest.main()
