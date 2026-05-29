# TD-3：清理空字符串 trigger_quest — 报告

**日期**: 2026-05-29  
**执行者**: narrative-designer  
**状态**: ✅ 完成

---

## 1. 搜索结果

在 8 个 `data/dialogues/*_dialogues.json` 文件中搜索 `"trigger_quest": ""`（空字符串）：
- **结果：0 个匹配** — 没有 entry 包含空字符串 trigger_quest。

但发现第二类问题：6 个 `trigger: "quest_trigger"` 的条目**完全缺失 `trigger_quest` 字段**。

---

## 2. 变更清单

为以下 6 个条目添加了 `"trigger_quest": null`（在 `"trigger": "quest_trigger"` 之后）：

| # | 文件 | 条目 ID | 变更 |
|---|------|---------|------|
| 1 | `admissions_director_dialogues.json` | `admissions_director_high_risk_001` | 添加 `"trigger_quest": null` |
| 2 | `compliance_officer_dialogues.json` | `compliance_officer_high_risk_001` | 添加 `"trigger_quest": null` |
| 3 | `homeroom_teacher_dialogues.json` | `homeroom_teacher_followup_001` | 添加 `"trigger_quest": null` |
| 4 | `parent_representative_dialogues.json` | `parent_representative_high_risk_001` | 添加 `"trigger_quest": null` |
| 5 | `principal_dialogues.json` | `principal_high_risk_001` | 添加 `"trigger_quest": null` |
| 6 | `student_representative_dialogues.json` | `student_representative_feedback_001` | 添加 `"trigger_quest": null` |

**未变更的 2 个文件** — 已有合法 quest_id 值：
- `it_operator_dialogues.json` — `q_canary_release_001`
- `logistics_manager_dialogues.json` — `q_repair_order_001`

---

## 3. Smoke Test 结果

```
✅ PASS — 333/333 checks passed
```

为兼容 `null` 值，对 `tools/smoke_npc_dialogues.py` 做了微调：
- 变更：`_check_dialogue_entry()` 中，当 `trigger_quest` 为 `None` 或 `""` 时跳过 quest_id 校验
- 理由：`null` 表示"不绑定特定任务"（quest_trigger 类型条目可在运行时由多个任务触发），不应作为未知 quest_id 报错

---

## 4. dialogue_manager.gd null 处理评估

**结论：不需要处理 — `trigger_quest` 字段在运行时完全不被消费。**

- `scripts/dialogue_manager.gd`：第 173 行读取 `line_data.get("quest_id", "")`，**不使用 `trigger_quest`**
- 全项目 `.gd` 文件中只有 `quest_manager.gd` 出现过 `trigger_quest` 字符串，但那是函数名 `trigger_quest_fail_condition()`，与 JSON 字段无关
- `trigger_quest` 当前仅用于 smoke test 的结构校验和跨文件一致性检查

### 如果未来要消费 trigger_quest

建议使用 `line_data.get("trigger_quest")` 并检查 truthiness：
```gdscript
var trigger_quest = line_data.get("trigger_quest")
if trigger_quest and trigger_quest != "":
    # 有绑定任务，启动
    _start_quest(trigger_quest)
```
`null`、`""` 和缺失字段在此逻辑下行为一致，不会触发任务启动。

---

## 5. 修改的文件

| 文件 | 类型 |
|------|------|
| `data/dialogues/admissions_director_dialogues.json` | 数据修改 |
| `data/dialogues/compliance_officer_dialogues.json` | 数据修改 |
| `data/dialogues/homeroom_teacher_dialogues.json` | 数据修改 |
| `data/dialogues/parent_representative_dialogues.json` | 数据修改 |
| `data/dialogues/principal_dialogues.json` | 数据修改 |
| `data/dialogues/student_representative_dialogues.json` | 数据修改 |
| `tools/smoke_npc_dialogues.py` | 工具修复（null 兼容） |

## 6. Schema 状态

修改后的 trigger_quest 分布：

| 状态 | 数量 | 说明 |
|------|------|------|
| 合法 quest_id | 10 | quest_start (8) + quest_trigger (2: it_operator, logistics_manager) |
| `null` | 6 | quest_trigger，不绑定特定任务 |
| 缺失 | 0 | ✅ 无 |
| 空字符串 | 0 | ✅ 无 |
