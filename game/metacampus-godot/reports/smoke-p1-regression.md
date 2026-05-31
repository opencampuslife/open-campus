# Smoke 回归验证报告：P1 仪器化

**日期**: 2026-05-28  
**测试**: P1 仪器化（LLM Bridge X-Bench + api_client.gd BENCH_MODE）未引发功能回归  
**执行**: g2 → g3 → g4 全量 smoke suite

## 结果

| Suite | 通过 | 总计 | 状态 |
|-------|------|------|------|
| G2.1 系统功能 | 35 | 35 | ✅ PASS |
| G3 API Bridge | 18 | 18 | ✅ PASS |
| G4 Demo Polish | 15 | 15 | ✅ PASS |
| **合计** | **68** | **68** | **✅ PASS** |

## 耗时

| 指标 | 耗时 |
|------|------|
| Godot 启动至 TestHarness 就绪 | ~0s |
| smoke_g2.py | ~15s |
| smoke_g3.py | ~17s |
| smoke_g4.py | ~17s |
| **总耗时** | **~49s** |

## 覆盖范围

- **G2**: System Health (6), Basic Controls (8), T1 知识库回答 (5), T2 错误/正确分支 (5), T3 材料催办 (3), T8 Canary 发布 (4), UI Observability (4)
- **G3**: Mode Switching (3), Mock Knowledge API (7), High Risk Guard (5), Mode OFF (1), G2 Regression (2)
- **G4**: Demo Reset (3), NPC Indicators (2), Metric Toasts (2), High Risk Warning (1), UI Readability (5), G2+G3 Regression (2)

## 结论

P1 仪器化（`tools/llm_bridge.py` X-Bench timing 和 `scripts/api_client.gd` BENCH_MODE 计时）**未引入功能回归**。全部 68 个检查项通过，所有功能行为与仪器化前一致。
