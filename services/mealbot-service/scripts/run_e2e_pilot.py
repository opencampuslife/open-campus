from __future__ import annotations

import base64
import hashlib
import json
import os
import struct
import subprocess
import sys
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "services" / "mealbot-service" / "src"))
sys.path.insert(0, str(ROOT / "services" / "api-gateway" / "src"))

from app.db.connection import get_conn
from app.db.repositories import inbound_messages as inbound_repo
from app.modules.wecom.callback import receive_callback_message
from app.modules.wecom.media_download import process_pending_media_downloads
from mealbot_gateway import (
    get_logistics_meal_summary,
    post_mealbot_lock,
    post_mealbot_meal_order,
    post_scheduler_run_due_reminders,
    post_vendor_confirmation,
    post_vendor_confirm_action,
)

SCHOOL_ID = "school_demo"
STUDENT_ID = "student_demo_001"
CLASS_ID = "class_g7_1"
PARENT_ID = "parent_demo_001"
TOKEN = "pilot-callback-token"
CORP_ID = "demo-corp"
AES_KEY = b"0123456789abcdef0123456789abcdef"


def _identity(role: str, user_id: str) -> dict[str, str]:
    return {
        "role": role,
        "user_id": user_id,
        "wecom_userid": user_id,
        "school_id": SCHOOL_ID,
        "campus": SCHOOL_ID,
        "student_id": STUDENT_ID,
    }


def _encrypt_message(message: str) -> str:
    plain = b"0123456789abcdef" + struct.pack("!I", len(message.encode("utf-8"))) + message.encode("utf-8") + CORP_ID.encode("utf-8")
    padding = 32 - (len(plain) % 32)
    result = subprocess.run(
        ["openssl", "enc", "-aes-256-cbc", "-K", AES_KEY.hex(), "-iv", AES_KEY[:16].hex(), "-nopad"],
        input=plain + bytes([padding]) * padding,
        capture_output=True,
        check=True,
    )
    return base64.b64encode(result.stdout).decode("ascii")


def _signature(timestamp: str, nonce: str, encrypted: str) -> str:
    return hashlib.sha1("".join(sorted([TOKEN, timestamp, nonce, encrypted])).encode("utf-8")).hexdigest()


def _clean_dates(lock_date: date, attachment_date: date, msg_id: str) -> None:
    with get_conn() as conn:
        conn.execute("DELETE FROM reminder_tasks WHERE biz_id = %s", (msg_id,))
        conn.execute("DELETE FROM inbound_messages WHERE msg_id = %s", (msg_id,))
        conn.execute("DELETE FROM attachments WHERE biz_type = 'inbound_message' AND biz_id = %s", (msg_id,))
        conn.execute(
            "DELETE FROM reminder_tasks WHERE biz_id IN (SELECT confirmation_id FROM vendor_confirmations WHERE meal_lock_id IN (SELECT lock_id FROM meal_locks WHERE meal_date IN (%s, %s)))",
            (lock_date, attachment_date),
        )
        conn.execute(
            "DELETE FROM vendor_confirmations WHERE meal_lock_id IN (SELECT lock_id FROM meal_locks WHERE meal_date IN (%s, %s))",
            (lock_date, attachment_date),
        )
        conn.execute("DELETE FROM meal_locks WHERE meal_date IN (%s, %s)", (lock_date, attachment_date))
        conn.execute(
            "DELETE FROM reminder_tasks WHERE biz_id IN (SELECT order_id FROM meal_orders WHERE meal_date IN (%s, %s))",
            (lock_date, attachment_date),
        )
        conn.execute(
            "DELETE FROM attachments WHERE biz_type = 'meal_order' AND biz_id IN (SELECT order_id FROM meal_orders WHERE meal_date IN (%s, %s))",
            (lock_date, attachment_date),
        )
        conn.execute("DELETE FROM meal_orders WHERE meal_date IN (%s, %s)", (lock_date, attachment_date))


def run() -> dict[str, object]:
    lock_date = date.today() + timedelta(days=45)
    attachment_date = lock_date + timedelta(days=1)
    msg_id = f"PILOT-{lock_date.strftime('%Y%m%d')}"
    _clean_dates(lock_date, attachment_date, msg_id)
    parent = _identity("parent_or_student_h5", PARENT_ID)
    logistics = _identity("logistics_staff", "logistics_001")

    initial = post_mealbot_meal_order({
        "student_id": STUDENT_ID,
        "class_id": CLASS_ID,
        "meal_date": lock_date.isoformat(),
        "meal_type": "lunch",
        "action": "order",
        "photo_bytes": b"\xff\xd8\xff\xe0\x00\x10JFIF\x00" + b"\x00" * 30,
        "photo_filename": "pilot.jpg",
        "photo_content_type": "image/jpeg",
    }, parent, ROOT)
    lock = post_mealbot_lock({"meal_date": lock_date.isoformat(), "meal_type": "lunch"}, logistics, ROOT)
    rejected = post_mealbot_meal_order({
        "student_id": STUDENT_ID,
        "class_id": CLASS_ID,
        "meal_date": lock_date.isoformat(),
        "meal_type": "lunch",
        "action": "add",
    }, parent, ROOT)
    vendor = post_vendor_confirmation({
        "meal_lock_id": lock["lock"]["lock_id"],
        "vendor_name": "pilot-vendor",
    }, logistics, ROOT)
    reminder_counts = post_scheduler_run_due_reminders({"worker_id": "pilot"}, logistics, ROOT)
    token = vendor["confirm_url"].split("t=")[-1]
    confirmation = post_vendor_confirm_action({"token": token, "action": "confirmed"}, {}, ROOT)

    image_xml = (
        f"<xml><ToUserName><![CDATA[{CORP_ID}]]></ToUserName>"
        f"<FromUserName><![CDATA[{PARENT_ID}]]></FromUserName>"
        "<CreateTime>1710000000</CreateTime><MsgType><![CDATA[image]]></MsgType>"
        "<MediaId><![CDATA[MEDIA-PILOT]]></MediaId>"
        f"<MsgId>{msg_id}</MsgId><AgentID>1000001</AgentID></xml>"
    )
    encrypted = _encrypt_message(image_xml)
    old_env = {key: os.environ.get(key) for key in ("WECOM_TOKEN", "WECOM_ENCODING_AES_KEY", "WECOM_CORP_ID", "WECOM_SCHOOL_ID")}
    os.environ.update({
        "WECOM_TOKEN": TOKEN,
        "WECOM_ENCODING_AES_KEY": base64.b64encode(AES_KEY).decode("ascii").rstrip("="),
        "WECOM_CORP_ID": CORP_ID,
        "WECOM_SCHOOL_ID": SCHOOL_ID,
    })
    try:
        receive_callback_message({
            "timestamp": "1710000000",
            "nonce": "pilot",
            "msg_signature": _signature("1710000000", "pilot", encrypted),
        }, f"<xml><Encrypt><![CDATA[{encrypted}]]></Encrypt></xml>", ROOT)
        process_pending_media_downloads(
            ROOT,
            downloader=lambda _media_id: (b"\xff\xd8\xff\xe0\x00\x10JFIF\x00" + b"\x00" * 30, "image/jpeg"),
            school_id=SCHOOL_ID,
        )
    finally:
        for key, value in old_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    attachment_id = inbound_repo.get_inbound_message(msg_id)["attachment_id"]
    callback_cancel = post_mealbot_meal_order({
        "student_id": STUDENT_ID,
        "class_id": CLASS_ID,
        "meal_date": attachment_date.isoformat(),
        "meal_type": "dinner",
        "action": "cancel",
        "reason": "企微图片退餐确认",
        "attachment_id": attachment_id,
    }, parent, ROOT)
    summary = get_logistics_meal_summary({"meal_date": lock_date.isoformat()}, logistics, ROOT)

    checks = {
        "initial_order_created": initial["ok"],
        "meal_locked": lock["lock"]["status"] == "locked",
        "future_submit_blocked": rejected.get("error", {}).get("code") == "MEAL_LOCKED",
        "vendor_confirmed": confirmation["confirmation"]["status"] == "confirmed",
        "reminders_sent": reminder_counts["sent"] >= 1,
        "wecom_attachment_downloaded": bool(attachment_id),
        "attachment_order_linked": callback_cancel["ok"],
        "logistics_summary_exported": bool(summary.get("locks")),
    }
    passed = sum(1 for value in checks.values() if value)
    report: dict[str, object] = {
        "suite": "mealbot_e2e",
        "total": len(checks),
        "passed": passed,
        "failed": len(checks) - passed,
        "score": round(passed * 100 / len(checks), 2),
        "checks": checks,
        "orders_created": 2,
        "attachments_created": 2,
        "meal_lock_status": summary["locks"][0]["status"],
        "vendor_confirmation_status": confirmation["confirmation"]["status"],
        "reminders_sent": reminder_counts["sent"],
    }
    reports = ROOT / "data" / "reports"
    reports.mkdir(parents=True, exist_ok=True)
    (reports / "mealbot_e2e_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


if __name__ == "__main__":
    result = run()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    raise SystemExit(0 if result["failed"] == 0 else 1)
