#!/usr/bin/env python3
"""MetaCampus NPC Asset Smoke Test
Checks 8 NPC profile JSONs, persona files, and dialogue files exist and have required fields.
Output: reports/smoke_npc_assets.json
"""
import json
import sys
from pathlib import Path

PROJECT_DIR = Path(__file__).parent.parent
NPCS_DIR = PROJECT_DIR / "data" / "npcs"
PERSONAS_DIR = PROJECT_DIR / "data" / "personas"
DIALOGUES_DIR = PROJECT_DIR / "data" / "dialogues"
REPORT_PATH = PROJECT_DIR / "reports" / "smoke_npc_assets.json"

# The 8 extended NPCs (file names match npc_id)
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

# Required fields in each NPC profile JSON
REQUIRED_FIELDS = [
    "npc_id",
    "display_name",
    "role",
    "location",
    "quest_ids",
    "primary_metric",
    "metric_effects",
]

# 4 core metric IDs
CORE_METRICS = {"school_efficiency", "parent_trust", "compliance_safety", "system_stability"}


class SmokeNpcAssets:
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
        print("MetaCampus NPC Asset Smoke Test")
        print("=" * 60)

        self._check_directories_exist()
        self._check_npc_profiles()
        self._check_persona_files()
        self._check_dialogue_files()

        self._write_report()

    def _check_directories_exist(self):
        print("\n── Directory Existence ──")
        for name, path in [
            ("npcs_dir", NPCS_DIR),
            ("personas_dir", PERSONAS_DIR),
            ("dialogues_dir", DIALOGUES_DIR),
        ]:
            self.check(f"dir_{name}", path.is_dir(), f"missing: {path}")

    def _check_npc_profiles(self):
        print("\n── NPC Profile Files ──")

        for npc_id in NPC_IDS:
            filename = f"npc_{npc_id}.json"
            filepath = NPCS_DIR / filename

            # File exists and is valid JSON
            if not filepath.exists():
                self.check(f"npc_profile_{npc_id}_exists", False, f"missing: {filepath}")
                continue
            self.check(f"npc_profile_{npc_id}_exists", True)

            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except json.JSONDecodeError as e:
                self.check(f"npc_profile_{npc_id}_json_parse", False, str(e))
                continue
            self.check(f"npc_profile_{npc_id}_json_parse", True)

            # Required fields
            for field in REQUIRED_FIELDS:
                present = field in data
                if field == "npc_id":
                    present = present and data[field] == npc_id
                    self.check(
                        f"npc_{npc_id}_field_{field}",
                        present,
                        f"expected {npc_id!r}, got {data.get(field)!r}" if not present else "",
                    )
                elif field == "quest_ids":
                    present = present and isinstance(data[field], list) and len(data[field]) > 0
                    self.check(
                        f"npc_{npc_id}_field_{field}",
                        present,
                        f"got {data.get(field)!r}" if not present else "",
                    )
                elif field == "primary_metric":
                    present = present and data[field] in CORE_METRICS
                    self.check(
                        f"npc_{npc_id}_field_{field}",
                        present,
                        f"got {data.get(field)!r}, expected one of {CORE_METRICS}" if not present else "",
                    )
                elif field == "metric_effects":
                    present = present and isinstance(data[field], dict)
                    self.check(
                        f"npc_{npc_id}_field_{field}",
                        present,
                        f"got {type(data.get(field)).__name__}" if not present else "",
                    )
                else:
                    present = present and bool(data[field])
                    self.check(
                        f"npc_{npc_id}_field_{field}",
                        present,
                        f"got {data.get(field)!r}" if not present else "",
                    )

            # Validate metric_effects keys are valid core metrics
            if "metric_effects" in data and isinstance(data["metric_effects"], dict):
                for effect_key, effect_value in data["metric_effects"].items():
                    if isinstance(effect_value, dict):
                        for metric_id in effect_value:
                            valid = metric_id in CORE_METRICS
                            self.check(
                                f"npc_{npc_id}_metric_effect_{effect_key}_{metric_id}_valid",
                                valid,
                                f"unknown metric {metric_id!r}" if not valid else "",
                            )

    def _check_persona_files(self):
        print("\n── Persona Markdown Files ──")

        for npc_id in NPC_IDS:
            # Persona filename uses the short name (not npc_ prefix)
            filename = f"{npc_id}.md"
            filepath = PERSONAS_DIR / filename

            exists = filepath.exists()
            self.check(f"persona_{npc_id}_exists", exists, f"missing: {filepath}")

            if exists:
                # Check file is not empty
                content = filepath.read_text(encoding="utf-8").strip()
                self.check(
                    f"persona_{npc_id}_not_empty",
                    len(content) > 0,
                    f"empty file: {filepath}",
                )

    def _check_dialogue_files(self):
        print("\n── Dialogue JSON Files ──")

        for npc_id in NPC_IDS:
            filename = f"{npc_id}_dialogues.json"
            filepath = DIALOGUES_DIR / filename

            exists = filepath.exists()
            self.check(f"dialogue_{npc_id}_exists", exists, f"missing: {filepath}")

            if exists:
                try:
                    with open(filepath, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    self.check(f"dialogue_{npc_id}_json_parse", True)

                    # Basic structure check
                    has_dialogues = "dialogues" in data and isinstance(data["dialogues"], list) and len(data["dialogues"]) > 0
                    self.check(
                        f"dialogue_{npc_id}_has_entries",
                        has_dialogues,
                        f"dialogues array empty or missing",
                    )

                    # Check npc_id matches
                    npc_id_match = data.get("npc_id") == npc_id
                    self.check(
                        f"dialogue_{npc_id}_id_match",
                        npc_id_match,
                        f"expected {npc_id!r}, got {data.get('npc_id')!r}",
                    )

                except json.JSONDecodeError as e:
                    self.check(f"dialogue_{npc_id}_json_parse", False, str(e))

    def _write_report(self):
        passed = all(self.results.values())
        report = {
            "phase": "NPC-Assets",
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
    SmokeNpcAssets().run()
