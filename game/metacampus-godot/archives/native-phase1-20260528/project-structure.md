# MetaCampus Godot 项目结构报告

生成时间: 2026-05-28 05:13 CST

---

## 1. Godot 版本

| 字段 | 值 |
|------|-----|
| 引擎版本 | **Godot 4.6** (stable, official) |
| 渲染器 | GL Compatibility (`gl_compatibility`) |
| 窗口 | 1280×720, canvas stretch, expand aspect |
| 主场景 | `res://scenes/Main.tscn` |

**来源**: `project.godot` 第 20 行 `config/features=PackedStringArray("4.6", "GL Compatibility")`。

---

## 2. godot-cpp 版本与构建环境

### 2.1 godot-cpp 版本

| 字段 | 值 |
|------|-----|
| 仓库分支 | **master** (v10 beta 系列) |
| 最新提交 | `6f7a333a` — "Harden release gates and add baseline governance" |
| 支持的 Godot API 版本 | 4.3, 4.4, 4.5, **4.6** (默认), 4.7 |
| 默认 API 版本 | **4.6** (`extension_api.json` 头中包含 `v4.6.stable.official`) |
| 扩展 API JSON | `gdextension/extension_api.json` (346,936 行) |

### 2.2 SCons 构建配置

**主构建文件**: `godot-cpp/SConstruct` (56 行)

- 需要 SCons ≥ 4.0, Python ≥ 3.8
- 通过 `godot-cpp/tools/godotcpp.py` 工具链实现跨平台构建
- 支持的平台: linux, macos, windows, android, ios, web
- 架构: x86_32, x86_64, arm32, arm64, rv64, ppc32, ppc64, wasm32, universal
- 可选参数: `api_version`, `custom_api_file`, `use_llvm`, `lto`, `deprecated`, `precision`

**项目级 SConstruct**: 项目根目录**没有** SConstruct/SConscript — 这意味着没有自主的 GDExtension C++ 扩展构建（游戏目前仅有 GDScript 逻辑 + 外部 Python 桥接服务）。

**GDExtension 文件**: godot-cpp 自带的测试项目有一个 `example.gdextension`，但游戏项目本身不包含 `.gdextension` 文件，表明尚未集成任何 C++ GDExtension 模块。

---

## 3. 场景清单 (`scenes/`)

| 场景文件 | 用途 |
|----------|------|
| `Main.tscn` | 主场景（程序入口） |
| `CampusMap.tscn` | 校园地图 |
| `Player.tscn` | 玩家角色 |
| `NPC.tscn` | NPC 角色模板 |
| `DialogueBox.tscn` | 对话界面 |
| `TaskBoard.tscn` | 任务看板 UI |
| `Dashboard.tscn` | 指标仪表盘 |
| `QuestToast.tscn` | 任务完成 Toast |

---

## 4. GDScript 模块清单

### 4.1 总览

12 个 `.gd` 脚本，总计 **2665 行**。

### 4.2 模块分类

| 模块 | 文件 | 行数 | 说明 |
|------|------|------|------|
| **核心系统** | | | |
| | `scripts/test_harness.gd` | 376 | HTTP 测试接口层（游戏内 HTTP Server） |
| | `scripts/json_loader.gd` | 175 | JSON 数据加载器（Autoload） |
| | `scripts/api_client.gd` | 280 | API 客户端（LLM 桥接） |
| **寻路** | | | |
| | `scripts/player_controller.gd` | 106 | 玩家移动控制（WASD 方向键） |
| | `scripts/npc_controller.gd` | 165 | NPC 控制器（含交互检测） |
| **对话** | | | |
| | `scripts/dialogue_manager.gd` | 307 | 对话管理器（分支选择、指标变更） |
| | `scripts/visual_feedback.gd` | 141 | 视觉反馈（Toast/对话框动画） |
| **任务** | | | |
| | `scripts/quest_manager.gd` | 333 | 任务管理器（注册/状态追踪/完成验证） |
| | `scripts/quest_toast.gd` | 215 | 任务完成 Toast 界面 |
| | `scripts/taskboard.gd` | 268 | 任务看板 UI |
| **指标** | | | |
| | `scripts/metric_manager.gd` | 171 | 4 个核心指标管理 |
| **仪表盘** | | | |
| | `scripts/dashboard.gd` | 128 | 指标仪表盘 UI |

### 4.3 Autoload 注册表

`project.godot` 中注册了 6 个 Autoload 单例:

| Autoload 名称 | 脚本路径 | 用途 |
|---------------|----------|------|
| `TestHarness` | `scripts/test_harness.gd` | HTTP 测试端点 |
| `JsonLoader` | `scripts/json_loader.gd` | JSON 数据加载 |
| `QuestManager` | `scripts/quest_manager.gd` | 任务系统 |
| `MetricManager` | `scripts/metric_manager.gd` | 指标系统 |
| `ApiClient` | `scripts/api_client.gd` | API 桥接 |
| `VisualFeedback` | `scripts/visual_feedback.gd` | 视觉反馈 |

---

## 5. 数据文件 (`data/`)

| 文件 | 用途 |
|------|------|
| `dialogues.json` | 对话树数据（含 T1/T2/T3/T8 分支） |
| `quests.json` | 任务定义 |
| `npcs.json` | NPC 定义 |
| `locations.json` | 场景位置定义 |
| `metrics.json` | 指标定义（初始值/范围） |
| `api_config.json` | API 桥接配置（当前 mode=mock） |
| `mock_knowledge_responses.json` | Mock 知识库回答 |
| `tools.json` | 工具定义 |

---

## 6. 测试与工具 (`tools/`)

| 文件 | 行数 | 用途 |
|------|------|------|
| `smoke_g2.py` | 346 | G2 冒烟测试 — 任务/对话/指标核心流程 |
| `smoke_g3.py` | 183 | G3 冒烟测试 — API Bridge mock/live 切换 |
| `smoke_g4.py` | 218 | G4 冒烟测试 — Demo polish/UI 回归 |
| `llm_bridge.py` | 185 | DeepSeek 对话桥接服务 (port 8788) |

所有冒烟测试均通过 `TestHarness` HTTP 端点 (`http://127.0.0.1:16007`) 驱动。已有报告:

| 报告 | 路径 |
|------|------|
| G2 报告 | `reports/g2_smoke_report.json` |
| G3 报告 | `reports/g3_smoke_report.json` |
| G4 报告 | `reports/g4_smoke_report.json` |

---

## 7. 构建环境现状

| 项目 | 状态 |
|------|------|
| Godot 引擎版本 | ✅ 4.6 (stable) |
| godot-cpp 版本 | ✅ master (v10 beta), target 4.6 |
| SCons 工具链 | ✅ godot-cpp/ 内可用，项目级未使用 |
| Python 桥接服务 | ✅ `tools/llm_bridge.py` (port 8788) |
| GDExtension 集成 | ❌ 尚未创建 `.gdextension` 文件，无自定义 C++ 扩展 |
| 测试框架 | ✅ TestHarness HTTP + 3 个冒烟测试脚本 |
| API 配置 | mode=mock, fallback to mock, high_risk_keywords 已配置 |

---

## 8. 关键发现

1. **纯 GDScript 项目**: 当前游戏完全使用 GDScript 实现，未编译任何 C++ GDExtension 模块。`godot-cpp/` 作为 submodule 存在但未实际使用。
2. **HTTP 驱动测试**: `TestHarness.gd` 是游戏内嵌的 HTTP 服务器，冒烟测试通过 HTTP 驱动游戏逻辑，无需模拟器。
3. **4+1 层架构**: Autoload 单例构成基础服务层（JsonLoader → ApiClient → MetricManager/QuestManager → VisualFeedback），场景层引用 Autoload。
4. **API Bridge 模式**: 支持 mock/live/off 三种模式切换，`api_config.json` 中定义了高风控关键词列表。
5. **指标系统**: 4 个核心指标（school_efficiency, parent_trust, compliance_safety, system_stability）初始值分别为 40/50/70/60。
