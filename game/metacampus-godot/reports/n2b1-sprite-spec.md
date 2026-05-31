# Sprite Animation Spec Report — n2b1-sprite-spec

> 版本：v1.0
> 日期：2026-05-28
> 作者：Narrative Designer
> 任务：定义 NPC walk sheet 动画规格
> 验收方：Pixel Artist & Godot Developer

---

## 一、任务目标

为 MetaCampus Godot 项目的两个 NPC 定义 walk sheet 动画规范：
- **admissions_director**（周明远，招生办主任）
- **student_representative**（林澈，学生代表）

---

## 二、规格决策依据

### 2.1 帧尺寸决策

| 选项 | 规格 | 选择理由 |
|------|------|----------|
| art-style-guide.md §5.2 | 28×28px（tile内） | MVP阶段静态NPC |
| npc-style-bible.md §11.3 | 64×64px | AI生图规格，立绘级精度 |
| **最终决策** | **64×64px** | 当前baseline sprite已是64×64，风格圣经已明确此规格 |

**决策逻辑**：
1. baseline sprite输入文件已确认是64×64 PNG RGBA
2. npc-style-bible.md §11.3已明确定义64×64单帧尺寸
3. AI生图工具（Matrix MCP）生成此规格无障碍
4. 64×64在Godot中缩放灵活（可下采样为28×28用于tile内显示）

### 2.2 帧数决策

| 选项 | 帧数 | 选择理由 |
|------|------|----------|
| 3帧/方向 | art-style-guide.md §1.2 | 早期规范 |
| **4帧/方向** | **npc-style-bible.md §11.3** | 最新规范，walk cycle完整性更高 |
| 8帧/方向 | - | 过度设计，MVP不需要 |

**决策逻辑**：
1. npc-style-bible.md v1.1明确指定4帧walk cycle
2. 4帧（接触→过渡→交叉→过渡）覆盖标准行走周期
3. 150ms/帧 ≈ 6.67fps，流畅且性能友好

### 2.3 方向数决策

| 选项 | 方向数 | 选择理由 |
|------|--------|----------|
| 1方向 | 俯视角游戏通用 | MVP简化 |
| **4方向** | **npc-style-bible.md §2.4** | 玩家一致，交互体验完整 |
| 8方向 | 斜向行走 | 过度设计 |

**决策逻辑**：
1. npc-style-bible.md §2.4明确"四方向（上下左右），与玩家一致"
2. 4方向足以覆盖俯视角游戏的典型移动场景
3. 每个方向独立walk sheet文件，便于管理

### 2.4 锚点决策

| 字段 | 值 | 理由 |
|------|-----|------|
| anchor.x | 32 | 水平居中 |
| anchor.y | 60 | 64px高度减4px底部阴影 |

**决策逻辑**：
1. 锚点位于脚底中心偏下
2. 便于与地面tile对齐（地面tile的碰撞点在顶部）
3. 与Godot的Sprite2D锚点机制兼容

---

## 三、Walk Sheet 布局规格

```
┌──────────┬──────────┬──────────┬──────────┐
│ 帧0      │ 帧1      │ 帧2      │ 帧3      │
│ 接触帧   │ 过渡帧   │ 交叉帧   │ 过渡帧   │
│ 64×64px  │ 64×64px  │ 64×64px  │ 64×64px  │
└──────────┴──────────┴──────────┴──────────┘
Canvas: 256×64px
```

| 参数 | 值 |
|------|------|
| 单帧尺寸 | 64×64px |
| Sheet尺寸 | 256×64px |
| 帧排列 | 1行×4列，横向 |
| 方向文件 | 4个（down/up/left/right） |

---

## 四、颜色规格来源

### 4.1 admissions_director（周明远）

| 部位 | 色号 | Hex | 来源 |
|------|------|-----|------|
| 西装 | 深蓝 | #2D4A6B | npc-style-bible.md §11.5 表 |
| 衬衫 | 暖白 | #F5E6D3 | 同上 |
| 肤色 | 暖白 | #F4C7A1 | npc-style-bible.md §11.6.2 统一肤色 |
| 校徽 | 金色 | #D4A843 | 同上 |
| 描边 | 深色 | #1A1A2E | 同上 |

### 4.2 student_representative（林澈）

| 部位 | 色号 | Hex | 来源 |
|------|------|-----|------|
| 校服衬衫 | 暖白 | #F5E6D3 | npc-style-bible.md §11.5 表 |
| 西装外套 | 深蓝 | #2D4A6B | 同上 |
| 校裤 | 中灰 | #6B7280 | 同上 |
| 双肩背包 | 深蓝 | #2D4A6B | 同上 |
| 肤色 | 暖白 | #F4C7A1 | 统一肤色 |
| 校徽 | 金色 | #D4A843 | 同上 |

---

## 五、Baseline Sprite 分析结论

### 5.1 admissions_director/baseline/sprite_idle.png

| 分析项 | 结论 |
|--------|------|
| 尺寸 | 64×64 PNG RGBA ✅ |
| 头身比 | 约1:5~1:6，非Q版 ✅ |
| 视角 | 正面3/4视图，轻微俯视 ✅ |
| 颜色 | 白色外套+深色裤子，高对比明暗法 ✅ |
| 风格 | 复古暗黑风格，与规范有差异 ⚠️ |

**说明**：baseline sprite呈现复古暗黑风格，颜色偏白/黑高对比，与style bible的温暖配色有差异。这是初期生成的结果，后续应按本规格重新生成或手工修正。

### 5.2 student_representative/baseline/sprite_idle.png

| 分析项 | 结论 |
|--------|------|
| 尺寸 | 64×64 PNG RGBA ✅ |
| 头身比 | 约1:4~1:5 ✅ |
| 视角 | 3/4侧视图 ✅ |
| 颜色 | 青蓝+白色，噪点较多 ✅ |
| 风格 | 暗黑幻想/故障风格 ⚠️ |

**说明**：baseline sprite噪点较多，色彩跳跃大。应在后续生成中明确使用柔和配色和干净轮廓。

---

## 六、与其他规范的冲突处理

### 6.1 art-style-guide.md vs npc-style-bible.md

| 冲突项 | art-style-guide.md | npc-style-bible.md | 决策 |
|--------|-------------------|-------------------|------|
| 角色尺寸 | 28×28px | 64×64px（单帧） | **npc-style-bible.md优先**（更新版本v1.1） |
| 动画帧数 | 3帧/方向 | 4帧/方向 | **npc-style-bible.md优先** |
| tile尺寸 | 32×32 | 不涉及 | **art-style-guide.md优先** |

**处理原则**：
- npc-style-bible.md是专门针对NPC资产的设计圣经，优先级高于通用art-style-guide
- 64×64可下采样为28×28用于tile内显示，技术上可行
- 4帧walk cycle覆盖更完整，MVP阶段影响不大

### 6.2 规范层级

```
npc-style-bible.md（NPC专项） > art-style-guide.md（通用美术）
```

---

## 七、输出文件清单

| 文件 | 位置 | 用途 |
|------|------|------|
| `animation_spec.json` | `assets/npcs/admissions_director/` | admissions_director动画规格 |
| `animation_spec.json` | `assets/npcs/student_representative/` | student_representative动画规格 |
| `walk_sheet_prompt.md` | `prompts/npcs/admissions_director/` | AI生图prompt |
| `walk_sheet_prompt.md` | `prompts/npcs/student_representative/` | AI生图prompt |
| `n2b1-sprite-spec.md` | `reports/` | 设计决策报告 |

---

## 八、验收清单

- [x] 帧尺寸：64×64px
- [x] 帧数：4帧/方向
- [x] 方向数：4方向（上下左右）
- [x] 锚点：anchor_point (32, 60)
- [x] 透明边框：top/left/right各留4-8px
- [x] walk_sheet_layout：256×64px，1×4网格
- [x] naming_convention：符合规范
- [x] animations定义：idle/walk/talk
- [x] Godot导入参数：import_mode/filter/hframes/vframes
- [x] 颜色规格与npc-style-bible.md一致
- [x] walk_sheet_prompt包含完整角色描述
- [x] walk_sheet_prompt包含4帧详细描述
- [x] walk_sheet_prompt包含禁止元素清单
- [x] walk_sheet_prompt包含AI生图完整prompt

---

## 九、版本历史

| 版本 | 日期 | 变更 |
|------|------|------|
| v1.0 | 2026-05-28 | 初始发布：定义64×64/4帧/4方向规格，完成两个NPC的animation_spec.json和walk_sheet_prompt.md |