from __future__ import annotations

import sys
import unittest
from pathlib import Path

TEST_DIR = Path(__file__).resolve().parent
SRC_DIR = TEST_DIR.parent / "src"
sys.path.insert(0, str(SRC_DIR))

from profile_merge_policy import (  # noqa: E402
    apply_merge_policy,
    confirm_profile_field,
    detect_corrections,
    update_profile_meta,
    ProfileMergeDecision,
)


class ProfileMergePolicyTest(unittest.TestCase):
    def test_low_confidence_patch_does_not_override_high_confidence_existing(self):
        existing = {"current_score": 430}
        existing_meta = {"current_score": {"confidence": 0.95, "source": "explicit_user", "confirmed": False}}
        merged, decisions, warnings = apply_merge_policy(
            existing, {"current_score": 400}, {"current_score": 0.3},
            existing_meta=existing_meta,
        )
        self.assertEqual(merged.get("current_score"), 430)

    def test_explicit_correction_overrides_high_confidence_existing(self):
        existing = {"current_score": 430}
        existing_meta = {"current_score": {"confidence": 0.95, "source": "explicit_user", "confirmed": True}}
        corrections = [{"field": "current_score", "corrected_to": "460", "marker": "不是430,是460"}]
        merged, decisions, warnings = apply_merge_policy(
            existing, {"current_score": 460}, {"current_score": 0.95},
            existing_meta=existing_meta, corrections=corrections,
        )
        self.assertEqual(merged.get("current_score"), 460)

    def test_same_value_refreshes_confidence_and_evidence(self):
        existing = {"subject_type": "physics"}
        existing_meta = {"subject_type": {"confidence": 0.9, "source": "inferred", "confirmed": False}}
        merged, decisions, warnings = apply_merge_policy(
            existing, {"subject_type": "physics"}, {"subject_type": 0.95},
            existing_meta=existing_meta,
        )
        self.assertEqual(merged.get("subject_type"), "physics")
        self.assertTrue(any(d.action == "keep" for d in decisions))

    def test_conflicting_subject_type_without_correction_needs_confirmation(self):
        existing = {"subject_type": "physics"}
        existing_meta = {"subject_type": {"confidence": 0.9, "source": "explicit_user", "confirmed": False}}
        merged, decisions, warnings = apply_merge_policy(
            existing, {"subject_type": "history"}, {"subject_type": 0.9},
            existing_meta=existing_meta,
        )
        self.assertEqual(merged.get("subject_type"), "physics")
        self.assertTrue(any(d.action == "needs_confirmation" for d in decisions))
        self.assertTrue(any("conflict" in w for w in warnings))

    def test_conflicting_score_without_correction_keeps_existing(self):
        existing = {"current_score": 430}
        existing_meta = {"current_score": {"confidence": 0.95, "source": "explicit_user", "confirmed": False}}
        merged, decisions, warnings = apply_merge_policy(
            existing, {"current_score": 500}, {"current_score": 0.95},
            existing_meta=existing_meta,
        )
        self.assertEqual(merged.get("current_score"), 430)
        self.assertTrue(any(d.action == "needs_confirmation" for d in decisions))

    def test_correction_marker_score_override(self):
        corrections = detect_corrections("不是430,是460")
        self.assertTrue(any(c["field"] == "current_score" for c in corrections))
        self.assertTrue(any(c["corrected_to"] == "460" for c in corrections))

    def test_correction_marker_subject_type_override(self):
        corrections = detect_corrections("不是物理类的，是历史类的")
        self.assertTrue(any(c["field"] == "subject_type" and c["corrected_to"] == "历史类" for c in corrections))

    def test_correction_marker_identity_type_override(self):
        corrections = detect_corrections("刚才说错了，是孩子类的")
        self.assertTrue(any(c["field"] == "identity_type" for c in corrections))

    def test_confirmed_field_not_overwritten_by_inferred_value(self):
        existing = {"current_score": 430}
        existing_meta = {"current_score": {"confidence": 0.95, "source": "sales", "confirmed": True}}
        merged, decisions, warnings = apply_merge_policy(
            existing, {"current_score": 460}, {"current_score": 0.85},
            existing_meta=existing_meta, source="inferred",
        )
        self.assertEqual(merged.get("current_score"), 430)

    def test_sales_source_can_confirm_field(self):
        meta = {"current_score": {"confidence": 0.9, "source": "inferred", "confirmed": False}}
        result = confirm_profile_field(meta, "current_score", source="sales")
        self.assertTrue(result["current_score"]["confirmed"])
        self.assertEqual(result["current_score"]["source"], "sales")

    def test_profile_meta_persists_confidence(self):
        decisions = [
            ProfileMergeDecision(field="current_score", action="set", new_value=430, new_confidence=0.95),
        ]
        meta = update_profile_meta({}, {"current_score": 430}, {"current_score": 0.95}, decisions)
        self.assertIn("current_score", meta)
        self.assertAlmostEqual(meta["current_score"]["confidence"], 0.95)

    def test_merge_decisions_returned(self):
        existing = {"current_score": 430}
        merged, decisions, warnings = apply_merge_policy(
            existing, {"current_score": 430}, {"current_score": 0.95},
        )
        self.assertGreater(len(decisions), 0)
        self.assertTrue(any(d.field == "current_score" for d in decisions))

    def test_profile_merge_warnings_sync(self):
        existing = {"subject_type": "physics"}
        existing_meta = {"subject_type": {"confidence": 0.95, "source": "explicit_user", "confirmed": False}}
        merged, decisions, warnings = apply_merge_policy(
            existing, {"subject_type": "history"}, {"subject_type": 0.95},
            existing_meta=existing_meta,
        )
        self.assertGreater(len(warnings), 0)

    def test_correction_detection_basic(self):
        corrections = detect_corrections("不对，是理科的")
        self.assertGreater(len(corrections), 0)
        self.assertTrue(any(c["field"] in ("subject_type", "identity_type") for c in corrections))


if __name__ == "__main__":
    unittest.main()
