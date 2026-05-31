# visual-style-rules — Done

> 完成时间：2026-05-28 16:15
> 执行者：pixel-artist

## 完成内容

1. **docs/npc-style-bible.md v1.1 追加** — 第十一节 视觉深化规范，含角色比例 64px/1:4、立绘 256×256、sprite 4帧 walk sheet 150ms、服装色板（5主色 + 8辅色）、禁止视觉元素（6类禁止+6类正向关键词）

2. **prompts/npc_image_prompt_template.md** — 立绘生成（正面/3/4视角）、表情生成（4种表情×描述速查）、sprite 生成（单帧+walk sheet），全部使用 {{VARIABLE}} 占位符，含完整填充示例

3. **prompts/npc_video_prompt_template.md** — 4类动作视频（对话待机/表情切换/行走循环/手势）、2类场景视频（NPC场景定位/场景空镜），含场景描述速查表和手势动作速查表

## 合规检查

- ✅ 禁止视觉元素清单已包含：农田、牧场、Stardew Valley 元素、乡村、奇幻、古风、低幼化
- ✅ 色板仅使用授权颜色，肤色 #F4C7A1 全角色统一
- ✅ 所有模板使用变量占位符（非硬编码 NPC 数据）
- ✅ 与 npc-style-bible.md v1.0 原有内容不冲突（v1.1 为深化补充）
