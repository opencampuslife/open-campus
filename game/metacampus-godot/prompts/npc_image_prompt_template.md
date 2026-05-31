# NPC Image Prompt Template — MetaCampus

> 版本：v1.0
> 日期：2026-05-28
> 用途：为 AI 图像生成工具（Midjourney / Stable Diffusion / DALL·E）提供可参数化的 prompt 模板
> 关联文档：docs/npc-style-bible.md v1.1 第十一章

---

## 变量说明 (Variables Reference)

| 变量 | 类型 | 说明 | 示例 |
|------|------|------|------|
| `{{NPC_ID}}` | string | NPC 唯一标识 | `parent_001` |
| `{{DISPLAY_NAME}}` | string | 中文显示名 | `张同学家长` |
| `{{ROLE}}` | string | 角色类型（中文） | `家长代表` |
| `{{GENDER}}` | string | 性别 | `male` / `female` |
| `{{CLOTHING}}` | string | 服装描述（从色板规范填充） | `深蓝西装外套，暖白衬衫` |
| `{{HAIR_STYLE}}` | string | 发型描述 | `黑色短发，偏分` |
| `{{ACCESSORY}}` | string | 配饰/标识物 | `手提公文包` 或 `none` |
| `{{EXPRESSION}}` | string | 表情 ID | `neutral` / `happy` / `worried` / `strict` |
| `{{EXPRESSION_DESC}}` | string | 表情英文描述 | `neutral expression, straight mouth` |
| `{{VIEW_ANGLE}}` | string | 视角 | `front-facing` / `three-quarter view` |
| `{{SKIN_TONE}}` | string | 肤色 hex | `#F4C7A1` |

---

## 1. 立绘生成模板 (Portrait Prompt)

### 1.1 正面立绘 (Front-facing Portrait)

```
[Subject] A {{GENDER}} Chinese {{ROLE}} character, {{DISPLAY_NAME}}, {{VIEW_ANGLE}} portrait, modern pixel art style.
[Appearance] {{HAIR_STYLE}}. Wearing {{CLOTHING}}. {{ACCESSORY}}.
[Facial] Skin tone {{SKIN_TONE}}. {{EXPRESSION_DESC}}. Clean facial features with soft shading.
[Composition] 256x256 pixels. Character occupies 70-80% of canvas, centered and slightly elevated. Transparent background or warm white #F5E6D3 placeholder background. 1-2 pixel dark outline around character.
[Lighting] Soft top-down lighting, 2-3 levels of light/shadow depth. Warm ambient tone.
[Style Keywords] Modern cozy 2D pixel art, NOT 8-bit retro, NOT Stardew Valley. Clean lines. Contemporary Chinese international school setting.
[Technical] Pixel art, 256x256 canvas, PNG format. Visible pixel grid at 1x scale. Limited color palette from approved swatches only.
[Negative] NO farmland, NO farm tools, NO scarecrows, NO rustic cabins, NO medieval, NO fantasy elements, NO magic, NO chibi proportions, NO oversaturated colors, NO 8-bit retro pixels.
```

### 1.2 3/4 侧视立绘 (Three-quarter View Portrait)

```
[Subject] A {{GENDER}} Chinese {{ROLE}} character, {{DISPLAY_NAME}}, three-quarter view portrait facing slightly left, modern pixel art style.
[Appearance] {{HAIR_STYLE}}. Wearing {{CLOTHING}}. {{ACCESSORY}}.
[Facial] Skin tone {{SKIN_TONE}}. {{EXPRESSION_DESC}}. Three-quarter angle showing facial depth.
[Composition] 256x256 pixels. Character occupies 65-75% of canvas, positioned slightly off-center. Warm white #F5E6D3 placeholder background. 1-2 pixel dark outline.
[Lighting] Soft key light from upper-left, subtle fill light from right. 2-3 levels of shadow depth.
[Style Keywords] Modern cozy 2D pixel art, NOT 8-bit retro, NOT Stardew Valley. Contemporary Chinese international school.
[Technical] Pixel art, 256x256 canvas, PNG format. Visible pixel grid at 1x scale.
[Negative] NO farmland, NO rustic elements, NO fantasy, NO magic, NO chibi, NO 8-bit retro.
```

---

## 2. 表情生成模板 (Expression Prompt)

### 2.1 通用表情 Prompt

```
[Subject] Close-up face of {{DISPLAY_NAME}} ({{NPC_ID}}), {{EXPRESSION}} expression, modern pixel art.
[Fixed Features] Face shape, hair, and ears IDENTICAL to the base neutral portrait. Same {{HAIR_STYLE}}. Same {{SKIN_TONE}} skin color.
[Expression Change: {{EXPRESSION}}] {{EXPRESSION_DESC}}.
[Composition] Face-only close-up, 128x128 pixels. Head centered, showing from top of hair to chin. Dark outline 1px.
[Style] Same art style as portrait.png. Modern cozy 2D pixel art.
[Technical] Pixel art, 128x128 canvas, PNG format. Facial feature changes limited to ≤3px from base position.
[Negative] NO change to face shape. NO change to hair. NO change to clothing visible. NO background details. NO 8-bit retro.
```

### 2.2 四种表情描述速查 (Expression Description Quick Reference)

| `{{EXPRESSION}}` | `{{EXPRESSION_DESC}}` (English prompt) |
|------------------|----------------------------------------|
| `neutral` | neutral expression, round eyes looking forward, horizontal eyebrows, straight mouth line |
| `happy` | happy expression, upward-curved crescent eyes ^^, raised arched eyebrows, open smiling mouth curved upward |
| `worried` | worried expression, slightly wider round eyes, downward-slanted eyebrows forming a /\ shape, downward curved mouth |
| `strict` | strict expression, half-closed narrow eyes (vertical slits), lowered eyebrows close to eyes, tightly closed straight thin mouth |

---

## 3. Sprite 行走动画模板 (Walk Sprite Prompt)

### 3.1 单帧 Sprite Prompt

```
[Subject] Full-body sprite of {{DISPLAY_NAME}} ({{NPC_ID}}), {{GENDER}} Chinese {{ROLE}}, modern pixel art game sprite.
[Appearance] {{HAIR_STYLE}}. Wearing {{CLOTHING}}. {{ACCESSORY}}. Skin tone {{SKIN_TONE}}.
[Proportions] 64 pixels tall total (head 16px = 1/4 body height). Body proportions: head 16px, torso 20px, legs 28px.
[Pose] Upright standing pose, arms at sides, facing camera (downward direction for top-down RPG). Feet together or slight stride.
[Composition] 64x64 pixel canvas. Character centered horizontally. 4px shadow ellipse at bottom (20% opacity, color #1A1A2E). 1px dark outline around character.
[Style Keywords] Modern cozy 2D pixel art, NOT 8-bit retro, NOT Stardew Valley. Top-down RPG sprite style. Clean readable silhouette.
[Technical] Pixel art, 64x64 canvas, PNG format. Visible pixel grid at 1x scale. Maximum 5 colors per sprite (including outline and shadow).
[Negative] NO farmland, NO rustic elements, NO fantasy, NO chibi (head must be 1/4 of height), NO 8-bit retro, NO oversaturated colors.
```

### 3.2 Walk Sheet Prompt (4 帧横向排列)

```
[Subject] 4-frame walk cycle sheet for {{DISPLAY_NAME}} ({{NPC_ID}}), {{GENDER}} Chinese {{ROLE}}, modern pixel art.
[Appearance] {{HAIR_STYLE}}. Wearing {{CLOTHING}}. {{ACCESSORY}}. Skin tone {{SKIN_TONE}}.
[Animation Frames] Left to right: Frame 1 (contact pose - one foot forward), Frame 2 (passing pose - legs crossing), Frame 3 (contact pose - opposite foot forward), Frame 4 (passing pose - legs crossing opposite).
[Composition] 256x64 pixel canvas (4 frames × 64px each, horizontal strip). Each frame: 64x64 pixels with 4px bottom shadow. Consistent lighting and colors across all 4 frames.
[Proportions] Each frame: character 64px tall, head 16px (1/4 height). Consistent body proportions across all frames.
[Style Keywords] Modern cozy 2D pixel art, NOT 8-bit retro, NOT Stardew Valley. Smooth walk cycle, natural arm swing.
[Technical] Pixel art, 256x64 canvas, PNG format. Frame duration: 150ms per frame. Maximum 5 colors per sprite.
[Negative] NO smear frames, NO motion blur, NO frame distortion, NO 8-bit retro, NO chibi.
```

---

## 4. 使用说明 (Usage Guide)

### 4.1 填充变量流程

1. 从 `data/npcs/npc_*.json` 读取 NPC profile
2. 从 `docs/npc-style-bible.md` 第 11.5 节查找 `{{CLOTHING}}`
3. 从 `docs/npc-style-bible.md` 第 11.4 节查找 `{{EXPRESSION_DESC}}`
4. `{{HAIR_STYLE}}` 和 `{{ACCESSORY}}` 由设计师根据角色人设手动填写
5. `{{SKIN_TONE}}` 始终为 `#F4C7A1`

### 4.2 生成顺序

```
1. portrait (正面) → 验证角色外观
2. neutral 表情 → 基于 portrait 微调
3. happy / worried / strict 表情 → 基于 neutral 微调
4. sprite (单帧站立) → 基于 portrait 缩小+调整比例
5. walk sheet → 基于 sprite 生成 4 帧
```

### 4.3 调校建议

- **Midjourney**: 使用 `--style raw --no 8-bit,farm,rural` 保持风格纯净
- **Stable Diffusion**: 在 Negative Embedding 中加入 `8-bit, retro pixel, farm, stardew`
- **DALL·E 3**: prompt 中的样式描述放在开头，negative 放在末尾

---

## 附录：完整填充示例 (Filled Example)

### 示例：parent_001（张同学家长）

```
{{NPC_ID}}        = parent_001
{{DISPLAY_NAME}}  = 张同学家长
{{ROLE}}          = 家长代表
{{GENDER}}        = female
{{CLOTHING}}      = 深蓝休闲西装外套（不系扣），暖白内搭，深灰休闲裤
{{HAIR_STYLE}}    = 棕色及肩卷发，侧分
{{ACCESSORY}}     = 手提公文包
{{EXPRESSION}}    = neutral
{{EXPRESSION_DESC}} = neutral expression, round eyes looking forward, horizontal eyebrows, straight mouth line
{{VIEW_ANGLE}}    = front-facing
{{SKIN_TONE}}     = #F4C7A1
```

**填充后的 Portrait Prompt**:

```
[Subject] A female Chinese 家长代表 character, 张同学家长, front-facing portrait, modern pixel art style.
[Appearance] 棕色及肩卷发，侧分. Wearing 深蓝休闲西装外套（不系扣），暖白内搭，深灰休闲裤. 手提公文包.
[Facial] Skin tone #F4C7A1. neutral expression, round eyes looking forward, horizontal eyebrows, straight mouth line. Clean facial features with soft shading.
[Composition] 256x256 pixels. Character occupies 70-80% of canvas, centered and slightly elevated. Transparent background or warm white #F5E6D3 placeholder background. 1-2 pixel dark outline around character.
[Lighting] Soft top-down lighting, 2-3 levels of light/shadow depth. Warm ambient tone.
[Style Keywords] Modern cozy 2D pixel art, NOT 8-bit retro, NOT Stardew Valley. Clean lines. Contemporary Chinese international school setting.
[Technical] Pixel art, 256x256 canvas, PNG format. Visible pixel grid at 1x scale. Limited color palette from approved swatches only.
[Negative] NO farmland, NO farm tools, NO scarecrows, NO rustic cabins, NO medieval, NO fantasy elements, NO magic, NO chibi proportions, NO oversaturated colors, NO 8-bit retro pixels.
```

---

*本模板为 MetaCampus NPC 图像生成的权威参考。生成前必须填充所有变量，填充值必须来自 npc-style-bible.md 授权规范。*
