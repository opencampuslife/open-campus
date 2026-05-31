#!/usr/bin/env python3
"""MetaCampus G2 Automated Smoke Test — Phase G2.1
Tests all game systems via TestHarness HTTP endpoints.
Output: reports/g2_smoke_report.json
"""
import json
import sys
import time
import urllib.request
import urllib.error
from pathlib import Path

BASE = "http://127.0.0.1:16007"
REPORT_PATH = Path(__file__).parent.parent / "reports" / "g2_smoke_report.json"

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
    except Exception as e:
        return {"_error": str(e)}

class SmokeTest:
    def __init__(self):
        self.results = {}
        self.failures = []

    def check(self, name: str, condition: bool, detail: str = ""):
        self.results[name] = condition
        if condition:
            print(f"  ✅ {name}")
        else:
            print(f"  ❌ {name} — {detail}")
            self.failures.append(f"{name}: {detail}")

    def run(self):
        print("=" * 60)
        print("MetaCampus G2.1 Automated Smoke Test")
        print("=" * 60)

        self._layer1_health()
        self._layer2_controls()
        self._layer3_t1_correct()
        self._layer3_t2_error()
        self._layer3_t2_correct()
        self._layer3_t3_reminder()
        self._layer3_t8_canary()
        self._layer4_ui()

        self._write_report()

    # ── Layer 1: System Health ──

    def _layer1_health(self):
        print("\n── Layer 1: System Health ──")

        # Health check
        h = request("/health")
        self.check("harness_health", h.get("status") == "ok",
                    f"got {h}")

        # Reset to known state
        r = request("/reset")
        self.check("reset_ok", r.get("status") == "ok",
                    f"got {r}")
        time.sleep(0.3)

        # Initial metrics
        m = request("/metrics")
        metrics = m.get("metrics", {})
        self.check("initial_school_efficiency",
                    metrics.get("school_efficiency") == 40,
                    f"got {metrics.get('school_efficiency')}")
        self.check("initial_parent_trust",
                    metrics.get("parent_trust") == 50,
                    f"got {metrics.get('parent_trust')}")
        self.check("initial_compliance_safety",
                    metrics.get("compliance_safety") == 70,
                    f"got {metrics.get('compliance_safety')}")
        self.check("initial_system_stability",
                    metrics.get("system_stability") == 60,
                    f"got {metrics.get('system_stability')}")

        # Store for later delta checks
        self._baseline = metrics.copy()

    # ── Layer 2: Basic Controls ──

    def _layer2_controls(self):
        print("\n── Layer 2: Basic Controls ──")

        for direction in ["up", "down", "left", "right"]:
            r = request(f"/move?dir={direction}")
            self.check(f"move_{direction}",
                        r.get("status") == "ok",
                        f"got {r}")

        r = request("/interact")
        self.check("interact", r.get("status") == "ok", f"got {r}")

        r = request("/key?name=toggle_taskboard")
        self.check("key_tab", r.get("status") == "ok", f"got {r}")

        r = request("/key?name=ui_cancel")
        self.check("key_esc", r.get("status") == "ok", f"got {r}")

        r = request("/teleport?x=480&y=288")
        self.check("teleport", r.get("status") == "ok", f"got {r}")

    # ── Layer 3: Task Logic ──

    def _layer3_t1_correct(self):
        print("\n── Layer 3: T1 知识库回答 ──")
        request("/reset")
        time.sleep(0.2)

        self._baseline = request("/metrics").get("metrics", {})

        # Start dialogue with parent
        ds = request("/dialogue/start?npc_id=parent_001")
        self.check("t1_dialogue_start",
                    ds.get("status") == "ok",
                    f"got {ds}")
        self.check("t1_has_choices",
                    ds.get("choices_count", 0) >= 1,
                    f"choices={ds.get('choices_count')}")
        time.sleep(0.2)

        # Choose "知识库回答" (index 0)
        dc = request("/dialogue/choose?index=0")
        self.check("t1_choose_ok",
                    dc.get("status") == "ok",
                    f"got {dc}")
        time.sleep(0.2)

        # Verify metric changes
        m = request("/metrics")
        metrics = m.get("metrics", {})
        pt = metrics.get("parent_trust", 0) - self._baseline.get("parent_trust", 0)
        cs = metrics.get("compliance_safety", 0) - self._baseline.get("compliance_safety", 0)

        self.check("t1_parent_trust_+8",
                    pt >= 8,
                    f"got delta={pt} (expected >=8)")
        self.check("t1_compliance_safety_+5",
                    cs >= 5,
                    f"got delta={cs} (expected >=5)")

    def _layer3_t2_error(self):
        print("\n── Layer 3: T2 错误分支 (保证录取) ──")
        request("/reset")
        time.sleep(0.2)

        # Start parent dialogue
        request("/dialogue/start?npc_id=parent_001")
        time.sleep(0.2)

        # T1 first (needed to reach line 1)
        request("/dialogue/choose?index=0")  # T1 correct
        time.sleep(0.3)

        # Now at line 1: 保证录取
        # Choose error branch: index 1 ("这个我帮您问问……")
        dc = request("/dialogue/choose?index=1")
        self.check("t2_error_choose_ok",
                    dc.get("status") == "ok",
                    f"got {dc}")
        time.sleep(0.2)

        m = request("/metrics")
        metrics = m.get("metrics", {})
        cs = metrics.get("compliance_safety", 0)

        # After reset=70, T1:+5=75, T2 error:-20=55
        self.check("t2_error_compliance_dropped",
                    cs <= 55,
                    f"compliance_safety={cs} (expected <=55 after T1+5 and T2-20)")

    def _layer3_t2_correct(self):
        print("\n── Layer 3: T2 正确分支 (转人工) ──")
        request("/reset")
        time.sleep(0.2)

        self._baseline = request("/metrics").get("metrics", {})

        request("/dialogue/start?npc_id=parent_001")
        time.sleep(0.2)
        request("/dialogue/choose?index=0")  # T1
        time.sleep(0.3)

        # Choose correct branch: index 0 ("不能承诺录取")
        dc = request("/dialogue/choose?index=0")
        self.check("t2_correct_choose_ok",
                    dc.get("status") == "ok",
                    f"got {dc}")
        time.sleep(0.2)

        m = request("/metrics")
        metrics = m.get("metrics", {})
        cs = metrics.get("compliance_safety", 0)
        pt = metrics.get("parent_trust", 0)

        # 70 + 5(T1) + 10(T2) = 85
        self.check("t2_correct_compliance_up",
                    cs >= 85,
                    f"compliance_safety={cs}")
        # 50 + 8(T1) + 6(T2) = 64
        self.check("t2_correct_parent_trust_up",
                    pt >= 64,
                    f"parent_trust={pt}")

    def _layer3_t3_reminder(self):
        print("\n── Layer 3: T3 材料催办 ──")
        request("/reset")
        time.sleep(0.2)

        self._baseline = request("/metrics").get("metrics", {})

        # Start parent_001 at line 2 (材料催办) — T2 closes dialogue, can't chain
        ds = request("/dialogue/start?npc_id=parent_001&line=2")
        self.check("t3_dialogue_start",
                    ds.get("status") == "ok",
                    f"got {ds}")
        time.sleep(0.2)

        # Choose "自动提醒催办" (index 0)
        dc = request("/dialogue/choose?index=0")
        self.check("t3_choose_ok",
                    dc.get("status") == "ok",
                    f"got {dc}")
        time.sleep(0.2)

        m = request("/metrics")
        metrics = m.get("metrics", {})
        se = metrics.get("school_efficiency", 0)

        # 40 + 8(T3) = 48
        self.check("t3_school_efficiency_up",
                    se >= 48,
                    f"school_efficiency={se} (expected >=48)")

    def _layer3_t8_canary(self):
        print("\n── Layer 3: T8 Canary 发布 ──")
        request("/reset")
        time.sleep(0.2)

        self._baseline = request("/metrics").get("metrics", {})

        # Start AI Assistant at line 1 (Canary release) — line 0 closes dialogue, can't chain
        ds = request("/dialogue/start?npc_id=ai_assistant_001&line=1")
        self.check("t8_dialogue_start",
                    ds.get("status") == "ok",
                    f"got {ds}")
        time.sleep(0.2)

        # Choose "1%灰度发布" (index 0)
        dc = request("/dialogue/choose?index=0")
        self.check("t8_canary_choose",
                    dc.get("status") == "ok",
                    f"got {dc}")
        time.sleep(0.2)

        m = request("/metrics")
        metrics = m.get("metrics", {})
        ss = metrics.get("system_stability", 0)
        cs = metrics.get("compliance_safety", 0)

        # 60 + 12(T8) = 72
        self.check("t8_system_stability_up",
                    ss >= 72,
                    f"system_stability={ss} (expected >=72)")
        # 70 + 8(T8) = 78
        self.check("t8_compliance_safety_up",
                    cs >= 78,
                    f"compliance_safety={cs} (expected >=78)")

    # ── Layer 4: UI Observability ──

    def _layer4_ui(self):
        print("\n── Layer 4: UI Observability ──")

        # Quest listing
        r = request("/quests")
        quests = r.get("quests", [])
        self.check("quests_listed",
                    len(quests) >= 8,
                    f"got {len(quests)} quests")

        # TaskBoard toggle
        r = request("/taskboard")
        self.check("taskboard_toggle",
                    r.get("status") == "ok",
                    f"got {r}")

        # Dashboard toggle
        r = request("/dashboard")
        self.check("dashboard_toggle",
                    r.get("status") == "ok",
                    f"got {r}")

        # Status check
        r = request("/status")
        self.check("status_ok",
                    r.get("status") == "ok",
                    f"got {r}")

    # ── Report ──

    def _write_report(self):
        passed = all(self.results.values())
        report = {
            "phase": "G2.1",
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
        print(f"Checks: {report['checks_passed']}/{report['checks_total']} passed")
        if self.failures:
            print(f"Failures ({len(self.failures)}):")
            for f in self.failures:
                print(f"  - {f}")
        print(f"Report: {REPORT_PATH}")
        print(f"{'=' * 60}")

        sys.exit(0 if passed else 1)


if __name__ == "__main__":
    SmokeTest().run()
