from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
ADMIN_SRC = ROOT / "services" / "api-gateway" / "src"
sys.path.insert(0, str(ADMIN_SRC))

from event_schema import AuditEvent, EventType, make_event
from audit_store import write_audit_event, query_audit_events, query_by_trace, query_by_session, get_event_by_id
from admin_gateway import _filter_events_by_role, _filter_by_visibility


class AuditEventSchemaTest(unittest.TestCase):
    def test_make_event_populates_all_fields(self):
        ev = make_event(
            EventType.CHAT_RECEIVED,
            trace_id="t1", request_id="r1", session_id="s1", lead_id="l1",
            user_id="u1", role="parent", campus="zhengzhou", entrypoint="public_chat",
            status="ok", latency_ms=42,
        )
        self.assertTrue(ev.event_id)
        self.assertEqual(ev.event_type, EventType.CHAT_RECEIVED)
        self.assertEqual(ev.trace_id, "t1")
        self.assertEqual(ev.session_id, "s1")
        self.assertEqual(ev.lead_id, "l1")
        self.assertEqual(ev.status, "ok")
        self.assertEqual(ev.latency_ms, 42)

    def test_to_dict_redacts_sensitive_metadata(self):
        ev = make_event(EventType.CHAT_RECEIVED, metadata={"phone": "13800138000", "name": "test"})
        d = ev.to_dict()
        self.assertEqual(d["metadata"].get("phone"), "[REDACTED]")
        self.assertEqual(d["metadata"].get("name"), "test")

    def test_to_dict_redacts_nested_sensitive(self):
        ev = make_event(EventType.CHAT_RECEIVED, metadata={"profile": {"phone": "138", "age": 18}})
        d = ev.to_dict()
        self.assertEqual(d["metadata"]["profile"].get("phone"), "[REDACTED]")
        self.assertEqual(d["metadata"]["profile"].get("age"), 18)


class AuditEventStoreTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.audit_dir = self.root / "data" / "audit" / "events"
        self.audit_dir.mkdir(parents=True, exist_ok=True)

    def tearDown(self):
        self._tmp.cleanup()

    def test_write_and_query_by_event_id(self):
        ev = make_event(EventType.CHAT_RECEIVED, trace_id="t100", session_id="s100",
                        user_id="u1", role="parent")
        eid = write_audit_event(self.root, ev)
        self.assertTrue(eid)

        result = query_audit_events(self.root, event_id=eid)
        self.assertEqual(len(result["events"]), 1)
        self.assertEqual(result["events"][0]["trace_id"], "t100")

    def test_query_by_trace_id(self):
        for i in range(3):
            ev = make_event(EventType.CHAT_RECEIVED, trace_id="trace_abc", session_id=f"s{i}")
            write_audit_event(self.root, ev)
        ev = make_event(EventType.CHAT_RECEIVED, trace_id="other_trace")
        write_audit_event(self.root, ev)

        result = query_by_trace(self.root, "trace_abc")
        self.assertEqual(len(result["events"]), 3)

    def test_query_by_session_id(self):
        write_audit_event(self.root, make_event(EventType.CHAT_RECEIVED, trace_id="t1", session_id="sess_a"))
        write_audit_event(self.root, make_event(EventType.CHAT_ANSWERED, trace_id="t2", session_id="sess_a"))
        write_audit_event(self.root, make_event(EventType.CHAT_RECEIVED, trace_id="t3", session_id="sess_b"))

        result = query_by_session(self.root, "sess_a")
        self.assertEqual(len(result["events"]), 2)

    def test_query_by_lead_id(self):
        write_audit_event(self.root, make_event(EventType.LEAD_UPDATED, lead_id="lead_x"))
        write_audit_event(self.root, make_event(EventType.HANDOFF_REQUESTED, lead_id="lead_x"))
        write_audit_event(self.root, make_event(EventType.LEAD_UPDATED, lead_id="lead_y"))

        result = query_audit_events(self.root, lead_id="lead_x")
        self.assertEqual(len(result["events"]), 2)

    def test_query_by_event_type(self):
        write_audit_event(self.root, make_event(EventType.CHAT_RECEIVED))
        write_audit_event(self.root, make_event(EventType.CHAT_ANSWERED))
        write_audit_event(self.root, make_event(EventType.SECURITY_CSRF_BLOCKED))

        result = query_audit_events(self.root, event_type=EventType.SECURITY_CSRF_BLOCKED)
        self.assertEqual(len(result["events"]), 1)

    def test_query_by_status(self):
        write_audit_event(self.root, make_event(EventType.CHAT_RECEIVED, status="ok"))
        write_audit_event(self.root, make_event(EventType.CHAT_RECEIVED, status="blocked"))

        result = query_audit_events(self.root, status="blocked")
        self.assertEqual(len(result["events"]), 1)

    def test_query_limit_offset(self):
        for _ in range(10):
            write_audit_event(self.root, make_event(EventType.CHAT_RECEIVED))

        result = query_audit_events(self.root, limit=3, offset=0)
        self.assertEqual(len(result["events"]), 3)
        self.assertGreaterEqual(result["total"], 3)

        result2 = query_audit_events(self.root, limit=3, offset=3)
        self.assertEqual(len(result2["events"]), 3)

    def test_get_event_by_id_not_found(self):
        result = get_event_by_id(self.root, "nonexistent")
        self.assertIsNone(result)

    def test_since_until_filter(self):
        write_audit_event(self.root, AuditEvent(
            event_id="e1", timestamp="2026-01-01T00:00:00+00:00",
            event_type=EventType.CHAT_RECEIVED,
        ))
        write_audit_event(self.root, AuditEvent(
            event_id="e2", timestamp="2026-06-01T00:00:00+00:00",
            event_type=EventType.CHAT_RECEIVED,
        ))

        result = query_audit_events(self.root, since="2026-03-01")
        self.assertEqual(len(result["events"]), 1)
        self.assertEqual(result["events"][0]["event_id"], "e2")


class AuditRoleVisibilityTest(unittest.TestCase):
    def test_admin_sees_all_events(self):
        events = [
            {"event_type": EventType.CHAT_RECEIVED, "campus": "zhengzhou"},
            {"event_type": EventType.SECURITY_CSRF_BLOCKED, "campus": "beijing"},
            {"event_type": EventType.ADMIN_DOC_PUBLISHED, "campus": "all"},
        ]
        filtered = _filter_events_by_role(events, {"role": "admin", "campus": "zhengzhou"})
        self.assertEqual(len(filtered), 3)

    def test_campus_admin_sees_same_campus(self):
        events = [
            {"event_type": EventType.CHAT_RECEIVED, "campus": "zhengzhou"},
            {"event_type": EventType.CHAT_RECEIVED, "campus": "beijing"},
        ]
        filtered = _filter_events_by_role(events, {"role": "campus_admin", "campus": "zhengzhou"})
        self.assertEqual(len(filtered), 1)
        self.assertEqual(filtered[0]["campus"], "zhengzhou")

    def test_sales_sees_only_sales_events(self):
        events = [
            {"event_type": EventType.CHAT_RECEIVED, "campus": "all"},
            {"event_type": EventType.ADMIN_DOC_PUBLISHED, "campus": "all"},
            {"event_type": EventType.LEAD_UPDATED, "campus": "all"},
            {"event_type": EventType.SECURITY_CSRF_BLOCKED, "campus": "all"},
        ]
        filtered = _filter_events_by_role(events, {"role": "sales", "campus": "all"})
        event_types = {e["event_type"] for e in filtered}
        self.assertIn(EventType.CHAT_RECEIVED, event_types)
        self.assertIn(EventType.LEAD_UPDATED, event_types)
        self.assertNotIn(EventType.SECURITY_CSRF_BLOCKED, event_types)
        self.assertNotIn(EventType.ADMIN_DOC_PUBLISHED, event_types)

    def test_content_operator_sees_knowledge_events(self):
        events = [
            {"event_type": EventType.ADMIN_DOC_PUBLISHED, "campus": "all"},
            {"event_type": EventType.CHAT_RECEIVED, "campus": "all"},
        ]
        filtered = _filter_events_by_role(events, {"role": "content_operator", "campus": "all"})
        self.assertEqual(len(filtered), 1)
        self.assertEqual(filtered[0]["event_type"], EventType.ADMIN_DOC_PUBLISHED)

    def test_reviewer_sees_approved_published(self):
        events = [
            {"event_type": EventType.ADMIN_DOC_PUBLISHED, "campus": "all"},
            {"event_type": EventType.CHAT_RECEIVED, "campus": "all"},
        ]
        filtered = _filter_events_by_role(events, {"role": "reviewer", "campus": "all"})
        self.assertEqual(len(filtered), 1)

    def test_visitor_sees_nothing(self):
        events = [
            {"event_type": EventType.CHAT_RECEIVED, "campus": "all"},
        ]
        filtered = _filter_events_by_role(events, {"role": "visitor", "campus": "all"})
        self.assertEqual(len(filtered), 0)

    def test_filter_by_visibility_raises_for_unauthorized_type(self):
        with self.assertRaises(ValueError):
            _filter_by_visibility(
                {"event_type": EventType.ADMIN_DOC_PUBLISHED, "campus": "all"},
                {"role": "sales", "campus": "all"},
            )

    def test_filter_by_visibility_raises_for_wrong_campus(self):
        with self.assertRaises(ValueError):
            _filter_by_visibility(
                {"event_type": EventType.CHAT_RECEIVED, "campus": "beijing"},
                {"role": "campus_admin", "campus": "zhengzhou"},
            )

    def test_admin_can_access_all_campuses(self):
        try:
            _filter_by_visibility(
                {"event_type": EventType.CHAT_RECEIVED, "campus": "beijing"},
                {"role": "admin", "campus": "zhengzhou"},
            )
        except ValueError:
            self.fail("admin should access all campuses")

    def test_all_campus_visible_to_campus_admin(self):
        try:
            _filter_by_visibility(
                {"event_type": EventType.CHAT_RECEIVED, "campus": "all"},
                {"role": "campus_admin", "campus": "zhengzhou"},
            )
        except ValueError:
            self.fail("campus_admin should access events with campus='all'")


if __name__ == "__main__":
    unittest.main()
