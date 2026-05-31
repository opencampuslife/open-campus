# MetaCampus 2D — C# 迁移完成报告

**日期**: 2026-05-29
**阶段**: Phase 1 → Phase 2 (C# 迁移）

---

## 一、迁移目标

将 MetaCampus 2D 的核心业务系统从 **GDScript** 迁移到 **C# (.NET)**，保留 Godot 4.6 的 Autoload 单例架构，利用 C# 的强类型和 .NET 生态优势。

**关键判断**：C# 是脚本层，不是 GDExtension。GDExtension (C++) 留给性能敏感模块（RAG 加速、向量计算等）。

---

## 二、已完成工作

### 1. 启用 .NET 支持

**文件**: `project.godot`

```ini
config/features=PackedStringArray("4.6", "GL Compatibility", ".NET")
```

### 2. C# 目录结构

```
scripts/csharp/
├── core/
│   └── QuestModels.cs      # QuestDefinition, QuestState, QuestEffects 等模型
├── managers/
│   ├── QuestManager.cs       # 四层任务系统（主线/每日/NPC/随机事件）
│   ├── TimeManager.cs        # 日循环/学期/时间刻度（7:00-22:00）
│   ├── ResourceManager.cs   # 行动点(AP)/算力(Compute)/预算(Budget)
│   ├── MetricManager.cs      # 4主指标 + 12子指标
│   ├── SkillManager.cs       # 6大技能 × 10级
│   ├── EventManager.cs      # 随机事件触发/结算
│   ├── SaveManager.cs       # 6槽位存档系统
│   ├── NpcRegistry.cs       # 8 NPC 信任度/日程/关系事件
│   └── GameState.cs         # 解锁区域/全局状态
└── ui/
    ├── HudController.cs      # (待实现)
    └── DashboardController.cs  # (待实现)
```

### 3. 四层任务 JSON

```
data/quests/
├── main_quests.json          # Chapter 1-6 主线任务
├── daily_quests.json        # 每日刷新任务（公告栏）
├── npc_quests.json          # NPC 支线（信任解锁）
└── random_event_quests.json  # 随机事件（高风险决策）
```

### 4. Autoload 配置

**文件**: `project.godot` [autoload] 节

```ini
TimeManager="*res://scripts/csharp/managers/TimeManager.cs"
ResourceManager="*res://scripts/csharp/managers/ResourceManager.cs"
SkillManager="*res://scripts/csharp/managers/SkillManager.cs"
EventManager="*res://scripts/csharp/managers/EventManager.cs"
SaveManager="*res://scripts/csharp/managers/SaveManager.cs"
MetricManager="*res://scripts/csharp/managers/MetricManager.cs"
NpcRegistry="*res://scripts/csharp/managers/NpcRegistry.cs"
GameState="*res://scripts/csharp/managers/GameState.cs"
QuestManager="*res://scripts/csharp/managers/QuestManager.cs"
```

### 5. 移除的旧文件

以下 GDScript 文件已被 C# 版本替换并删除：

- `scripts/quest_manager.gd` + `.uid`
- `scripts/metric_manager.gd` + `.uid`
- `scripts/resource_manager.gd` + `.uid`
- `scripts/skill_manager.gd` + `.uid`
- `scripts/event_manager.gd` + `.uid`
- `scripts/save_manager.gd` + `.uid`
- `scripts/time_manager.gd` + `.uid`
- `scripts/npc_registry.gd` + `.uid`
- `scripts/json_loader.gd` + `.uid`
- `scripts/test_harness.gd` + `.uid`

保留的 GDScript 文件（UI/场景/玩家控制）：

- `scripts/api_client.gd`
- `scripts/audio_manager.gd`
- `scripts/dashboard.gd`
- `scripts/dialogue_manager.gd`
- `scripts/npc_controller.gd`
- `scripts/npc_factory.gd`
- `scripts/npc_persona_bridge.gd`
- `scripts/npc_sprite_loader.gd`
- `scripts/player_controller.gd`
- `scripts/quest_toast.gd`
- `scripts/taskboard.gd`
- `scripts/visual_feedback.gd`

---

## 三、核心系统功能

### TimeManager.cs

- 日循环：7:00 → 22:00，每 tick 10 分钟
- 学期循环：28 天/学期 × 4 学期（春/夏/秋/冬）
- 阶段划分：早晨/上午/中午/下午/傍晚/夜间
- 信号：`day_started`, `time_changed`, `phase_changed`, `day_ended`, `semester_ended`

### ResourceManager.cs

- 行动点 AP（上限 10，每日恢复）
- 算力 Compute（上限 100，按 tick 恢复）
- 预算 Budget（基础拨款 + 效率奖励 + 声誉加成 - 运维成本）
- 升级项解锁追踪
- 信号：`ap_changed`, `compute_changed`, `budget_changed`

### MetricManager.cs

- 4 主指标：学校效率/家长信任/合规安全/系统稳定性
- 12 子指标：工单积压/投诉率/AI幻觉率/API延迟等
- 阈值后果检查：合规<40 审计预警，系统<20 宕机等
- 信号：`metric_changed`, `sub_metric_changed`, `threshold_triggered`

### SkillManager.cs

- 6 大技能：招生咨询/教务处理/合规治理/系统运维/数据智能/沟通协调
- 每技能 10 级，经验需求：100 + level × 50
- 升级解锁能力（如合规 L2 招生承诺检测）
- 行为自动给予技能 XP（如 `add_xp_for_action("admission_consultation")`）
- 信号：`skill_xp_changed`, `skill_leveled_up`

### QuestManager.cs

- 四层任务结构：Main / Daily / NPC / RandomEvent
- 任务状态机：Locked → Available → Active → Completed/Failed/Expired
- 目标系统（Objectives）、选择效果（Choices）、解锁（Unlocks）
- 每日刷新（Shuffle + Requirements 检查）
- 截止时间检查（Deadline）
- 信号：`quest_available`, `quest_started`, `quest_updated`, `quest_completed`, `quest_failed`, `quest_expired`, `daily_quests_refreshed`

### EventManager.cs

- 随机事件触发（概率 + 指标阈值）
- 待处理事件队列
- 事件解决（选择应用效果）
- 信号：`event_triggered`, `event_resolved`, `pending_events_changed`

### SaveManager.cs

- 6 槽位存档（user://saves/save_X.json`）
- 收集所有系统状态（Time/Resources/Skills/Metrics/NPC/GameState）
- AutoSave 在每日结束时触发
- 新游戏重置所有系统

### NpcRegistry.cs

- 8 NPC 信任度（0-10 级）
- 关系事件追踪（按信任等级解锁）
- 信号：`trust_changed`

### GameState.cs

- 解锁区域管理（12 个校园区域）
- 信号：`location_unlocked`

---

## 四、Phase 2 流程图

已生成：`phase2_flowchart_cjk.png`（含中文标注）

内容包含：
1. HUD 面板（实时显示：时间/AP/算力/预算/指标）
2. Dashboard 面板（Tab 分页：指标/技能/NPC 信任/升级项）
3. 每日结算流程（22:00 自动触发）
4. 四层任务系统（主线/每日/支线/随机事件）

---

## 五、下一步（Phase 2 剩余工作）

### 高优先级

1. **HUD 场景**（`scenes/HUD.tscn` + `scripts/csharp/ui/HudController.cs`）
   - 显示：时间/AP/算力/预算/4 指标
   - 绑定：TimeManager/ResourceManager/MetricManager 信号

2. **Dashboard 场景**（`scenes/Dashboard.tscn` + `scripts/csharp/ui/DashboardController.cs`）
   - Tab 1：主指标趋势 + 子指标
   - Tab 2：6 大技能进度条
   - Tab 3：8 NPC 信任等级 + 关系事件
   - Tab 4：12 个升级项进度

3. **每日结算可视化**
   - 在 TimeManager.EndDay() 后显示结算报告
   - 显示：资源收支/指标变化/事件触发

### 中优先级

4. **任务 UI 重写**
   - 公告栏（每日任务）
   - NPC 对话中的任务提示
   - 任务追踪器（HUD 显示当前目标）

5. **NPC 日程可视化**
   - 在地图上显示 NPC 当前位置（根据 schedule.json）
   - NPC 按时间表移动

### 低优先级

6. **GDExtension 模块（Phase 3）**
   - RAG Ranker (C++)
   - Risk Scorer (C++)
   - Canary Simulator (C++)
   - NPC Scheduler (C++)

---

## 六、关键设计决策

| 决策 | 选择 | 原因 |
|------|------|------|
| 脚本语言 | C# (.NET) | 强类型、.NET 生态、IDE 支持好 |
| 性能模块 | C++ GDExtension | 原生性能、复杂算法 |
| 配置数据 | JSON | 易编辑、版本控制友好 |
| UI | Godot Scene + C# Controller | 可视化编辑 + 逻辑分离 |
| 存档 | JSON (user://) | 跨平台、易调试 |
| Autoload | 保留 | 跨场景持久化、信号驱动 |

---

## 七、参考文档

- [Godot .NET 文档](https://docs.godotengine.org/en/4.4/tutorials/scripting/cross_language_scripting.html)
- [Godot Autoload 文档](https://docs.godotengine.org/en/latest/tutorials/scripting/singletons_autoload.html)
- [Godot GDExtension 文档](https://docs.godotengine.org/en/4.4/tutorials/scripting/gdextension/index.html)

---

**迁移完成度**：Phase 1 (100%) → Phase 2 Core (100%) → Phase 2 UI (0%)

**下一步**：实现 HUD + Dashboard + 每日结算可视化。
