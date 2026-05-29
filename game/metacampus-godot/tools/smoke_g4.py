#!/usr/bin/env python3
"""MetaCampus G4 Smoke Test — Demo Polish
Tests NPC indicators, metric toasts, warnings, demo-reset.
Output: reports/g4_smoke_report.json
"""
import json
import sys
import time
import urllib.request
import urllib.error
import urllib.parse
from pathlib import Path

BASE = "http://127.0.0.1:16007"
REPORT_PATH = Path(__file__).parent.parent / "reports" / "g4_smoke_report.json"

def request(path, timeout=5):
    url = BASE + path
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            body = r.read().decode("utf-8")
            try:
                return json.loads(body)
            except json.JSONDecodeError:
                return {"raw": body}
    except urllib.error.URLError as e:
        return {"_error": str(e)}

class SmokeG4:
    def __init__(self):
        self.results = {}
        self.failures = []

    def check(self, name, condition, detail=""):
        self.results[name] = condition
        if condition:
            print(f"  ✅ {name}")
        else:
            print(f"  ❌ {name} — {detail}")
            self.failures.append(f"{name}: {detail}")

    def run(self):
        print("=" * 60)
        print("MetaCampus G4 Demo Polish Smoke Test")
        print("=" * 60)

        self._test_demo_reset()
        self._test_npc_indicators()
        self._test_metric_toasts()
        self._test_high_risk_warning()
        self._test_ui_readability()
        self._test_g2_g3_regression()

        self._write_report()

    def _test_demo_reset(self):
        print("\n── Demo Reset ──")

        # Mess up the state first
        request("/dialogue/start?npc_id=parent_001")
        time.sleep(0.1)
        request("/dialogue/choose?index=0")
        time.sleep(0.3)

        # Reset
        r = request("/demo-reset")
        self.check("demo_reset_ok",
                    r.get("status") == "ok",
                    f"got {r}")
        self.check("demo_reset_position",
                    r.get("position", {}).get("x") == 128,
                    f"got {r.get('position')}")
        time.sleep(0.3)

        # Verify clean state
        m = request("/metrics")
        mt = m.get("metrics", {})
        self.check("demo_reset_metrics",
                    mt.get("parent_trust") == 50,
                    f"got {mt}")

    def _test_npc_indicators(self):
        print("\n── NPC Indicators ──")
        request("/demo-reset")
        time.sleep(0.3)

        # Start a quest to see indicator change
        request("/dialogue/start?npc_id=parent_001")
        time.sleep(0.2)

        # NPC should now show "?" (active quest)
        r = request("/status")
        self.check("npc_game_running",
                    r.get("status") == "ok",
                    f"got {r}")

        # Complete the quest
        request("/dialogue/choose?index=0")
        time.sleep(0.5)

        # Check quest status
        r = request("/quest?id=q_admission_001")
        self.check("npc_quest_completed",
                    r.get("quest", {}).get("status") == "completed",
                    f"got {r}")

    def _test_metric_toasts(self):
        print("\n── Metric Change Toasts ──")
        request("/demo-reset")
        time.sleep(0.3)

        request("/dialogue/start?npc_id=parent_001")
        time.sleep(0.2)
        request("/dialogue/choose?index=0")
        time.sleep(0.5)

        m = request("/metrics")
        mt = m.get("metrics", {})
        self.check("toast_parent_trust",
                    mt.get("parent_trust", 0) >= 58,
                    f"parent_trust={mt.get('parent_trust')}")
        self.check("toast_compliance",
                    mt.get("compliance_safety", 0) >= 75,
                    f"compliance_safety={mt.get('compliance_safety')}")

    def _test_high_risk_warning(self):
        print("\n── High Risk Warning ──")
        request("/demo-reset")
        time.sleep(0.3)

        request("/dialogue/start?npc_id=parent_001")
        time.sleep(0.2)
        request("/dialogue/choose?index=0")  # T1 → line 1
        time.sleep(0.5)

        # T2 error branch
        request("/dialogue/choose?index=1")
        time.sleep(0.5)

        m = request("/metrics")
        mt = m.get("metrics", {})
        self.check("warning_compliance_drop",
                    mt.get("compliance_safety", 100) <= 55,
                    f"compliance={mt.get('compliance_safety')} (expected <=55 after T2 error)")

    def _test_ui_readability(self):
        print("\n── UI Readability ──")

        r = request("/quests")
        quests = r.get("quests", [])
        self.check("ui_quests_visible",
                    len(quests) >= 8,
                    f"got {len(quests)} quests")

        r = request("/taskboard")
        self.check("ui_taskboard", r.get("status") == "ok", f"{r}")

        r = request("/dashboard")
        self.check("ui_dashboard", r.get("status") == "ok", f"{r}")

        r = request("/status")
        self.check("ui_status", r.get("status") == "ok", f"{r}")

        # Verify T1/T2/T3 exist and are first in list
        top_quests = [q.get("quest_id") for q in quests[:3]]
        self.check("ui_t1_t2_t3_available",
                    all(q in top_quests for q in ["q_admission_001", "q_admission_002", "q_material_reminder_001"]),
                    f"top 3: {top_quests}")

    def _test_g2_g3_regression(self):
        print("\n── G2 + G3 Quick Regression ──")
        request("/demo-reset")
        time.sleep(0.3)

        # G2: basic task flow
        request("/dialogue/start?npc_id=parent_001")
        time.sleep(0.2)
        request("/dialogue/choose?index=0")
        time.sleep(0.3)

        m = request("/metrics")
        mt = m.get("metrics", {})
        self.check("regression_g2_parent_trust",
                    mt.get("parent_trust", 0) >= 58,
                    f"{mt.get('parent_trust')}")

        # G3: API still works
        r = request("/api/ask?q=" + urllib.parse.quote("报名需要哪些材料"))
        self.check("regression_g3_api_ok",
                    r.get("ok") == True,
                    f"{r}")

    def _write_report(self):
        passed = all(self.results.values())
        report = {
            "phase": "G4",
            "result": "PASS" if passed else "FAIL",
            "checks_total": len(self.results),
            "checks_passed": sum(1 for v in self.results.values() if v),
            "checks_failed": sum(1 for v in self.results.values() if not v),
            "checks": self.results,
            "failures": self.failures
        }
        REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(REPORT_PATH, "w") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        print(f"\n{'=' * 60}")
        print(f"Result: {'✅ PASS' if passed else '❌ FAIL'}")
        print(f"Checks: {report['checks_passed']}/{report['checks_total']}")
        if self.failures:
            for f in self.failures:
                print(f"  - {f}")
        print(f"Report: {REPORT_PATH}")
        print(f"{'=' * 60}")
        sys.exit(0 if passed else 1)

if __name__ == "__main__":
    SmokeG4().run()
