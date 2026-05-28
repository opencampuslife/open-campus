# Heart Mode Phase Roadmap

> 状态：P2+P3-C+P3-D 完成 · 最后更新：2026-05-28

## 1. 分阶段策略

Heart Mode 采用分阶段交付策略：P1 产设计文档和 Contract Schema，不上代码。P2 起逐步实现能力，每 Phase 有明确的交付物和验收标准。

## 2. Phase 总览

| Phase | 主题 | 风险等级 | 核心交付物 | 依赖 |
|-------|------|---------|-----------|------|
| P1 | 规格冻结与 Contract 建模 | Low | 文档 + JSON Schema | 无 |
| P2 | 只读 MVP | Medium | HeartEngine、TaskGraph、PlannerAgent、ResearchAgent、ReporterAgent、EvidenceStore | P1 |
| P3 | 审批后半自动执行 | High | ApprovalGate、ExecutorAgent、GitHubTool、ReviewerAgent、EvidenceGate | P2 |
| P4 | 测试、CI 与修复闭环 | Medium | TestRunner、CIReader、RepairLoop | P3 |
| P5 | Admin Console 可视化 | Low | HeartDashboard、TaskGraphView、ApprovalQueue、EvidenceTimeline | P2 |

## 3. P1：规格冻结与 Contract 建模（当前 Phase）

**目标**：定义 Heart Mode 的完整设计规范，不写运行时代码。

**交付物**：

```
docs/heart-mode/overview.md           # 工程定位、边界、非目标
docs/heart-mode/pipeline.md           # 7 阶段 Pipeline + 状态机
docs/heart-mode/agent-roles.md        # 6 角色定义 + 权限矩阵
docs/heart-mode/benchmark.md          # KPI + 验收指标
docs/heart-mode/phase-roadmap.md      # 本文档

contracts/schemas/heart-task.schema.json    # TaskRun / TaskNode
contracts/schemas/heart-event.schema.json   # EvidenceEvent / lifecycle events
contracts/schemas/heart-agent.schema.json   # AgentRole / permissions
contracts/schemas/heart-api.schema.json     # /api/heart/* 草案
```

**不交付**：Python 代码、Go 路由、前端页面、GitHub tool、LLM execution、自动任务执行。

**验收项**：见 benchmark.md §3。

## 4. P2：只读 MVP（✅ 完成）

**目标**：实现任务创建、规划、Agent 编排和 Evidence 记录。系统可读不可写。

**已实现文件**（`services/agent-orchestrator/src/heart/`）：

| 文件 | 职责 |
|------|------|
| `engine.py` | HeartEngine 主入口 |
| `models.py` | 数据模型 |
| `events.py` | EvidenceEvent |
| `store.py` / `store_sqlite.py` | 持久化（SQLite） |
| `evidence_gate.py` | evidence_gate 状态 |
| `approval.py` | ApprovalGate |
| `write_guard.py` | WriteGuard |
| `agents/base.py` | Agent 抽象基类 |
| `agents/planner.py` | PlannerAgent |
| `agents/researcher.py` | ResearchAgent |
| `agents/reporter.py` | ReporterAgent |
| `agents/executor.py` | ExecutorAgent |
| `agents/reviewer.py` | ReviewerAgent |
| `execution.py` | TaskExecution |
| `policies.py` | PolicyGate |
| `errors.py` | 错误类型 |
| `team.py` | Team 编排 |
| `api.py` | API 端点 |

**验收**：247 tests passing。

## 5. P3：审批后半自动执行（✅ P3-C + P3-D 完成）

**P3-C：WriteGuard + FakeGitHubAdapter（commit `9112c6e1`）**

- `apply_execution_plan()`: dry_run=True → FakeGitHubAdapter，生成 delivery_evidence
- WriteGuard: 分层规则（risk_level / approval / plan / file_size / protected_branch）
- delivery_evidence: task_id 去重（`delivery_{task_id}`）
- 状态边界：`apply_execution_plan` 不改 task 状态；`advance()` 才推进到 completed

**P3-D：RealGitHubAdapter + FeatureFlag（commit `8ce9bf7f`）**

| 组件 | 说明 |
|------|------|
| `GitHubProviderConfig` | 读 `HEART_GITHUB_WRITE_ENABLED` / `HEART_GITHUB_PROVIDER` / token / owner / repo；默认 write_enabled=False |
| `RealGitHubAdapter` | 依赖注入 HTTP client；无 requests 时自动降级 MockGitHubHTTPClient |
| `MockGitHubHTTPClient` | 全 mock：POST/PATCH/GET for refs、blobs、commits、PRs；追踪调用；预置 heads/main |
| `select_git_provider()` | 标志门控：`FeatureFlagDisabled`（非 ValueError）|
| `apply_execution_plan()` | `provider=real` + `dry_run=False` 时触发真实写入；delivery_evidence 含 git_results |

**门控条件**（`dry_run=False` 必须同时满足）：
1. `HEART_GITHUB_WRITE_ENABLED=1`
2. `HEART_GITHUB_PROVIDER=real`
3. `HEART_GITHUB_TOKEN` + `HEART_GITHUB_OWNER` + `HEART_GITHUB_REPO` 均已设置
4. WriteGuard 全部通过
5. 任务处于 evidence_gate 状态

**验收**：270 tests passing。

**新增文件**：

```
services/agent-orchestrator/src/heart/
├── approval.py             # ApprovalGate
├── tools/
│   └── github.py           # 受控 GitHub 操作
└── agents/
    ├── executor.py          # ExecutorAgent
    └── reviewer.py          # ReviewerAgent

contracts/schemas/heart-approval.schema.json

control-plane/internal/gatewayhttp/
└── heart_routes.go          # /api/heart/* 路由注册
```

## 6. P4：测试、CI 与修复闭环

**新增文件**：

```
services/agent-orchestrator/src/heart/
├── tools/
│   ├── test_runner.py       # TestRunner
│   └── ci_reader.py         # CIReader
└── repair_loop.py           # RepairLoop（MAX_RETRIES=3）
```

## 7. P5：Admin Console 可视化

**新增文件**：

```
apps/admin-console/src/pages/
├── HeartDashboard.tsx
├── HeartTaskGraphView.tsx
├── HeartApprovalQueue.tsx
└── HeartEvidenceTimeline.tsx
```

## 8. 推荐落地顺序

```
P1 → P2 → EvidenceStore + Go 路由 → P3 → P4 → P5
```

P2 产出后即可通过 Go shadow gateway 进行低风险 canary 验证，不必等全部 Phase 完成再上线。
