# admissions_director (周明远) — Revised AI Generation Prompts v1.0

> 版本：v1.0 | 日期：2026-05-28 | NPC：admissions_director（招生办主任）
> 用途：N2B-2 风格修正版 AI 生图 prompt，修正暗黑复古风格 → 明亮温暖校园风格
> 关联规范：npc-style-bible.md v1.1 §11

---

## 周明远 — 角色基础信息

| 字段 | 值 |
|------|-----|
| npc_id | `admissions_director` |
| display_name | 周明远 |
| role | 招生办主任 |
| location | admission_office（招生办） |
| 服装 | 深蓝西装套装 + 白衬衫 + 深色领带 + 金色校徽 |
| 气质 | 专业、权威、可亲、自信但不傲慢 |
| 主色 | 深蓝 #2D4A6B |
| 辅色 | 暖白 #F5E6D3 |
| 点缀色 | 校徽金 #D4A843 |
| 肤色 | #F4C7A1 |

---

## A. Portrait（立绘头像）

### A1. portrait_neutral — 中性表情立绘（主交付物）

**正向 Prompt（Positive）：**
```
Pixel art illustration of a professional Chinese adult male, front-facing portrait, 256×256 canvas.

Subject: Zhou Mingyuan (周明远), the Admissions Director at a modern Chinese international school. Mid-30s, clean-shaven, composed professional demeanor.

Clothing: Dark navy blue suit jacket (#2D4A6B), warm white dress shirt (#F5E6D3), dark navy tie, left chest golden school emblem badge (#D4A843).

Face: Warm skin tone (#F4C7A1), neutral expression, gentle slight upward mouth curve (not a full smile, approachable but composed), round 2×2 dot eyes centered, flat horizontal 4×1 eyebrows.

Background: Transparent PNG, or pure warm white (#F5E6D3) fill. No dark gradient, no retro stone texture.

Style keywords: modern Chinese international school, warm campus atmosphere, cozy 2D style (NOT 8-bit retro), clean pixel art, professional attire, warm lighting, bright and inviting color palette, contemporary educational technology setting. 1px dark outline (#1A1A2E), 2-3 level soft lighting from top + ambient fill, clear color blocks with ≤ 5 colors total.

Character proportions: 1:4 head-to-body ratio, head 16×14px, body proportion professional and clean.
```

**Negative Prompt：**
```
dark tone, dark background, black shadows, high contrast black-white, harsh shadows
retro pixel, 8-bit, 16-bit, pixel art retro style, old school game aesthetic
Stardew Valley, farm elements, harvest, fishing rod, farm hat, medieval RPG
fantasy elements, magic wand, wings, dragon, elf ears, spell circle
medieval setting, dungeon, stone brick path, cobblestone, castle wall
French countryside, Provence, lavender, ironwork decoration, rural scenery
low quality, blurry, noisy, grainy texture, JPEG artifacts
oversaturated, candy colors, bright neon, candy shop colors
cute chibi style, big head (head-to-body ratio > 1:3), baby face, exaggerated features
theatrical expression, dramatic pose, over-emotional, extreme smiling
farm, field, garden, grass, nature background, outdoor rural scene
```

---

### A2. portrait_happy — 开心表情立绘

**正向 Prompt：**
```
Pixel art illustration of a professional Chinese adult male, front-facing portrait, 256×256 canvas.

Subject: Zhou Mingyuan (周明远), the Admissions Director at a modern Chinese international school. Mid-30s, clean-shaven, warm happy expression.

Clothing: Dark navy blue suit jacket (#2D4A6B), warm white dress shirt (#F5E6D3), dark navy tie, left chest golden school emblem badge (#D4A843).

Face: Warm skin tone (#F4C7A1), happy expression, crescent upward curved eyes ^^, arched upward 4×1 eyebrows, open gentle smile arc 4×1, optional 1px light pink cheek highlight dots (#F4C7A1 highlight variant).

Background: Transparent PNG, or pure warm white (#F5E6D3) fill. No dark gradient.

Style keywords: modern Chinese international school, warm campus atmosphere, cozy 2D style (NOT 8-bit retro), clean pixel art, professional attire, warm lighting, bright and inviting color palette, contemporary educational technology setting. 1px dark outline (#1A1A2E), 2-3 level soft lighting from top + ambient fill, clear color blocks with ≤ 5 colors total.

Character proportions: 1:4 head-to-body ratio.
```

**Negative Prompt：**
```
[同 A1 Negative Prompt — 全部适用]
```

---

### A3. portrait_worried — 担心表情立绘

**正向 Prompt：**
```
Pixel art illustration of a professional Chinese adult male, front-facing portrait, 256×256 canvas.

Subject: Zhou Mingyuan (周明远), the Admissions Director at a modern Chinese international school. Mid-30s, clean-shaven, mildly worried/concerned expression.

Clothing: Dark navy blue suit jacket (#2D4A6B), warm white dress shirt (#F5E6D3), dark navy tie, left chest golden school emblem badge (#D4A843).

Face: Warm skin tone (#F4C7A1), worried expression, slightly larger 2×2 round eyes, downward slanting 4×1 eyebrows (八字眉 / \ ), downward curved 3×1 mouth (⌢).

Background: Transparent PNG, or pure warm white (#F5E6D3) fill.

Style keywords: modern Chinese international school, warm campus atmosphere, cozy 2D style (NOT 8-bit retro), clean pixel art, professional attire, warm lighting, bright and inviting color palette. 1px dark outline (#1A1A2E), soft top lighting + ambient fill. ≤ 5 colors total.

Character proportions: 1:4 head-to-body ratio.
```

**Negative Prompt：**
```
[同 A1 Negative Prompt — 全部适用]
```

---

### A4. portrait_strict — 严肃表情立绘

**正向 Prompt：**
```
Pixel art illustration of a professional Chinese adult male, front-facing portrait, 256×256 canvas.

Subject: Zhou Mingyuan (周明远), the Admissions Director at a modern Chinese international school. Mid-30s, clean-shaven, stern strict expression (compliance warning scenario).

Clothing: Dark navy blue suit jacket (#2D4A6B), warm white dress shirt (#F5E6D3), dark navy tie, left chest golden school emblem badge (#D4A843).

Face: Warm skin tone (#F4C7A1), strict expression, half-closed 1×3 narrow vertical eye slits, downward pressed 4×1 eyebrows close to eyes, tightly closed 2×1 straight line mouth.

Background: Transparent PNG, or pure warm white (#F5E6D3) fill.

Style keywords: modern Chinese international school, warm campus atmosphere, cozy 2D style (NOT 8-bit retro), clean pixel art, professional attire, warm lighting. 1px dark outline (#1A1A2E), ≤ 5 colors total.

Character proportions: 1:4 head-to-body ratio.
```

**Negative Prompt：**
```
[同 A1 Negative Prompt — 全部适用]
```

---

## B. Sprite — Idle 精灵（64×64px）

**正向 Prompt：**
```
Pixel art sprite sheet, single 64×64px frame, idle standing pose, front-facing or 3/4 view for map display.

Subject: Zhou Mingyuan (周明远), the Admissions Director at a modern Chinese international school. Mid-30s adult male, standing upright with slight forward posture.

Clothing: Dark navy blue suit jacket (#2D4A6B), warm white dress shirt (#F5E6D3), dark navy tie, left chest golden school emblem badge (#D4A843).

Face: Warm skin tone (#F4C7A1), neutral expression, round 2×2 dot eyes, flat horizontal 4×1 eyebrows, straight 3×1 mouth.

Body: 1:4 head-to-body ratio. Head 16×14px. Body upright professional stance, not slouching.

Style keywords: modern Chinese international school, warm campus atmosphere, cozy 2D style (NOT 8-bit retro), clean pixel art, professional attire, warm lighting, bright and inviting color palette. 1px dark outline (#1A1A2E), soft top lighting + ambient fill. ≤ 5 colors total.

Background: Transparent PNG.

Note: This is an idle frame. No walking motion. Simple standing pose.
```

**Negative Prompt：**
```
dark tone, dark background, black shadows, high contrast
retro pixel, 8-bit, 16-bit, pixel art retro style
Stardew Valley, farm, fantasy, medieval
low quality, blurry, noisy, grainy
oversaturated, candy colors, chibi style
dramatic shadows, theatrical pose
walking pose, motion blur, action frame
```

---

## C. Walk Sheet — 行走动画精灵（256×64px = 4×64px 帧）

### C1. walk_down — 朝下行走

**正向 Prompt：**
```
Pixel art walk cycle sheet, 256×64px total, 4 frames arranged horizontally left-to-right (contact → transition → crossing → transition).

Subject: Zhou Mingyuan (周明远), the Admissions Director, walking downward (away from camera, back view or slight angle).

Clothing: Dark navy blue suit jacket (#2D4A6B), warm white dress shirt (#F5E6D3), dark navy tie, left chest golden school emblem badge (#D4A843).

Walking pose frames:
- Frame 1 (contact): Left foot forward on ground, right foot raised mid-step, arms neutral at sides
- Frame 2 (transition): Legs passing, slight body tilt forward
- Frame 3 (crossing): Right foot forward on ground, left foot raised mid-step
- Frame 4 (transition): Legs passing back, return to starting position

Each frame: 64×64px. Character height: 60px (4px bottom for shadow space).

Style keywords: modern Chinese international school, warm campus atmosphere, cozy 2D style (NOT 8-bit retro), clean pixel art, professional attire, warm lighting, bright and inviting color palette. 1px dark outline (#1A1A2E). ≤ 5 colors total.

Background: Transparent PNG.

Animation timing: 150ms per frame (~6.67 fps).
```

**Negative Prompt：**
```
dark tone, dark background, black shadows, high contrast
retro pixel, 8-bit, 16-bit, pixel art retro style
Stardew Valley, farm, fantasy, medieval
low quality, blurry, noisy, grainy
oversaturated, candy colors, chibi style
dramatic shadows, theatrical pose
jumping, running, sliding, unusual poses
```

---

### C2. walk_up — 朝上行走

**正向 Prompt：**
```
Pixel art walk cycle sheet, 256×64px total, 4 frames arranged horizontally left-to-right (contact → transition → crossing → transition).

Subject: Zhou Mingyuan (周明远), the Admissions Director, walking upward (toward camera, front view).

Walking pose frames: Similar to walk_down but character faces upward.
- Frame 1: Left foot forward, right foot raised
- Frame 2: Legs passing
- Frame 3: Right foot forward, left foot raised
- Frame 4: Legs returning

Face visible: warm skin tone (#F4C7A1), neutral expression, round 2×2 eyes, flat eyebrows.

Clothing: Dark navy blue suit jacket (#2D4A6B), warm white dress shirt (#F5E6D3), dark navy tie.

Style keywords: modern Chinese international school, warm campus atmosphere, cozy 2D style (NOT 8-bit retro), clean pixel art, warm lighting. 1px dark outline (#1A1A2E). ≤ 5 colors total.

Background: Transparent PNG. 150ms/frame.
```

**Negative Prompt：**
```
[同 C1 Negative Prompt]
```

---

### C3. walk_left — 朝左行走

**正向 Prompt：**
```
Pixel art walk cycle sheet, 256×64px total, 4 frames arranged horizontally left-to-right.

Subject: Zhou Mingyuan (周明远), the Admissions Director, walking left (side profile facing left).

Clothing: Dark navy blue suit jacket (#2D4A6B), warm white dress shirt (#F5E6D3), dark navy tie, golden school emblem on visible side.

Walking pose: Side view, legs alternating walk motion.
- Frame 1: Left foot on ground
- Frame 2: Mid-stride transition
- Frame 3: Right foot on ground
- Frame 4: Mid-stride return

Style keywords: modern Chinese international school, warm campus atmosphere, cozy 2D style (NOT 8-bit retro), clean pixel art, warm lighting. 1px dark outline (#1A1A2E). ≤ 5 colors total.

Background: Transparent PNG. 150ms/frame.
```

**Negative Prompt：**
```
[同 C1 Negative Prompt]
```

---

### C4. walk_right — 朝右行走

**正向 Prompt：**
```
Pixel art walk cycle sheet, 256×64px total, 4 frames arranged horizontally left-to-right.

Subject: Zhou Mingyuan (周明远), the Admissions Director, walking right (side profile facing right).

[Same structure as walk_left, mirrored]

Style keywords: modern Chinese international school, warm campus atmosphere, cozy 2D style (NOT 8-bit retro), clean pixel art, warm lighting. 1px dark outline (#1A1A2E). ≤ 5 colors total.

Background: Transparent PNG. 150ms/frame.
```

**Negative Prompt：**
```
[同 C1 Negative Prompt]
```

---

## D. 关键修正对照（Style Delta）

| 维度 | N2A 问题 | N2B-2 修正 |
|------|----------|------------|
| 色调 | 暗黑复古，白/黑高对比 | 明亮温暖：#2D4A6B 深蓝 + #F5E6D3 暖白 |
| 对比度 | 偏高 | 中等（2-3级明暗） |
| 服装色 | 泛化无精确值 | 必须 #2D4A6B + #F5E6D3 + #D4A843 |
| 场景联想 | 复古 RPG 石板地牢 | 现代校园无中世纪元素 |
| 角色气质 | 戏剧化表情夸张 | 专业可亲，表情自然中性 |
| 线条 | 过重描边 | 1px #1A1A2E 描边 |
| 肤色 | 若有偏差 | 统一 #F4C7A1 |
| 背景 | 暗色渐变 | 透明或 #F5E6D3 暖白 |

---

## E. 版本历史

| 版本 | 日期 | 变更 |
|------|------|------|
| v1.0 | 2026-05-28 | 初始发布：4种表情 portrait + idle sprite + 4方向 walk sheet prompt |