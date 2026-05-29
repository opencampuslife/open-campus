#!/usr/bin/env python3
"""MetaCampus NPC Dialogue Smoke Test
Checks all 8 dialogue JSON files: parse, required fields, metric_effects range, quest markers.
Output: reports/smoke_npc_dialogues.json
"""
import json
import sys
from pathlib import Path

PROJECT_DIR = Path(__file__).parent.parent
DIALOGUES_DIR = PROJECT_DIR / "data" / "dialogues"
QUESTS_PATH = PROJECT_DIR / "data" / "quests.json"
REPORT_PATH = PROJECT_DIR / "reports" / "smoke_npc_dialogues.json"

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

# Required fields per dialogue entry
DIALOGUE_REQUIRED_FIELDS = ["id", "trigger", "speaker", "text", "choices"]

# Required fields per choice entry
CHOICE_REQUIRED_FIELDS = ["text", "action", "metric_effects", "next_line"]

# Valid trigger values
VALID_TRIGGERS = {"quest_start", "quest_trigger"}


class SmokeNpcDialogues:
    def __init__(self):
        self.results = {}
        self.failures = []
        self.valid_quest_ids = set()

    def check(self, name: str, condition: bool, detail: str = ""):
        self.results[name] = condition
        if condition:
            print(f"  ✅ {name}")
        else:
            print(f"  ❌ {name} — {detail}")
            self.failures.append(f"{name}: {detail}")

    def run(self):
        print("=" * 60)
        print("MetaCampus NPC Dialogue Smoke Test")
        print("=" * 60)

        self._load_valid_quest_ids()
        self._check_all_dialogues()

        self._write_report()

    def _load_valid_quest_ids(self):
        """Load quest IDs from quests.json for cross-referencing."""
        try:
            with open(QUESTS_PATH, "r", encoding="utf-8") as f:
                quests = json.load(f)
            self.valid_quest_ids = {q["quest_id"] for q in quests}
            self.check(
                "quests_json_loaded",
                len(self.valid_quest_ids) > 0,
                f"loaded {len(self.valid_quest_ids)} quest IDs",
            )
        except (FileNotFoundError, json.JSONDecodeError, KeyError) as e:
            self.check("quests_json_loaded", False, str(e))

    def _check_all_dialogues(self):
        print("\n── Dialogue File Checks ──")

        for npc_id in NPC_IDS:
            filename = f"{npc_id}_dialogues.json"
            filepath = DIALOGUES_DIR / filename

            if not filepath.exists():
                self.check(f"dlg_{npc_id}_file_exists", False, f"missing: {filepath}")
                continue
            self.check(f"dlg_{npc_id}_file_exists", True)

            # Parse JSON
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except json.JSONDecodeError as e:
                self.check(f"dlg_{npc_id}_json_parse", False, str(e))
                continue
            self.check(f"dlg_{npc_id}_json_parse", True)

            # Top-level fields
            self.check(
                f"dlg_{npc_id}_has_npc_id",
                "npc_id" in data and data["npc_id"] == npc_id,
                f"expected {npc_id!r}, got {data.get('npc_id')!r}",
            )

            dialogues = data.get("dialogues", [])
            self.check(
                f"dlg_{npc_id}_has_dialogues_array",
                isinstance(dialogues, list) and len(dialogues) > 0,
                f"got {type(dialogues).__name__} with {len(dialogues) if isinstance(dialogues, list) else '?'} entries",
            )

            for idx, dlg in enumerate(dialogues):
                prefix = f"dlg_{npc_id}_entry{idx}"
                self._check_dialogue_entry(prefix, dlg)
                self._check_choices(prefix, dlg.get("choices", []))

    def _check_dialogue_entry(self, prefix: str, dlg: dict):
        """Check a single dialogue entry for required fields and valid values."""

        # Required fields
        for field in DIALOGUE_REQUIRED_FIELDS:
            present = field in dlg and bool(dlg[field]) if field != "choices" else field in dlg
            if field == "id":
                present = present and isinstance(dlg[field], str) and len(dlg[field]) > 0
                self.check(
                    f"{prefix}_field_{field}",
                    present,
                    f"got {dlg.get(field)!r}" if not present else "",
                )
            elif field == "trigger":
                present = present and dlg[field] in VALID_TRIGGERS
                self.check(
                    f"{prefix}_field_{field}",
                    present,
                    f"got {dlg.get(field)!r}, expected one of {VALID_TRIGGERS}" if not present else "",
                )
            elif field == "text":
                present = present and isinstance(dlg[field], str) and len(dlg[field]) > 0
                self.check(
                    f"{prefix}_field_{field}",
                    present,
                    f"got {type(dlg.get(field)).__name__}" if not present else "",
                )
            elif field == "choices":
                present = present and isinstance(dlg[field], list) and len(dlg[field]) >= 1
                self.check(
                    f"{prefix}_field_{field}",
                    present,
                    f"got {len(dlg[field]) if isinstance(dlg.get(field), list) else 'not a list'} choices" if not present else "",
                )
            else:
                self.check(
                    f"{prefix}_field_{field}",
                    present,
                    f"missing or empty" if not present else "",
                )

        # Check trigger_quest validity if present
        if "trigger_quest" in dlg:
            tq = dlg["trigger_quest"]
            if tq is None or tq == "":
                # null or empty = intentionally unbound, skip validation
                pass
            else:
                valid = tq in self.valid_quest_ids if self.valid_quest_ids else True
                self.check(
                    f"{prefix}_trigger_quest_valid",
                    valid,
                    f"unknown quest_id {tq!r}" if not valid else "",
                )

    def _check_choices(self, prefix: str, choices: list):
        """Check all choices in a dialogue entry."""
        for cidx, choice in enumerate(choices):
            if not isinstance(choice, dict):
                self.check(
                    f"{prefix}_choice{cidx}_is_dict",
                    False,
                    f"got {type(choice).__name__}",
                )
                continue

            cp = f"{prefix}_choice{cidx}"

            # Required choice fields
            for field in CHOICE_REQUIRED_FIELDS:
                present = field in choice
                if field == "text":
                    present = present and isinstance(choice[field], str) and len(choice[field]) > 0
                elif field == "action":
                    present = present and isinstance(choice[field], str) and len(choice[field]) > 0
                elif field == "metric_effects":
                    present = present and isinstance(choice[field], dict)
                elif field == "next_line":
                    present = present and isinstance(choice[field], int)
                self.check(
                    f"{cp}_field_{field}",
                    present,
                    f"got {choice.get(field)!r}" if not present else "",
                )

            # Check metric_effects range [-25, +25]
            me = choice.get("metric_effects", {})
            if isinstance(me, dict):
                for metric_id, value in me.items():
                    # Validate metric_id
                    if metric_id not in CORE_METRICS:
                        self.check(
                            f"{cp}_metric_{metric_id}_valid_id",
                            False,
                            f"unknown metric {metric_id!r}",
                        )
                        continue

                    # Validate range
                    if not isinstance(value, (int, float)):
                        self.check(
                            f"{cp}_metric_{metric_id}_range",
                            False,
                            f"value is {type(value).__name__}, not number",
                        )
                    elif value < -25 or value > 25:
                        self.check(
                            f"{cp}_metric_{metric_id}_range",
                            False,
                            f"value {value} out of range [-25, +25]",
                        )
                    else:
                        self.check(
                            f"{cp}_metric_{metric_id}_range",
                            True,
                        )

            # Check quest markers (complete_quest / fail_quest) reference valid quests
            for qfield in ("complete_quest", "fail_quest"):
                if qfield in choice:
                    qval = choice[qfield]
                    valid = qval in self.valid_quest_ids if self.valid_quest_ids else True
                    self.check(
                        f"{cp}_{qfield}_valid",
                        valid,
                        f"unknown quest_id {qval!r}" if not valid else "",
                    )

    def _write_report(self):
        passed = all(self.results.values())
        report = {
            "phase": "NPC-Dialogues",
            "result": "PASS" if passed else "FAIL",
            "checks_total": len(self.results),
            "checks_passed": sum(1 for v in self.results.values() if v),
            "checks_failed": sum(1 for v in self.results.values() if not v),
            "checks": self.results,
            "failures": self.failures,
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
    SmokeNpcDialogues().run()
