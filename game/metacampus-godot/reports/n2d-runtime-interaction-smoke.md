# N2D-3 Runtime Interaction Smoke Report

**Test:** `smoke_npc_runtime_interaction.py`
**Date:** 2026-05-29
**Result:** ✅ 17/17 passed, 0 failed

---

## 1. Scope

Validates the NPC interaction chain for 3 NPCs:
- `admissions_director`
- `compliance_officer`
- `it_operator`

---

## 2. Test Cases

| # | Test | Target | Result |
|---|------|--------|--------|
| 1 | Dialogue structure: required keys present | admissions_director | PASS |
| 2 | trigger_quest IDs resolve in quests.json | admissions_director | PASS |
| 3 | Choice metric_effects: keys ⊆ core 4, values ∈ [-30,+30] | admissions_director | PASS |
| 4 | complete_quest / fail_quest IDs exist in quests.json | admissions_director | PASS |
| 5 | Simulated interaction chain: quest triggers → choice → effects | admissions_director | PASS |
| 6 | Dialogue structure: required keys present | compliance_officer | PASS |
| 7 | trigger_quest IDs resolve in quests.json | compliance_officer | PASS |
| 8 | Choice metric_effects: keys ⊆ core 4, values ∈ [-30,+30] | compliance_officer | PASS |
| 9 | complete_quest / fail_quest IDs exist in quests.json | compliance_officer | PASS |
| 10 | Simulated interaction chain: quest triggers → choice → effects | compliance_officer | PASS |
| 11 | Dialogue structure: required keys present | it_operator | PASS |
| 12 | trigger_quest IDs resolve in quests.json | it_operator | PASS |
| 13 | Choice metric_effects: keys ⊆ core 4, values ∈ [-30,+30] | it_operator | PASS |
| 14 | complete_quest / fail_quest IDs exist in quests.json | it_operator | PASS |
| 15 | Simulated interaction chain: quest triggers → choice → effects | it_operator | PASS |
| 16 | High-risk branch metric validation (safe_intercept + let_slide) | compliance_officer | PASS |
| 17 | quest_manager.gd state transition flow documented | quest_manager.gd | PASS |

---

## 3. High-Risk Branch Details

### admissions_director (`admissions_director_high_risk_001`)

| Choice | action | compliance_safety | Expected | Status |
|--------|--------|-------------------|----------|--------|
| 正确 | safe_answer | +15 | +15 | ✅ |
| 错误 | promise_admission | -20 | -20 | ✅ |

### compliance_officer (`compliance_officer_high_risk_001`)

| Choice | action | compliance_safety | Expected | Status |
|--------|--------|-------------------|----------|--------|
| 正确 | safe_intercept | +15 | +15 | ✅ |
| 错误 | let_slide | -20 | -20 | ✅ |

---

## 4. quest_manager.gd State Machine

Documented from `scripts/quest_manager.gd` (334 lines, Godot 4 GDScript):

### States
- `STATUS_AVAILABLE` → initial state after `_initialize_quests()`
- `STATUS_ACTIVE` → set by `activate_quest(quest_id)`
- `STATUS_COMPLETED` → set by `complete_quest(quest_id)`
- `STATUS_FAILED` → set by `fail_quest(quest_id)`

### Transitions
```
available ──[activate_quest()]──→ active
   active ──[all steps done]──────→ completed
   active ──[trigger_quest_fail_condition()]→ failed
completed / failed ──[reset_all_quests()]──→ available
```

### Key Methods
| Method | Purpose |
|--------|---------|
| `activate_quest(quest_id)` | Transition available → active; emits `quest_status_changed` |
| `complete_objective(quest_id, idx)` | Mark step done; calls `_check_quest_completion` |
| `_check_quest_completion()` | If all required_steps done → `complete_quest()` |
| `complete_quest(quest_id)` | active → completed; emits `quest_completed`; calls `_apply_reward()` |
| `fail_quest(quest_id)` | active → failed; emits `quest_failed`; calls `_apply_penalty()` |
| `_apply_reward(quest_data)` | Gets `metric_manager` from tree group, calls `apply_effects(reward)` |
| `_apply_penalty(quest_data)` | Gets `metric_manager` from tree group, calls `apply_effects(penalty)` |
| `trigger_quest_fail_condition(quest_id, action)` | If `fail_condition.action == action` → `fail_quest()` |

### Metric Integration
`quest_manager.gd` interacts with `metric_manager` via Godot group lookup:
```gdscript
var metric_manager = get_tree().get_first_node_in_group("metric_manager")
if metric_manager and metric_manager.has_method("apply_effects"):
    metric_manager.apply_effects(effects_dict)
```
Rewards and penalties are applied atomically when a quest completes or fails.

---

## 5. Core Metric Contract

4 core metrics validated against `data/metrics.json`:

| metric_id | name | initial |
|-----------|------|---------|
| school_efficiency | 学校效率 | 40 |
| parent_trust | 家长信任 | 50 |
| compliance_safety | 合规安全 | 70 |
| system_stability | 系统稳定性 | 60 |

All choice `metric_effects` values across the 3 NPCs are within [-30, +30] and reference only these 4 keys.

---

## 6. File Inventory

| File | Description |
|------|-------------|
| `tools/smoke_npc_runtime_interaction.py` | Smoke test runner (offline, no Godot required) |
| `tools/reports/n2d-runtime-interaction-smoke.json` | JSON test report |
| `data/dialogues/admissions_director_dialogues.json` | Dialogue data |
| `data/dialogues/compliance_officer_dialogues.json` | Dialogue data |
| `data/dialogues/it_operator_dialogues.json` | Dialogue data |
| `data/quests.json` | Quest definitions |
| `data/metrics.json` | Core metric definitions |
| `scripts/quest_manager.gd` | Quest state machine |

---

## 7. Usage

```bash
cd game/metacampus-godot
python tools/smoke_npc_runtime_interaction.py
```
Exit code 0 on all pass, exit code 1 on any failure.