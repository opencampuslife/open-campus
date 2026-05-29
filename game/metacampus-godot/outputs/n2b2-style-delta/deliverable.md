# N2B-2 Style Delta — Deliverable

> 日期：2026-05-28 | 负责人：Narrative Designer

---

## Summary

完成 N2B-2 风格修正分析：读取 npc-style-bible.md v1.1 §11、npc-visual-baseline-review.md、n2b1-animation-integration.md，识别暗黑复古/噪点过多两个核心问题，产出风格修正硬门槛表（10 项）、admissions_director 和 student_representative 各一套修订后 AI 生图 prompt（portrait×4表情 + idle sprite + walk sheet×4方向）、以及可推广至 8 NPC 的 npc-palette-guide-v1.md 完整色板规范。

---

## Changed Files

### 产出文件（位于 outputs/n2b2-style-delta/）

| # | 文件 | 类型 | 说明 |
|---|------|------|------|
| 1 | `style-correction-checklist.md` | 风格修正表 | 10 项硬门槛 + 正向/禁止关键词 + 验证方法 |
| 2 | `revised-prompts-admissions-director.md` | AI Prompt | admissions_director × portrait 4表情 + idle sprite + walk 4方向 |
| 3 | `revised-prompts-student-representative.md` | AI Prompt | student_representative × portrait 4表情 + idle sprite + walk 4方向 |
| 4 | `npc-palette-guide-v1.md` | 色板规范 | 5主色+8辅色+肤色规范+8 NPC分配+正/负向关键词+使用规则 |

### 绝对路径

```
/Users/kevinzzz/Documents/database/gaokao-agent/game/metacampus-godot/outputs/n2b2-style-delta/style-correction-checklist.md
/Users/kevinzzz/Documents/database/gaokao-agent/game/metacampus-godot/outputs/n2b2-style-delta/revised-prompts-admissions-director.md
/Users/kevinzzz/Documents/database/gaokao-agent/game/metacampus-godot/outputs/n2b2-style-delta/revised-prompts-student-representative.md
/Users/kevinzzz/Documents/database/gaokao-agent/game/metacampus-godot/outputs/n2b2-style-delta/npc-palette-guide-v1.md
```

---

## Notes

- **核心修正方向**：暗黑复古 → 明亮温暖（主色 #2D4A6B 深蓝 + #F5E6D3 暖白）、噪点消除（明确禁止 noise/grain/dithering）
- **肤色强制统一**：所有 NPC 面部/手部使用 #F4C7A1，无变体
- **校长唐毓色板超限**：西装+衬衫+领带+校徽共 6 色，需精简为 5 色（建议领带改 S1 深灰）
- **规范出处**：所有色值和规格均来自 npc-style-bible.md v1.1 §11，可直接引用
- **待验证**：palette guide 中校长色板精简方案待 pixel-artist 确认后写入 npc-style-bible.md