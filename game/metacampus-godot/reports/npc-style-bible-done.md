# NPC Style Bible — 完成标记

> 版本：v1.0
> 日期：2026-05-28
> 产出文档：docs/npc-style-bible.md

---

## 完成状态

✅ **NPC 风格圣经已完成** — docs/npc-style-bible.md 已创建并包含以下 8 个核心章节：

| # | 章节 | 内容概述 |
|---|------|----------|
| 1 | 世界观定位 | 校园 AI 运营模拟身份定义、NPC 角色树、禁止 Stardew-like 元素 |
| 2 | 角色视觉规范 | 2D cozy campus 风格、颜色分配、Godot sprite 可读性规范 |
| 3 | 表情规则 | 4 种表情定义 (neutral/happy/worried/strict)、设计原则、文件命名 |
| 4 | 命名规则 | npc_id snake_case、display_name 中文、location 英文标识 |
| 5 | 资产目录结构 | assets/npcs/<npc_id>/ 完整目录树、prompt 文件模板 |
| 6 | JSON 数据规范 | quest_ids + metric_effects 必填、Schema 定义、一致性校验清单 |
| 7 | Persona 安全规则 | 三大禁止承诺、对话安全边界、敏感词库 |
| 8 | 禁止事项 (Hard Rules) | 8 条绝对禁止 + 5 条设计禁区 |

## 审计发现

| 项目 | 状态 | 说明 |
|------|------|------|
| npcs.json metric_effects | ❌ 5 个条目全缺 | 需补充四指标基线 |
| 未注册 NPC | ⚠️ 2 个 | canteen_staff、academic_affairs 在 dialogues.json 但不在 npcs.json |
| 表情资产 | ❌ 全部缺失 | 5 个 NPC 均无 4 表情 sprite |
| prompt 文件 | ❌ 全部缺失 | 5 个 NPC 均无 _prompt.md |

## 下一步

1. 补充 npcs.json 全部 metric_effects 字段
2. 注册或清理 dialogues.json 中的游离 NPC
3. 按样式圣经绘制 5 角色 × 4 表情 = 20 张表情 sprite（可委派 pixel-artist）
4. 为每个 NPC 编写 prompt.md

---

*此文件标记 NPC 风格圣经 v1.0 已完成，后续迭代应更新 docs/npc-style-bible.md 的版本历史。*
