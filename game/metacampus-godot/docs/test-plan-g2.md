# MetaCampus 2D — Phase G2 测试计划

## 概述

Phase G2 引入任务闭环、对话分支、指标变化和 Dashboard 显示。本测试计划覆盖 8 个 MVP 任务的完整生命周期验证。

---

## 1. 任务触发测试

### TC-G2-001: NPC 对话自动触发任务
- **前置**: 玩家位于家长 NPC 附近
- **操作**: 靠近家长 NPC → 按 E
- **预期**: DialogueBox 弹出，任务 T1 自动从 available → active
- **验证**: `quest_manager.get_quest_status("q_admission_001")` 返回 `"active"`

### TC-G2-002: 多个 NPC 均可触发对应对话
- **前置**: 5 个 NPC 都在各自位置
- **操作**: 依次靠近 5 个 NPC 并按 E
- **预期**: 每个 NPC 弹出不同的对话内容，与 dialogues.json 一致

### TC-G2-003: 无任务 NPC 正常对话
- **前置**: 与李招生老师交互
- **操作**: 靠近李招生老师 → 按 E
- **预期**: 对话弹出，无任务自动激活

---

## 2. 对话选择测试

### TC-G2-004: T1 知识库回答
- **前置**: 与家长 NPC 对话中
- **操作**: 选择「调用招生知识库回答」
- **预期**:
  - metric_effects 生效：parent_trust +8, compliance_safety +5
  - T1 任务完成 toast 弹出
  - TaskBoard 中 T1 标记为 completed

### TC-G2-005: T1 让家长去官网
- **前置**: 与家长 NPC 对话中
- **操作**: 选择「让家长去官网自己看」
- **预期**:
  - school_efficiency -2, parent_trust -1
  - 对话关闭，任务不完成

### TC-G2-006: T1 选择「不清楚」
- **前置**: 与家长 NPC 对话中
- **操作**: 选择「直接说不清楚」
- **预期**: parent_trust -4，对话关闭

### TC-G2-007: T2 高风险 — 正确分支
- **前置**: 在与家长 NPC 的第二轮对话
- **操作**: 选择「不能承诺录取，请联系招生办确认」
- **预期**:
  - compliance_safety +10, parent_trust +6
  - T2 任务完成
  - Toast: 合规安全加分

### TC-G2-008: T2 高风险 — 错误分支
- **前置**: 在与家长 NPC 的第二轮对话
- **操作**: 选择「这个我帮您问问……（暗示可以操作）」
- **预期**:
  - compliance_safety -20, parent_trust +2
  - T2 任务标记为 failed
  - 显示错误 warning（红色文字）

### TC-G2-009: T3 自动提醒催办
- **前置**: 与家长 NPC 第三轮对话
- **操作**: 选择「使用企业微信自动提醒催办」
- **预期**:
  - school_efficiency +8, parent_trust +5
  - T3 任务完成

### TC-G2-010: T4 AI请假汇总
- **前置**: 与王班主任对话
- **操作**: 选择「使用AI辅助汇总请假数据」
- **预期**:
  - school_efficiency +10, compliance_safety +6
  - T4 任务完成

### TC-G2-011: T5 OCR订餐
- **前置**: 与陈后勤老师对话（第一轮）
- **操作**: 选择「OCR识别订餐截图」
- **预期**:
  - school_efficiency +10, compliance_safety +6
  - 进入下一轮对话

### TC-G2-012: T6 AI派单
- **前置**: 与陈后勤老师对话（第二轮）
- **操作**: 选择「使用AI系统自动派单」
- **预期**:
  - school_efficiency +8, compliance_safety +5
  - T5 和 T6 同时完成

### TC-G2-013: T7 运营驾驶舱
- **前置**: 与AI助手对话
- **操作**: 选择「查看运营驾驶舱」
- **预期**:
  - school_efficiency +5
  - T7 完成
  - Dashboard 自动打开

### TC-G2-014: T8 Canary发布
- **前置**: 与AI助手对话（第二轮）
- **操作**: 选择「使用 Canary 1% 灰度发布」
- **预期**:
  - system_stability +12, compliance_safety +8
  - T8 完成

### TC-G2-015: T8 跳过灰度错误分支
- **前置**: 与AI助手对话（第二轮）
- **操作**: 选择「直接全量发布」
- **预期**:
  - system_stability -15, compliance_safety -10
  - T8 标记为 failed

---

## 3. 指标变化测试

### TC-G2-016: 四指标初始化
- **前置**: 游戏刚启动
- **操作**: 按 D 打开 Dashboard
- **预期**:
  - school_efficiency = 40
  - parent_trust = 50
  - compliance_safety = 70
  - system_stability = 60

### TC-G2-017: 指标变化后 Dashboard 更新
- **前置**: 完成 T1 知识库回答
- **操作**: 按 D 打开 Dashboard
- **预期**:
  - parent_trust = 58 (50 + 8)
  - compliance_safety = 75 (70 + 5)

### TC-G2-018: 指标不超出 0-100
- **前置**: compliance_safety 当前 > 80
- **操作**: 多次进行合规加分操作
- **预期**: compliance_safety 不会超过 100

### TC-G2-019: 指标过低警告
- **前置**: parent_trust < 30
- **操作**: 查看 Dashboard
- **预期**: parent_trust 显示为红色警告

---

## 4. TaskBoard 测试

### TC-G2-020: Tab 键打开/关闭 TaskBoard
- **前置**: 游戏运行中
- **操作**: 按 Tab
- **预期**: TaskBoard 面板打开，显示 8 个任务
- **操作**: 再按 Tab
- **预期**: TaskBoard 关闭

### TC-G2-021: TaskBoard Tab 切换
- **前置**: TaskBoard 打开
- **操作**: 依次点击「进行中」「已完成」「全部」
- **预期**: 任务列表按状态过滤正确显示

### TC-G2-022: 任务完成状态同步
- **前置**: 完成 T1
- **操作**: 打开 TaskBoard →「已完成」Tab
- **预期**: T1 显示为 ✅ 状态

---

## 5. JSON 数据验证

### TC-G2-023: dialogues.json schema
- **验证项**: 所有对话有 npc_id / lines / choices
- **验证项**: 每个 choice 有 text / action / metric_effects
- **验证项**: T2 错误分支有 fail_quest 字段

### TC-G2-024: quests.json schema
- **验证项**: 每个 quest 有 quest_id / title / description
- **验证项**: 每个 quest 有 objectives 数组
- **验证项**: 每个 quest 有 reward 和 fail_condition
- **验证项**: T2 fail_condition.action = "promise_admission"

### TC-G2-025: metrics.json schema
- **验证项**: 4 个核心指标（school_efficiency / parent_trust / compliance_safety / system_stability）
- **验证项**: 每个指标有 initial / min / max / thresholds

### TC-G2-026: npcs.json schema
- **验证项**: 5 个 NPC 数据完整
- **验证项**: 每个 NPC 有 npc_id / name / role / location / dialogue_id / quest_ids

---

## 6. 回归测试

### TC-G2-027: 玩家仍可自由移动
- **前置**: 无对话/无面板打开
- **操作**: WASD 方向键
- **预期**: 玩家四方向移动，无法穿墙

### TC-G2-028: ESC 正确关闭面板
- **前置**: 对话 / TaskBoard / Dashboard 任意面板打开
- **操作**: 按 ESC
- **预期**: 面板关闭，玩家恢复控制

---

## 测试环境

- Godot 4.x
- macOS / Windows
- 不依赖后端 API（Mock Mode Only）
- JSON 数据文件使用 game/metacampus-godot/data/ 目录
