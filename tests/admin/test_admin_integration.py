from __future__ import annotations

import json
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[2]
ADMIN_SRC = ROOT / "services" / "api-gateway" / "src"
KNOWLEDGE_SRC = ROOT / "services" / "knowledge-service" / "src"
import sys
sys.path.extend([str(ADMIN_SRC), str(KNOWLEDGE_SRC)])

from admin_gateway import admin_health, admin_list_sources
from admin_policy import Action, require_action_str
from bff_gateway import post_chat
from indexer import build_index


class AdminIntegrationTest(unittest.TestCase):
    def setUp(self):
        self.admin_identity = {"user_id": "u_admin", "role": "admin", "campus": "all", "auth_level": "admin"}
        self.sales_identity = {"user_id": "u_sales", "role": "sales", "campus": "zhengzhou", "auth_level": "staff"}
        self.parent_identity = {"user_id": "u_parent", "role": "parent", "campus": "zhengzhou", "auth_level": "phone_verified"}
        self.tmp_root = Path(__file__).resolve().parents[3] / "data"

    def test_admin_health_accessible(self):
        result = admin_health(self.admin_identity, ROOT)
        self.assertIn("status", result)
        self.assertEqual(result["status"], "ok")

    def test_non_admin_cannot_list_sources(self):
        with self.assertRaises(ValueError):
            require_action_str(self.sales_identity, Action.STAGING_READ)

    def test_admin_list_sources_accessible_by_admin(self):
        result = admin_list_sources(self.admin_identity, ROOT)
        self.assertIn("sources", result)

    def test_gaokao_chat_still_works(self):
        build_index(ROOT)
        result = post_chat(
            {"session_id": "test_admin_int", "message": "你好"},
            self.parent_identity,
            ROOT,
        )
        self.assertIn("answer", result)
        self.assertIn("session_id", result)

    def test_staging_dir_created(self):
        staging = ROOT / "data" / "staging"
        staging.mkdir(parents=True, exist_ok=True)
        self.assertTrue(staging.exists())


if __name__ == "__main__":
    unittest.main()
