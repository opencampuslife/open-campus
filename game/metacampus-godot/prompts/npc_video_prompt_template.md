# NPC Video Prompt Template — MetaCampus

> 版本：v1.0
> 日期：2026-05-28
> 用途：为 AI 视频生成工具（Runway / Pika / Kling / Sora）提供可参数化的 5 秒视频 prompt 模板
> 关联文档：docs/npc-style-bible.md v1.1 第十一章

---

## 变量说明 (Variables Reference)

| 变量 | 类型 | 说明 | 示例 |
|------|------|------|------|
| `{{NPC_ID}}` | string | NPC 唯一标识 | `parent_001` |
| `{{DISPLAY_NAME}}` | string | 中文显示名 | `张同学家长` |
| `{{ROLE}}` | string | 角色类型（中文） | `家长代表` |
| `{{GENDER}}` | string | 性别 | `male` / `female` |
| `{{CLOTHING}}` | string | 服装描述 | `深蓝休闲西装，暖白内搭` |
| `{{LOCATION}}` | string | 场景名（英文） | `admission_office` |
| `{{LOCATION_CN}}` | string | 场景中文名 | `招生办公室` |
| `{{LOCATION_DESC}}` | string | 场景英文描述 | `modern admission office with glass walls and a reception desk` |
| `{{MOOD}}` | string | 氛围 | `warm and welcoming` / `professional and calm` |
| `{{ACTION}}` | string | 动作描述 | `slight nod while speaking` |
| `{{ACTION_DURATION}}` | string | 动作时长 | `5 seconds` |
| `{{SKIN_TONE}}` | string | 肤色 hex | `#F4C7A1` |

---

## 1. NPC 动作视频模板 (Action Video)

### 1.1 对话待机动画 (Idle Talk Animation)

**用途**：NPC 在对话界面中的待机微动，5 秒循环，用于立绘位置展示。

```
[Subject] {{DISPLAY_NAME}}, a {{GENDER}} Chinese {{ROLE}} in modern pixel art style, standing in {{LOCATION_CN}} ({{LOCATION}}).
[Appearance] Wearing {{CLOTHING}}. Skin tone {{SKIN_TONE}}. Clean pixel art rendering with 1-2px dark outlines.
[Action] Gentle idle breathing animation: chest subtly rising and falling. Occasional slow blink (eyes close for ~200ms). Slight weight shift between feet. Natural, calm, not exaggerated.
[Duration] 5 seconds, seamless loop.
[Camera] Static shot, waist-up or full-body centered in frame. No camera movement.
[Lighting] Soft indoor lighting from ceiling panels. Warm ambient tone matching {{MOOD}} mood. Subtle shadow on floor.
[Style Keywords] Modern cozy 2D pixel art animation, NOT 8-bit, NOT Stardew Valley. Pixel-art motion at 12fps. Contemporary Chinese international school setting.
[Technical] 5 seconds, 12 fps, 60 frames total. Seamless loop. 512x512 output recommended for upscale.
[Negative] NO 8-bit choppy animation, NO smooth 30fps tween animation (keep pixel-jump feel), NO exaggerated cartoon squash-and-stretch, NO rural or farm elements, NO fantasy, NO 3D rendering.
```

### 1.2 表情切换动画 (Expression Transition)

**用途**：NPC 表情从 neutral → 目标表情的过渡动画，用于对话反馈。

```
[Subject] Close-up face of {{DISPLAY_NAME}} ({{NPC_ID}}), modern pixel art portrait style.
[Appearance] Same face shape, hair, and features as the base neutral portrait. No clothing visible (face-only frame).
[Action] Expression transition from neutral to {{EXPRESSION}}: smooth pixel-level change in eyes, eyebrows, and mouth over 1.5 seconds, hold the {{EXPRESSION}} expression for 0.5 seconds, then slowly return to neutral over 1.5 seconds. Total 5 seconds.
[Facial Changes] Eyes reshape (max 3px displacement), eyebrows shift angle, mouth curves. Face outline and hair remain ABSOLUTELY STATIC.
[Duration] 5 seconds total (transition-in 1.5s → hold 0.5s → transition-out 1.5s → neutral hold 1.5s).
[Camera] Extreme close-up on face. Static. Head centered.
[Style Keywords] Modern pixel art, subtle emotion change, NOT exaggerated anime-style reaction.
[Technical] 12 fps, 60 frames. 256x256 canvas. Pixel art.
[Negative] NO face shape change, NO hair movement, NO background, NO text, NO anime-style sweat drops or vein marks, NO 8-bit retro.
```

### 1.3 行走循环视频 (Walk Cycle Video)

**用途**：NPC 在地图上的行走动画参考，验证 walk sheet 流畅度。

```
[Subject] Full-body walk cycle of {{DISPLAY_NAME}} ({{NPC_ID}}), {{GENDER}} Chinese {{ROLE}}, modern pixel art game sprite.
[Appearance] {{CLOTHING}}. Body proportions: 64px tall, head 16px (1/4 height). 1px dark outline.
[Action] Smooth 4-frame walk cycle in place (character walks on a treadmill-like spot). Step sequence: contact → passing → contact → passing. Natural arm swing opposite to leg movement. Walking speed: brisk but calm walk.
[Duration] 5 seconds, seamless loop (approximately 8 cycles at 150ms/frame).
[Camera] Static side-view or diagonal-down view (top-down RPG perspective). Character centered. Simple floor shadow beneath.
[Background] Plain light gray floor (#D1D5DB) or transparent. No environment details.
[Style Keywords] Modern cozy 2D pixel art game sprite, top-down RPG style, NOT 8-bit.
[Technical] 12 fps, 60 frames, seamless loop. 256x256 canvas. 4 distinct frame poses cycling smoothly.
[Negative] NO motion blur, NO smear frames, NO 3D rendering, NO 8-bit retro, NO chibi, NO foot sliding.
```

### 1.4 手势动作视频 (Gesture Animation)

**用途**：特定 NPC 的关键动作展示，如递文件、看平板、挥手等。

```
[Subject] {{DISPLAY_NAME}} ({{NPC_ID}}), {{GENDER}} Chinese {{ROLE}}, performing a specific gesture, modern pixel art.
[Appearance] Wearing {{CLOTHING}}. Waist-up framing.
[Action] {{GESTURE_DESCRIPTION}}. Duration: {{ACTION_DURATION}}. Natural timing, no rush. One continuous motion with clear start, hold, and return phases.
[Duration] 5 seconds total (action ~3s, return to rest ~2s).
[Camera] Waist-up shot, static, character centered. Slightly framed to show the gesture clearly.
[Lighting] Soft indoor lighting, {{MOOD}} mood.
[Style Keywords] Modern cozy 2D pixel art animation, subtle gesture, professional manner.
[Technical] 12 fps, 60 frames. 512x384 canvas. Pixel art.
[Negative] NO exaggerated movement, NO 8-bit retro, NO anime-style motion lines, NO 3D.
```

### 手势动作速查表 (Gesture Quick Reference)

| NPC Role | Gesture | `{{GESTURE_DESCRIPTION}}` |
|----------|---------|--------------------------|
| 招生办主任 | 递出文件 | reaches forward with right hand holding a document folder, offers it to the viewer, then withdraws hand back to rest |
| 合规专员 | 翻开文件夹 | lifts a folder with left hand, opens it with right hand, glances down at the contents, then closes it |
| IT 运维 | 推眼镜+指向屏幕 | adjusts glasses with index finger, then points right hand toward an off-screen monitor |
| 班主任 | 看平板做笔记 | holds a tablet in left hand, taps the screen with right index finger, nods slightly |
| 后勤主管 | 拿对讲机通话 | unclips walkie-talkie from belt, brings it to mouth, speaks briefly, clips it back |
| 家长代表 | 询问姿态 | slight forward lean, both hands clasped at waist level, concerned facial expression, slight head tilt |
| 学生代表 | 挥手打招呼 | raises right hand in a friendly wave, slight smile, then lowers hand |
| 校长 | 点头肯定 | slow deliberate nod, hands clasped behind back, authoritative but warm posture |

---

## 2. 场景视频模板 (Scene Video)

### 2.1 NPC 场景定位视频 (NPC in Environment)

**用途**：展示 NPC 在所属场景中的定位和氛围，用于游戏宣传/概念展示。

```
[Subject] {{DISPLAY_NAME}}, a {{GENDER}} Chinese {{ROLE}}, standing in {{LOCATION_CN}} ({{LOCATION}}), modern pixel art.
[Appearance] Full-body sprite: 64px tall, head-to-body ratio 1:4. Wearing {{CLOTHING}}. Skin tone {{SKIN_TONE}}. 1px dark outline.
[Environment] {{LOCATION_DESC}}. Modern educational campus interior. Clean lines, warm lighting. Educational technology elements visible (digital screens, tablets, modern furniture).
[Camera] Wide shot showing the NPC in the center of the room. Camera slowly zooms in from wide establishing shot to medium shot over 5 seconds. Smooth digital zoom (no camera shake).
[Atmosphere] {{MOOD}} atmosphere. {{TIME_OF_DAY}} lighting. Subtle ambient animation: gentle light flicker from screens, slight plant movement if any.
[Duration] 5 seconds.
[Style Keywords] Modern cozy 2D pixel art, educational technology campus, NOT rural, NOT Stardew Valley. Warm professional environment.
[Technical] 12 fps, 60 frames. 1024x576 canvas. Pixel art with subtle ambient motion.
[Negative] NO farmland, NO rustic furniture, NO 8-bit retro, NO dark dungeon lighting, NO fantasy, NO 3D rendering, NO realistic photo textures.
```

### 2.2 场景空镜视频 (Environment Establishing Shot)

**用途**：纯场景氛围展示，无 NPC，用于场景切换过渡或菜单背景。

```
[Subject] {{LOCATION_CN}} ({{LOCATION}}), interior establishing shot without characters, modern pixel art.
[Environment] {{LOCATION_DESC}}. Modern educational campus interior. Clean architectural lines, glass partitions, digital displays, modern furniture. Educational technology ambiance.
[Camera] Slow pan from left to right over 5 seconds. Smooth, cinematic pace. Reveals the space naturally.
[Atmosphere] {{MOOD}} atmosphere. {{TIME_OF_DAY}} lighting. Subtle ambient elements: computer screen glow, gentle dust particles in light beams, leaves outside window swaying slightly.
[Duration] 5 seconds.
[Style Keywords] Modern cozy 2D pixel art environmental shot. Contemporary school interior. Educational technology aesthetic.
[Technical] 12 fps, 60 frames. 1024x576 canvas (16:9). Pixel art.
[Negative] NO characters visible, NO 8-bit retro, NO rural or outdoor farm views, NO fantasy architecture, NO 3D, NO realistic photos.
```

### 场景描述速查表 (Location Quick Reference)

| `{{LOCATION}}` | `{{LOCATION_CN}}` | `{{LOCATION_DESC}}` | `{{MOOD}}` | `{{TIME_OF_DAY}}` |
|----------------|-------------------|---------------------|------------|-------------------|
| `school_gate` | 校门 | modern school entrance with digital welcome board, glass doors, security desk, trees lining the path | welcoming and orderly | bright morning sunlight |
| `admission_office` | 招生办公室 | bright admission office with glass walls, reception counter, informational brochures on stands, modern seating area | warm and professional | mid-morning soft daylight |
| `academic_affairs` | 教务处 | organized academic office with filing cabinets, teacher workstations, schedule board on wall, potted plants | professional and calm | afternoon diffuse light |
| `canteen` | 食堂 | clean modern cafeteria with food service counters, digital menu boards, rows of tables and chairs, warm lighting | busy and warm | noon bright light |
| `ai_hub` | AI 中枢 | futuristic control room with large dashboard screens showing data visualizations, holographic displays, sleek dark interface design | focused and high-tech | dim ambient blue glow |

---

## 3. 使用说明 (Usage Guide)

### 3.1 生成顺序

```
Phase 1 — 角色动作:
  1. idle_talk (对话待机) → 验证角色像素动画风格
  2. expression_transition (表情切换) → 验证表情像素变化
  3. walk_cycle (行走循环) → 验证 walk sheet
  4. gesture (手势) → 按需生成

Phase 2 — 场景展示:
  5. npc_in_environment (场景定位) → 验证角色+场景融合
  6. establishing_shot (场景空镜) → 用于 UI 背景
```

### 3.2 视频参数建议

| 工具 | 推荐分辨率 | FPS | 格式 | 备注 |
|------|-----------|-----|------|------|
| Runway Gen-3 | 1280×768 | 24 | MP4 | 使用 image-to-video 模式，以立绘图为起始帧 |
| Pika 2.0 | 1088×640 | 24 | MP4 | 支持 --style pixel 参数 |
| Kling 1.6 | 960×960 | 24 | MP4 | 中英文 prompt 均可 |
| Sora | 1024×576 | 24 | MP4 | 需要详细的环境描述 |
| Luma Dream Machine | 1280×720 | 24 | MP4 | 支持 start_frame + end_frame |

### 3.3 调校建议

- **像素风保持**：在 prompt 中强调 "12fps" 和 "pixel art" 以保留逐帧感觉
- **避免过度平滑**：Negative 中加入 "smooth 30fps tween animation, 3D render, claymation"
- **颜色一致性**：如生图工具支持，可提供色板图作为 reference image
- **循环验证**：对 idle 和 walk 视频，检查首尾帧是否可无缝循环

---

## 附录：完整填充示例 (Filled Example)

### 示例：teacher_admission_001（李招生老师）— 对话待机视频

```
{{NPC_ID}}            = teacher_admission_001
{{DISPLAY_NAME}}      = 李招生老师
{{ROLE}}              = 招生办主任
{{GENDER}}            = female
{{CLOTHING}}          = 深蓝西装套装，暖白衬衫，深色领带，左胸佩戴校徽
{{LOCATION}}          = admission_office
{{LOCATION_CN}}       = 招生办公室
{{LOCATION_DESC}}     = bright admission office with glass walls, reception counter, informational brochures on stands, modern seating area
{{MOOD}}              = warm and professional
{{SKIN_TONE}}         = #F4C7A1
```

**填充后的 Prompt**:

```
[Subject] 李招生老师, a female Chinese 招生办主任 in modern pixel art style, standing in 招生办公室 (admission_office).
[Appearance] Wearing 深蓝西装套装，暖白衬衫，深色领带，左胸佩戴校徽. Skin tone #F4C7A1. Clean pixel art rendering with 1-2px dark outlines.
[Action] Gentle idle breathing animation: chest subtly rising and falling. Occasional slow blink (eyes close for ~200ms). Slight weight shift between feet. Natural, calm, not exaggerated.
[Duration] 5 seconds, seamless loop.
[Camera] Static shot, waist-up or full-body centered in frame. No camera movement.
[Lighting] Soft indoor lighting from ceiling panels. Warm ambient tone matching warm and professional mood. Subtle shadow on floor.
[Style Keywords] Modern cozy 2D pixel art animation, NOT 8-bit, NOT Stardew Valley. Pixel-art motion at 12fps. Contemporary Chinese international school setting.
[Technical] 5 seconds, 12 fps, 60 frames total. Seamless loop. 512x512 output recommended for upscale.
[Negative] NO 8-bit choppy animation, NO smooth 30fps tween animation (keep pixel-jump feel), NO exaggerated cartoon squash-and-stretch, NO rural or farm elements, NO fantasy, NO 3D rendering.
```

---

*本模板为 MetaCampus NPC 视频生成的权威参考。生成前必须填充所有变量。场景描述和氛围必须来自已注册的 location 定义。*
