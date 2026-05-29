#!/usr/bin/env python3
"""MetaCampus G3 Smoke Test — API Bridge mock/live
Tests ApiClient via TestHarness /api/ask and /api/mode endpoints.
Output: reports/g3_smoke_report.json
"""
import json
import sys
import time
import urllib.request
import urllib.error
import urllib.parse
from pathlib import Path

BASE = "http://127.0.0.1:16007"
REPORT_PATH = Path(__file__).parent.parent / "reports" / "g3_smoke_report.json"

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

class SmokeG3:
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
        print("MetaCampus G3 API Bridge Smoke Test")
        print("=" * 60)

        self._test_mode_switching()
        self._test_mock_knowledge()
        self._test_high_risk_guard()
        self._test_mode_off()
        self._test_g2_regression()

        self._write_report()

    def _test_mode_switching(self):
        print("\n── Mode Switching ──")

        # Get current mode
        r = request("/api/mode")
        self.check("mode_readable", r.get("status") == "ok", f"got {r}")
        print(f"    current: {r.get('mode', 'unknown')}")

        # Switch to mock explicitly
        r = request("/api/mode?set=mock")
        self.check("mode_set_mock", r.get("mode") == "mock", f"got {r}")

        # Switch to live
        r = request("/api/mode?set=live")
        self.check("mode_set_live", r.get("mode") == "live", f"got {r}")

        # Switch back to mock for tests
        request("/api/mode?set=mock")

    def _test_mock_knowledge(self):
        print("\n── Mock: Knowledge Ask ──")
        request("/api/mode?set=mock")
        time.sleep(0.1)

        # T1: 报名材料
        r = request("/api/ask?q=" + urllib.parse.quote("报名需要哪些材料"))
        self.check("mock_q_admission",
                    r.get("ok") == True,
                    f"got {r}")
        self.check("mock_q_admission_answer",
                    len(r.get("answer", "")) > 10,
                    f"answer too short: '{r.get('answer', '')}'")
        self.check("mock_q_admission_citations",
                    len(r.get("citations", [])) > 0,
                    f"no citations")
        self.check("mock_q_admission_no_handoff",
                    r.get("handoff_required") != True,
                    f"unexpected handoff: {r.get('handoff_required')}")

        # T2: 保证录取
        r = request("/api/ask?q=" + urllib.parse.quote("能不能保证录取"))
        self.check("mock_q_guarantee_handoff",
                    r.get("handoff_required") == True,
                    f"expected handoff_required=true, got {r}")
        self.check("mock_q_guarantee_reason",
                    len(r.get("handoff_reason", "")) > 0,
                    f"missing handoff_reason: {r}")

        # Default query
        r = request("/api/ask?q=" + urllib.parse.quote("今天天气怎么样"))
        self.check("mock_q_default_ok",
                    r.get("ok") == True,
                    f"got {r}")

    def _test_high_risk_guard(self):
        print("\n── High Risk Safety Guard ──")

        # "保证录取" — must be intercepted regardless of mode
        for kw in ["保证录取", "内部名额", "特殊照顾", "走后门", "包进"]:
            r = request("/api/ask?q=" + urllib.parse.quote(kw))
            self.check(f"guard_{kw}",
                        r.get("handoff_required") == True,
                        f"expected handoff for '{kw}', got {r.get('handoff_required')}")

    def _test_mode_off(self):
        print("\n── Mode OFF ──")
        request("/api/mode?set=off")
        time.sleep(0.1)

        r = request("/api/ask?q=" + urllib.parse.quote("报名需要哪些材料"))
        self.check("off_q_ok_false",
                    r.get("ok") == False,
                    f"expected ok=false in off mode, got {r}")

        # Restore mock
        request("/api/mode?set=mock")

    def _test_g2_regression(self):
        print("\n── G2 Regression (quick) ──")
        request("/reset")
        time.sleep(0.2)

        m = request("/metrics")
        mt = m.get("metrics", {})
        self.check("g2_init_metrics",
                    mt.get("school_efficiency") == 40 and
                    mt.get("compliance_safety") == 70,
                    f"got {mt}")

        # Run one task flow
        request("/dialogue/start?npc_id=parent_001")
        time.sleep(0.2)
        request("/dialogue/choose?index=0")
        time.sleep(0.2)

        m2 = request("/metrics")
        mt2 = m2.get("metrics", {})
        self.check("g2_t1_parent_trust",
                    mt2.get("parent_trust", 0) >= 58,
                    f"parent_trust={mt2.get('parent_trust')}")

    def _write_report(self):
        passed = all(self.results.values())
        report = {
            "phase": "G3",
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
    SmokeG3().run()
