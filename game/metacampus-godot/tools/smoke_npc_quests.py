#!/usr/bin/env python3
"""MetaCampus NPC Quest Smoke Test
Checks NPC quest_ids exist in quests.json, each NPC binds core metrics, and T1-T8 are fully covered.
Output: reports/smoke_npc_quests.json
"""
import json
import sys
from pathlib import Path

PROJECT_DIR = Path(__file__).parent.parent
NPCS_DIR = PROJECT_DIR / "data" / "npcs"
QUESTS_PATH = PROJECT_DIR / "data" / "quests.json"
REPORT_PATH = PROJECT_DIR / "reports" / "smoke_npc_quests.json"

NPC_IDS = [
    "admissions_director",
    "compliance_officer",
    "homeroom_teacher",
    "it_operator",
    "logistics_manager",
    "parent_representative",
    "principal",
    "student_representative",
]

# 4 core metric IDs
CORE_METRICS = {"school_efficiency", "parent_trust", "compliance_safety", "system_stability"}

# Expected T1-T8 quest IDs (all 8 quests in quests.json)
# These are the 8 quests that must be covered by NPCs
EXPECTED_QUEST_IDS = [
    "q_admission_001",       # T1
    "q_admission_002",       # T2
    "q_material_reminder_001",  # T3
    "q_leave_request_001",   # T4
    "q_meal_count_001",      # T5
    "q_repair_order_001",    # T6
    "q_dashboard_001",       # T7
    "q_canary_release_001",  # T8
]


class SmokeNpcQuests:
    def __init__(self):
        self.results = {}
        self.failures = []
        self.valid_quest_ids = set()
        self.npc_quest_map: dict[str, list[str]] = {}

    def check(self, name: str, condition: bool, detail: str = ""):
        self.results[name] = condition
        if condition:
            print(f"  ✅ {name}")
        else:
            print(f"  ❌ {name} — {detail}")
            self.failures.append(f"{name}: {detail}")

    def run(self):
        print("=" * 60)
        print("MetaCampus NPC Quest Smoke Test")
        print("=" * 60)

        self._load_quests()
        self._check_npc_quest_ids()
        self._check_core_metric_binding()
        self._check_t1_t8_coverage()

        self._write_report()

    def _load_quests(self):
        """Load all quest IDs from quests.json."""
        print("\n── Load Quest Definitions ──")

        try:
            with open(QUESTS_PATH, "r", encoding="utf-8") as f:
                quests = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError) as e:
            self.check("quests_json_load", False, str(e))
            return
        self.check("quests_json_load", True)

        if not isinstance(quests, list) or len(quests) == 0:
            self.check("quests_json_is_array", False, f"got {type(quests).__name__}")
            return
        self.check("quests_json_is_array", True, f"loaded {len(quests)} quests")

        self.valid_quest_ids = {q["quest_id"] for q in quests if "quest_id" in q}
        self.check(
            "quests_all_have_ids",
            len(self.valid_quest_ids) == len(quests),
            f"{len(self.valid_quest_ids)}/{len(quests)} have quest_id",
        )

    def _check_npc_quest_ids(self):
        """For each NPC, verify quest_ids reference valid quest IDs."""
        print("\n── NPC Quest ID Validation ──")

        for npc_id in NPC_IDS:
            filename = f"npc_{npc_id}.json"
            filepath = NPCS_DIR / filename

            if not filepath.exists():
                self.check(f"npc_{npc_id}_profile_exists", False, f"missing: {filepath}")
                continue

            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except json.JSONDecodeError as e:
                self.check(f"npc_{npc_id}_profile_parse", False, str(e))
                continue

            quest_ids = data.get("quest_ids", [])
            self.npc_quest_map[npc_id] = quest_ids

            if not isinstance(quest_ids, list) or len(quest_ids) == 0:
                self.check(
                    f"npc_{npc_id}_has_quest_ids",
                    False,
                    f"quest_ids empty or missing",
                )
                continue
            self.check(
                f"npc_{npc_id}_has_quest_ids",
                True,
                f"{len(quest_ids)} quest(s): {quest_ids}",
            )

            for qid in quest_ids:
                valid = qid in self.valid_quest_ids if self.valid_quest_ids else True
                self.check(
                    f"npc_{npc_id}_quest_{qid}_exists",
                    valid,
                    f"quest_id {qid!r} not found in quests.json" if not valid else "",
                )

    def _check_core_metric_binding(self):
        """Verify each NPC binds a core metric via primary_metric."""
        print("\n── Core Metric Binding ──")

        for npc_id in NPC_IDS:
            filename = f"npc_{npc_id}.json"
            filepath = NPCS_DIR / filename

            if not filepath.exists():
                continue

            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except json.JSONDecodeError:
                continue

            primary = data.get("primary_metric")
            if not primary:
                self.check(
                    f"npc_{npc_id}_has_primary_metric",
                    False,
                    "primary_metric is missing or empty",
                )
                continue

            valid = primary in CORE_METRICS
            self.check(
                f"npc_{npc_id}_primary_metric_valid",
                valid,
                f"got {primary!r}, expected one of {CORE_METRICS}" if not valid else "",
            )

            # Check secondary_metric if present
            secondary = data.get("secondary_metric")
            if secondary:
                valid_sec = secondary in CORE_METRICS
                self.check(
                    f"npc_{npc_id}_secondary_metric_valid",
                    valid_sec,
                    f"got {secondary!r}, expected one of {CORE_METRICS}" if not valid_sec else "",
                )

    def _check_t1_t8_coverage(self):
        """Verify all 8 quests (T1-T8) are covered by at least one NPC."""
        print("\n── T1-T8 Quest Coverage ──")

        if not self.valid_quest_ids:
            self.check("coverage_t1_t8", False, "no valid quest IDs loaded")
            return

        # Collect all quest IDs assigned across all NPCs
        all_assigned = set()
        for npc_id, quest_ids in self.npc_quest_map.items():
            all_assigned.update(quest_ids)

        # Also check if expected T1-T8 quests exist in quests.json
        for qid in EXPECTED_QUEST_IDS:
            in_quests_json = qid in self.valid_quest_ids
            self.check(
                f"quest_def_{qid}_exists",
                in_quests_json,
                f"missing from quests.json" if not in_quests_json else "",
            )

        # Check each T1-T8 quest is covered by at least one NPC
        all_covered = True
        for qid in EXPECTED_QUEST_IDS:
            covered = qid in all_assigned
            covering_npcs = [nid for nid, qids in self.npc_quest_map.items() if qid in qids]
            self.check(
                f"coverage_{qid}",
                covered,
                f"not assigned to any NPC" if not covered else f"covered by {covering_npcs}",
            )
            if not covered:
                all_covered = False

        # Summary: all T1-T8 covered?
        covered_count = sum(1 for qid in EXPECTED_QUEST_IDS if qid in all_assigned)
        self.check(
            "coverage_all_t1_t8",
            all_covered,
            f"{covered_count}/{len(EXPECTED_QUEST_IDS)} quests covered",
        )

        # Print coverage matrix
        print("\n── Quest Coverage Matrix ──")
        for qid in EXPECTED_QUEST_IDS:
            covering = [nid for nid, qids in self.npc_quest_map.items() if qid in qids]
            status = "✅" if covering else "❌"
            print(f"  {status} {qid}: {covering if covering else 'UNCOVERED'}")

    def _write_report(self):
        passed = all(self.results.values())
        report = {
            "phase": "NPC-Quests",
            "result": "PASS" if passed else "FAIL",
            "checks_total": len(self.results),
            "checks_passed": sum(1 for v in self.results.values() if v),
            "checks_failed": sum(1 for v in self.results.values() if not v),
            "checks": self.results,
            "failures": self.failures,
            "coverage_matrix": {
                qid: [nid for nid, qids in self.npc_quest_map.items() if qid in qids]
                for qid in EXPECTED_QUEST_IDS
            },
        }

        REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(REPORT_PATH, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)

        print(f"\n{'=' * 60}")
        print(f"Result: {'✅ PASS' if passed else '❌ FAIL'}")
        print(f"Checks: {report['checks_passed']}/{report['checks_total']} passed")
        if self.failures:
            print(f"Failures ({len(self.failures)}):")
            for failure in self.failures:
                print(f"  - {failure}")
        print(f"Report: {REPORT_PATH}")
        print(f"{'=' * 60}")

        sys.exit(0 if passed else 1)


if __name__ == "__main__":
    SmokeNpcQuests().run()
