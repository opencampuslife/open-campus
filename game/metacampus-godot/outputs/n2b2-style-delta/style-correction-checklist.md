# N2B-2 Style Delta Checklist — 风格修正硬门槛表

> 版本：v1.0
> 日期：2026-05-28
> 用途：分析 N2A 当前资产的风格偏差，产出精确修正方向
> 覆盖 NPC：admissions_director (周明远)、student_representative (沈一诺)
> 关联规范：docs/npc-style-bible.md v1.1 §11

---

## 1. 风格修正硬门槛对照表

| # | 项目 | 当前问题 | 目标规范 | npc-style-bible 引用 | 修正优先级 |
|---|------|----------|----------|---------------------|------------|
| 1 | **色调** | 暗黑复古风，白/黑高对比，饱和度过高或过低 | 明亮温暖：主色饱和度适中，环境光柔暖，不得出现纯黑 (#000) 或纯白 (#FFF) 大面积色块 | §11.6.1 主色板（饱和度参考值：深蓝 45-74-107、暖白 245-230-211） | P0 |
| 2 | **对比度** | 偏高（黑白对比极端化，缺乏灰阶过渡） | 中等对比：主色与辅色差值 40-60% 亮度，明暗层次 2-3 级 | §11.6.3 色板使用规则：不超过 5 种颜色 | P0 |
| 3 | **服装色精确度** | 服装色调泛化，未使用 npc-style-bible §11.5 的精确色值 | 必须使用 §11.5 规范色值：招生办主任深蓝西装 #2D4A6B + 白衬衫 #F5E6D3；学生代表校服衬衫 #F5E6D3 + 深蓝外套 #2D4A6B | §11.5 服装规范（精确 Hex 值） | P0 |
| 4 | **场景联想** | 复古 RPG 石板路/地牢感，与 Stardew/法式乡村暧昧 | 现代校园场景：现代建筑、玻璃幕墙、暖色地砖、温馨灯光，无中世纪/奇幻元素 | §11.7 禁止视觉元素（乡村/农业、奇幻、Stardew） | P1 |
| 5 | **角色气质** | 戏剧化/戏剧张力强，表情夸张，色彩饱和度极端 | 专业可亲：中性面部表情，饱和度适中，色彩协调，无过度表情化 | §2.1 总体风格：温暖、干净、可读性强 | P1 |
| 6 | **线条重量** | 过重描边（≥2px），线条粗黑，视觉压迫感强 | 清晰不厚重：1px 深色描边（#1A1A2E 或深于主色的对比色），线条流畅 | §11.1 比例规范：1px 深色描边 | P2 |
| 7 | **肤色** | 若出现肤色偏差（偏暗/偏粉/偏黄绿） | 统一使用 #F4C7A1（244-199-161），所有 NPC 面部和手部一致 | §11.6.2 辅助色板：肤色 | P0 |
| 8 | **服装层次** | 服装细节模糊，颜色块不分明 | 服装色块分明，主色 + 辅色 ≤ 3 种颜色（不含肤色和描边） | §2.2 角色颜色分配：≤ 3 种颜色 | P1 |
| 9 | **背景** | 复古色块背景或暗色渐变，非透明即暗黑 | 立绘 portrait.png：透明 PNG 或纯色 #F5E6D3 暖白占位；无暗色渐变背景 | §11.2 立绘规格：背景透明 PNG 或暖白占位 | P1 |
| 10 | **人物比例** | 头身比偏差（头过大或过小） | 1:4 头身比，头部 16×14px 占整体 1/4，躯干 20px，腿部 28px | §11.1 角色比例规范 | P2 |

---

## 2. 各 NPC 风格偏差详情

### 2.1 admissions_director（周明远）— 招生办主任

| 偏差项 | 现状描述 | 目标状态 | 来源 |
|--------|----------|----------|------|
| 色调 | 暗黑复古风，颜色偏白/黑高对比 | 明亮温暖：深蓝西装 #2D4A6B + 暖白衬衫 #F5E6D3 | n2b1-animation-integration.md §6.1 |
| 服装 | 服装色调泛化，无精确色值 | 精确使用 §11.5：深蓝西装 + 白色衬衫 + 深色领带 + 校徽 | npc-style-bible.md §11.5 |
| 气质 | 偏戏剧化/严肃感强 | 专业可亲：挺拔站姿、平静表情即可 | npc-style-bible.md §2.1 |
| 线条 | 描边过重 | 1px #1A1A2E 描边 | npc-style-bible.md §11.1 |

### 2.2 student_representative（沈一诺）— 学生代表

| 偏差项 | 现状描述 | 目标状态 | 来源 |
|--------|----------|----------|------|
| 色调 | 噪点较多，色彩跳跃大 | 明亮干净：白色校服衬衫 #F5E6D3 + 深蓝西装外套 #2D4A6B | n2b1-animation-integration.md §6.1 |
| 服装 | 校服色彩模糊 | 精确使用 §11.5：校服衬衫 + 深蓝西装外套（校徽）+ 深灰校裤 | npc-style-bible.md §11.5 |
| 气质 | 表情过于戏剧化（眼大、八字眉） | 青春自然：活泼但不夸张，微笑柔和 | npc-style-bible.md §2.1 |
| 配饰 | 配饰不明确 | 书包肩带、学生会徽章 | npc-visual-baseline-review.md §2 |

---

## 3. 修正后的正向关键词（Prompt 注入词）

以下关键词应在所有 NPC 生成 prompt 中**强制包含**：

```
warm campus atmosphere, modern Chinese international school
cozy 2D style (not 8-bit), clean pixel art
professional attire, warm lighting
bright and inviting color palette
contemporary educational technology setting
friendly and approachable character expression
```

---

## 4. 禁止关键词清单（Prompt Negative 词）

以下关键词应在所有 NPC 生成 prompt 的 Negative prompt 中**强制禁止**：

```
dark tone, dark background, black shadows, high contrast black-white
retro pixel, 8-bit, 16-bit, pixel art retro style
Stardew Valley, farm elements, harvest, fishing rod
fantasy elements, magic wand, wings, dragon, elf ears
medieval setting, dungeon, stone brick path
French countryside, Provence, lavender, ironwork decoration
low quality, blurry, noise, grainy texture
oversaturated, candy colors, bright neon
cute chibi style, big head (head-to-body ratio > 1:3)
harsh lighting, dramatic shadows, theatrical expression
```

---

## 5. 验证方法

### 5.1 视觉检查（非自动化）

- [ ] 色调明亮温暖，无大面积纯黑/纯白色块
- [ ] 对比度适中，明暗过渡柔和
- [ ] 服装主色与 npc-style-bible §11.5 规范色值偏差 ≤ 10%
- [ ] 肤色为 #F4C7A1（允许色温轻微偏差，不允许偏暗）
- [ ] 1px 描边清晰可见但不过重
- [ ] 无复古 RPG / 奇幻 / Stardew 视觉联想
- [ ] 角色比例符合 1:4 头身比

### 5.2 技术检查

- [ ] PNG RGBA 格式（透明背景）
- [ ] portrait.png 尺寸 256×256px
- [ ] sprite_idle.png / walk sheet 单帧 64×64px
- [ ] generation_metadata.json 记录 prompt 和生成参数

---

## 6. 版本历史

| 版本 | 日期 | 变更 |
|------|------|------|
| v1.0 | 2026-05-28 | 初始发布：10 项硬门槛 + 正向/禁止关键词 + 验证方法 |