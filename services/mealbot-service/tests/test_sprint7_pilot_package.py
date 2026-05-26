from __future__ import annotations

import json
import sys
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "services" / "mealbot-service" / "src"))
sys.path.insert(0, str(ROOT / "services" / "api-gateway" / "src"))

from app.db.connection import get_conn
from app.db.repositories import inbound_messages as inbound_repo
from app.db.repositories import reminder_tasks as tasks_repo
from app.modules.pilot.service import export_meal_summary
from app.scripts.import_pilot_data import import_pilot_data
from app.scripts.onboard_school import onboard
from mealbot_gateway import get_h5_students, get_pilot_status, post_mealbot_meal_order, post_pilot_runtime_control


class Sprint7PilotPackageTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.tmp = Path(self.temp.name)
        self.school_id = "pilot_" + uuid4().hex[:10]
        self.parent_id = "parent_" + uuid4().hex[:8]
        self.teacher_id = "teacher_" + uuid4().hex[:8]
        self.logistics_id = "logistics_" + uuid4().hex[:8]
        self._write_files()
        self.onboard_result = onboard(self.tmp / "pilot_school.yaml", self.school_id)
        self.import_result = import_pilot_data(
            school_id=self.school_id,
            classes_path=self.tmp / "classes.csv",
            students_path=self.tmp / "students.csv",
            teachers_path=self.tmp / "teachers.csv",
            parent_bindings_path=self.tmp / "parent_bindings.csv",
            report_path=self.tmp / "import_report.json",
        )
        with get_conn() as conn:
            self.student_id = conn.execute(
                "SELECT student_id FROM students WHERE school_id = %s AND student_no = '2026001'",
                (self.school_id,),
            ).fetchone()["student_id"]
            self.class_id = conn.execute(
                "SELECT class_id FROM classes WHERE school_id = %s AND name = '初一3班'",
                (self.school_id,),
            ).fetchone()["class_id"]

    def tearDown(self) -> None:
        with get_conn() as conn:
            conn.execute("DELETE FROM worker_heartbeats WHERE school_id = %s", (self.school_id,))
            conn.execute("DELETE FROM schools WHERE school_id = %s", (self.school_id,))
        self.temp.cleanup()

    def _write_files(self) -> None:
        (self.tmp / "pilot_school.yaml").write_text(
            """school:
  name: "示范中学"
  timezone: "Asia/Shanghai"
wecom:
  corp_id: "wwpilot"
  agent_id: "1000002"
  callback_url: "https://pilot.example.com/wecom/callback/message"
meal:
  lunch_cutoff: "09:30"
  dinner_cutoff: "15:30"
  extra_cutoff: "16:30"
  lunch_delivery_time: "12:00"
  dinner_delivery_time: "18:00"
vendor:
  name: "试点供应商"
  contact: "13800000000"
  channel: "wecom_group_bot"
""",
            encoding="utf-8",
        )
        (self.tmp / "classes.csv").write_text("class_name,grade\n初一3班,初一\n", encoding="utf-8")
        (self.tmp / "students.csv").write_text(
            f"student_no,name,class_name,parent_name,parent_mobile,parent_wecom_userid\n"
            f"2026001,张三,初一3班,张家长,13800000000,{self.parent_id}\n",
            encoding="utf-8",
        )
        (self.tmp / "teachers.csv").write_text(
            f"name,wecom_userid,role,class_name\n李老师,{self.teacher_id},head_teacher,初一3班\n"
            f"王老师,{self.logistics_id},logistics_staff,\n",
            encoding="utf-8",
        )
        (self.tmp / "parent_bindings.csv").write_text(
            f"student_no,parent_name,parent_mobile,parent_wecom_userid\n"
            f"2026001,张家长,13800000000,{self.parent_id}\n",
            encoding="utf-8",
        )

    def _parent_identity(self) -> dict[str, str]:
        return {
            "user_id": self.parent_id,
            "wecom_userid": self.parent_id,
            "role": "parent_or_student_h5",
            "school_id": self.school_id,
            "campus": self.school_id,
            "student_id": self.student_id,
        }

    def _operations_identity(self) -> dict[str, str]:
        return {
            "user_id": self.logistics_id,
            "role": "logistics_staff",
            "school_id": self.school_id,
            "campus": self.school_id,
        }

    def test_onboard_school_is_idempotent_and_safe(self) -> None:
        repeated = onboard(self.tmp / "pilot_school.yaml", self.school_id)
        self.assertEqual(repeated["school_id"], self.school_id)
        self.assertTrue(repeated["callback_check"]["configured"])
        self.assertNotIn("13800000000", json.dumps(repeated, ensure_ascii=False))
        with get_conn() as conn:
            config_count = conn.execute(
                "SELECT count(*) AS count FROM pilot_school_configs WHERE school_id = %s",
                (self.school_id,),
            ).fetchone()["count"]
        self.assertEqual(config_count, 1)

    def test_csv_import_upserts_and_reports_invalid_rows(self) -> None:
        self.assertTrue(self.import_result["ok"])
        invalid = self.tmp / "invalid_students.csv"
        invalid.write_text("student_no,name,class_name\n2026002,坏行,不存在班\n", encoding="utf-8")
        report = import_pilot_data(
            school_id=self.school_id,
            classes_path=None,
            students_path=invalid,
            teachers_path=None,
            parent_bindings_path=None,
            report_path=self.tmp / "invalid_report.json",
        )
        self.assertFalse(report["ok"])
        self.assertEqual(len(report["errors"]), 1)
        self.assertTrue((self.tmp / "invalid_report.json").exists())

    def test_parent_binding_enables_h5_student_selection(self) -> None:
        result = get_h5_students({}, self._parent_identity(), ROOT)
        self.assertEqual(result["students"][0]["student_id"], self.student_id)

    def test_pilot_status_reports_pending_and_failed_work(self) -> None:
        with get_conn() as conn:
            conn.execute(
                """
                INSERT INTO reminder_tasks (
                    reminder_id, school_id, biz_type, biz_id, receiver_type,
                    receiver_id, channel, status, scheduled_at
                ) VALUES (%s, %s, 'meal_order', 'status-order', 'logistics', 'default', 'noop', 'pending', now())
                """,
                ("RT-" + uuid4().hex[:12], self.school_id),
            )
            conn.execute(
                """
                INSERT INTO inbound_messages (
                    msg_id, school_id, from_wecom_userid, msg_type, media_id, status
                ) VALUES (%s, %s, %s, 'image', 'failed-media', 'failed')
                """,
                ("MSG-" + uuid4().hex[:12], self.school_id, self.parent_id),
            )
        result = get_pilot_status(
            {"school_id": self.school_id, "date": date.today().isoformat()},
            self._operations_identity(),
            ROOT,
        )
        self.assertGreaterEqual(result["mealbot"]["reminders_pending"], 1)
        self.assertGreaterEqual(result["mealbot"]["inbound_images_failed"], 1)

    def test_pause_and_resume_preserve_work_and_control_submission(self) -> None:
        reminder_id = "RT-" + uuid4().hex[:12]
        msg_id = "MSG-" + uuid4().hex[:12]
        with get_conn() as conn:
            conn.execute(
                """
                INSERT INTO reminder_tasks (
                    reminder_id, school_id, biz_type, biz_id, receiver_type,
                    receiver_id, channel, status, scheduled_at
                ) VALUES (%s, %s, 'meal_order', 'paused-order', 'logistics', 'default', 'noop', 'pending', now())
                """,
                (reminder_id, self.school_id),
            )
            conn.execute(
                """
                INSERT INTO inbound_messages (
                    msg_id, school_id, from_wecom_userid, msg_type, media_id, status
                ) VALUES (%s, %s, %s, 'image', 'paused-media', 'download_pending')
                """,
                (msg_id, self.school_id, self.parent_id),
            )
        post_pilot_runtime_control(
            "pause",
            {"features": ["h5_submissions", "reminder_worker", "wecom_media_worker"]},
            self._operations_identity(),
            ROOT,
        )
        blocked = post_mealbot_meal_order({
            "student_id": self.student_id,
            "class_id": self.class_id,
            "meal_date": (date.today() + timedelta(days=20)).isoformat(),
            "meal_type": "lunch",
            "action": "order",
        }, self._parent_identity(), ROOT)
        self.assertEqual(blocked["error"]["code"], "PILOT_PAUSED")
        self.assertNotIn(reminder_id, {row["reminder_id"] for row in tasks_repo.claim_due_tasks("test", 100, self.school_id)})
        self.assertNotIn(msg_id, {row["msg_id"] for row in inbound_repo.claim_pending_downloads(100, self.school_id)})
        post_pilot_runtime_control(
            "resume",
            {"features": ["h5_submissions", "reminder_worker", "wecom_media_worker"]},
            self._operations_identity(),
            ROOT,
        )
        self.assertIn(reminder_id, {row["reminder_id"] for row in tasks_repo.claim_due_tasks("test", 100, self.school_id)})
        self.assertIn(msg_id, {row["msg_id"] for row in inbound_repo.claim_pending_downloads(100, self.school_id)})

    def test_export_meal_summary_writes_csv(self) -> None:
        meal_date = date.today() + timedelta(days=21)
        result = post_mealbot_meal_order({
            "student_id": self.student_id,
            "class_id": self.class_id,
            "meal_date": meal_date.isoformat(),
            "meal_type": "lunch",
            "action": "order",
        }, self._parent_identity(), ROOT)
        self.assertTrue(result["ok"])
        output = self.tmp / "meal_summary.csv"
        exported = export_meal_summary(self.school_id, meal_date, output)
        self.assertEqual(exported["rows"], 1)
        self.assertIn("student_no", output.read_text(encoding="utf-8-sig"))


if __name__ == "__main__":
    unittest.main()
