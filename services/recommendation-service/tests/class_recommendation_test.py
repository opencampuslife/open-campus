from __future__ import annotations

import sys
import unittest
from pathlib import Path

TEST_DIR = Path(__file__).resolve().parent
SRC_DIR = TEST_DIR.parent / "src"
sys.path.insert(0, str(SRC_DIR))

from recommendation_model import ClassRecommendation, RecommendationInput
from recommendation_engine import generate_recommendation
from recommendation_explainer import explain_recommendation


class ClassRecommendationTest(unittest.TestCase):
    def _profile(self, **kw):
        base = {"current_score": 400, "subject_type": "physics", "target_school_level": "undergraduate", "weak_subjects": ["数学", "英语"], "self_discipline_level": "medium"}
        base.update(kw)
        return base

    def test_recommends_small_class_for_mid_score_multi_weak(self):
        rec = generate_recommendation(self._profile(weak_subjects=["数学","英语"]), [])
        self.assertEqual(rec.recommended_class_type, "小班强化班")
        self.assertGreater(len(rec.reasons), 0)

    def test_recommends_closed_boarding_for_low_discipline(self):
        rec = generate_recommendation(self._profile(self_discipline_level="low", weak_subjects=["数学"], boarding_preference="boarding"), [])
        self.assertEqual(rec.recommended_class_type, "全日制封闭班")

    def test_recommends_single_subject_for_one_weak_high_discipline(self):
        rec = generate_recommendation(self._profile(weak_subjects=["数学"], self_discipline_level="high"), [])
        self.assertEqual(rec.recommended_class_type, "单科突破班")

    def test_recommends_sprint_class_for_near_target(self):
        rec = generate_recommendation(
            self._profile(current_score=460, target_score=490, weak_subjects=[], self_discipline_level="high"),
            [],
        )
        self.assertEqual(rec.recommended_class_type, "冲刺班")

    def test_no_recommendation_without_key_info(self):
        rec = generate_recommendation({}, [])
        self.assertIsNone(rec.recommended_class_type)
        self.assertEqual(rec.confidence, "low")
        self.assertGreater(len(rec.next_questions), 0)

    def test_recommendation_includes_evidence_ids(self):
        evidence = [{"chunk_id": "doc::001", "content": "小班和分层管理", "title": "班型介绍"}]
        rec = generate_recommendation(self._profile(), evidence)
        self.assertIn("evidence_ids", rec.__dataclass_fields__)

    def test_recommendation_never_promises_score(self):
        rec = generate_recommendation(self._profile(), [])
        for reason in rec.reasons:
            self.assertNotIn("保证", reason)
        for warning in rec.risk_warnings:
            self.assertIn("不承诺", warning)

    def test_recommendation_never_promises_admission(self):
        rec = generate_recommendation(self._profile(), [])
        for reason in rec.reasons:
            self.assertNotIn("录取", reason)
        all_text = " ".join(rec.reasons + rec.risk_warnings)
        self.assertNotIn("保证录取", all_text)

    def test_recommendation_returns_next_questions(self):
        rec = generate_recommendation(self._profile(), [])
        self.assertGreater(len(rec.next_questions), 0)

    def test_explainer_does_not_promise(self):
        rec = generate_recommendation(self._profile(), [])
        text = explain_recommendation(rec, "parent")
        self.assertNotIn("保证提分", text)
        self.assertNotIn("保证录取", text)
