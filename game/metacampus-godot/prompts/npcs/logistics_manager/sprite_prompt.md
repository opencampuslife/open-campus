# NPC Sprite Prompt — logistics_manager

> 版本：v1.0
> 日期：2026-05-28
> 用途：AI 生图 prompt，用于生成 64×64 sprite 和 walk sheet

---

## 变量填充卡

| 变量 | 值 |
|------|-----|
| `{{NPC_ID}}` | `logistics_manager` |
| `{{DISPLAY_NAME}}` | `赵启山` |
| `{{ROLE}}` | `后勤主管` |
| `{{GENDER}}` | `male` |
| `{{CLOTHING}}` | `深灰工作服` |
| `{{HAIR_STYLE}}` | `短发平头` |
| `{{ACCESSORY}}` | `腰间对讲机` |
| `{{SKIN_TONE}}` | `#F4C7A1` |

---

## 1. Sprite 单帧 Prompt（64×64 站立 Idle）

```
[Subject] Full-body sprite of 赵启山 (logistics_manager), male Chinese 后勤主管, modern pixel art game sprite.
[Appearance] 短发平头. Wearing 深灰工作服. 腰间对讲机. Skin tone #F4C7A1.
[Proportions] 64 pixels tall total (head 16px = 1/4 body height). Body proportions: head 16px, torso 20px, legs 28px.
[Pose] Upright standing pose, arms at sides, facing camera (downward direction for top-down RPG). Feet together or slight stride.
[Composition] 64x64 pixel canvas. Character centered horizontally. 4px shadow ellipse at bottom (20% opacity, color #1A1A2E). 1px dark outline around character.
[Style Keywords] Modern cozy 2D pixel art, NOT 8-bit retro, NOT Stardew Valley. Top-down RPG sprite style. Clean readable silhouette.
[Technical] Pixel art, 64x64 canvas, PNG format. Visible pixel grid at 1x scale. Maximum 5 colors per sprite (including outline and shadow).
[Negative] NO farmland, NO rustic elements, NO fantasy, NO chibi (head must be 1/4 of height), NO 8-bit retro, NO oversaturated colors, NO Stardew Valley, NO rural, NO village, NO farm.
```

---

## 2. Walk Sheet Prompt（4 帧横向排列）

```
[Subject] 4-frame walk cycle sheet for 赵启山 (logistics_manager), male Chinese 后勤主管, modern pixel art.
[Appearance] 短发平头. Wearing 深灰工作服. 腰间对讲机. Skin tone #F4C7A1.
[Animation Frames] Left to right: Frame 1 (contact pose - one foot forward), Frame 2 (passing pose - legs crossing), Frame 3 (contact pose - opposite foot forward), Frame 4 (passing pose - legs crossing opposite).
[Composition] 256x64 pixel canvas (4 frames × 64px each, horizontal strip). Each frame: 64x64 pixels with 4px bottom shadow. Consistent lighting and colors across all 4 frames.
[Proportions] Each frame: character 64px tall, head 16px (1/4 height). Consistent body proportions across all frames.
[Style Keywords] Modern cozy 2D pixel art, NOT 8-bit retro, NOT Stardew Valley. Smooth walk cycle, natural arm swing.
[Technical] Pixel art, 256x64 canvas, PNG format. Frame duration: 150ms per frame. Maximum 5 colors per sprite.
[Negative] NO smear frames, NO motion blur, NO frame distortion, NO 8-bit retro, NO chibi, NO Stardew Valley, NO rural, NO farm, NO oversaturated colors.
```