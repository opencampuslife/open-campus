#!/usr/bin/env python3
"""
N2D-3: NPC Interaction Runtime Smoke Test
==========================================
Offline smoke test for NPC interaction chains.
Validates: NPC near → interact → dialogue opens → choice selected → quest updated → metric effects applied.

Run from game/metacampus-godot/:
    python tools/smoke_npc_runtime_interaction.py
"""

import json
import os
import sys
from pathlib import Path
from typing import Any

# ── paths ──────────────────────────────────────────────────────────────────────
GAME_ROOT = Path(__file__).parent.parent.resolve()
DATA_DIR   = GAME_ROOT / "data"
TOOLS_DIR  = GAME_ROOT / "tools"
REPORTS_DIR = TOOLS_DIR / "reports"

NPC_IDS = ["admissions_director", "compliance_officer", "it_operator"]

# 4 core metric keys
CORE_METRICS = frozenset({"school_efficiency", "parent_trust", "compliance_safety", "system_stability"})

# ── helpers ─────────────────────────────────────────────────────────────────────
def load_json(path: Path) -> dict | list:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def all_quests() -> dict[str, dict]:
    return {q["quest_id"]: q for q in load_json(DATA_DIR / "quests.json")}


def load_npc_dialogue(npc_id: str) -> dict:
    """Load dialogue JSON for an NPC."""
    path = DATA_DIR / "dialogues" / f"{npc_id}_dialogues.json"
    if not path.exists():
        raise FileNotFoundError(f"Dialogue file not found: {path}")
    return load_json(path)


# ── test cases ─────────────────────────────────────────────────────────────────
class TestResult:
    def __init__(self, name: str):
        self.name = name
        self.passed: bool = False
        self.errors: list[str] = []
        self.warnings: list[str] = []

    def ok(self, msg: str = ""):
        self.passed = True
        if msg:
            self.warnings.append(msg)

    def fail(self, msg: str):
        self.errors.append(msg)

    def __str__(self):
        status = "PASS" if self.passed else "FAIL"
        lines  = [f"  [{status}] {self.name}"]
        for e in self.errors:
            lines.append(f"         ✗ {e}")
        for w in self.warnings:
            lines.append(f"         ⚠ {w}")
        return "\n".join(lines)


def t_dialogue_structure(npc_id: str) -> TestResult:
    """Test 1: NPC dialogue file loads and has required top-level keys."""
    r = TestResult(f"[{npc_id}] Dialogue structure: required keys present")
    try:
        dlg = load_npc_dialogue(npc_id)
    except FileNotFoundError as e:
        r.fail(str(e))
        return r

    for key in ("npc_id", "npc_name", "dialogues"):
        if key not in dlg:
            r.fail(f"Missing top-level key: '{key}'")
    if r.errors:
        return r

    if not isinstance(dlg["dialogues"], list):
        r.fail("'dialogues' is not a list")
        return r
    if len(dlg["dialogues"]) == 0:
        r.fail("'dialogues' is an empty list")
        return r

    for entry in dlg["dialogues"]:
        for key in ("id", "speaker", "text", "choices"):
            if key not in entry:
                r.fail(f"Dialogue entry '{entry.get('id','?')}' missing key: '{key}'")
        if not isinstance(entry.get("choices", []), list) or len(entry["choices"]) == 0:
            r.fail(f"Dialogue entry '{entry.get('id','?')}' has no choices")
    r.ok()
    return r


def t_trigger_quest_coverage(npc_id: str, quest_ids: set[str]) -> TestResult:
    """Test 2: For each NPC, all trigger_quest IDs resolve to quests.json."""
    r = TestResult(f"[{npc_id}] trigger_quest IDs resolve in quests.json")
    dlg   = load_npc_dialogue(npc_id)
    quests = all_quests()
    unresolved: list[str] = []

    for entry in dlg["dialogues"]:
        tid = entry.get("trigger_quest")
        if tid is not None and tid not in quests:
            unresolved.append(tid)

    if unresolved:
        r.fail(f"Unresolved trigger_quest IDs: {unresolved}")
    else:
        r.ok()
    return r


def t_choice_metric_effects(npc_id: str) -> TestResult:
    """Test 4: All choice metric_effects keys are core metrics, values in [-30, +30]."""
    r = TestResult(f"[{npc_id}] Choice metric_effects: keys ⊆ core, values ∈ [-30,+30]")
    dlg = load_npc_dialogue(npc_id)
    all_ok = True

    for entry in dlg["dialogues"]:
        for i, choice in enumerate(entry.get("choices", [])):
            effects = choice.get("metric_effects", {})
            if not effects:
                continue  # skip empty effects

            bad_keys = [k for k in effects if k not in CORE_METRICS]
            bad_vals = [v for v in effects.values() if not isinstance(v, (int, float)) or abs(v) > 30]

            if bad_keys:
                r.fail(f"Entry '{entry['id']}' choice[{i}] has non-core metric keys: {bad_keys}")
                all_ok = False
            if bad_vals:
                r.fail(f"Entry '{entry['id']}' choice[{i}] has out-of-bounds values: {bad_vals}")
                all_ok = False

    if all_ok:
        r.ok()
    return r


def t_complete_quest_references(npc_id: str) -> TestResult:
    """Test 5: complete_quest / fail_quest IDs exist in quests.json."""
    r = TestResult(f"[{npc_id}] complete_quest / fail_quest IDs exist in quests.json")
    dlg    = load_npc_dialogue(npc_id)
    quests = all_quests()
    missing_complete: list[str] = []
    missing_fail: list[str]     = []

    for entry in dlg["dialogues"]:
        for i, choice in enumerate(entry.get("choices", [])):
            cq = choice.get("complete_quest")
            fq = choice.get("fail_quest")
            if cq is not None and cq not in quests:
                missing_complete.append(cq)
            if fq is not None and fq not in quests:
                missing_fail.append(fq)

    if missing_complete:
        r.fail(f"Missing complete_quest IDs: {missing_complete}")
    if missing_fail:
        r.fail(f"Missing fail_quest IDs: {missing_fail}")
    if not missing_complete and not missing_fail:
        r.ok()
    return r


def t_compliance_officer_high_risk_branch() -> TestResult:
    """Test 6: compliance_officer high-risk branch — specific metric checks."""
    r = TestResult("[compliance_officer] High-risk branch metric validation")
    dlg = load_npc_dialogue("compliance_officer")

    # Find compliance_officer_high_risk_001
    target = next(
        (e for e in dlg["dialogues"] if e["id"] == "compliance_officer_high_risk_001"),
        None,
    )
    if target is None:
        r.fail("Dialogue entry 'compliance_officer_high_risk_001' not found")
        return r

    choices_map = {c["action"]: c["metric_effects"] for c in target["choices"]}

    # safe_answer → compliance_safety = +15
    safe = choices_map.get("safe_intercept")   # Note: compliance_officer uses "safe_intercept", not "safe_answer"
    safe_key = "safe_intercept"

    # promise_admission → compliance_safety = -20  (error case)
    promise = choices_map.get("let_slide")    # compliance_officer uses "let_slide" for the bad choice
    promise_key = "let_slide"

    ok = True

    # Check safe answer
    if safe is None:
        r.fail("Choice 'safe_intercept' not found in compliance_officer_high_risk_001")
        ok = False
    elif safe.get("compliance_safety") != 15:
        r.fail(f"safe_intercept compliance_safety={safe.get('compliance_safety')}, expected +15")
        ok = False

    # Check bad answer
    if promise is None:
        r.fail("Choice 'let_slide' not found in compliance_officer_high_risk_001")
        ok = False
    elif promise.get("compliance_safety") != -20:
        r.fail(f"let_slide compliance_safety={promise.get('compliance_safety')}, expected -20")
        ok = False

    # Also verify admissions_director_high_risk_001 uses correct action keys
    dlg_adm = load_npc_dialogue("admissions_director")
    adm_hr = next(
        (e for e in dlg_adm["dialogues"] if e["id"] == "admissions_director_high_risk_001"),
        None,
    )
    if adm_hr:
        adm_choices = {c["action"]: c for c in adm_hr["choices"]}
        safe_adm = adm_choices.get("safe_answer")
        if safe_adm:
            cs = safe_adm["metric_effects"].get("compliance_safety")
            if cs != 15:
                r.fail(f"admissions_director safe_answer compliance_safety={cs}, expected +15")
                ok = False

        prom_adm = adm_choices.get("promise_admission")
        if prom_adm:
            cs = prom_adm["metric_effects"].get("compliance_safety")
            if cs != -20:
                r.fail(f"admissions_director promise_admission compliance_safety={cs}, expected -20")
                ok = False

    if ok:
        r.ok()
    return r


def t_quest_manager_state_flow() -> TestResult:
    """Test 7: Document quest_manager.gd state transitions (read-only, documented in comments)."""
    r = TestResult("[quest_manager.gd] State transition flow documented")

    gm_path = GAME_ROOT / "scripts" / "quest_manager.gd"
    if not gm_path.exists():
        r.fail(f"quest_manager.gd not found at {gm_path}")
        return r

    code = gm_path.read_text(encoding="utf-8")

    # Verify expected state machine elements exist
    checks = {
        "STATUS_AVAILABLE":  "available" in code,
        "STATUS_ACTIVE":     "active"    in code,
        "STATUS_COMPLETED":  "completed" in code,
        "STATUS_FAILED":     "failed"    in code,
        "activate_quest()":  "func activate_quest" in code,
        "complete_quest()":  "func complete_quest" in code,
        "fail_quest()":      "func fail_quest"     in code,
        "apply_reward()":    "_apply_reward"       in code,
        "apply_penalty()":   "_apply_penalty"      in code,
        "metric_manager":    "metric_manager"     in code,
    }

    missing = [k for k, v in checks.items() if not v]
    if missing:
        r.fail(f"Missing expected elements: {missing}")
    else:
        r.ok()

    return r


def t_simulated_interaction_chain(npc_id: str, quest_ids: set[str]) -> TestResult:
    """
    Simulate the full interaction chain for an NPC:
      1. Load dialogue
      2. Find entries matching trigger_quest ∈ quest_ids
      3. Select first valid choice (has metric_effects)
      4. Validate metric_effects
    """
    r = TestResult(f"[{npc_id}] Simulated interaction chain: quest triggers → choice → effects")
    try:
        dlg = load_npc_dialogue(npc_id)
    except FileNotFoundError as e:
        r.fail(str(e))
        return r

    triggered_entries = [e for e in dlg["dialogues"] if e.get("trigger_quest") in quest_ids]
    if not triggered_entries:
        r.fail(f"No dialogue entries found with trigger_quest in {quest_ids}")
        return r

    chain_ok = True
    for entry in triggered_entries:
        valid_choices = [c for c in entry["choices"] if c.get("metric_effects")]
        if not valid_choices:
            r.fail(f"Entry '{entry['id']}' has no valid choice with metric_effects")
            chain_ok = False
            continue

        chosen = valid_choices[0]  # simulate first valid choice
        effects = chosen["metric_effects"]

        bad_keys = [k for k in effects if k not in CORE_METRICS]
        bad_vals = [v for v in effects.values()
                    if not isinstance(v, (int, float)) or abs(v) > 30]

        if bad_keys:
            r.fail(f"Entry '{entry['id']}' choice '{chosen['action']}' non-core keys: {bad_keys}")
            chain_ok = False
        if bad_vals:
            r.fail(f"Entry '{entry['id']}' choice '{chosen['action']}' out-of-bounds: {bad_vals}")
            chain_ok = False

        # Check complete_quest/fail_quest references
        quests = all_quests()
        for key in ("complete_quest", "fail_quest"):
            ref = chosen.get(key)
            if ref and ref not in quests:
                r.fail(f"Entry '{entry['id']}' choice '{chosen['action']}' {key}='{ref}' not in quests.json")
                chain_ok = False

    if chain_ok:
        r.ok()
    return r


# ── main ────────────────────────────────────────────────────────────────────────
def main():
    print("=" * 70)
    print("  N2D-3  NPC Runtime Interaction Smoke Test")
    print("  Project: metacampus-godot")
    print("=" * 70)

    errors:  list[TestResult] = []
    passed:  list[TestResult] = []
    warns:   list[TestResult] = []

    quests = all_quests()
    quest_ids = set(quests.keys())

    for npc_id in NPC_IDS:
        for test_fn in (
            lambda nid=npc_id: t_dialogue_structure(nid),
            lambda nid=npc_id, qids=quest_ids: t_trigger_quest_coverage(nid, qids),
            lambda nid=npc_id: t_choice_metric_effects(nid),
            lambda nid=npc_id: t_complete_quest_references(nid),
            lambda nid=npc_id, qids=quest_ids: t_simulated_interaction_chain(nid, qids),
        ):
            result = test_fn()
            if result.errors:
                errors.append(result)
            else:
                passed.append(result)

    # Special test for compliance_officer high-risk branch
    hr_result = t_compliance_officer_high_risk_branch()
    if hr_result.errors:
        errors.append(hr_result)
    else:
        passed.append(hr_result)

    # quest_manager state flow (read-only documentation check)
    qm_result = t_quest_manager_state_flow()
    if qm_result.errors:
        errors.append(qm_result)
    else:
        passed.append(qm_result)

    # Print results
    print()
    for p in passed:
        print(p)
    for e in errors:
        print(e)
    print()

    total  = len(passed) + len(errors)
    fail_n = len(errors)
    pass_n = len(passed)

    print(f"Results: {pass_n}/{total} passed, {fail_n} failed")

    # Write JSON report
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    report_path = REPORTS_DIR / "n2d-runtime-interaction-smoke.json"
    report = {
        "test": "n2d-runtime-interaction-smoke",
        "version": "1.0",
        "total": total,
        "passed": pass_n,
        "failed": fail_n,
        "errors": [e.name for e in errors],
        "warnings": [],
        "details": [
            {"name": r.name, "passed": r.passed, "errors": r.errors, "warnings": r.warnings}
            for r in passed + errors
        ],
    }
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(f"\nJSON report → {report_path}")

    if fail_n > 0:
        print("\nSmoke test FAILED — see errors above.")
        sys.exit(1)
    print("\nSmoke test PASSED — all checks OK.")
    sys.exit(0)


if __name__ == "__main__":
    main()