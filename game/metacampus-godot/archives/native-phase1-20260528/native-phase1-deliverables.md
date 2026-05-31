# Native Phase 1 — Deliverables Inventory

> 归档于：2026-05-28
> 项目：MetaCampus 2D (Godot 4.6.3)
> 目标：GDExtension 可用性验证 + 性能基线采集 + 迁移决策

---

## 1. 核心文档

| # | 文件 | 内容 | 验证状态 |
|---|------|------|----------|
| 1 | `reports/project-structure.md` | Godot 版本、godot-cpp 版本、12 GDScript 模块清单（2665 LOC）、Smoke 测试结构 | ✅ Verifier PASS |
| 2 | `reports/perf-baseline.md` | NPC 梯度 10/50/100/300 的 FPS/P50/P95/P99/Physics/内存/Spike；API 延迟；Smoke 耗时；JSON 加载 | ✅ Verifier PASS |
| 3 | `reports/gdextension-poc.md` | 构建链搭建、C++ 源码、验证结果、注意事项 | ✅ Verifier PASS |
| 4 | `reports/native-phase1-decision.md` | 决策记录 + 证据链 + 后续优先级 | ✅ 已归档 |

## 2. GDExtension 构建产物

| 产物 | 路径 | 用途 | 验证 |
|------|------|------|------|
| C++ 源文件 | `src/native/` (4 文件) | MetaCampusNative class + register_types | ✅ |
| 构建脚本 | `SConstruct` | SCons 入口：编译 godot-cpp → 编译扩展 | ✅ |
| 扩展配置 | `metacampus_native.gdextension` | Godot 加载入口符号配置 | ✅ |
| macOS .dylib | `bin/libmetacampus_native.macos.template_debug.framework/` | arm64 .dylib (201 KB) + Info.plist | ✅ Godot headless 加载 |

## 3. 性能基准工具链

| 工具 | 路径 | 用途 |
|------|------|------|
| Python 编排器 | `tools/perf_baseline.py` | 多轮采集、汇总 CSV、生成 Markdown 报告 |
| GDScript 采集 | `tools/perf_capture.gd` | Godot headless 帧耗时采集脚本 |
| 原始数据 | `tools/perf_output/` | 各梯度 CSV + JSON summaries |
| 聚合数据 | `reports/perf-baseline-data.csv` | 四梯度对比表 |

## 4. 如何复现

### GDExtension 构建
```bash
cd metacampus-godot
scons platform=macos arch=arm64 target=template_debug -j$(sysctl -n hw.logicalcpu)
# 产出: bin/libmetacampus_native.macos.template_debug.framework/
```

### Godot 加载验证
```bash
/path/to/Godot.app/Contents/MacOS/Godot --headless --path . --quit
# 期望: 无崩溃、TestHarness 正常、无 GDExtension load error
```

### 性能基线采集
```bash
python tools/perf_baseline.py
# 产出: reports/perf-baseline.md + perf-baseline-data.csv
```

## 5. 关键技术决策

| 决策 | 判断 | 核心依据 |
|------|------|----------|
| GDExtension 技术路线 | ✅ 验证通过 | godot-cpp 编译、加载、调用全链路通 |
| NativePathfinder Phase 2 | ❌ 暂停 | 寻路 P95 仅 3.3μs，不是性能瓶颈 |
| API 延迟为下一步重心 | ✅ P1 | API P95 15.66ms，是寻路的 4,500 倍 |

## 6. 后续使用指引

- 新模块如需 C++ 原生化：参照 `src/native/` 结构 + `metacampus_native.gdextension` 注册方式
- 性能基准工具链可直接用于其他 Godot 项目（`--headless` + `perf_capture.gd`）
- 决策记录可作为后续"要不要做 C++ 迁移"的参考模板
- PoC 构建产物（`.dylib`）在 `bin/` 下，可直接附加到 Godot 导出包
