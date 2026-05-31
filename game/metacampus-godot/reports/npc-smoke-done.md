# NPC Smoke Test Results

**Date**: 2026-05-28  
**Phase**: NPC Smoke (Assets / Dialogues / Quests)  
**Status**: ✅ ALL PASS

---

## Test Summary

| Test | Checks | Passed | Failed | Result |
|------|--------|--------|--------|--------|
| smoke_npc_assets | 151 | 151 | 0 | ✅ PASS |
| smoke_npc_dialogues | 333 | 333 | 0 | ✅ PASS |
| smoke_npc_quests | 53 | 53 | 0 | ✅ PASS |
| **Total** | **537** | **537** | **0** | **✅ ALL PASS** |

---

## 1. NPC Assets (smoke_npc_assets)

### Scope
- 8 NPC profile JSONs in `data/npcs/` exist and parse correctly
- All required fields present: `npc_id`, `display_name`, `role`, `location`, `quest_ids`, `primary_metric`, `metric_effects`
- All `metric_effects` keys validated against 4 core metrics
- 8 persona markdown files in `data/personas/` exist and non-empty
- 8 dialogue JSON files in `data/dialogues/` exist, parse correctly, have entry arrays, and `npc_id` matches

### NPC Roster Verified
| NPC ID | Display Name | Role | Primary Metric |
|--------|-------------|------|----------------|
| admissions_director | 周明远 | 招生办主任 | school_efficiency |
| compliance_officer | 林澈 | 合规专员 | compliance_safety |
| homeroom_teacher | 陈芷 | 班主任 | school_efficiency |
| it_operator | 许航 | IT运维 | system_stability |
| logistics_manager | 赵启山 | 后勤主管 | school_efficiency |
| parent_representative | 顾兰 | 家长代表 | parent_trust |
| principal | 唐毓 | 校长 | school_efficiency |
| student_representative | 沈一诺 | 学生代表 | parent_trust |

---

## 2. NPC Dialogues (smoke_npc_dialogues)

### Scope
- All 8 dialogue JSON files parse successfully
- Each dialogue entry has required fields: `id`, `trigger`, `speaker`, `text`, `choices`
- Each choice has: `text`, `action`, `metric_effects`, `next_line`
- All `metric_effects` values are within [-25, +25] range
- `trigger` values are valid (`quest_start` / `quest_trigger`)
- `trigger_quest`, `complete_quest`, `fail_quest` reference valid quest IDs from `quests.json`

### Dialogue Statistics
- 8 NPCs × 2 dialogue entries each = 16 dialogue entries total
- 8 NPCs × 2 choices each = 32 choices total
- All metric_effects ranges valid (no values outside [-25, +25])

---

## 3. NPC Quests (smoke_npc_quests)

### Scope
- All NPC `quest_ids` reference quests that exist in `data/quests.json`
- All 8 NPCs bind core metrics via `primary_metric` (all valid)
- 7/8 NPCs also have valid `secondary_metric` (compliance_officer has no secondary)
- All T1-T8 quests are covered by at least one NPC

### Quest Coverage Matrix
| Quest | Title | Covering NPCs |
|-------|-------|---------------|
| q_admission_001 | T1: 家长招生咨询 | admissions_director |
| q_admission_002 | T2: 拦截高风险问题 | compliance_officer |
| q_material_reminder_001 | T3: 材料催办 | parent_representative |
| q_leave_request_001 | T4: 请假处理 | homeroom_teacher, student_representative |
| q_meal_count_001 | T5: 订餐统计 | logistics_manager |
| q_repair_order_001 | T6: 报修工单 | logistics_manager |
| q_dashboard_001 | T7: 运营驾驶舱 | it_operator, principal |
| q_canary_release_001 | T8: Canary发布 | it_operator |

---

## Report Files
- `reports/smoke_npc_assets.json`
- `reports/smoke_npc_dialogues.json`
- `reports/smoke_npc_quests.json`

## Notes
- All existing smoke scripts (g2/g3/g4) remain unmodified
- All 3 scripts use Python stdlib only (no pip dependencies)
- Exit code: 0 on pass, 1 on fail
