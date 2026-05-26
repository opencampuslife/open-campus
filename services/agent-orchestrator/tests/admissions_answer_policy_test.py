from __future__ import annotations
import sys
import unittest
from pathlib import Path

TEST_DIR = Path(__file__).resolve().parent
SRC_DIR = TEST_DIR.parent / "src"
sys.path.insert(0, str(SRC_DIR))
from policies.admissions_answer_policy import build_admissions_answer  # noqa: E402


class AdmissionsAnswerPolicyTest(unittest.TestCase):
    def test_answer_asks_missing_profile_questions_before_recommendation(self) -> None:
        result = build_admissions_answer(
            message="你们有什么班型？",
            intent="class_recommendation",
            profile={},
            profile_completeness=0.2,
            consultation_stage="NEEDS_ASSESSMENT",
            recommendation={"recommended_class_type": "冲刺班"},
            allowed_evidence=[],
            identity_type="parent",
        )
        self.assertIn("物理类还是历史类", result)

    def test_answer_uses_recommendation_reasons(self) -> None:
        result = build_admissions_answer(
            message="适合什么班型？",
            intent="class_recommendation",
            profile={"current_score": 430, "subject_type": "physics", "target_school_level": "undergraduate"},
            profile_completeness=0.65,
            consultation_stage="CLASS_RECOMMENDING",
            recommendation={
                "recommended_class_type": "全日制冲刺班",
                "reasons": ["基础薄弱适合全日制", "目标一本需要冲刺"],
                "not_suitable_if": ["自律性很强"],
                "next_questions": ["孩子平时晚上能专注学习吗"],
                "risk_warnings": ["全日制学习强度大"],
            },
            allowed_evidence=[],
            identity_type="parent",
        )
        self.assertIn("全日制冲刺班", result)
        self.assertIn("基础薄弱", result)

    def test_answer_includes_not_suitable_if(self) -> None:
        result = build_admissions_answer(
            message="适合什么班型？",
            intent="class_recommendation",
            profile={"current_score": 430, "subject_type": "physics", "target_school_level": "undergraduate"},
            profile_completeness=0.65,
            consultation_stage="CLASS_RECOMMENDING",
            recommendation={
                "recommended_class_type": "全日制冲刺班",
                "reasons": ["基础薄弱适合全日制"],
                "not_suitable_if": ["自律性很强"],
            },
            allowed_evidence=[],
            identity_type="parent",
        )
        self.assertIn("未必是最优选择", result)

    def test_class_recommendation_keeps_assessment_citation_and_no_promise_notice(self) -> None:
        result = build_admissions_answer(
            message="适合什么班型？",
            intent="class_recommendation",
            profile={"current_score": 430, "subject_type": "physics", "target_school_level": "undergraduate"},
            profile_completeness=0.65,
            consultation_stage="CLASS_RECOMMENDING",
            recommendation={"recommended_class_type": "全日制封闭班", "reasons": ["需要较强管理"]},
            allowed_evidence=[{"title": "全日制高考复读班介绍"}],
            identity_type="parent",
        )
        self.assertIn("预约学情评估", result)
        self.assertIn("不能承诺固定提分或录取结果", result)
        self.assertIn("来源：全日制高考复读班介绍", result)

    def test_answer_does_not_promise_score(self) -> None:
        result = build_admissions_answer(
            message="你们能保证提分100分吗？",
            intent="promise_risk",
            profile={"current_score": 430, "subject_type": "physics"},
            profile_completeness=0.5,
            consultation_stage="OBJECTION_HANDLING",
            recommendation=None,
            allowed_evidence=[],
            identity_type="parent",
        )
        self.assertNotIn("保证提分100分", result)
        self.assertNotIn("一定", result)

    def test_answer_does_not_promise_admission(self) -> None:
        result = build_admissions_answer(
            message="一定能录取吗？",
            intent="promise_risk",
            profile={"current_score": 430, "subject_type": "physics"},
            profile_completeness=0.5,
            consultation_stage="OBJECTION_HANDLING",
            recommendation=None,
            allowed_evidence=[],
            identity_type="parent",
        )
        self.assertNotIn("保证录取", result)

    def test_answer_routes_uncertain_price_to_handoff(self) -> None:
        result = build_admissions_answer(
            message="费用方面不太确定",
            intent="pricing_consulting",
            profile={"current_score": 430, "subject_type": "physics"},
            profile_completeness=0.5,
            consultation_stage="READY_FOR_HANDOFF",
            recommendation=None,
            allowed_evidence=[],
            identity_type="parent",
        )
        self.assertIn("招生顾问", result)

    def test_objection_stage_takes_priority_over_previous_recommendation(self) -> None:
        result = build_admissions_answer(
            message="这个班太贵了，真的值得吗？",
            intent="pricing_consulting",
            profile={"current_score": 430, "subject_type": "physics", "target_school_level": "undergraduate"},
            profile_completeness=0.65,
            consultation_stage="OBJECTION_HANDLING",
            recommendation={"recommended_class_type": "小班强化班", "reasons": ["多科薄弱"]},
            allowed_evidence=[],
            identity_type="parent",
        )
        self.assertIn("顾虑是合理的", result)
        self.assertNotIn("建议优先了解「小班强化班」", result)

    def test_parent_answer_uses_parent_friendly_explanation(self) -> None:
        result = build_admissions_answer(
            message="适合什么班型？",
            intent="class_recommendation",
            profile={"current_score": 430, "subject_type": "physics", "target_school_level": "undergraduate"},
            profile_completeness=0.65,
            consultation_stage="CLASS_RECOMMENDING",
            recommendation={
                "recommended_class_type": "全日制冲刺班",
                "reasons": ["基础薄弱适合全日制"],
            },
            allowed_evidence=[],
            identity_type="parent",
        )
        self.assertIn("您", result)

    def test_student_answer_uses_student_friendly_explanation(self) -> None:
        result = build_admissions_answer(
            message="适合什么班型？",
            intent="class_recommendation",
            profile={"current_score": 430, "subject_type": "physics", "target_school_level": "undergraduate"},
            profile_completeness=0.65,
            consultation_stage="CLASS_RECOMMENDING",
            recommendation={
                "recommended_class_type": "全日制冲刺班",
                "reasons": ["基础薄弱适合全日制"],
            },
            allowed_evidence=[],
            identity_type="student",
        )
        self.assertNotIn("您", result)


if __name__ == "__main__":
    unittest.main()
