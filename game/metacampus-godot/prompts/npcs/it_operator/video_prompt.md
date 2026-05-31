# NPC Video Prompt — it_operator

> 版本：v1.0
> 日期：2026-05-28
> 用途：AI 视频生成 prompt，用于生成 5 秒 NPC 动作视频

---

## 变量填充卡

| 变量 | 值 |
|------|-----|
| `{{NPC_ID}}` | `it_operator` |
| `{{DISPLAY_NAME}}` | `许航` |
| `{{ROLE}}` | `IT运维` |
| `{{GENDER}}` | `male` |
| `{{CLOTHING}}` | `灰色连帽衫，深色休闲裤` |
| `{{HAIR_STYLE}}` | `黑色短发` |
| `{{ACCESSORY}}` | `黑框眼镜` |
| `{{LOCATION}}` | `server_room` |
| `{{LOCATION_CN}}` | `服务器机房` |
| `{{LOCATION_DESC}}` | `server room with rack-mounted servers, blinking LED lights, dual monitors on desk, cable management systems, cool ambient blue glow` |
| `{{MOOD}}` | `focused and high-tech` |
| `{{TIME_OF_DAY}}` | `dim ambient blue glow` |
| `{{SKIN_TONE}}` | `#F4C7A1` |

**visual_keywords**（用于 Action/Environment 描述）: `灰色连帽衫，双显示器满屏终端命令，机架上闪烁的LED灯，键盘旁的能量饮料罐`

---

## 1. 对话待机动画（Idle Talk Animation）

```
[Subject] 许航, a male Chinese IT运维 in modern pixel art style, standing in 服务器机房 (server_room).
[Appearance] 黑色短发. 黑框眼镜. Wearing 灰色连帽衫，深色休闲裤. Skin tone #F4C7A1. Clean pixel art rendering with 1-2px dark outlines.
[Action] Gentle idle breathing animation: chest subtly rising and falling. Occasional slow blink (eyes close for ~200ms). Slight weight shift between feet. Natural, calm, not exaggerated. Environment: server rack with blinking LED indicators, dual monitors displaying terminal commands, energy drink cans beside keyboard.
[Duration] 5 seconds, seamless loop.
[Camera] Static shot, waist-up or full-body centered in frame. No camera movement.
[Lighting] Soft indoor lighting from ceiling panels. Cool ambient blue tone matching focused and high-tech mood. Subtle shadow on floor.
[Style Keywords] Modern cozy 2D pixel art animation, NOT 8-bit, NOT Stardew Valley. Pixel-art motion at 12fps. Contemporary Chinese international school setting.
[Technical] 5 seconds, 12 fps, 60 frames total. Seamless loop. 512x512 output recommended for upscale.
[Negative] NO 8-bit choppy animation, NO smooth 30fps tween animation (keep pixel-jump feel), NO exaggerated cartoon squash-and-stretch, NO rural or farm elements, NO fantasy, NO 3D rendering, NO Stardew Valley, NO farmland, NO village.
```

---

## 2. 表情切换动画（Expression Transition）

```
[Subject] Close-up face of 许航 (it_operator), modern pixel art portrait style.
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
[Subject] 许航 (it_operator), male Chinese IT运维, performing a specific gesture, modern pixel art.
[Appearance] 黑色短发. 黑框眼镜. Wearing 灰色连帽衫，深色休闲裤. Waist-up framing.
[Action] adjusts glasses with index finger, then points right hand toward an off-screen monitor. Duration: 5 seconds. Natural timing, no rush. One continuous motion with clear start, hold, and return phases.
[Duration] 5 seconds total (action ~3s, return to rest ~2s).
[Camera] Waist-up shot, static, character centered. Slightly framed to show the gesture clearly.
[Lighting] Soft indoor lighting, focused and high-tech mood.
[Style Keywords] Modern cozy 2D pixel art animation, subtle gesture, professional manner.
[Technical] 12 fps, 60 frames. 512x384 canvas. Pixel art.
[Negative] NO exaggerated movement, NO 8-bit retro, NO anime-style motion lines, NO 3D, NO Stardew Valley, NO farmland, NO rural elements.
```