# NPC Video Prompt — parent_representative

> 版本：v1.0
> 日期：2026-05-28
> 用途：AI 视频生成 prompt，用于生成 5 秒 NPC 动作视频

---

## 变量填充卡

| 变量 | 值 |
|------|-----|
| `{{NPC_ID}}` | `parent_representative` |
| `{{DISPLAY_NAME}}` | `顾兰` |
| `{{ROLE}}` | `家长代表` |
| `{{GENDER}}` | `female` |
| `{{CLOTHING}}` | `碎花连衣裙` |
| `{{HAIR_STYLE}}` | `棕色中长发` |
| `{{ACCESSORY}}` | `帆布袋` |
| `{{LOCATION}}` | `reception_area` |
| `{{LOCATION_CN}}` | `接待区` |
| `{{LOCATION_DESC}}` | `modern reception area with comfortable seating, information display screens, reception desk, warm welcoming atmosphere` |
| `{{MOOD}}` | `warm and welcoming` |
| `{{TIME_OF_DAY}}` | `morning soft daylight` |
| `{{SKIN_TONE}}` | `#F4C7A1` |

**visual_keywords**（用于 Action/Environment 描述）: `碎花连衣裙，帆布袋里装着家长联名信，手机屏幕常亮家长群，保温杯和文件夹从不离手`

---

## 1. 对话待机动画（Idle Talk Animation）

```
[Subject] 顾兰, a female Chinese 家长代表 in modern pixel art style, standing in 接待区 (reception_area).
[Appearance] 棕色中长发. 帆布袋. Wearing 碎花连衣裙. Skin tone #F4C7A1. Clean pixel art rendering with 1-2px dark outlines.
[Action] Gentle idle breathing animation: chest subtly rising and falling. Occasional slow blink (eyes close for ~200ms). Slight weight shift between feet. Natural, calm, not exaggerated. Holding a canvas tote bag containing parent petition letters, phone screen lit with parent group chat, thermos and folder always at hand.
[Duration] 5 seconds, seamless loop.
[Camera] Static shot, waist-up or full-body centered in frame. No camera movement.
[Lighting] Soft indoor lighting from ceiling panels. Warm ambient tone matching warm and welcoming mood. Subtle shadow on floor.
[Style Keywords] Modern cozy 2D pixel art animation, NOT 8-bit, NOT Stardew Valley. Pixel-art motion at 12fps. Contemporary Chinese international school setting.
[Technical] 5 seconds, 12 fps, 60 frames total. Seamless loop. 512x512 output recommended for upscale.
[Negative] NO 8-bit choppy animation, NO smooth 30fps tween animation (keep pixel-jump feel), NO exaggerated cartoon squash-and-stretch, NO rural or farm elements, NO fantasy, NO 3D rendering, NO Stardew Valley, NO farmland, NO village.
```

---

## 2. 表情切换动画（Expression Transition）

```
[Subject] Close-up face of 顾兰 (parent_representative), modern pixel art portrait style.
[Appearance] Same face shape, hair, and features as the base neutral portrait. No clothing visible (face-only frame).
[Action] Expression transition from neutral to worried: smooth pixel-level change in eyes, eyebrows, and mouth over 1.5 seconds, hold the worried expression for 0.5 seconds, then slowly return to neutral over 1.5 seconds. Total 5 seconds.
[Facial Changes] Eyes reshape (max 3px displacement), eyebrows shift angle, mouth curves. Face outline and hair remain ABSOLUTELY STATIC.
[Duration] 5 seconds total (transition-in 1.5s → hold 0.5s → transition-out 1.5s → neutral hold 1.5s).
[Camera] Extreme close-up on face. Static. Head centered.
[Style Keywords] Modern pixel art, subtle emotion change, NOT exaggerated anime-style reaction.
[Technical] 12 fps, 60 frames. 256x256 canvas. Pixel art.
[Negative] NO face shape change, NO hair movement, NO background, NO text, NO anime-style sweat drops or vein marks, NO 8-bit retro, NO Stardew Valley.
```

---

## 3. 手势动作视频（Gesture Animation）

```
[Subject] 顾兰 (parent_representative), female Chinese 家长代表, performing a specific gesture, modern pixel art.
[Appearance] 棕色中长发. 帆布袋. Wearing 碎花连衣裙. Waist-up framing.
[Action] slight forward lean, both hands clasped at waist level, concerned facial expression, slight head tilt. Duration: 5 seconds. Natural timing, no rush. One continuous motion with clear start, hold, and return phases.
[Duration] 5 seconds total (action ~3s, return to rest ~2s).
[Camera] Waist-up shot, static, character centered. Slightly framed to show the gesture clearly.
[Lighting] Soft indoor lighting, warm and welcoming mood.
[Style Keywords] Modern cozy 2D pixel art animation, subtle gesture, professional manner.
[Technical] 12 fps, 60 frames. 512x384 canvas. Pixel art.
[Negative] NO exaggerated movement, NO 8-bit retro, NO anime-style motion lines, NO 3D, NO Stardew Valley, NO farmland, NO rural elements.
```