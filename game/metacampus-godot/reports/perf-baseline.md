# MetaCampus Perf Baseline Report

> Generated: 2026-05-28 05:32:51
> Engine: Godot 4.6.3 (GL Compatibility), Pure GDScript

---

## 环境信息

| 项目 | 值 |
|------|-----|
| 主机 | macOS (Apple Silicon) |
| Godot 版本 | 4.6.3.stable |
| 渲染器 | GL Compatibility |
| 运行模式 | headless (CPU profiling) |
| 采集脚本 | `tools/perf_capture.gd` |
| 采样时长 | 35s / run |
| 每轮样本数 | ~5071 frames |
| NPC 梯度 | 10, 50, 100, 300 |
| 基线状态 | **纯 GDScript** (GDExtension 迁移前) |


## NPC 梯度性能对比

| NPC 数 | FPS avg | FPS min | 帧处理 P50(μs) | 帧处理 P95(μs) | 帧处理 P99(μs) | Physics P95(μs) | Spike 频率 | 内存 |
|--------|---------|---------|----------------|----------------|----------------|-----------------|------------|------|
| 10 | 144.91 | 144.0 | 0.6 | 2.6 | 5.3 | 1.6 | 0.0 | 282.1 MB |
| 50 | 144.91 | 144.0 | 0.5 | 1.3 | 4.0 | 2.4 | 0.0 | 283.7 MB |
| 100 | 144.91 | 144.0 | 0.7 | 1.4 | 1.7 | 1.1 | 0.0 | 285.7 MB |
| 300 | 144.94 | 144.0 | 1.1 | 3.3 | 5.4 | 0.7 | 0.0 | 293.6 MB |


## API 延迟统计 (mock mode)

| 指标 | 值 |
|------|-----|
| 采样数 | 60 |
| 失败数 | 0 |
| 平均 (ms) | 10.83 |
| P50 (ms) | 11.96 |
| P95 (ms) | 15.66 |
| P99 (ms) | 15.9 |
| 最小 (ms) | 1.86 |
| 最大 (ms) | 15.9 |

> API 通过 TestHarness HTTP 端点 (/api/ask) 测量，mode=mock。
> 包括 HTTP 序列化/反序列化 + GDScript 处理开销。


## Smoke 测试全量耗时

| Phase | 耗时 | 结果 |
|-------|------|------|
| G2 | 4.37s | ✅ |
| G3 | 1.08s | ✅ |
| G4 | 5.39s | ✅ |
| **合计** | **10.8s** | ✅ All PASS |


## JSON 配置加载耗时

| 文件 | 冷加载(μs) | JSON解析(μs) | 热加载(μs) |
|------|-----------|-------------|-----------|
| `api_config.json` | 127μs | 29μs | 19μs |
| `dialogues.json` | 224μs | 128μs | 31μs |
| `locations.json` | 127μs | 50μs | 21μs |
| `npcs.json` | 98μs | 61μs | 22μs |
| `quests.json` | 150μs | 111μs | 30μs |


## 结论

- **NPC 规模缩放**: 从 10 NPC → 300 NPC, 帧处理 P95 从 **2.6μs** 增长到 **3.3μs** (1.3x)。
  - 缩放效率较好 (< 30x NPC 增长对应 < 10x 开销增长)
- **内存增长**: 10→300 NPC 内存增量 11.5 MB (每 NPC ~41620 bytes)
- **API P95 延迟**: 15.66ms (mock mode, 60 samples)
- **Smoke 全量耗时**: 10.8s (全部通过)

> 此报告作为 **GDExtension 迁移基线**。
> GDExtension 迁移后需对比此基线，P95 帧处理改善 ≥30% 方可通过准入。