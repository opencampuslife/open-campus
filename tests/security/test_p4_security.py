from __future__ import annotations

import json
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parents[2]
ADMIN_SRC = ROOT / "services" / "api-gateway" / "src"
INGESTION_SRC = ROOT / "services" / "source-ingestion-service" / "src"
CRM_SRC = ROOT / "services" / "crm-service" / "src"
AGENT_SRC = ROOT / "services" / "agent-orchestrator" / "src"
COMPLIANCE_SRC = ROOT / "services" / "compliance-service" / "src"
KNOWLEDGE_SRC = ROOT / "services" / "knowledge-service" / "src"
RAG_SRC = ROOT / "services" / "rag-service" / "src"
PERMISSION_SRC = ROOT / "services" / "permission-service" / "src"
LLM_SRC = ROOT / "services" / "llm-gateway" / "src"
sys.path.extend([str(AGENT_SRC), str(CRM_SRC), str(ADMIN_SRC), str(INGESTION_SRC), str(COMPLIANCE_SRC), str(KNOWLEDGE_SRC), str(RAG_SRC), str(PERMISSION_SRC), str(LLM_SRC)])

from csrf_protection import generate_csrf_token, validate_csrf_token, verify_csrf, is_admin_path
from rate_limiter import RateLimiter, check_rate_limit, DEFAULT_CHAT_LIMIT, DEFAULT_ADMIN_LIMIT
from url_validator import validate_url, _is_private_ip, _is_safe_host, _resolve_dns


class P40IdentitySourceTest(unittest.TestCase):
    def test_headers_only_in_production(self):
        os.environ["GAOKAO_ENV"] = "production"
        try:
            from server import _identity_from_headers, GaokaoHandler

            headers = {
                "x-gaokao-user-id": "admin1",
                "x-gaokao-role": "admin",
                "x-gaokao-campus": "zhengzhou",
                "x-gaokao-auth-level": "mfa",
                "x-gaokao-trusted-proxy": "internal-gateway",
            }
            identity = _identity_from_headers(headers)
            self.assertEqual(identity["user_id"], "admin1")
            self.assertEqual(identity["role"], "admin")
            self.assertEqual(identity["campus"], "zhengzhou")
            self.assertEqual(identity["auth_level"], "mfa")

            h = GaokaoHandler.__new__(GaokaoHandler)
            h.headers = {k.lower(): v for k, v in headers.items()}
            identity_prod = h._resolve_identity({"user_id": "q_user", "role": "admin", "campus": "evil", "auth_level": "low"})
            self.assertEqual(identity_prod["user_id"], "admin1")
            self.assertEqual(identity_prod["role"], "admin")
            self.assertEqual(identity_prod["campus"], "zhengzhou")
        finally:
            os.environ.pop("GAOKAO_ENV", None)

    def test_dev_allows_query_fallback(self):
        os.environ["GAOKAO_ENV"] = "development"
        try:
            from server import GaokaoHandler
            h = GaokaoHandler.__new__(GaokaoHandler)
            h.headers = {}
            query_id = {"user_id": "q_user", "role": "sales", "campus": "beijing", "auth_level": "phone_verified"}
            identity = h._resolve_identity(query_id)
            self.assertEqual(identity["user_id"], "q_user")
            self.assertEqual(identity["role"], "sales")
            self.assertEqual(identity["campus"], "beijing")
        finally:
            os.environ.pop("GAOKAO_ENV", None)

    def test_headers_override_query_in_dev(self):
        os.environ["GAOKAO_ENV"] = "development"
        try:
            from server import GaokaoHandler
            h = GaokaoHandler.__new__(GaokaoHandler)
            h.headers = {"x-gaokao-role": "admin", "x-gaokao-user-id": "h_user"}
            query_id = {"user_id": "q_user", "role": "visitor", "campus": "all", "auth_level": "low"}
            identity = h._resolve_identity(query_id)
            self.assertEqual(identity["user_id"], "h_user")
            self.assertEqual(identity["role"], "admin")
        finally:
            os.environ.pop("GAOKAO_ENV", None)

    def test_no_headers_returns_empty(self):
        identity = __import__("server")._identity_from_headers({})
        self.assertEqual(identity, {})


class P40CsrfProtectionTest(unittest.TestCase):
    def test_generate_and_validate_token(self):
        token = generate_csrf_token("session_abc123")
        self.assertTrue(validate_csrf_token(token, "session_abc123"))

    def test_validate_expired_token(self):
        token = generate_csrf_token("test_session")
        parts = token.split(".")
        old_ts = str(int(__import__("time").time()) - 4000)
        bad_token = old_ts + "." + parts[1] + "." + parts[2]
        self.assertFalse(validate_csrf_token(bad_token, "test_session"))

    def test_validate_wrong_session(self):
        token = generate_csrf_token("session_a")
        self.assertFalse(validate_csrf_token(token, "session_b"))

    def test_validate_invalid_format(self):
        self.assertFalse(validate_csrf_token("not-a-token", ""))
        self.assertFalse(validate_csrf_token("", ""))

    def test_generate_tokens_differ(self):
        t1 = generate_csrf_token("session_a")
        t2 = generate_csrf_token("session_a")
        self.assertNotEqual(t1, t2)

    def test_verify_csrf_with_header(self):
        token = generate_csrf_token("sess1")
        headers = {"x-csrf-token": token}
        self.assertTrue(verify_csrf(headers, "sess1"))

    def test_verify_csrf_no_header(self):
        self.assertFalse(verify_csrf({}, "sess1"))

    def test_is_admin_path(self):
        self.assertTrue(is_admin_path("/api/admin/health"))
        self.assertTrue(is_admin_path("/api/admin/staging/docs"))
        self.assertFalse(is_admin_path("/api/gaokao/chat"))
        self.assertFalse(is_admin_path("/api/sales/sessions"))

    def test_csrf_token_independent_from_session(self):
        token = generate_csrf_token()
        self.assertTrue(validate_csrf_token(token, ""))
        self.assertTrue(validate_csrf_token(token, "some_other_session_with_diff_prefix"))


class P40RateLimiterTest(unittest.TestCase):
    def setUp(self):
        self.limiter = RateLimiter()

    def test_allow_first_request(self):
        self.assertTrue(self.limiter.allow("127.0.0.1", "chat", DEFAULT_CHAT_LIMIT))

    def test_block_after_burst(self):
        for _ in range(DEFAULT_CHAT_LIMIT):
            self.limiter.allow("192.168.1.1", "chat", DEFAULT_CHAT_LIMIT)
        self.assertFalse(self.limiter.allow("192.168.1.1", "chat", DEFAULT_CHAT_LIMIT))

    def test_chat_rate_limit_check(self):
        allowed, info = check_rate_limit("10.0.0.1", "/api/gaokao/chat", "user_1")
        self.assertTrue(allowed)
        self.assertEqual(info["category"], "chat")

    def test_admin_rate_limit_check(self):
        allowed, info = check_rate_limit("10.0.0.2", "/api/admin/health", "admin_1")
        self.assertTrue(allowed)
        self.assertEqual(info["category"], "admin")

    def test_non_limited_path_passes(self):
        allowed, info = check_rate_limit("10.0.0.3", "/api/sessions", "user_1")
        self.assertTrue(allowed)
        self.assertEqual(info, {})

    def test_different_paths_independent(self):
        for _ in range(DEFAULT_CHAT_LIMIT):
            self.limiter.allow("10.10.10.10", "chat", DEFAULT_CHAT_LIMIT)
        self.assertFalse(self.limiter.allow("10.10.10.10", "chat", DEFAULT_CHAT_LIMIT))
        self.assertTrue(self.limiter.allow("10.10.10.10", "admin", DEFAULT_ADMIN_LIMIT))


class P40UrlSsrValidationTest(unittest.TestCase):
    def setUp(self):
        os.environ["ENABLE_REMOTE_URL_INGESTION"] = "1"

    def tearDown(self):
        os.environ.pop("ENABLE_REMOTE_URL_INGESTION", None)

    def test_disabled_when_flag_off(self):
        os.environ["ENABLE_REMOTE_URL_INGESTION"] = "0"
        try:
            result = validate_url("https://example.com")
            self.assertFalse(result["valid"])
            self.assertTrue(result["ssrf_blocked"])
        finally:
            os.environ["ENABLE_REMOTE_URL_INGESTION"] = "1"

    def test_private_ip_detection(self):
        self.assertTrue(_is_private_ip("127.0.0.1"))
        self.assertTrue(_is_private_ip("10.0.0.1"))
        self.assertTrue(_is_private_ip("192.168.1.1"))
        self.assertTrue(_is_private_ip("172.16.0.1"))
        self.assertTrue(_is_private_ip("169.254.1.1"))
        self.assertTrue(_is_private_ip("0.0.0.0"))
        self.assertTrue(_is_private_ip("::1"))
        self.assertTrue(_is_private_ip("fc00::1"))
        self.assertFalse(_is_private_ip("8.8.8.8"))
        self.assertFalse(_is_private_ip("1.1.1.1"))

    def test_block_localhost(self):
        result = validate_url("http://localhost:8080/admin")
        self.assertTrue(result["ssrf_blocked"] or result["warnings"])

    def test_block_loopback(self):
        result = validate_url("http://127.0.0.1:3000/data")
        self.assertTrue(result["ssrf_blocked"])

    def test_block_private_ip(self):
        result = validate_url("http://10.0.0.1/api")
        self.assertTrue(result["ssrf_blocked"])
        result2 = validate_url("http://192.168.1.100/config")
        self.assertTrue(result2.get("ssrf_blocked"))

    def test_block_file_scheme(self):
        result = validate_url("file:///etc/passwd")
        self.assertTrue(result["ssrf_blocked"])

    def test_block_gopher_scheme(self):
        result = validate_url("gopher://127.0.0.1:6379/_INFO")
        self.assertTrue(result["ssrf_blocked"])

    def test_allow_public_url(self):
        with patch("url_validator._is_safe_host", return_value=True):
            result = validate_url("https://example.com/page")
            self.assertTrue(result["valid"])
            self.assertEqual(result["normalized_url"], "https://example.com/page")

    def test_block_disallowed_hostname_chars(self):
        result = validate_url("http://evil\n.com/path")
        self.assertFalse(result["valid"])

    def test_block_empty_url(self):
        result = validate_url("")
        self.assertFalse(result["valid"])

    def test_dns_resolve_private(self):
        with patch("url_validator._resolve_dns", return_value=["127.0.0.1"]):
            self.assertFalse(_is_safe_host("internal.example.com"))

    def test_safe_host_resolves(self):
        self.assertFalse(_is_safe_host("127.0.0.1"))
        self.assertFalse(_is_safe_host("::1"))
        self.assertFalse(_is_safe_host("0.0.0.0"))


if __name__ == "__main__":
    unittest.main()
