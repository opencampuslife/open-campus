from __future__ import annotations

import json
import sys
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TOOLS_SRC = ROOT / "tools"
sys.path.insert(0, str(TOOLS_SRC))

import shadow_mirror_driver  # noqa: E402


class ShadowMirrorDriverTest(unittest.TestCase):
    def test_dry_run_report_stays_redacted(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            replay_path = root / "sample.jsonl"
            replay_path.write_text(
                json.dumps(
                    {
                        "name": "chat_basic",
                        "method": "POST",
                        "path": "/api/gaokao/chat",
                        "route": "POST /api/gaokao/chat",
                        "privacy": {
                            "sanitized": True,
                            "contains_pii": False,
                            "reviewed_by": "engineering",
                        },
                        "headers": {
                            "content-type": "application/json",
                            "x-request-id": "parity-mirror-001",
                        },
                        "body_json": {
                            "message": "请介绍高考志愿填报流程",
                            "user_id": "synthetic-user-001",
                        },
                    },
                    ensure_ascii=False,
                )
                + "\n",
                encoding="utf-8",
            )
            cases = shadow_mirror_driver.load_cases(replay_path)
            report = shadow_mirror_driver.run_cases(cases, None, None, timeout_seconds=1.0, dry_run=True)

            self.assertEqual(report["mode"], "dry_run")
            self.assertEqual(report["summary"]["skipped_cases"], 1)
            self.assertEqual(report["cases"][0]["diff_category"], "skipped")
            serialized = json.dumps(report, ensure_ascii=False)
            self.assertNotIn("请介绍高考志愿填报流程", serialized)
            self.assertNotIn("synthetic-user-001", serialized)

    def test_live_report_uses_redacted_body_summaries(self) -> None:
        payload = b'{"status":"ok"}'
        with _server(payload) as legacy_url, _server(payload) as shadow_url:
            cases = [
                {
                    "name": "admin_cancel",
                    "method": "POST",
                    "path": "/api/admin/ingestion/runs/run-parity-001/cancel",
                    "route": "POST /api/admin/ingestion/runs/run-parity-001/cancel",
                    "privacy": {
                        "sanitized": True,
                        "contains_pii": False,
                        "reviewed_by": "engineering",
                    },
                    "headers": {
                        "content-type": "application/json",
                        "x-request-id": "parity-mirror-002",
                    },
                    "body_json": {},
                }
            ]
            report = shadow_mirror_driver.run_cases(cases, legacy_url, shadow_url, timeout_seconds=1.0, dry_run=False)

            self.assertEqual(report["mode"], "live")
            self.assertEqual(report["summary"]["drifted_cases"], 0)
            case = report["cases"][0]
            self.assertEqual(case["diff_category"], "none")
            self.assertEqual(case["comparison_status"], "passed")
            self.assertTrue(case["legacy_body_summary"].startswith("[redacted len="))
            self.assertTrue(case["shadow_body_summary"].startswith("[redacted len="))
            serialized = json.dumps(report, ensure_ascii=False)
            self.assertNotIn(payload.decode("utf-8"), serialized)


class _FixedResponseHandler(BaseHTTPRequestHandler):
    payload = b""
    content_type = "application/json"

    def do_POST(self) -> None:  # noqa: N802
        content_length = int(self.headers.get("Content-Length", "0"))
        if content_length:
            _ = self.rfile.read(content_length)
        self.send_response(200)
        self.send_header("Content-Type", self.content_type)
        self.end_headers()
        self.wfile.write(self.payload)

    def log_message(self, format: str, *args: object) -> None:  # noqa: A003
        return


class _ServerContext:
    def __init__(self, payload: bytes) -> None:
        handler = type("FixedHandler", (_FixedResponseHandler,), {"payload": payload})
        self._server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)

    def __enter__(self) -> str:
        self._thread.start()
        host, port = self._server.server_address
        return f"http://{host}:{port}"

    def __exit__(self, exc_type, exc, tb) -> None:
        self._server.shutdown()
        self._server.server_close()
        self._thread.join(timeout=2)


def _server(payload: bytes) -> _ServerContext:
    return _ServerContext(payload)


if __name__ == "__main__":
    unittest.main()
