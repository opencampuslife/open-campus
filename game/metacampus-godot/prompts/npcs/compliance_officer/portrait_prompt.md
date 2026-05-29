# NPC Image Prompt — compliance_officer

> 版本：v1.0
> 日期：2026-05-28
> 用途：AI 生图 prompt，用于生成 NPC 立绘和 sprite

---

## 变量填充卡

| 变量 | 值 |
|------|-----|
| `{{NPC_ID}}` | `compliance_officer` |
| `{{DISPLAY_NAME}}` | `林澈` |
| `{{ROLE}}` | `合规专员` |
| `{{GENDER}}` | `male` |
| `{{CLOTHING}}` | `白色衬衫，灰色职业套装` |
| `{{HAIR_STYLE}}` | `黑色短发` |
| `{{ACCESSORY}}` | `黑框眼镜` |
| `{{EXPRESSION}}` | `neutral` |
| `{{EXPRESSION_DESC}}` | `neutral expression, round eyes looking forward, horizontal eyebrows, straight mouth line` |
| `{{VIEW_ANGLE}}` | `front-facing` |
| `{{SKIN_TONE}}` | `#F4C7A1` |

---

## 1. 立绘 Prompt（正面）

```
[Subject] A male Chinese 合规专员 character, 林澈, front-facing portrait, modern pixel art style.
[Appearance] 黑色短发. Wearing 白色衬衫，灰色职业套装. 黑框眼镜.
[Facial] Skin tone #F4C7A1. neutral expression, round eyes looking forward, horizontal eyebrows, straight mouth line. Clean facial features with soft shading.
[Composition] 256x256 pixels. Character occupies 70-80% of canvas, centered and slightly elevated. Transparent background or warm white #F5E6D3 placeholder background. 1-2 pixel dark outline around character.
[Lighting] Soft top-down lighting, 2-3 levels of light/shadow depth. Warm ambient tone.
[Style Keywords] Modern cozy 2D pixel art, NOT 8-bit retro, NOT Stardew Valley. Clean lines. Contemporary Chinese international school setting.
[Technical] Pixel art, 256x256 canvas, PNG format. Visible pixel grid at 1x scale. Limited color palette from approved swatches only.
[Negative] NO farmland, NO farm tools, NO scarecrows, NO rustic cabins, NO medieval, NO fantasy elements, NO magic, NO chibi proportions, NO oversaturated colors, NO 8-bit retro pixels, NO Stardew Valley style, NO rural elements, NO village, NO farming.
```

---

## 2. 立绘 Prompt（3/4 侧视）

```
[Subject] A male Chinese 合规专员 character, 林澈, three-quarter view portrait facing slightly left, modern pixel art style.
[Appearance] 黑色短发. Wearing 白色衬衫，灰色职业套装. 黑框眼镜.
[Facial] Skin tone #F4C7A1. neutral expression, round eyes looking forward, horizontal eyebrows, straight mouth line. Three-quarter angle showing facial depth.
[Composition] 256x256 pixels. Character occupies 65-75% of canvas, positioned slightly off-center. Warm white #F5E6D3 placeholder background. 1-2 pixel dark outline.
[Lighting] Soft key light from upper-left, subtle fill light from right. 2-3 levels of shadow depth.
[Style Keywords] Modern cozy 2D pixel art, NOT 8-bit retro, NOT Stardew Valley. Contemporary Chinese international school.
[Technical] Pixel art, 256x256 canvas, PNG format. Visible pixel grid at 1x scale.
[Negative] NO farmland, NO rustic elements, NO fantasy, NO magic, NO chibi, NO 8-bit retro, NO Stardew Valley, NO rural, NO village, NO farming, NO oversaturated colors.
```

---

## 3. Sprite 单帧 Prompt（64×64 站立）

```
[Subject] Full-body sprite of 林澈 (compliance_officer), male Chinese 合规专员, modern pixel art game sprite.
[Appearance] 黑色短发. Wearing 白色衬衫，灰色职业套装. 黑框眼镜. Skin tone #F4C7A1.
[Proportions] 64 pixels tall total (head 16px = 1/4 body height). Body proportions: head 16px, torso 20px, legs 28px.
[Pose] Upright standing pose, arms at sides, facing camera (downward direction for top-down RPG). Feet together or slight stride.
[Composition] 64x64 pixel canvas. Character centered horizontally. 4px shadow ellipse at bottom (20% opacity, color #1A1A2E). 1px dark outline around character.
[Style Keywords] Modern cozy 2D pixel art, NOT 8-bit retro, NOT Stardew Valley. Top-down RPG sprite style. Clean readable silhouette.
[Technical] Pixel art, 64x64 canvas, PNG format. Visible pixel grid at 1x scale. Maximum 5 colors per sprite (including outline and shadow).
[Negative] NO farmland, NO rustic elements, NO fantasy, NO chibi (head must be 1/4 of height), NO 8-bit retro, NO oversaturated colors, NO Stardew Valley, NO rural, NO village, NO farm.
```

---

## 4. Walk Sheet Prompt（4 帧横向排列）

```
[Subject] 4-frame walk cycle sheet for 林澈 (compliance_officer), male Chinese 合规专员, modern pixel art.
[Appearance] 黑色短发. Wearing 白色衬衫，灰色职业套装. 黑框眼镜. Skin tone #F4C7A1.
[Animation Frames] Left to right: Frame 1 (contact pose - one foot forward), Frame 2 (passing pose - legs crossing), Frame 3 (contact pose - opposite foot forward), Frame 4 (passing pose - legs crossing opposite).
[Composition] 256x64 pixel canvas (4 frames × 64px each, horizontal strip). Each frame: 64x64 pixels with 4px bottom shadow. Consistent lighting and colors across all 4 frames.
[Proportions] Each frame: character 64px tall, head 16px (1/4 height). Consistent body proportions across all frames.
[Style Keywords] Modern cozy 2D pixel art, NOT 8-bit retro, NOT Stardew Valley. Smooth walk cycle, natural arm swing.
[Technical] Pixel art, 256x64 canvas, PNG format. Frame duration: 150ms per frame. Maximum 5 colors per sprite.
[Negative] NO smear frames, NO motion blur, NO frame distortion, NO 8-bit retro, NO chibi, NO Stardew Valley, NO rural, NO farm, NO oversaturated colors.
```