from __future__ import annotations

import json
import os
import sys
import time
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
AGENT_SRC = ROOT / "services" / "agent-orchestrator" / "src"
API_SRC = ROOT / "services" / "api-gateway" / "src"
sys.path.extend([str(AGENT_SRC), str(API_SRC)])


class DangerousActionConfirmationTest(unittest.TestCase):
    def setUp(self):
        from admin_policy import Action, DANGEROUS_ACTION_CONFIRMATIONS
        self.Action = Action
        self.confirmations = DANGEROUS_ACTION_CONFIRMATIONS

    def test_all_dangerous_actions_have_confirmation_phrase(self):
        from admin_policy import is_dangerous_action, get_confirmation_phrase
        dangerous = [k for k, v in self.confirmations.items()]
        for action in dangerous:
            self.assertTrue(is_dangerous_action(action),
                           f"is_dangerous_action should be True for {action}")
            phrase = get_confirmation_phrase(action)
            self.assertIsNotNone(phrase, f"Confirmation phrase missing for {action}")
            self.assertGreater(len(phrase), 0, f"Confirmation phrase empty for {action}")

    def test_valid_publish_confirmation_passes(self):
        from admin_policy import validate_confirmation
        self.assertIsNone(validate_confirmation(self.Action.STAGING_PUBLISH, "PUBLISH"))

    def test_invalid_publish_confirmation_fails(self):
        from admin_policy import validate_confirmation
        err = validate_confirmation(self.Action.STAGING_PUBLISH, "approve")
        self.assertIsNotNone(err)
        self.assertIn("PUBLISH", err)

    def test_empty_confirmation_fails(self):
        from admin_policy import validate_confirmation
        err = validate_confirmation(self.Action.STAGING_PUBLISH, "")
        self.assertIsNotNone(err)

    def test_case_insensitive_confirmation_passes(self):
        from admin_policy import validate_confirmation
        self.assertIsNone(validate_confirmation(self.Action.STAGING_PUBLISH, "publish "))

    def test_non_dangerous_action_does_not_require_confirmation(self):
        from admin_policy import validate_confirmation, is_dangerous_action
        self.assertFalse(is_dangerous_action(self.Action.HEALTH_READ))
        self.assertIsNone(validate_confirmation(self.Action.HEALTH_READ, "whatever"))

    def test_enable_remote_url_ingestion_requires_confirmation(self):
        from admin_policy import validate_confirmation, Action as A
        self.assertTrue(A.INGESTION_ENABLE_REMOTE in self.confirmations)
        err = validate_confirmation(A.INGESTION_ENABLE_REMOTE, "wrong")
        self.assertIsNotNone(err)

    def test_change_permission_fields_requires_confirmation(self):
        from admin_policy import validate_confirmation, Action as A
        self.assertTrue(A.STAGING_EDIT_PERMISSION in self.confirmations)
        err = validate_confirmation(A.STAGING_EDIT_PERMISSION, "wrong")
        self.assertIsNotNone(err)

    def test_assign_admin_requires_confirmation(self):
        from admin_policy import validate_confirmation, Action as A
        self.assertTrue(A.ASSIGN_ADMIN in self.confirmations)
        err = validate_confirmation(A.ASSIGN_ADMIN, "wrong")
        self.assertIsNotNone(err)


class AdminSessionExpiryTest(unittest.TestCase):
    def setUp(self):
        from admin_policy import _session_store, invalidate_admin_session
        _session_store.clear()
        self.uid = "admin_test_user"

    def tearDown(self):
        from admin_policy import invalidate_admin_session
        invalidate_admin_session(self.uid)

    def test_session_ok_when_active(self):
        from admin_policy import record_admin_session_activity, check_admin_session
        record_admin_session_activity(self.uid)
        err = check_admin_session(self.uid)
        self.assertIsNone(err)

    @patch.dict(os.environ, {"ADMIN_SESSION_TTL_SECONDS": "1", "ADMIN_IDLE_TIMEOUT_SECONDS": "1"})
    def test_session_expired_after_ttl(self):
        from admin_policy import record_admin_session_activity, check_admin_session, _session_store
        record_admin_session_activity(self.uid)
        _session_store[self.uid]["created_at"] = time.time() - 10
        err = check_admin_session(self.uid)
        self.assertIsNotNone(err)

    @patch.dict(os.environ, {"ADMIN_SESSION_TTL_SECONDS": "3600", "ADMIN_IDLE_TIMEOUT_SECONDS": "1"})
    def test_session_expired_after_idle(self):
        from admin_policy import record_admin_session_activity, check_admin_session, _session_store
        record_admin_session_activity(self.uid)
        _session_store[self.uid]["last_active"] = time.time() - 10
        err = check_admin_session(self.uid)
        self.assertIsNotNone(err)

    def test_invalidate_session_removes_it(self):
        from admin_policy import record_admin_session_activity, check_admin_session, invalidate_admin_session
        record_admin_session_activity(self.uid)
        invalidate_admin_session(self.uid)
        err = check_admin_session(self.uid)
        self.assertIsNone(err)


class TrustedProxyTest(unittest.TestCase):
    def setUp(self):
        os.environ["TRUSTED_PROXY_TOKEN"] = "test-token-32chars-minimum"
        from admin_policy import validate_trusted_proxy
        self.validate = validate_trusted_proxy

    def tearDown(self):
        os.environ.pop("TRUSTED_PROXY_TOKEN", None)

    def test_trusted_proxy_accepted(self):
        err = self.validate({
            "x-gaokao-user-id": "u_admin",
            "x-gaokao-role": "admin",
            "x-gaokao-trusted-proxy": "test-token-32chars-minimum",
        })
        self.assertIsNone(err, f"Trusted proxy should be accepted: {err}")

    def test_untrusted_proxy_with_identity_headers_rejected(self):
        err = self.validate({
            "x-gaokao-user-id": "u_admin",
            "x-gaokao-role": "admin",
            "x-gaokao-trusted-proxy": "wrong-token",
        })
        self.assertIsNotNone(err)

    def test_missing_trusted_proxy_with_identity_headers_rejected(self):
        err = self.validate({
            "x-gaokao-user-id": "u_admin",
            "x-gaokao-role": "admin",
        })
        self.assertIsNotNone(err)

    def test_no_identity_headers_no_trust_check(self):
        err = self.validate({
            "user-agent": "test",
        })
        self.assertIsNone(err)

    def test_case_insensitive_header_names(self):
        err = self.validate({
            "X-GAOKAO-USER-ID": "u_admin",
            "X-Gaokao-Role": "admin",
            "X-Gaokao-Trusted-Proxy": "test-token-32chars-minimum",
        })
        self.assertIsNone(err)


class DocsAndChecklistTest(unittest.TestCase):
    D = ROOT / "docs"

    def test_trusted_proxy_doc_exists(self):
        self.assertTrue((self.D / "TRUSTED_PROXY_IDENTITY_HEADERS.md").is_file())

    def test_production_admin_checklist_exists(self):
        self.assertTrue((self.D / "PRODUCTION_ADMIN_CHECKLIST.md").is_file())


class AdminPolicyIntegrationTest(unittest.TestCase):
    def test_all_dangerous_actions_are_role_gated(self):
        from admin_policy import DANGEROUS_ACTION_CONFIRMATIONS, ACTION_ROLES, ROLE_ADMIN
        for action in DANGEROUS_ACTION_CONFIRMATIONS:
            allowed = ACTION_ROLES.get(action, set())
            self.assertIn(ROLE_ADMIN, allowed,
                         f"Dangerous action {action} should allow ROLE_ADMIN")

    def test_non_admin_cannot_do_dangerous_actions(self):
        from admin_policy import AdminContext, Action, require_action_str
        for role in ("sales", "content_operator", "reviewer"):
            identity = {"user_id": f"u_{role}", "role": role, "campus": "all"}
            for action in (Action.STAGING_PUBLISH, Action.STAGING_DELETE,
                          Action.BACKUP_RESTORE, Action.ASSIGN_ADMIN):
                with self.assertRaises(ValueError, msg=f"Role {role} should not do {action}"):
                    require_action_str(identity, action)


if __name__ == "__main__":
    unittest.main()
