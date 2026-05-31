# NPC Registry Module — 完成标记

- **完成时间**: 2026-05-28 16:00
- **模块**: NPC Registry (Autoload 单例 + 工厂 + Persona Bridge)
- **状态**: ✅ done

## 交付清单

| 文件 | 类型 | 说明 |
|------|------|------|
| `scripts/npc_registry.gd` | 新建 | Autoload 单例：加载/查询 NPC profile |
| `scripts/npc_factory.gd` | 新建 | NPC 节点工厂：根据 profile 生成场景节点 |
| `scripts/npc_persona_bridge.gd` | 新建 | Persona-LLM 桥接：生成 system prompt |
| `project.godot` | 修改 | 注册 NpcRegistry 为第 7 个 Autoload |

## 依赖验证

- NpcRegistry 加载 `data/npcs/npc_*.json`（8 个文件，narrative-designer 已创建）
- NpcPersonaBridge 读取 `data/personas/<npc_id>.md`（5 个已就绪，3 个 narrative-designer 正在创建中）
- 已注册的 6 个 Autoload 全部保留（TestHarness / JsonLoader / QuestManager / MetricManager / ApiClient / VisualFeedback）

## 已知限制

1. `data/personas/` 中 parent_representative、principal、student_representative 的 .md 文件尚未创建（narrative-designer 的 npc-persona-prompts 任务还在 in_progress），NpcPersonaBridge 会优雅降级为仅使用 JSON profile 生成 prompt。
2. NpcFactory.create_npc() 依赖 NPCController 类（已有，`scripts/npc_controller.gd`），未引入新类。
