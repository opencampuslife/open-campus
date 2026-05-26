from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SERVICE_SRC = ROOT / "services" / "crm-service" / "src"
sys.path.insert(0, str(SERVICE_SRC))

from leads import (  # noqa: E402
    LeadStatus,
    VALID_TRANSITIONS,
    add_followup_to_lead,
    assign_lead,
    list_leads,
    load_lead,
    score_lead,
    update_lead_status,
    upsert_lead,
    _visible_to,
    _hash_phone,
)


class LeadScoringTest(unittest.TestCase):
    def test_high_score_price_and_signup(self) -> None:
        result = score_lead(
            messages=["学费多少钱？怎么报名？我想预约到校看看"],
            intent="pricing_consulting",
            profile={"current_score": 430, "target_school_level": "一本", "weak_subjects": "数学"},
        )
        self.assertGreaterEqual(result["score"], 70)
        self.assertEqual(result["intent_level"], "high")

    def test_medium_score_with_profile(self) -> None:
        result = score_lead(
            messages=["孩子430分，物理类，想了解一下全日制班型"],
            intent="class_recommendation",
            profile={"current_score": 430, "subject_type": "物理类"},
        )
        self.assertGreaterEqual(result["score"], 40)
        self.assertLess(result["score"], 70)
        self.assertEqual(result["intent_level"], "medium")

    def test_low_score_for_generic_intro(self) -> None:
        result = score_lead(
            messages=["你们学校怎么样？有什么专业？"],
            intent="general_query",
        )
        self.assertLess(result["score"], 40)
        self.assertEqual(result["intent_level"], "low")

    def test_no_interest_penalty(self) -> None:
        result = score_lead(
            messages=["我不需要了，再看看别的，不考虑"],
            intent="general_query",
        )
        self.assertLessEqual(result["score"], 10)

    def test_request_transfer_human(self) -> None:
        result = score_lead(
            messages=["太复杂了，能不能让顾问给我打电话联系我"],
            intent="class_recommendation",
        )
        self.assertGreaterEqual(result["score"], 45)

    def test_score_has_reasons(self) -> None:
        result = score_lead(
            messages=["430分想报名全日制，学费多少钱？加我微信"],
            intent="pricing_consulting",
        )
        self.assertIn("reasons", result)
        self.assertGreaterEqual(len(result["reasons"]), 3)

    def test_intent_bonus(self) -> None:
        base = score_lead(messages=["430分"], intent="general_query")
        boosted = score_lead(messages=["430分"], intent="pricing_consulting")
        self.assertGreaterEqual(boosted["score"], base["score"])


class LeadCRUDTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.project_root = Path(self.tmp_dir.name)

    def tearDown(self) -> None:
        self.tmp_dir.cleanup()

    def test_upsert_creates_new_lead(self) -> None:
        lead = upsert_lead(
            self.project_root,
            session_id="s_test_001",
            identity={"user_id": "u_parent", "role": "parent", "campus": "zhengzhou"},
            message="孩子430分想报名",
            intent="class_recommendation",
            profile={"current_score": 430},
            campus_id="zhengzhou",
        )
        self.assertEqual(lead["session_id"], "s_test_001")
        self.assertEqual(lead["status"], LeadStatus.NEW.value)
        self.assertGreaterEqual(lead["score"], 40)
        self.assertIn("intent_level", lead)
        self.assertIn("events", lead)
        self.assertEqual(len(lead["events"]), 1)
        self.assertEqual(lead["events"][0]["event_type"], "created")

    def test_upsert_updates_existing_lead(self) -> None:
        lead1 = upsert_lead(
            self.project_root,
            session_id="s_test_002",
            identity={"user_id": "u_parent", "role": "parent", "campus": "zhengzhou"},
            message="你们有什么班型？",
            intent="general_query",
        )
        score1 = lead1["score"]

        lead2 = upsert_lead(
            self.project_root,
            session_id="s_test_002",
            identity={"user_id": "u_parent", "role": "parent", "campus": "zhengzhou"},
            message="430分想报名，学费多少？",
            intent="pricing_consulting",
            profile={"current_score": 430},
        )
        self.assertEqual(lead2["lead_id"], lead1["lead_id"])
        self.assertNotEqual(lead2["score"], score1)
        self.assertEqual(lead2["session_id"], "s_test_002")

    def test_assign_lead(self) -> None:
        lead = upsert_lead(
            self.project_root,
            session_id="s_test_003",
            identity={"user_id": "u_parent", "role": "parent", "campus": "zhengzhou"},
            message="想预约到校",
            intent="class_recommendation",
        )
        result = assign_lead(self.project_root, lead["lead_id"], "sales_001",
                             {"user_id": "campus_admin", "role": "campus_admin"})
        self.assertEqual(result["assigned_consultant_id"], "sales_001")
        self.assertEqual(result["status"], LeadStatus.ASSIGNED.value)
        self.assertIn("assigned_at", result)

        reloaded = load_lead(self.project_root, lead["lead_id"])
        self.assertEqual(reloaded["assigned_consultant_id"], "sales_001")

    def test_update_lead_status_valid_transition(self) -> None:
        lead = upsert_lead(
            self.project_root,
            session_id="s_test_004",
            identity={"user_id": "u_parent", "role": "parent", "campus": "zhengzhou"},
            message="想报名",
            intent="class_recommendation",
        )
        lead = assign_lead(self.project_root, lead["lead_id"], "sales_001",
                           {"user_id": "campus_admin", "role": "campus_admin"})
        self.assertEqual(lead["status"], LeadStatus.ASSIGNED.value)

        result = update_lead_status(self.project_root, lead["lead_id"], LeadStatus.CONTACTED.value,
                                     {"user_id": "sales_001", "role": "sales"})
        self.assertEqual(result["status"], LeadStatus.CONTACTED.value)

        reloaded = load_lead(self.project_root, lead["lead_id"])
        self.assertEqual(reloaded["status"], LeadStatus.CONTACTED.value)

    def test_invalid_status_transition_rejected(self) -> None:
        lead = upsert_lead(
            self.project_root,
            session_id="s_test_005",
            identity={"user_id": "u_parent", "role": "parent", "campus": "zhengzhou"},
            message="想报名",
            intent="class_recommendation",
        )
        with self.assertRaisesRegex(ValueError, "Invalid status transition"):
            update_lead_status(self.project_root, lead["lead_id"], LeadStatus.ENROLLED.value,
                               {"user_id": "sales_001", "role": "sales"})

    def test_add_followup_to_lead(self) -> None:
        lead = upsert_lead(
            self.project_root,
            session_id="s_test_006",
            identity={"user_id": "u_parent", "role": "parent", "campus": "zhengzhou"},
            message="想报名",
            intent="class_recommendation",
        )
        result = add_followup_to_lead(
            self.project_root, lead["lead_id"],
            consultant_id="sales_001",
            note="已电话沟通，家长意向明确",
            followup_type="call",
            next_followup_at="2026-05-30T10:00:00",
            identity={"user_id": "sales_001", "role": "sales"},
        )
        self.assertIn("followup", result)
        self.assertEqual(result["followup"]["note"], "已电话沟通，家长意向明确")
        self.assertEqual(result["followup"]["followup_type"], "call")

        reloaded = load_lead(self.project_root, lead["lead_id"])
        self.assertEqual(len(reloaded["followups"]), 1)
        self.assertEqual(reloaded["next_followup_at"], "2026-05-30T10:00:00")

    def test_phone_is_hashed(self) -> None:
        phone = "13800138000"
        h = _hash_phone(phone)
        self.assertNotEqual(h, phone)
        self.assertEqual(len(h), 16)

        lead = upsert_lead(
            self.project_root,
            session_id="s_test_007",
            identity={"user_id": "u_parent", "role": "parent", "campus": "zhengzhou"},
            message="想报名",
            intent="class_recommendation",
            phone=phone,
        )
        self.assertNotEqual(lead.get("parent_phone_hash", ""), phone)
        self.assertEqual(lead["parent_phone_hash"], h)

    def test_lead_events_recorded(self) -> None:
        lead = upsert_lead(
            self.project_root,
            session_id="s_test_events",
            identity={"user_id": "u_parent", "role": "parent", "campus": "zhengzhou"},
            message="430分想报名",
            intent="class_recommendation",
        )
        lead = assign_lead(self.project_root, lead["lead_id"], "sales_001",
                           {"user_id": "campus_admin", "role": "campus_admin"})
        lead = update_lead_status(self.project_root, lead["lead_id"], LeadStatus.CONTACTED.value,
                                   {"user_id": "sales_001", "role": "sales"})
        add_followup_to_lead(
            self.project_root, lead["lead_id"],
            consultant_id="sales_001",
            note="已沟通",
            followup_type="call",
        )

        reloaded = load_lead(self.project_root, lead["lead_id"])
        event_types = [e["event_type"] for e in reloaded["events"]]
        self.assertIn("created", event_types)
        self.assertIn("assigned", event_types)
        self.assertIn("status_changed", event_types)
        self.assertIn("followup_added", event_types)


class LeadPermissionTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.project_root = Path(self.tmp_dir.name)

    def tearDown(self) -> None:
        self.tmp_dir.cleanup()

    def test_admin_visible_all(self) -> None:
        lead = upsert_lead(
            self.project_root,
            session_id="s_perm_001",
            identity={"user_id": "u_parent", "role": "parent", "campus": "beijing"},
            message="想报名",
            intent="class_recommendation",
            campus_id="beijing",
        )
        self.assertTrue(_visible_to(lead, {"user_id": "admin", "role": "admin", "campus": "zhengzhou"}))

    def test_campus_admin_visible_own_campus(self) -> None:
        lead = upsert_lead(
            self.project_root,
            session_id="s_perm_002",
            identity={"user_id": "u_parent", "role": "parent", "campus": "zhengzhou"},
            message="想报名",
            intent="class_recommendation",
            campus_id="zhengzhou",
        )
        self.assertTrue(_visible_to(lead, {"user_id": "ca", "role": "campus_admin", "campus": "zhengzhou"}))
        self.assertFalse(_visible_to(lead, {"user_id": "ca", "role": "campus_admin", "campus": "beijing"}))

    def test_sales_visible_assigned_or_campus(self) -> None:
        lead = upsert_lead(
            self.project_root,
            session_id="s_perm_003",
            identity={"user_id": "u_parent", "role": "parent", "campus": "zhengzhou"},
            message="想报名",
            intent="class_recommendation",
            campus_id="zhengzhou",
        )
        assign_lead(self.project_root, lead["lead_id"], "sales_001",
                    {"user_id": "campus_admin", "role": "campus_admin"})

        self.assertTrue(_visible_to(lead, {"user_id": "sales_001", "role": "sales", "campus": "zhengzhou"}))
        self.assertTrue(_visible_to(lead, {"user_id": "sales_002", "role": "sales", "campus": "zhengzhou"}))
        self.assertFalse(_visible_to(lead, {"user_id": "sales_003", "role": "sales", "campus": "beijing"}))

    def test_parent_cannot_see_leads(self) -> None:
        self.assertFalse(_visible_to(
            {"campus_id": "zhengzhou"},
            {"user_id": "u_parent", "role": "parent", "campus": "zhengzhou"},
        ))

    def test_list_leads_filters_by_role(self) -> None:
        upsert_lead(
            self.project_root,
            session_id="s_perm_a",
            identity={"user_id": "u_1", "role": "parent", "campus": "zhengzhou"},
            message="A",
            intent="class_recommendation",
            campus_id="zhengzhou",
        )
        upsert_lead(
            self.project_root,
            session_id="s_perm_b",
            identity={"user_id": "u_2", "role": "parent", "campus": "beijing"},
            message="B",
            intent="pricing_consulting",
            campus_id="beijing",
        )

        all_leads = list_leads(self.project_root, {"user_id": "admin", "role": "admin"})
        self.assertEqual(len(all_leads), 2)

        zh_leads = list_leads(self.project_root, {"user_id": "s1", "role": "sales", "campus": "zhengzhou"})
        self.assertEqual(len(zh_leads), 1)
        self.assertEqual(zh_leads[0]["campus_id"], "zhengzhou")

    def test_parent_cannot_access_crm_api_via_list_leads(self) -> None:
        upsert_lead(
            self.project_root,
            session_id="s_no_parent",
            identity={"user_id": "u_parent", "role": "parent", "campus": "zhengzhou"},
            message="想报名",
            intent="class_recommendation",
            campus_id="zhengzhou",
        )
        with self.assertRaisesRegex(ValueError, "CRM access denied"):
            list_leads(self.project_root, {"user_id": "u_parent", "role": "parent", "campus": "zhengzhou"})


class LeadStatusTransitionTest(unittest.TestCase):
    def test_new_can_go_to_assigned(self) -> None:
        self.assertIn(LeadStatus.ASSIGNED, VALID_TRANSITIONS[LeadStatus.NEW])

    def test_new_cannot_go_to_enrolled(self) -> None:
        self.assertNotIn(LeadStatus.ENROLLED, VALID_TRANSITIONS[LeadStatus.NEW])

    def test_assigned_can_go_to_contacted(self) -> None:
        self.assertIn(LeadStatus.CONTACTED, VALID_TRANSITIONS[LeadStatus.ASSIGNED])

    def test_feasible_chain(self) -> None:
        chain = [LeadStatus.NEW, LeadStatus.ASSIGNED, LeadStatus.CONTACTED,
                 LeadStatus.ASSESSMENT_BOOKED, LeadStatus.VISIT_BOOKED, LeadStatus.ENROLLED]
        for i in range(len(chain) - 1):
            self.assertIn(chain[i + 1], VALID_TRANSITIONS[chain[i]],
                          f"Invalid transition {chain[i]} -> {chain[i + 1]}")


if __name__ == "__main__":
    unittest.main()
