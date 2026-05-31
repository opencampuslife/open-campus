# student_representative (沈一诺) — Revised AI Generation Prompts v1.0

> 版本：v1.0 | 日期：2026-05-28 | NPC：student_representative（学生代表）
> 用途：N2B-2 风格修正版 AI 生图 prompt，修正噪点过多/色彩跳跃 → 明亮干净校园风格
> 关联规范：npc-style-bible.md v1.1 §11

---

## 沈一诺 — 角色基础信息

| 字段 | 值 |
|------|-----|
| npc_id | `student_representative` |
| display_name | 沈一诺 |
| role | 学生代表 |
| location | school_gate（校门）/ canteen（食堂） |
| 服装 | 白色/暖白校服衬衫 + 深蓝西装外套（校徽）+ 深灰校裤 |
| 气质 | 青春活力、自然亲和、阳光但不夸张 |
| 主色 | 暖白 #F5E6D3（校服衬衫） |
| 辅色 | 深蓝 #2D4A6B（西装外套） |
| 点缀色 | 学生会徽章（可选金色） |
| 肤色 | #F4C7A1 |

---

## A. Portrait（立绘头像）

### A1. portrait_neutral — 中性表情立绘（主交付物）

**正向 Prompt（Positive）：**
```
Pixel art illustration of a young Chinese female student, front-facing portrait, 256×256 canvas.

Subject: Shen Yinuo (沈一诺), the Student Representative at a modern Chinese international school. Late teens, youthful and approachable, natural neutral expression (slight gentle smile is acceptable).

Clothing: Warm white school uniform shirt (#F5E6D3), dark navy blue school blazer/jacket (#2D4A6B) with school emblem, dark grey school trousers or pleated skirt (#4B5563 or darker), school bag with shoulder strap visible.

Accessories: School student council badge (optional, gold), school bag slung over one shoulder.

Face: Warm skin tone (#F4C7A1), neutral friendly expression, round 2×2 dot eyes centered, flat horizontal 4×1 eyebrows, straight or slight gentle upward 3×1 mouth curve.

Background: Transparent PNG, or pure warm white (#F5E6D3) fill. No dark gradient, no retro background textures.

Style keywords: modern Chinese international school, warm campus atmosphere, cozy 2D style (NOT 8-bit retro), clean pixel art, youthful school uniform, warm lighting, bright and inviting color palette, contemporary educational technology setting, friendly and approachable character expression. 1px dark outline (#1A1A2E), 2-3 level soft lighting from top + ambient fill, clear color blocks with ≤ 5 colors total.

Character proportions: 1:4 head-to-body ratio, youthful proportions (slightly larger head is acceptable for age-appropriate character design, but head-to-body should not exceed 1:3 ratio).
```

**Negative Prompt：**
```
dark tone, dark background, black shadows, high contrast black-white, harsh shadows
retro pixel, 8-bit, 16-bit, pixel art retro style, old school game aesthetic
Stardew Valley, farm elements, harvest, fishing rod, farm hat, medieval RPG
fantasy elements, magic wand, wings, dragon, elf ears, spell circle
medieval setting, dungeon, stone brick path, cobblestone, castle wall
French countryside, Provence, lavender, ironwork decoration, rural scenery
low quality, blurry, noisy, grainy texture, JPEG artifacts, pixel noise
oversaturated, candy colors, bright neon, candy shop colors
cute chibi style, big head (head-to-body ratio > 1:3), baby face, exaggerated features
theatrical expression, dramatic pose, over-emotional, extreme smiling
farm, field, garden, grass, nature background, outdoor rural scene
noisy texture, color bleeding, color jumping, dithering artifacts
```

---

### A2. portrait_happy — 开心表情立绘

**正向 Prompt：**
```
Pixel art illustration of a young Chinese female student, front-facing portrait, 256×256 canvas.

Subject: Shen Yinuo (沈一诺), the Student Representative at a modern Chinese international school. Late teens, bright happy expression, natural joyful smile.

Clothing: Warm white school uniform shirt (#F5E6D3), dark navy blue school blazer (#2D4A6B) with school emblem, dark grey school trousers.

Accessories: Student council badge (optional, gold), school bag.

Face: Warm skin tone (#F4C7A1), happy expression, crescent upward curved eyes ^^, arched upward 4×1 eyebrows, open gentle smile 4×1, optional 1px light pink cheek highlight dots.

Background: Transparent PNG, or pure warm white (#F5E6D3) fill.

Style keywords: modern Chinese international school, warm campus atmosphere, cozy 2D style (NOT 8-bit retro), clean pixel art, warm lighting, bright and inviting color palette, friendly expression. 1px dark outline (#1A1A2E), ≤ 5 colors total. No noise or grain.

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
Pixel art illustration of a young Chinese female student, front-facing portrait, 256×256 canvas.

Subject: Shen Yinuo (沈一诺), the Student Representative at a modern Chinese international school. Late teens, mildly worried/concerned expression (natural concern, not exaggerated drama).

Clothing: Warm white school uniform shirt (#F5E6D3), dark navy blue school blazer (#2D4A6B) with school emblem, dark grey school trousers.

Face: Warm skin tone (#F4C7A1), worried expression, slightly larger 2×2 round eyes, downward slanting 4×1 eyebrows (八字眉 / \ ), downward curved 3×1 mouth (⌢). Natural concern, not theatrical.

Background: Transparent PNG, or pure warm white (#F5E6D3) fill.

Style keywords: modern Chinese international school, warm campus atmosphere, cozy 2D style (NOT 8-bit retro), clean pixel art, warm lighting. 1px dark outline (#1A1A2E), ≤ 5 colors total. No noise.

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
Pixel art illustration of a young Chinese female student, front-facing portrait, 256×256 canvas.

Subject: Shen Yinuo (沈一诺), the Student Representative at a modern Chinese international school. Late teens, stern strict expression (formal meeting or serious discussion scenario).

Clothing: Warm white school uniform shirt (#F5E6D3), dark navy blue school blazer (#2D4A6B) with school emblem, dark grey school trousers. Tucked-in shirt for formal look.

Face: Warm skin tone (#F4C7A1), strict expression, half-closed 1×3 narrow vertical eye slits, downward pressed 4×1 eyebrows close to eyes, tightly closed 2×1 straight line mouth.

Background: Transparent PNG, or pure warm white (#F5E6D3) fill.

Style keywords: modern Chinese international school, warm campus atmosphere, cozy 2D style (NOT 8-bit retro), clean pixel art, warm lighting. 1px dark outline (#1A1A2E), ≤ 5 colors total. No noise.

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
Pixel art sprite sheet, single 64×64px frame, idle standing pose, front-facing for map display.

Subject: Shen Yinuo (沈一诺), the Student Representative at a modern Chinese international school. Late teens female student, standing with slightly lively posture (not rigid, but composed).

Clothing: Warm white school uniform shirt (#F5E6D3), dark navy blue school blazer (#2D4A6B) with school emblem on visible side, school bag with strap over shoulder, dark grey school trousers.

Face: Warm skin tone (#F4C7A1), neutral friendly expression, round 2×2 eyes, flat eyebrows.

Body: 1:4 head-to-body ratio. Youthful but proportional. Standing pose, slightly lively but not exaggerated.

Style keywords: modern Chinese international school, warm campus atmosphere, cozy 2D style (NOT 8-bit retro), clean pixel art, youthful school uniform, warm lighting, bright and inviting color palette. 1px dark outline (#1A1A2E), soft top lighting + ambient fill. ≤ 5 colors total. NO noise, NO grain, NO dithering artifacts.

Background: Transparent PNG.

Note: This is an idle frame. No walking motion. Simple standing pose.
```

**Negative Prompt：**
```
dark tone, dark background, black shadows, high contrast
retro pixel, 8-bit, 16-bit, pixel art retro style
Stardew Valley, farm, fantasy, medieval
low quality, blurry, noisy, grainy, dithering
oversaturated, candy colors, chibi style
dramatic shadows, theatrical pose
walking pose, motion blur, action frame
color jumping, color bleeding
```

---

## C. Walk Sheet — 行走动画精灵（256×64px = 4×64px 帧）

### C1. walk_down — 朝下行走

**正向 Prompt：**
```
Pixel art walk cycle sheet, 256×64px total, 4 frames arranged horizontally left-to-right (contact → transition → crossing → transition).

Subject: Shen Yinuo (沈一诺), the Student Representative, walking downward (away from camera, back view or slight angle).

Clothing: Warm white school uniform shirt (#F5E6D3), dark navy blue school blazer (#2D4A6B) with school emblem, school bag visible, dark grey school trousers.

Walking pose frames:
- Frame 1 (contact): Left foot forward on ground, right foot raised mid-step, arms natural at sides, school bag strap slight swing
- Frame 2 (transition): Legs passing, slight body tilt forward
- Frame 3 (crossing): Right foot forward on ground, left foot raised mid-step
- Frame 4 (transition): Legs passing back, return to starting position

Each frame: 64×64px. Character height: 60px (4px bottom for shadow space).

Style keywords: modern Chinese international school, warm campus atmosphere, cozy 2D style (NOT 8-bit retro), clean pixel art, warm lighting, bright and inviting color palette. 1px dark outline (#1A1A2E). ≤ 5 colors total. NO noise, NO grain.

Background: Transparent PNG.

Animation timing: 150ms per frame (~6.67 fps).
```

**Negative Prompt：**
```
dark tone, dark background, black shadows, high contrast
retro pixel, 8-bit, 16-bit, pixel art retro style
Stardew Valley, farm, fantasy, medieval
low quality, blurry, noisy, grainy, dithering
oversaturated, candy colors, chibi style
dramatic shadows, theatrical pose
jumping, running, sliding, unusual poses
color jumping, color bleeding
```

---

### C2. walk_up — 朝上行走

**正向 Prompt：**
```
Pixel art walk cycle sheet, 256×64px total, 4 frames arranged horizontally left-to-right.

Subject: Shen Yinuo (沈一诺), the Student Representative, walking upward (toward camera, front view).

Walking pose: Similar to walk_down but character faces upward, school bag and blazer visible.
- Frame 1: Left foot forward, right foot raised
- Frame 2: Mid-stride transition
- Frame 3: Right foot forward, left foot raised
- Frame 4: Mid-stride return

Face visible: warm skin tone (#F4C7A1), neutral friendly expression, round eyes.

Clothing: Warm white school uniform shirt (#F5E6D3), dark navy blue school blazer (#2D4A6B) with school emblem, school bag.

Style keywords: modern Chinese international school, warm campus atmosphere, cozy 2D style (NOT 8-bit retro), clean pixel art, warm lighting. 1px dark outline (#1A1A2E). ≤ 5 colors total. No noise.

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

Subject: Shen Yinuo (沈一诺), the Student Representative, walking left (side profile facing left).

Clothing: Warm white school uniform shirt (#F5E6D3), dark navy blue school blazer (#2D4A6B) with school emblem on visible side, school bag with strap, dark grey school trousers.

Walking pose: Side view, legs alternating walk motion.
- Frame 1: Left foot on ground
- Frame 2: Mid-stride transition
- Frame 3: Right foot on ground
- Frame 4: Mid-stride return

Style keywords: modern Chinese international school, warm campus atmosphere, cozy 2D style (NOT 8-bit retro), clean pixel art, warm lighting. 1px dark outline (#1A1A2E). ≤ 5 colors total. No noise.

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

Subject: Shen Yinuo (沈一诺), the Student Representative, walking right (side profile facing right).

[Same structure as walk_left, mirrored]

Style keywords: modern Chinese international school, warm campus atmosphere, cozy 2D style (NOT 8-bit retro), clean pixel art, warm lighting. 1px dark outline (#1A1A2E). ≤ 5 colors total. No noise.

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
| 色调 | 噪点过多，色彩跳跃大 | 明亮干净：#F5E6D3 暖白 + #2D4A6B 深蓝，无噪点 |
| 对比度 | 不稳定，色彩跳跃 | 中等稳定：≤ 5 颜色，明暗过渡柔和 |
| 服装色 | 校服色彩模糊 | 必须 #F5E6D3 + #2D4A6B + #4B5563（深灰校裤） |
| 配饰 | 不明确 | 书包肩带、学生会徽章 |
| 气质 | 表情过于戏剧化（眼大、八字眉夸张） | 青春自然：活泼但不夸张，微笑柔和 |
| 线条 | 若过重 | 1px #1A1A2E 描边 |
| 肤色 | 若有偏差 | 统一 #F4C7A1 |
| 背景 | 若暗色 | 透明或 #F5E6D3 暖白 |
| 纹理 | 噪点/dithering | 强制禁止：no noise, no grain, no dithering |

---

## E. 版本历史

| 版本 | 日期 | 变更 |
|------|------|------|
| v1.0 | 2026-05-28 | 初始发布：4种表情 portrait + idle sprite + 4方向 walk sheet prompt |