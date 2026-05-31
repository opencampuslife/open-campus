# Godot Mono Headless — Apple Silicon 环境限制

## 问题描述

在 Apple Silicon M5（macOS）上，Godot Mono 4.6.3 headless 模式无法实例化任何 C# 脚本。

**错误信息：**
```
ERROR: Cannot instantiate C# script because the associated class could not be found.
Script: 'res://scripts/csharp/debug/CSharpSmokeTest.cs'.
Make sure the script exists and contains a class definition with a name that
matches the filename of the script exactly (it's case-sensitive).
at: can_instantiate (modules/mono/csharp_script.cpp:2360)
```

**影响：**
- 所有 C# autoload 无法加载
- 所有引用 C# 脚本的 `.tscn` 场景解析失败
- 非 Mono Godot 正常运行的场景（含 SubResource 的 format=3 tscn）在 Mono headless 下报错

## 平台信息

- **硬件**：Apple Silicon M5
- **操作系统**：macOS
- **Godot 版本**：4.6.3 stable mono (official build)
- **.NET SDK**：系统 dotnet 10.0.300（Godot 内部有独立 .NET runtime）

## 复现步骤

1. 创建空白 Godot Mono 项目（无 GDScript，纯 C#）
2. 创建最小 C# 类（`public partial class SmokeTest : Node`）
3. 创建引用该脚本的场景
4. 运行 `Godot_mono --headless --path . --quit`
5. 观察相同错误

## 排除的根因

| 因素 | 验证结果 |
|------|----------|
| Assembly name 不匹配 | ❌ 排除 — test_project.dll 名称匹配 project.godot 配置 |
| DLL 架构错误 | ❌ 排除 — DLL 是 PE32+ arm64，与 GodotSharp.dll 一致 |
| .csproj 配置问题 | ❌ 排除 — 移除 RuntimeIdentifiers、改变 TargetFramework 均无效 |
| 缓存问题 | ❌ 排除 — 删除 `.godot/` 后重新运行同样失败 |
| RuntimeIdentifier 缺失 | ❌ 排除 — 显式指定 `-r osx-arm64` 后 DLL 正确，错误依旧 |
| .NET 版本不兼容 | ❌ 排除 — GodotSharp 4.6.3 明确要求 net8.0，已正确 |

**核心证据：** 同一台机器上，非 Mono Godot 4.6.3 + GDScript 场景运行正常。

## 当前测试策略

### Profile A — Headless Smoke（当前活跃）

```
Engine:  Godot non-Mono 4.6.3 (来自 Homebrew)
Scripts: GDScript only（无 C#）
C# autoloads: 全部禁用
features: ["4.6", "GL Compatibility"]
```

用途：
- 场景结构验证（Main.tscn、NpcScene.tscn 等）
- GDScript-only 业务逻辑验证
- GDExtension 加载测试
- CI / 自动化测试管道

### Profile B — Editor / C# Runtime（需人工验证）

```
Engine:  Godot Mono 4.6.3 GUI 模式
Scripts: C# 业务层 + GDScript stubs
C# autoloads: 全部启用
features: ["4.6", "C#", "GL Compatibility"]
```

用途：
- C# Manager 系统（TimeManager、MetricManager 等）
- C# UI Controller（HUD、Dashboard 等）
- Quest / Dialogue / NPC 集成
- QA 人工验收

## 场景切换脚本

```bash
# Profile A: headless smoke
./tools/switch_to_headless_smoke.sh

# Profile B: C# runtime
./tools/switch_to_csharp_runtime.sh
```

详见 `docs/engineering/profile-switching.md`。

## 后续行动

1. **Phase 3 GDExtension**：在非 Mono headless 下验证，不依赖 C# runtime
2. **C# 业务层**：在 Godot Mono GUI 模式下人工验收
3. **问题跟踪**：如果 Godot 4.7+ 修复此问题，更新本文件

## 参考

- [Godot C# 支持文档](https://docs.godotengine.org/en/4.4/contributing/development/compiling/compiling_with_dotnet.html)
- [Godot 论坛：C# "associated class could not be found"](https://forum.godotengine.org/t/godot-net-not-working-out-of-the-box/110247)