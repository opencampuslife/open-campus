# MetaCampus G3 — API Bridge 文档

## 概述

G3 引入 ApiClient，实现知识库查询 (`POST /api/knowledge/ask`) 的 mock/live 双模式切换。

## 模式

| mode | 行为 |
|------|------|
| `mock` (默认) | 读 `data/mock_knowledge_responses.json`，离线可用 |
| `live` | 调真实 `POST /api/knowledge/ask`，失败自动 fallback mock |
| `off` | 返回 "AI 工具暂不可用"，所有查询被禁用 |

## 配置

`data/api_config.json`:

```json
{
  "mode": "mock",
  "base_url": "http://127.0.0.1:8787",
  "timeout_ms": 2500,
  "fallback_to_mock": true
}
```

## 安全边界

游戏层持有独立的高风险关键词表，与后端 API 返回无关：

```
保证录取、内部名额、特殊照顾、走后门、包进、
承诺录取、一定能上、百分百录取
```

即使 live API 返回了看似承诺性内容，游戏层也会强制 `handoff_required=true`。

## TestHarness 端点

| 端点 | 说明 |
|------|------|
| `GET /api/ask?q=...` | Mock 模式下直接查询 |
| `GET /api/mode` | 查看当前模式 |
| `GET /api/mode?set=mock\|live\|off` | 切换模式 |

## 测试

```bash
python3 tools/smoke_g2.py   # G2 回归 (35 checks)
python3 tools/smoke_g3.py   # G3 API 测试
```
