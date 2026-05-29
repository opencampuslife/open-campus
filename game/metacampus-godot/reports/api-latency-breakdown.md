# MetaCampus API Latency Breakdown

> Generated: 2026-05-28 15:55:55
> Engine: Godot 4.6.3 (headless), GDScript api_client, llm_bridge.py → DeepSeek

---

## 测试环境

| 项目 | 值 |
|------|-----|
| 主机 | macOS (Apple Silicon) |
| Godot | 4.6.3.stable |
| 渲染器 | headless (SceneTree) |
| 采集脚本 | `tools/api_latency_capture.gd` |
| 采样数 | 30 / mode |
| 查询间隔 | 50ms |
| 桥接服务 | `tools/llm_bridge.py` → DeepSeek API |
| 采集时间 | 2026-05-28 15:55:55 |
| Fallback 超时 | 3000ms (patched) |


## 验收表 — 多模式延迟对比

| mode | samples | avg | median | P95 | P99 | error rate | main bottleneck |
|------|---------|-----|--------|-----|-----|------------|-----------------|
| mock | 30 | 0.01ms | 0.01ms | 0.03ms | 0.04ms | 13.3% | api_client internal routing (GDScript) |
| off | 29 | 0.01ms | 0.01ms | 0.04ms | 0.06ms | 13.8% | api_client internal routing (GDScript) |
| live | 30 | 4.90s | 4.89s | 9.17s | 13.35s | 13.3% | LLM provider API round-trip |
| fallback | 30 | 11.55ms | 13.80ms | 14.30ms | 14.64ms | 100.0% | HTTP timeout waiting for LLM Bridge |


## Mock 模式 — 本地响应匹配

Mock 模式下 `api_client` 从本地 `mock_knowledge_responses.json` 匹配回答，不发起任何网络请求。

| 指标 | 值 |
|------|-----|
| 采样数 | 30 |
| 平均 | 0.01ms |
| P50 (中位数) | 0.01ms |
| P95 | 0.03ms |
| P99 | 0.04ms |
| 最小值 | 0.01ms |
| 最大值 | 0.04ms |
| 错误率 | 13.3% |

> Mock 延迟代表 **api_client 内部 GDScript 路由 + 字符串匹配开销**，不含网络。
> 这是所有模式的性能下限基线。


## Off 模式 — API 关闭

Off 模式下 `api_client` 立即返回离线提示，不查询 mock 数据也不发起网络请求。

| 指标 | 值 |
|------|-----|
| 采样数 | 29 |
| 平均 | 0.01ms |
| P50 (中位数) | 0.01ms |
| P95 | 0.04ms |
| P99 | 0.06ms |
| 最小值 | 0.01ms |
| 最大值 | 0.06ms |
| 错误率 | 13.8% |

> Off 延迟代表 **函数返回 + Bench 记录的最小开销**，几乎全部在 µs 级别。


## Live 模式 — 全链路 (Godot → Bridge → DeepSeek)

Live 模式经过完整调用链：Godot `api_client` → HTTP POST → `llm_bridge.py` → DeepSeek API。

| 指标 | 值 |
|------|-----|
| 采样数 | 30 |
| 平均 | 4.90s |
| P50 (中位数) | 4.89s |
| P95 | 9.17s |
| P99 | 13.35s |
| 最小值 | 0.01ms |
| 最大值 | 13.35s |
| 错误率 | 13.3% |

### 耗时分解

| 阶段 | 占比 |
|------|------|
| JSON 序列化 (serialize_us) | 0.0% |
| HTTP 发送 (send_us) | 0.0% |
| LLM Provider + 网络 (推断值) | 100.0% |
| 响应解析 (parse_us) | 0.0% |
| 回调调度 (callback_us) | 0.0% |

> 平均总耗时 = 4902.92ms

> Live 延迟由 **DeepSeek API 响应时间** 主导（通常 1-5s），GDScript 侧开销仅占 <1%。


## Fallback 模式 — Bridge 不可达时的降级

Fallback 模式下 `llm_bridge.py` 已停止，`api_client` 尝试 live 请求 → HTTP 超时 (3000ms)
→ 自动降级到 mock 响应。此模式的超时配置为临时修改 `api_config.json` 的 `timeout_ms`。

| 指标 | 值 |
|------|-----|
| 采样数 | 30 |
| 平均 | 11.55ms |
| P50 (中位数) | 13.80ms |
| P95 | 14.30ms |
| P99 | 14.64ms |
| 最小值 | 0.01ms |
| 最大值 | 14.64ms |
| 错误率 | 100.0% |
| 超时配置 | 3000ms |

> Fallback 总延迟 = HTTP 超时等待 + mock 响应时间。生产环境 `timeout_ms=20000`（20s），
> 基准测试中临时降为 3000ms 以加快采集。生产 Fallback 延迟约为此值 × (20000 / 3000)。


## 综合分析

- **Mock P95 = 0.03ms** — GDScript 内部路由开销极小（sub-ms 级）。
- **Off P95 = 0.04ms** — 几乎为零，仅函数调用开销。
- **Live 模式 P95 = 9.17s** — 是 Mock 的 **305522x**，由 DeepSeek API 决定。
  - LLM provider 占全部延迟的 **100.0%** （GDScript 侧开销 <1%）
- **Fallback 平均 = 11.55ms** （超时=3000ms）。
  - 生产环境 `timeout_ms=20000` 下预期 Fallback 延迟 ~20s，建议优化。

### 优化建议
1. **Live 延迟高**由 LLM API 决定，非 Godot 侧问题。考虑引入响应缓存或预取。
3. **Mock 模式延迟极低（sub-ms）** — 适合作为离线模式和默认降级方案。
