# MetaCampus Godot 资产生产规范

## Matrix 图像配额处理
- matrix_generate_image 配额的 "insufficient quota" 错误会导致大量生图任务中断
- pixel-artist 任务须预设 cron 重试，prompt 写幂等逻辑（"已生成则跳过"）
- 交付物用增量模式，不覆盖已有产出

## NPC 资产目录结构（gaokao-agent game/metacampus-godot/）
- 目录：`assets/npcs/<npc_id>/`
- 禁止 `baseline/` 子目录（已废弃）
- 每个 NPC 需：portrait × 4（neutral/happy/worried/strict）+ sprite_idle + walk sheet（4帧 256×64）+ animation_spec.json + generation_metadata.json
- 所有 JSON 文件在 NPC root 层级（`assets/npcs/<npc_id>/`），不在 `baseline/` 子目录
- 规格：portrait 256×256 RGBA、sprite 64×64 RGBA、walk sheet 256×64 RGBA、透明背景

## admissions_director / student_representative 特殊处理
- 两 NPC 有 `baseline/` 子目录，含 v1（暗黑复古）和 v2（warm campus）两套资产
- v2 升为正式版（去 `_v2` 后缀），v1 清理
- post-processing 无 PIL/ImageMagick，用 sips + Python zlib

## 资产验收方式
- pixel-artist 超时后文件已在磁盘，用 Python struct+zlib 独立验证 PNG 规格
- 不依赖 agent session 存活状态

## plan decision 格式注意
- `last_cycle` 用 `verdict` 字段（不是 `status`）
- `next_cycle` 里的 task 即使状态是 `accept` 也必须带完整字段：`title/prompt/assigned_to/verified_by`
- 不能偷懒只写 verdict，否则报 schema 错误

## agent 漏写 deliverable.md 处理
- 若 agent 报完成但 deliverable.md 未写：owner 用 Python struct 独立验证文件存在和规格，直接写入 deliverable.md，再用 override_accept
- 不要等 agent 重试，这轮就收

## N2B-3 Fixup-B 资产验收规范
- 不能按"9 PNG 数量"验收，要按**资产类型矩阵**逐项验收
- 每个 NPC 必须有：portrait×4 + sprite_idle + walk×4（10 项），缺一不可
- walk sheet 数量齐 ≠ portrait/sprite 齐全，必须逐 NPC 检查 10 项
- 4 NPC（compliance_officer/homeroom_teacher/it_operator/logistics_manager）在 N2B-3 原有报告中漏报了 portrait/sprite 缺口

## NPC 资产文件格式问题
- Matrix 生成图片时可能产出 JPEG 数据但扩展名为 .png（magic byte 检查）
- portrait_worried.png 实为 JPEG（magic FF D8 FF），需转为标准 PNG 或更新 manifest 路径
- Fixup-B 重新生成时确保输出为标准 RGBA PNG，不接受 JPEG 伪装

## pixel-artist 不适合 PNG 二进制解析
- pixel-artist 在 struct.unpack/zlib 等低层 PNG 解析上容易卡死（15 分钟+）
- N2D TD-1 证明：pixel-artist 在 IHDR chunk 解析上反复出错，最终由 owner 直接写脚本解决
- 涉及到 struct/zlib/chunk 扫描的任务不要 assign pixel-artist，直接由 owner 写或 assign general

## pixel-artist 目录路径问题
- pixel-artist 有时在 NPC root 层级写文件（如 compliance_officer/portrait_neutral.png）而非 baseline/ 子目录
- 排查资产缺失时：同时检查 NPC root 和 baseline/ 两个位置
- 已知受影响：compliance_officer/homeroom_teacher/it_operator/logistics_manager 的 portrait + sprite_idle 在 root，owner 已手动移到 baseline/

## GDExtension 项目结构（2026-05-29）
- Git 根目录是 monorepo（`gaokao-agent/`），Godot 游戏在 `game/metacampus-godot/` 子目录中
- `game/metacampus-godot/` 和 `godot-cpp/` 在 monorepo 中 **untracked**（不是 submodule）
- **git worktree 不适用于 GDExtension 开发**：worktree 只包含 monorepo 追踪文件，不含 Godot 项目文件。所有开发直接在主目录进行
- Godot 4.6.3 引擎：`~/Downloads/Godot.app/`
- godot-cpp 绑定库：`game/metacampus-godot/godot-cpp/`
- 已验证 SCons 构建命令：
  ```bash
  cd game/metacampus-godot
  scons platform=macos arch=arm64 target=template_debug -j$(sysctl -n hw.logicalcpu)
  ```

## UI 面板开发规范（2026-05-29）

### 双重 UI bug（TaskBoard + QuestToast）
当 `.tscn` 已包含 UI 节点，且脚本的 `_ready()` 调用 `_setup_ui()` 动态创建相同结构的 UI 节点时，场景加载后会出现**两套重叠的 UI**。
- TaskBoard：脚本创建 Panel → Margin → VBox(标题/列表/按钮) 与 .tscn 节点集重复
- QuestToast：脚本创建 ToastPanel → Margin → VBox(标题/名称/奖励) 与 .tscn 节点集重复
- **修复模式**：移除 `_setup_ui()`，脚本改用 `@onready var foo: Type = $path/to/node` 引用场景节点，样式在 `_ready()` 中通过 `add_theme_*_override()` 设置

### CanvasLayer 面板快捷键约定
| 面板 | 打开键 | 关闭键 | 输入动作 |
|------|--------|--------|----------|
| TaskBoard | Tab (4194306) | Tab / ESC | `toggle_taskboard` |
| Dashboard | H (72) | H / ESC | `toggle_dashboard` |
- D 键 (68) 已被 `move_right` 占用，Dashboard 不能用 D
- ESC 统一走 `ui_cancel`，仅当面板 visible 时响应关闭
- 打开面板时调用 `player.set_enabled(false)`，关闭时恢复

### 指标实时更新信号链
```
dialogue_manager:choice_made
  → metric_manager:apply_effects() → apply_change()
    → metric_manager:all_metrics_updated
      → dashboard:_on_metrics_updated() → _update_all_metrics()
```
dashboard 同时直接监听 `choice_made` 做补充刷新。

### 动态 ProgressBar fill 颜色
Godot 4 ProgressBar 的 fill 颜色通过 `add_theme_stylebox_override("fill", StyleBoxFlat)` 设置。
每次更新时创建新的 StyleBoxFlat 实例，`bg_color` 设为当前指标的警告/正常色。

### Toast 动画
- 定位: `PRESET_CENTER`（顶部居中），offset_top=20
- 滑入: 单 Tween CUBIC EASE_OUT，从 `target - 80` 到 `target`，时长 0.35s
- 避免双 `create_tween()` 操作同一属性（会冲突导致抖动）
- 显示前杀旧 tween 防残留

## Quest 引擎架构（G2, 2026-05-29）
- **metric_effects 单一来源**：所有指标变化通过 dialogue choice 的 `metric_effects` 字段直接应用，quest_manager 的 `_apply_reward`/`_apply_penalty` 已注释掉（防止 dialogue 和 quest_manager 重复应用）
- **任务状态机闭环**：NPC 对话触发 → `_start_quest_if_available`（调用 `start_quest` → `activate_quest`）→ quest 变 active → 正确选择 `complete_quest` + toast | 错误选择 `fail_quest` + toast
- **repeat 守卫**：`complete_quest()` 和 `fail_quest()` 检查终态，已完成的 quest 不会再次触发
- **NPC-dialogue 数据关系**：`dialogues.json` 使用 `npc_id` 为 key 索引对话（而非 `npcs.json` 中的 `dialogue_id` 字段）。dialogue_manager 的 `_load_dialogues()` 遍历 `data.dialogues` 数组，按 `npc_id` 存入 `dialogues_data` 字典
- **fail_condition.action 与 dialogue choice action 必须一致**：`quests.json` 中的 `fail_condition.action` 应与对应 dialogue 错误分支的 `action` 字段精确匹配。T8 曾因 `"full_release_without_testing"` vs `"full_release"` 不匹配而修复