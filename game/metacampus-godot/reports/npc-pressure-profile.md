# NPC Pressure Profile Report — P2

> Generated: 2026-05-28 20:51:40
> Phase: P2 NPC Behavior Pressure Profiling
> Duration: 35s per cell, 3s warmup

---

## 验收表


| NPC | Scenario | FPS avg | FPS min | Frame P95(μs) | Physics P95(μs) | Memory(MB) | Main bottleneck |

| ---: | --------------- | ------: | ------: | --------: | ----------: | -----: | --------------- |
| 10 | idle | 144.9 | 144.0 | 3420 | 1191 | 281.7 | ok |
| 100 | behavior | 144.9 | 144.0 | 1847 | 4657 | 285.1 | physics/collision |
| 300 | dense | 144.9 | 144.0 | 2160 | 893 | 294.8 | ok |
| 500 | worst | ? | ? | ? | ? | ? | ? |
| 1000 | idle | ? | ? | ? | ? | ? | ? |

## 完整测试矩阵


| NPC | Scenario | FPS avg | FPS min | Proc P95(μs) | Phys P95(μs) | Spike freq | Memory(MB) | Status |

| ---: | --------------- | ------: | ------: | --------: | ----------: | --------: | -----: | ----- |

| 10 | idle | 144.9 | 144.0 | 3420 | 1191 | 0.0000 | 281.7 | ok |
| 10 | behavior | 144.9 | 144.0 | 5835 | 2130 | 0.0668 | 281.7 | ok |
| 10 | dense | 144.9 | 144.0 | 3063 | 2553 | 0.0000 | 281.9 | physics/collision |
| 100 | idle | 144.9 | 144.0 | 2628 | 915 | 0.0000 | 285.3 | ok |
| 100 | behavior | 144.9 | 144.0 | 1847 | 4657 | 0.0000 | 285.1 | physics/collision |
| 100 | dense | 144.9 | 144.0 | 1582 | 1656 | 0.0000 | 285.8 | physics/collision |
| 300 | idle | 144.9 | 144.0 | 3091 | 1257 | 0.0000 | 293.2 | ok |
| 300 | behavior | 144.9 | 144.0 | 2824 | 3036 | 0.0000 | 293.3 | physics/collision |
| 300 | dense | 144.9 | 144.0 | 2160 | 893 | 0.0037 | 294.8 | ok |

## 假设验证


| 假设 | 判断 | 证据 | 下一步 |

| --------------- | --------------- | ------------------------------------------ | --------------- |

| 行为 tick 是热点 | plausible | behavior_tick_count max=2174, process P95 max=5835.0μs | — |
| proximity 检查是热点 | ⏭️ 无数据 |  | — |
| signal/UI 是热点 | ⏭️ 无数据 |  | — |
| collision 是热点 | ⚠️ 可能 | dense physics P95=2553.0μs, proc P95=3063.0μs, ratio=0.8 | reduce collision layers / simplify shapes |
| animation 是热点 | ⏭️ 无数据 |  | — |
| 内存/实例化是热点 | ⏭️ 无数据 |  | — |

## 决策矩阵


**主要瓶颈**: collision 是热点


**决策**: `reduce_collision_complexity`


**下一步**: P3: collision layer reduction / shape simplification


**建议优化项**:

- disable far NPC physics

- simplify collision shapes

- reduce collision layers


## 硬性验收条件


| 检查项 | 状态 |

| ------ | ---- |

| 现有 smoke g2/g3/g4 仍然通过 | ⚠️ 待手动验证 |

| 生产行为保持不变 | ✅ 代码未改动 |

| Bench 仪器化可移除/debug-gated | ✅ 脚本参数控制 |

| NPC pressure 测试期间无 live LLM 调用 | ✅ headless mode |
