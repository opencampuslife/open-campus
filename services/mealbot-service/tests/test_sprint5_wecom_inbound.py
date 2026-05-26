from __future__ import annotations

import base64
import hashlib
import os
import shutil
import struct
import subprocess
import sys
import unittest
from contextlib import contextmanager
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "services" / "mealbot-service" / "src"))
sys.path.insert(0, str(ROOT / "services" / "api-gateway" / "src"))

from app.db.connection import get_conn
from app.db.repositories import attachments as attachments_repo
from app.db.repositories import inbound_messages as inbound_repo
from app.modules.wecom.callback import receive_callback_message, verify_callback_url
from app.modules.wecom.media_download import process_pending_media_downloads
from app.services.reminder_service import process_due_reminders
from app.services.wecom_crypto import WeComCryptoError
from mealbot_gateway import get_h5_attachment, post_mealbot_meal_order

SCHOOL_ID = "school_demo"
PARENT_ID = "parent_demo_001"
STUDENT_ID = "student_demo_001"
CLASS_ID = "class_g7_1"
TOKEN = "callback-token"
CORP_ID = "demo-corp"
AES_KEY = b"0123456789abcdef0123456789abcdef"
ENCODING_AES_KEY = base64.b64encode(AES_KEY).decode("ascii").rstrip("=")


def _signature(timestamp: str, nonce: str, encrypted: str) -> str:
    return hashlib.sha1("".join(sorted([TOKEN, timestamp, nonce, encrypted])).encode("utf-8")).hexdigest()


def _encrypt_message(message: str) -> str:
    if not shutil.which("openssl"):
        raise unittest.SkipTest("openssl is required for WeCom AES fixture encryption")
    plain = b"0123456789abcdef" + struct.pack("!I", len(message.encode("utf-8"))) + message.encode("utf-8") + CORP_ID.encode("utf-8")
    padding = 32 - (len(plain) % 32)
    padded = plain + bytes([padding]) * padding
    result = subprocess.run(
        [
            "openssl", "enc", "-aes-256-cbc", "-K", AES_KEY.hex(),
            "-iv", AES_KEY[:16].hex(), "-nopad",
        ],
        input=padded,
        capture_output=True,
        check=True,
    )
    return base64.b64encode(result.stdout).decode("ascii")


def _image_xml(msg_id: str, userid: str = PARENT_ID) -> str:
    return (
        "<xml>"
        f"<ToUserName><![CDATA[{CORP_ID}]]></ToUserName>"
        f"<FromUserName><![CDATA[{userid}]]></FromUserName>"
        "<CreateTime>1710000000</CreateTime>"
        "<MsgType><![CDATA[image]]></MsgType>"
        "<PicUrl><![CDATA[https://example.invalid/photo.jpg]]></PicUrl>"
        f"<MediaId><![CDATA[MEDIA-{msg_id}]]></MediaId>"
        f"<MsgId>{msg_id}</MsgId>"
        "<AgentID>1000001</AgentID>"
        "</xml>"
    )


@contextmanager
def callback_env():
    with patch.dict(os.environ, {
        "WECOM_TOKEN": TOKEN,
        "WECOM_ENCODING_AES_KEY": ENCODING_AES_KEY,
        "WECOM_CORP_ID": CORP_ID,
        "WECOM_SCHOOL_ID": SCHOOL_ID,
    }, clear=False):
        yield


def _identity(userid: str = PARENT_ID) -> dict[str, str]:
    return {
        "user_id": userid,
        "wecom_userid": userid,
        "role": "parent_or_student_h5",
        "school_id": SCHOOL_ID,
        "campus": SCHOOL_ID,
    }


class Sprint5WeComInboundTest(unittest.TestCase):
    def setUp(self) -> None:
        self.msg_ids: list[str] = []
        self.order_ids: list[str] = []

    def tearDown(self) -> None:
        with get_conn() as conn:
            for order_id in self.order_ids:
                conn.execute("DELETE FROM operation_logs WHERE biz_id = %(id)s", {"id": order_id})
                conn.execute("DELETE FROM attachments WHERE biz_id = %(id)s", {"id": order_id})
                conn.execute("DELETE FROM reminder_tasks WHERE biz_id = %(id)s", {"id": order_id})
                conn.execute("DELETE FROM meal_orders WHERE order_id = %(id)s", {"id": order_id})
            for msg_id in self.msg_ids:
                conn.execute("DELETE FROM operation_logs WHERE biz_id = %(id)s", {"id": msg_id})
                conn.execute("DELETE FROM reminder_tasks WHERE biz_id = %(id)s", {"id": msg_id})
                conn.execute("DELETE FROM inbound_messages WHERE msg_id = %(id)s", {"id": msg_id})
                conn.execute("DELETE FROM attachments WHERE biz_id = %(id)s", {"id": msg_id})

    def _post_callback(self, message_xml: str, msg_id: str) -> dict[str, object]:
        encrypted = _encrypt_message(message_xml)
        query = {
            "timestamp": "1710000000",
            "nonce": "fixture-nonce",
            "msg_signature": _signature("1710000000", "fixture-nonce", encrypted),
        }
        wrapper = f"<xml><Encrypt><![CDATA[{encrypted}]]></Encrypt></xml>"
        self.msg_ids.append(msg_id)
        with callback_env():
            return receive_callback_message(query, wrapper, ROOT)

    def test_get_callback_verification_returns_decrypted_echo(self) -> None:
        encrypted = _encrypt_message("verified-echo")
        query = {
            "timestamp": "1710000000",
            "nonce": "verify-nonce",
            "echostr": encrypted,
            "msg_signature": _signature("1710000000", "verify-nonce", encrypted),
        }
        with callback_env():
            self.assertEqual(verify_callback_url(query), "verified-echo")

    def test_callback_rejects_invalid_signature(self) -> None:
        encrypted = _encrypt_message("verified-echo")
        with get_conn() as conn:
            before = conn.execute(
                "SELECT count(*) AS count FROM operation_logs WHERE action = 'wecom_callback.invalid_signature'"
            ).fetchone()["count"]
        with callback_env(), self.assertRaises(WeComCryptoError):
            verify_callback_url({
                "timestamp": "1710000000",
                "nonce": "verify-nonce",
                "echostr": encrypted,
                "msg_signature": "not-valid",
            })
        with get_conn() as conn:
            after = conn.execute(
                "SELECT count(*) AS count FROM operation_logs WHERE action = 'wecom_callback.invalid_signature'"
            ).fetchone()["count"]
        self.assertEqual(after, before + 1)

    def test_post_callback_rejects_invalid_signature(self) -> None:
        msg_id = f"BADSIG-{uuid4().hex[:12]}"
        encrypted = _encrypt_message(_image_xml(msg_id))
        wrapper = f"<xml><Encrypt><![CDATA[{encrypted}]]></Encrypt></xml>"
        with callback_env(), self.assertRaises(WeComCryptoError):
            receive_callback_message({
                "timestamp": "1710000000",
                "nonce": "fixture-nonce",
                "msg_signature": "not-valid",
            }, wrapper, ROOT)
        self.assertIsNone(inbound_repo.get_inbound_message(msg_id))

    def test_image_callback_is_idempotent_and_async(self) -> None:
        msg_id = f"IMG-{uuid4().hex[:12]}"
        first = self._post_callback(_image_xml(msg_id), msg_id)
        second = self._post_callback(_image_xml(msg_id), msg_id)
        row = inbound_repo.get_inbound_message(msg_id)
        self.assertTrue(first["created"])
        self.assertFalse(second["created"])
        self.assertEqual(row["status"], "download_pending")
        self.assertIsNone(row.get("attachment_id"))

    def test_non_image_callback_is_ignored(self) -> None:
        msg_id = f"TXT-{uuid4().hex[:12]}"
        xml = _image_xml(msg_id).replace("image", "text").replace("<MediaId><![CDATA[MEDIA-" + msg_id + "]]></MediaId>", "")
        result = self._post_callback(xml, msg_id)
        self.assertEqual(result["status"], "ignored")

    def test_media_worker_creates_attachment_and_confirmation_task(self) -> None:
        msg_id = f"DL-{uuid4().hex[:12]}"
        self._post_callback(_image_xml(msg_id), msg_id)
        result = process_pending_media_downloads(
            ROOT,
            downloader=lambda _media_id: (b"\xff\xd8\xff\xe0\x00\x10JFIF\x00" + b"\x00" * 32, "image/jpeg"),
            school_id=SCHOOL_ID,
        )
        row = inbound_repo.get_inbound_message(msg_id)
        self.assertGreaterEqual(result["downloaded"], 1)
        self.assertEqual(row["status"], "downloaded")
        self.assertTrue(row["attachment_id"])
        with get_conn() as conn:
            task = conn.execute(
                "SELECT * FROM reminder_tasks WHERE biz_id = %(msg_id)s",
                {"msg_id": msg_id},
            ).fetchone()
        self.assertEqual(task["template_id"], "wecom_image_confirm_link")
        self.assertIn("/h5/meal/cancel?attachment_id=", task["payload_json"]["confirm_url"])

    def test_image_inbound_e2e_reaches_wecom_adapter_stub(self) -> None:
        msg_id = f"E2E-{uuid4().hex[:12]}"
        self._post_callback(_image_xml(msg_id), msg_id)
        process_pending_media_downloads(
            ROOT,
            downloader=lambda _media_id: (b"\xff\xd8\xff\xe0\x00\x10JFIF\x00" + b"\x00" * 32, "image/jpeg"),
            school_id=SCHOOL_ID,
        )

        sent: list[dict[str, object]] = []

        class StubAdapter:
            def send(self, task: dict[str, object]) -> dict[str, object]:
                sent.append(task)
                return {"ok": True, "channel": "wecom_app_message"}

        with patch("app.services.reminder_service.get_adapter", return_value=StubAdapter()):
            counts = process_due_reminders("test_e2e_worker")

        self.assertEqual(counts["sent"], 1)
        self.assertEqual(len(sent), 1)
        self.assertEqual(sent[0]["template_id"], "wecom_image_confirm_link")
        with get_conn() as conn:
            audit = conn.execute(
                "SELECT action FROM operation_logs WHERE biz_id = %(id)s AND action = 'reminder_task.sent' ORDER BY created_at DESC LIMIT 1",
                {"id": msg_id},
            ).fetchone()
        self.assertEqual(audit["action"], "reminder_task.sent")

    def test_media_worker_marks_download_failure(self) -> None:
        msg_id = f"FAIL-{uuid4().hex[:12]}"
        self._post_callback(_image_xml(msg_id), msg_id)

        def fail(_media_id: str) -> tuple[bytes, str]:
            raise ValueError("download unavailable")

        process_pending_media_downloads(ROOT, downloader=fail, school_id=SCHOOL_ID)
        row = inbound_repo.get_inbound_message(msg_id)
        self.assertEqual(row["status"], "failed")
        self.assertIn("download unavailable", row["last_error"])

    def test_cancel_links_owned_wecom_attachment(self) -> None:
        msg_id = f"LINK-{uuid4().hex[:12]}"
        self._post_callback(_image_xml(msg_id), msg_id)
        process_pending_media_downloads(
            ROOT,
            downloader=lambda _media_id: (b"\xff\xd8\xff\xe0\x00\x10JFIF\x00" + b"\x00" * 32, "image/jpeg"),
            school_id=SCHOOL_ID,
        )
        attachment_id = inbound_repo.get_inbound_message(msg_id)["attachment_id"]
        metadata = get_h5_attachment(attachment_id, _identity(), ROOT)
        self.assertEqual(metadata["attachment"]["attachment_id"], attachment_id)
        response = post_mealbot_meal_order({
            "student_id": STUDENT_ID,
            "class_id": CLASS_ID,
            "meal_date": str(date.today() + timedelta(days=11)),
            "meal_type": "lunch",
            "action": "cancel",
            "reason": "callback attachment",
            "attachment_id": attachment_id,
        }, _identity(), ROOT)
        self.order_ids.append(response["order"]["order_id"])
        attachment = attachments_repo.get_attachment(attachment_id)
        self.assertEqual(attachment["biz_type"], "meal_order")
        self.assertEqual(attachment["biz_id"], response["order"]["order_id"])
        with get_conn() as conn:
            audit = conn.execute(
                "SELECT action FROM operation_logs WHERE biz_id = %(id)s ORDER BY created_at DESC LIMIT 1",
                {"id": response["order"]["order_id"]},
            ).fetchone()
        self.assertEqual(audit["action"], "meal_order.created")

    def test_user_cannot_use_another_users_attachment(self) -> None:
        msg_id = f"OWN-{uuid4().hex[:12]}"
        self._post_callback(_image_xml(msg_id), msg_id)
        process_pending_media_downloads(
            ROOT,
            downloader=lambda _media_id: (b"\xff\xd8\xff\xe0\x00\x10JFIF\x00" + b"\x00" * 32, "image/jpeg"),
            school_id=SCHOOL_ID,
        )
        attachment_id = inbound_repo.get_inbound_message(msg_id)["attachment_id"]
        with self.assertRaises(ValueError):
            get_h5_attachment(attachment_id, _identity("someone_else"), ROOT)
        with self.assertRaises(ValueError):
            post_mealbot_meal_order({
                "student_id": STUDENT_ID,
                "class_id": CLASS_ID,
                "meal_date": str(date.today() + timedelta(days=12)),
                "meal_type": "lunch",
                "action": "cancel",
                "reason": "spoof",
                "attachment_id": attachment_id,
                "submitted_by_wecom_userid": PARENT_ID,
            }, _identity("someone_else"), ROOT)
        with get_conn() as conn:
            audit = conn.execute(
                "SELECT count(*) AS count FROM operation_logs WHERE action = 'attachment.rejected_owner_mismatch' AND biz_id = %(id)s",
                {"id": attachment_id},
            ).fetchone()
        self.assertGreaterEqual(audit["count"], 1)

    def test_cancel_page_consumes_attachment_query_parameter(self) -> None:
        page = (ROOT / "services" / "mealbot-service" / "src" / "app" / "static" / "h5" / "meal" / "cancel.html").read_text(encoding="utf-8")
        self.assertIn('get("attachment_id")', page)
        self.assertIn('name="attachment_id"', page)


if __name__ == "__main__":
    unittest.main()
