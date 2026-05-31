# NPC Video Prompt — logistics_manager

> 版本：v1.0
> 日期：2026-05-28
> 用途：AI 视频生成 prompt，用于生成 5 秒 NPC 动作视频

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
| `{{LOCATION}}` | `logistics_department` |
| `{{LOCATION_CN}}` | `后勤办公室` |
| `{{LOCATION_DESC}}` | `logistics office with key board on wall, inventory shelves, walkie-talkies, safety helmets, work vests, efficient and organized environment` |
| `{{MOOD}}` | `efficient and energetic` |
| `{{TIME_OF_DAY}}` | `bright daytime lighting` |
| `{{SKIN_TONE}}` | `#F4C7A1` |

**visual_keywords**（用于 Action/Environment 描述）: `深灰工作服，黄色安全帽挂墙，腰间一大串钥匙，办公桌上的对讲机和对账单`

---

## 1. 对话待机动画（Idle Talk Animation）

```
[Subject] 赵启山, a male Chinese 后勤主管 in modern pixel art style, standing in 后勤办公室 (logistics_department).
[Appearance] 短发平头. 腰间对讲机. Wearing 深灰工作服. Skin tone #F4C7A1. Clean pixel art rendering with 1-2px dark outlines.
[Action] Gentle idle breathing animation: chest subtly rising and falling. Occasional slow blink (eyes close for ~200ms). Slight weight shift between feet. Natural, calm, not exaggerated. Environment: yellow safety helmet on wall hook, large key ring on belt, walkie-talkie and billing sheets on desk.
[Duration] 5 seconds, seamless loop.
[Camera] Static shot, waist-up or full-body centered in frame. No camera movement.
[Lighting] Soft indoor lighting from ceiling panels. Bright ambient tone matching efficient and energetic mood. Subtle shadow on floor.
[Style Keywords] Modern cozy 2D pixel art animation, NOT 8-bit, NOT Stardew Valley. Pixel-art motion at 12fps. Contemporary Chinese international school setting.
[Technical] 5 seconds, 12 fps, 60 frames total. Seamless loop. 512x512 output recommended for upscale.
[Negative] NO 8-bit choppy animation, NO smooth 30fps tween animation (keep pixel-jump feel), NO exaggerated cartoon squash-and-stretch, NO rural or farm elements, NO fantasy, NO 3D rendering, NO Stardew Valley, NO farmland, NO village.
```

---

## 2. 表情切换动画（Expression Transition）

```
[Subject] Close-up face of 赵启山 (logistics_manager), modern pixel art portrait style.
[Appearance] Same face shape, hair, and features as the base neutral portrait. No clothing visible (face-only frame).
[Action] Expression transition from neutral to strict: smooth pixel-level change in eyes, eyebrows, and mouth over 1.5 seconds, hold the strict expression for 0.5 seconds, then slowly return to neutral over 1.5 seconds. Total 5 seconds.
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
[Subject] 赵启山 (logistics_manager), male Chinese 后勤主管, performing a specific gesture, modern pixel art.
[Appearance] 短发平头. 腰间对讲机. Wearing 深灰工作服. Waist-up framing.
[Action] unclips walkie-talkie from belt, brings it to mouth, speaks briefly, clips it back. Duration: 5 seconds. Natural timing, no rush. One continuous motion with clear start, hold, and return phases.
[Duration] 5 seconds total (action ~3s, return to rest ~2s).
[Camera] Waist-up shot, static, character centered. Slightly framed to show the gesture clearly.
[Lighting] Soft indoor lighting, efficient and energetic mood.
[Style Keywords] Modern cozy 2D pixel art animation, subtle gesture, professional manner.
[Technical] 12 fps, 60 frames. 512x384 canvas. Pixel art.
[Negative] NO exaggerated movement, NO 8-bit retro, NO anime-style motion lines, NO 3D, NO Stardew Valley, NO farmland, NO rural elements.
```