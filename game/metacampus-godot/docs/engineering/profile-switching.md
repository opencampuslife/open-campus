# Profile Switching Guide

## 概述

MetaCampus 2D 项目在 Apple Silicon 上存在 Godot Mono headless bug。
为了支持自动化测试和人工验证，提供两个 Profile：

| Profile | Engine | C# | GDScript stubs | 用途 |
|---------|--------|-----|----------------|------|
| A: Headless Smoke | non-Mono | ❌ | ✅ | CI / GDExtension / 场景验证 |
| B: C# Runtime | Godot Mono GUI | ✅ | ❌ | 业务层 / UI / Quest 系统 |

## Profile A: Headless Smoke

**运行方式：**
```bash
cd game/metacampus-godot
./tools/switch_to_headless_smoke.sh
/Applications/Godot.app/Contents/MacOS/Godot --headless --path . --quit
```

**激活的组件：**
- `project.godot`: features 无 "C#"，main_scene = scenes/Main.tscn
- C# autoloads: 全部注释（16个）
- AudioManager: GDScript stub（`scripts/audio_manager.gd`）
- UI scripts: 9个 GDScript stub（`scripts/csharp/**/*.gd`）
- 9个 C# UI 脚本已备份为 `.cs.bak`
- NpcScene.tscn: format=3，SubResource 在 node 之前

**验证项：**
```bash
# 场景加载
./tools/switch_to_headless_smoke.sh
/Applications/Godot.app/Contents/MacOS/Godot --headless --path . --quit

# GDExtension 加载
./tools/switch_to_headless_smoke.sh
# 确保 .godot/extension_list.cfg 有 native extension
/Applications/Godot.app/Contents/MacOS/Godot --headless --path . --quit
```

## Profile B: C# Runtime

**运行方式：**
1. 打开 Godot Mono GUI：`/Users/kevinzzz/Applications/Godot_mono.app/Contents/MacOS/Godot`
2. 打开项目：`game/metacampus-godot`
3. 或执行切换脚本后用 Godot Mono headless（需验证是否仍有问题）

**激活的组件：**
- `project.godot`: features 包含 "C#"
- C# autoloads: 全部取消注释
- UI scripts: `.cs` 恢复，`.gd` stub 作为备用
- Main.tscn 引用 C# scripts（NpcScheduleVisualizer.cs 等）

**切换脚本：**
```bash
./tools/switch_to_csharp_runtime.sh
```

## 切换脚本操作对照

### `switch_to_headless_smoke.sh`

| 操作 | 原状态 | 新状态 |
|------|--------|--------|
| C# UI scripts | `*.cs` | `*.cs.bak` |
| GDScript stubs | `*.gd` | ✅ 活跃 |
| scene 引用 | `.cs"` | `.gd"` |
| C# autoloads | 取消注释 | 注释 |
| features | 包含 "C#" | 无 "C#" |
| AudioManager | C# | GDScript stub |

### `switch_to_csharp_runtime.sh`

| 操作 | 原状态 | 新状态 |
|------|--------|--------|
| C# UI scripts | `*.cs.bak` | `*.cs` 恢复 |
| GDScript stubs | ✅ 活跃 | 保留作为备用 |
| scene 引用 | `.gd"` | `.cs"`（如果 .cs 存在）|
| C# autoloads | 注释 | 取消注释 |
| features | 无 "C#" | 包含 "C#" |

## 验证命令

```bash
# 当前 profile
grep '^config/features' project.godot

# C# autoloads 状态
grep -c '^;' project.godot  # 应该为 16（headless）或 0（C# runtime）

# UI scripts 状态
find scripts/csharp/ui -name '*.cs' ! -name '*.cs.bak' | wc -l  # headless=0, C# runtime=8
```

## 注意事项

- **不要**手动编辑 `.tscn` 文件切换 — 使用脚本
- **不要**同时保留 `.cs` 和 `.gd` 同名文件（会导致资源路径混乱）
- 切换后建议运行 smoke test 确认场景加载正常
- Profile B（C# Runtime）目前依赖 Godot Mono GUI 人工验证，headless 仍有 bug