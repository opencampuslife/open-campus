# MetaCampus NPC 调色板规范 v1.0

> 版本：v1.0
> 日期：2026-05-28
> 作者：Narrative Designer
> 用途：为 pixel-artist 生成 8 NPC 全部资产提供可推广色板规范
> 关联规范：docs/npc-style-bible.md v1.1 §11.6

---

## 一、核心色板（Primary Palette）

MetaCampus 所有 NPC 资产必须从以下 5 个主色中选取，每个 sprite 不超过 5 种颜色（含描边和阴影）。

### 1.1 主色板一览

| 色号 | 色名 | Hex | RGB | 用途 |
|------|------|-----|-----|------|
| **P1** | 深蓝（Deep Blue） | `#2D4A6B` | 45, 74, 107 | 校服西装、招生办服装、UI 主色 |
| **P2** | 暖白（Warm White） | `#F5E6D3` | 245, 230, 211 | 衬衫、背景占位、UI 底色 |
| **P3** | 橙红（Burnt Orange） | `#E8734A` | 232, 115, 74 | 强调色、提示图标、指标警示 |
| **P4** | 安全绿（Sage Green） | `#5BA87B` | 91, 168, 123 | 成功态、指标上升、合规安全 |
| **P5** | 肤色（Skin Tone） | `#F4C7A1` | 244, 199, 161 | **所有 NPC 面部和手部肤色，统一使用，禁止变体** |

### 1.2 主色板视觉参考

```
■ #2D4A6B  深蓝 P1    ■ #F5E6D3  暖白 P2    ■ #E8734A  橙红 P3
■ #5BA87B  安全绿 P4  ■ #F4C7A1  肤色 P5
```

---

## 二、辅助色板（Secondary Palette）

辅助色板用于 NPC 服装细节和辅助色彩搭配。每个 NPC sprite 的总颜色数（含主色+辅助色+描边+阴影）不超过 5 种。

### 2.1 辅助色板一览

| 色号 | 色名 | Hex | RGB | 用途 |
|------|------|-----|-----|------|
| **S1** | 深灰（Charcoal） | `#374151` | 55, 65, 81 | 校长西装、IT 裤子 |
| **S2** | 中灰（Medium Grey） | `#6B7280` | 107, 114, 128 | 合规套装 |
| **S3** | 浅蓝（Light Blue） | `#60A5FA` | 96, 165, 250 | 班主任衬衫 |
| **S4** | 卡其（Khaki） | `#C4A77D` | 196, 167, 125 | 后勤工装 |
| **S5** | 深棕（Dark Brown） | `#5C4033` | 92, 64, 51 | 后勤裤子 |
| **S6** | 深蓝辅（Deep Navy） | `#1E3A5F` | 30, 58, 95 | 班主任裤子、深色描边 |
| **S7** | 校徽金（Emblem Gold） | `#D4A843` | 212, 168, 67 | 校长/招生办主任校徽 |
| **S8** | 阴影（Outline） | `#1A1A2E` | 26, 26, 46 | 轮廓描边、阴影 |

### 2.2 辅助色板视觉参考

```
■ #374151  深灰 S1     ■ #6B7280  中灰 S2     ■ #60A5FA  浅蓝 S3
■ #C4A77D  卡其 S4    ■ #5C4033  深棕 S5     ■ #1E3A5F  深蓝辅 S6
■ #D4A843  校徽金 S7  ■ #1A1A2E  阴影 S8
```

---

## 三、肤色统一规范（Skin Tone）

| 规范 | 值 |
|------|-----|
| **统一肤色** | `#F4C7A1`（244, 199, 161） |
| **适用范围** | 所有 NPC 面部 + 手部，无例外 |
| **变体限制** | 禁止任何肤色变体（不得偏暗/偏粉/偏黄绿/偏白/偏黑） |
| **高光** | 开心表情可选：1px 淡粉色点（#F4C7A1 高光变体，如 #F9C9B1） |
| **实现方式** | AI 生图 prompt 中写入 `warm skin tone (#F4C7A1)`，禁用其他肤色词 |

---

## 四、8 NPC 推荐色板分配

### 4.1 招生办主任 — admissions_director（周明远）

| 角色 | npc_id | 主色 | 辅色 | 点缀色 | 肤色 | 说明 |
|------|--------|------|------|--------|------|------|
| 周明远 | `admissions_director` | P1 深蓝 #2D4A6B | P2 暖白 #F5E6D3 | S7 校徽金 #D4A843 | P5 #F4C7A1 | 深蓝西装+白衬衫+金色校徽 |

> **色块组合**（≤ 5色）：P1(西装) + P2(衬衫) + S7(校徽) + P5(肤色) + S8(描边)

### 4.2 合规专员 — compliance_officer（林澈）

| 角色 | npc_id | 主色 | 辅色 | 点缀色 | 肤色 | 说明 |
|------|--------|------|------|--------|------|------|
| 林澈 | `compliance_officer` | S2 中灰 #6B7280 | P2 暖白 #F5E6D3 | S8 深灰（眼镜） | P5 #F4C7A1 | 灰色职业套装+黑框眼镜 |

> **色块组合**：S2(套装) + P2(衬衫) + S1(眼镜框) + P5(肤色) + S8(描边)

### 4.3 IT运维 — it_operator（许航）

| 角色 | npc_id | 主色 | 辅色 | 点缀色 | 肤色 | 说明 |
|------|--------|------|------|--------|------|------|
| 许航 | `it_operator` | S1 深灰 #374151 | S2 中灰 #6B7280 | S7 校徽金 #D4A843 | P5 #F4C7A1 | 深灰 polo 衫 + 工牌 |

> **色块组合**：S1(polo衫) + S2(裤子) + S7(工牌) + P5(肤色) + S8(描边)

### 4.4 班主任 — homeroom_teacher（陈芷）

| 角色 | npc_id | 主色 | 辅色 | 点缀色 | 肤色 | 说明 |
|------|--------|------|------|--------|------|------|
| 陈芷 | `homeroom_teacher` | S3 浅蓝 #60A5FA | S6 深蓝辅 #1E3A5F | S8 深灰（平板） | P5 #F4C7A1 | 浅蓝衬衫+深色西裤+手持平板 |

> **色块组合**：S3(衬衫) + S6(裤子) + S1(平板) + P5(肤色) + S8(描边)

### 4.5 后勤主管 — logistics_manager（赵启山）

| 角色 | npc_id | 主色 | 辅色 | 点缀色 | 肤色 | 说明 |
|------|--------|------|------|--------|------|------|
| 赵启山 | `logistics_manager` | S4 卡其 #C4A77D | S5 深棕 #5C4033 | S8 深灰（对讲机） | P5 #F4C7A1 | 卡其工装夹克+深棕工装裤+对讲机 |

> **色块组合**：S4(工装) + S5(裤子) + S1(对讲机) + P5(肤色) + S8(描边)

### 4.6 家长代表 — parent_representative（顾兰）

| 角色 | npc_id | 主色 | 辅色 | 点缀色 | 肤色 | 说明 |
|------|--------|------|------|--------|------|------|
| 顾兰 | `parent_representative` | P1 深蓝 #2D4A6B | P2 暖白 #F5E6D3 | S1 深灰（公文包） | P5 #F4C7A1 | 深蓝休闲西装+暖白内搭+公文包 |

> **色块组合**：P1(外套) + P2(内搭) + S1(公文包) + P5(肤色) + S8(描边)

### 4.7 学生代表 — student_representative（沈一诺）

| 角色 | npc_id | 主色 | 辅色 | 点缀色 | 肤色 | 说明 |
|------|--------|------|------|--------|------|------|
| 沈一诺 | `student_representative` | P2 暖白 #F5E6D3 | P1 深蓝 #2D4A6B | S7 校徽金（学生会徽章） | P5 #F4C7A1 | 白校服衬衫+深蓝西装外套+校徽 |

> **色块组合**：P2(衬衫) + P1(外套) + S1(校裤/深灰) + P5(肤色) + S8(描边)

### 4.8 校长 — principal（唐毓）

| 角色 | npc_id | 主色 | 辅色 | 点缀色 | 肤色 | 说明 |
|------|--------|------|------|--------|------|------|
| 唐毓 | `principal` | S1 深灰 #374151 | P2 暖白 #F5E6D3 | S7 校徽金 #D4A843 + P3 橙红（领带） | P5 #F4C7A1 | 深灰西装三件套+白衬衫+深红领带+金色校徽 |

> **色块组合**：S1(西装) + P2(衬衫) + P3(领带) + S7(校徽) + P5(肤色) + S8(描边) = **6色，超限，需精简** → 领带和校徽选一个点缀色，或用 S1 深灰作领带色

---

## 五、正向关键词（Positive Keywords）

以下关键词应出现在**所有 NPC** 生成 prompt 的正向描述段：

```
modern Chinese international school    warm campus atmosphere
cozy 2D style (NOT 8-bit)          clean pixel art
professional attire                 warm lighting
bright and inviting color palette   contemporary educational technology setting
friendly and approachable expression
```

### 5.1 分层关键词（按资产类型）

**立绘 Portrait（256×256）：**
```
front-facing portrait, 256×256 canvas
warm skin tone (#F4C7A1)
1px dark outline (#1A1A2E)
2-3 level soft lighting from top + ambient fill
clear color blocks
≤ 5 colors total
```

**精灵 Sprite Idle（64×64）：**
```
64×64px sprite, idle standing pose, front-facing
1:4 head-to-body ratio
≤ 5 colors total
```

**行走 Walk Sheet（256×64）：**
```
256×64px walk cycle sheet, 4 frames
150ms per frame (~6.67 fps)
transparent PNG background
```

---

## 六、禁止关键词（Forbidden Keywords）

以下关键词必须在所有 NPC 生成 prompt 的 Negative prompt 中**强制禁止**：

### 6.1 禁止元素分类清单

| 类别 | 禁止词 | 原因 |
|------|--------|------|
| **复古像素风** | retro pixel, 8-bit, 16-bit, pixel art retro, old school game | 必须与 Stardew/复古像素区分 |
| **暗黑色调** | dark tone, dark background, black shadows, high contrast black-white, harsh shadows | 目标明亮温暖校园风 |
| **Stardew Valley** | Stardew Valley, farm elements, harvest, fishing rod, farm hat | 世界观：现代校园非农场 |
| **奇幻元素** | fantasy, magic wand, wings, dragon, elf ears, spell circle | 非奇幻世界观 |
| **中世纪/复古 RPG** | medieval setting, dungeon, stone brick path, cobblestone, castle wall | 场景：现代校园 |
| **法式乡村** | French countryside, Provence, lavender, ironwork decoration, rural scenery | 风格冲突 |
| **低质量** | low quality, blurry, noisy, grainy, JPEG artifacts | 规范质量要求 |
| **过饱和** | oversaturated, candy colors, bright neon | 目标适中饱和度 |
| **低幼Q版** | cute chibi style, big head (head-to-body ratio > 1:3), baby face | 目标专业可亲 |
| **戏剧化表情** | theatrical expression, dramatic pose, over-emotional | 目标自然中性 |
| **噪点/纹理** | noisy, grainy, dithering, color bleeding, color jumping | 目标干净清晰 |

### 6.2 合并 Negative Prompt 模板

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
noisy texture, color bleeding, color jumping, dithering artifacts
```

---

## 七、色板使用规则（Color Usage Rules）

### 7.1 颜色数量约束

| 资产类型 | 最大颜色数（含描边和阴影） | 说明 |
|----------|--------------------------|------|
| Sprite（地图精灵） | ≤ 5 种 | 主色 + 辅色 + 肤色 + 描边 + 阴影 |
| 立绘 Portrait | ≤ 16 种 | 对话立绘可使用完整色板 |
| Walk Sheet | ≤ 5 种/帧 | 同 sprite 规范 |

### 7.2 描边规范

- **描边色**：`#1A1A2E`（阴影 S8）或深于主色的对比色
- **描边宽度**：1px（portrait 可用 1-2px）
- **描边目的**：确保在俯视角地图上可辨识

### 7.3 阴影规范

- **阴影色**：`#1A1A2E`，20% 透明度椭圆
- **阴影位置**：脚底 4px 底部柔边
- **阴影动画**：不随动画帧变化

### 7.4 主色分配表（快速参考）

| NPC 角色 | npc_id | 服装主色 Hex | 辅色 Hex | 角色类型关键词 |
|----------|--------|-------------|---------|----------------|
| 周明远 | `admissions_director` | #2D4A6B | #F5E6D3 | 招生办主任, 深蓝西装 |
| 林澈 | `compliance_officer` | #6B7280 | #F5E6D3 | 合规专员, 灰色套装 |
| 许航 | `it_operator` | #374151 | #6B7280 | IT运维, 深灰polo |
| 陈芷 | `homeroom_teacher` | #60A5FA | #1E3A5F | 班主任, 浅蓝衬衫 |
| 赵启山 | `logistics_manager` | #C4A77D | #5C4033 | 后勤主管, 卡其工装 |
| 顾兰 | `parent_representative` | #2D4A6B | #F5E6D3 | 家长代表, 深蓝休闲 |
| 沈一诺 | `student_representative` | #F5E6D3 | #2D4A6B | 学生代表, 校服 |
| 唐毓 | `principal` | #374151 | #F5E6D3 | 校长, 深灰西装 |

---

## 八、版本历史

| 版本 | 日期 | 变更 |
|------|------|------|
| v1.0 | 2026-05-28 | 初始发布：5 主色板 + 8 辅助色板 + 肤色规范 + 8 NPC 分配 + 正向/禁止关键词 + 使用规则 |

---

*本文档为 MetaCampus NPC 资产生成的可推广色板规范，可直接被 pixel-artist 用于生成 8 NPC 全部资产。*
*如需更新色板，请同步更新 docs/npc-style-bible.md v1.1 §11.6 色板章节。*