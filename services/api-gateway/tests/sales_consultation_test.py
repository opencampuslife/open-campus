from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SERVICE_SRC = ROOT / "services" / "api-gateway" / "src"
sys.path.append(str(SERVICE_SRC))

from bff_gateway import (
    get_sales_session,
    _build_profile_summary_card,
    _build_recommendation_card,
    _build_next_best_action_card,
    _extract_risk_tags,
)


class SalesConsultationViewTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        (self.tmp / "data" / "sessions").mkdir(parents=True, exist_ok=True)
        self.sales_identity = {"user_id": "u_sales", "role": "sales", "campus": "zhengzhou"}
        self.session = {
            "session_id": "s_test_001",
            "user_id": "u_parent",
            "role": "parent",
            "campus": "zhengzhou",
            "created_at": "2026-01-01T00:00:00Z",
            "updated_at": "2026-01-01T00:00:00Z",
            "messages": [],
            "intent": {"intent": "class_recommendation"},
            "profile": {
                "identity_type": "parent",
                "subject_type": "physics",
                "current_score": 430,
                "target_school_level": "undergraduate",
                "weak_subjects": ["数学", "英语"],
                "self_discipline_level": "low",
                "preferred_campus": "郑州",
            },
            "consultation_stage": "CLASS_RECOMMENDING",
            "recommendation_result": {
                "recommended_class_type": "小班强化班",
                "confidence": "medium",
                "reasons": ["分数适中", "多科薄弱"],
                "not_suitable_if": ["自律性强且只有单科弱"],
                "missing_info": ["budget_range"],
                "next_questions": ["是否住宿？"],
            },
            "next_best_action": {"action": "recommend_class", "description": "已具备基本画像，推荐班型", "priority": "high"},
            "takeover_status": "open",
            "assigned_to": None,
            "followups": [],
        }
        session_path = self.tmp / "data" / "sessions" / "s_test_001.json"
        session_path.write_text(json.dumps(self.session, ensure_ascii=False, indent=2), encoding="utf-8")

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_sales_session_includes_profile_summary(self):
        result = get_sales_session("s_test_001", self.sales_identity, self.tmp)
        self.assertIn("profile_summary", result)
        ps = result["profile_summary"]
        self.assertEqual(ps["identity_type"], "parent")
        self.assertEqual(ps["current_score"], 430)
        self.assertIn("physics", ps["subject_type"])
        self.assertIn("数学", ps["weak_subjects"])

    def test_sales_session_includes_recommendation_summary(self):
        result = get_sales_session("s_test_001", self.sales_identity, self.tmp)
        self.assertIn("recommendation_summary", result)
        rs = result["recommendation_summary"]
        self.assertEqual(rs["recommended_class_type"], "小班强化班")
        self.assertEqual(rs["confidence"], "medium")
        self.assertGreater(len(rs["reasons"]), 0)

    def test_sales_session_includes_next_best_action(self):
        result = get_sales_session("s_test_001", self.sales_identity, self.tmp)
        self.assertIn("next_best_action", result)
        nba = result["next_best_action"]
        self.assertEqual(nba["action"], "recommend_class")
        self.assertEqual(nba["priority"], "high")

    def test_sales_session_includes_risk_tags(self):
        result = get_sales_session("s_test_001", self.sales_identity, self.tmp)
        self.assertIn("risk_tags", result)
        self.assertIn("low_discipline", result["risk_tags"])

    def test_sensitive_fields_are_not_leaked(self):
        result = get_sales_session("s_test_001", self.sales_identity, self.tmp)
        ps = result.get("profile_summary", {})
        result_str = json.dumps(result)
        self.assertNotIn("password", result_str.lower())
        self.assertNotIn("secret", result_str.lower())
