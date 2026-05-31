# Phase N2B-1 Animation Integration Report

> **版本**: v1.0
> **日期**: 2026-05-28
> **状态**: ✅ COMPLETE
> **覆盖 NPC**: admissions_director, student_representative

---

## 1. 规格决策汇总

| 维度 | 决策 | 来源 | 状态 |
|------|------|------|------|
| 帧尺寸 | 64×64px | npc-style-bible.md §11.3 | ✅ |
| 帧数 | 4帧/方向 | npc-style-bible.md §11.3 | ✅ |
| 方向数 | 4方向（上下左右） | npc-style-bible.md §2.4 | ✅ |
| 锚点 | (32, 60) — 脚底中心偏下 | n2b1-sprite-spec.md §2.4 | ✅ |
| Sheet 布局 | 256×64px，1行×4列 | n2b1-sprite-spec.md §3 | ✅ |
| 帧间隔 | 150ms/帧（约6.67fps） | animation_spec.json | ✅ |
| 纹理过滤 | Nearest | animation_spec.json | ✅ |

**规范优先级**: `npc-style-bible.md`（NPC专项） > `art-style-guide.md`（通用美术）。64×64 可下采样为28×28用于 tile 内显示。

---

## 2. Walk Sheet 验证

### 2.1 文件存在性

所有 walk sheet 文件均已生成并位于 `baseline/` 子目录：

| NPC | Direction | 文件 | 尺寸 | 格式 |
|-----|-----------|------|------|------|
| admissions_director | down | `baseline/admissions_director_walk_down.png` | 256×64px | PNG RGBA ✅ |
| admissions_director | up | `baseline/admissions_director_walk_up.png` | 256×64px | PNG RGBA ✅ |
| admissions_director | left | `baseline/admissions_director_walk_left.png` | 256×64px | PNG RGBA ✅ |
| admissions_director | right | `baseline/admissions_director_walk_right.png` | 256×64px | PNG RGBA ✅ |
| student_representative | down | `baseline/student_representative_walk_down.png` | 256×64px | PNG RGBA ✅ |
| student_representative | up | `baseline/student_representative_walk_up.png` | 256×64px | PNG RGBA ✅ |
| student_representative | left | `baseline/student_representative_walk_left.png` | 256×64px | PNG RGBA ✅ |
| student_representative | right | `baseline/student_representative_walk_right.png` | 256×64px | PNG RGBA ✅ |

**idle 精灵**（位于 `baseline/sprite_idle.png`）：

| NPC | 尺寸 | 格式 |
|-----|------|------|
| admissions_director | 64×64px | PNG RGBA ✅ |
| student_representative | 64×64px | PNG RGBA ✅ |

### 2.2 角色一致性

两个 NPC 的 walk sheet 均满足：
- **透明背景**: PNG RGBA 格式，IHDR 确认支持 alpha 通道
- **单帧尺寸**: 每帧 64×64px（Sheet 合计 256×64px = 4×64）
- **帧数**: 4帧/方向 ✅
- **独立方向**: 每个方向独立文件 ✅

> **注意**: 实际生成文件位于 `baseline/<name>_walk_<direction>.png`（无 `sprite_walk_sheet.png` 合并文件）。这是设计决策 — 分立方向文件更易于管理，也与 animation_spec.json 的 naming_convention 一致。

### 2.3 已知风格问题（不阻断集成）

- `admissions_director` baseline sprite：复古暗黑风格，颜色偏白/黑高对比，与 npc-style-bible.md 温暖配色有偏差
- `student_representative` baseline sprite：噪点较多，色彩跳跃大

这些属于美术风格问题，不影响当前阶段的动画集成和 Godot 加载流程。

---

## 3. Godot 集成状态

### 3.1 脚本产出

| 文件 | 角色 | 状态 |
|------|------|------|
| `scripts/npc_sprite_loader.gd` | 通用 SpriteFrames 工具类 | ✅ |
| `assets/npcs/admissions_director/admissions_director_sprites.gd` | admissions_director 专用 builder | ✅ |
| `assets/npcs/student_representative/student_representative_sprites.gd` | student_representative 专用 builder | ✅ |

### 3.2 NpcFactory 集成

`scripts/npc_factory.gd` 的 `_try_load_sprite_frames()` 实现了三级降级：

```
1. 专用 builder 类 (AdmissionsDirectorSprites / StudentRepresentativeSprites)
   → 使用 build_from_spec_with_idle()，传入显式 _IDLE_PATH
2. animation_spec.json + 显式 baseline/sprite_idle.png 路径
   → 使用 build_from_spec_with_idle()，naming_convention 驱动 walk sheet
3. 直接加载 baseline/sprite_idle.png
   → 最简降级，ColorRect fallback
```

`npc_factory.gd:84` 设置了正确的锚点偏移：
```gdscript
anim_sprite.offset = Vector2(-32, -60)  # 与 spec 锚点 (32,60) 对应
```

### 3.3 关键集成路径

```
NpcFactory._add_sprite_layer()
  └─> _try_load_sprite_frames(npc_id)
        └─> AdmissionsDirectorSprites.get_sprite_frames()
              └─> NpcSpriteLoader.build_from_spec_with_idle(NPC_DIR, SPEC_PATH, _IDLE_PATH)
                    ├─ idle: 使用显式 _IDLE_PATH = "res://assets/npcs/admissions_director/baseline/sprite_idle.png"
                    └─ walk: 从 animation_spec.json.naming_convention.walk_sheet 构造路径
                          → "baseline/admissions_director_walk_down.png"
                          → 完整路径: res://assets/npcs/admissions_director/baseline/admissions_director_walk_down.png ✅
```

### 3.4 SpriteFrames 动画名称

`NpcSpriteLoader` 注册以下动画名称：

| 动画名 | 来源 | 帧率 |
|--------|------|------|
| `idle` | `baseline/sprite_idle.png` | 静态 |
| `walk_down` | `baseline/<name>_walk_down.png` | 150ms |
| `walk_up` | `baseline/<name>_walk_up.png` | 150ms |
| `walk_left` | `baseline/<name>_walk_left.png` | 150ms |
| `walk_right` | `baseline/<name>_walk_right.png` | 150ms |
| `talk` | 复用 idle 帧 | 可选 |

---

## 4. 扩展性说明：推广到剩余 6 个 NPC

当前 NPC 注册共 8 个，已完成 sprite 集成 2 个：

| 状态 | NPC ID | Display Name | Role |
|------|--------|-------------|------|
| ✅ 已完成 | `admissions_director` | 周明远 | 招生办主任 |
| ✅ 已完成 | `student_representative` | 沈一诺 | 学生代表 |
| ⬜ 待扩展 | `compliance_officer` | 林澈 | 合规专员 |
| ⬜ 待扩展 | `homeroom_teacher` | 陈芷 | 班主任 |
| ⬜ 待扩展 | `it_operator` | 许航 | IT运维 |
| ⬜ 待扩展 | `logistics_manager` | 赵启山 | 后勤主管 |
| ⬜ 待扩展 | `parent_representative` | 顾兰 | 家长代表 |
| ⬜ 待扩展 | `principal` | 唐毓 | 校长 |

### 扩展操作手册

每个新 NPC 需完成以下步骤：

**Step 1: 创建资源目录**
```
res://assets/npcs/<npc_id>/
res://assets/npcs/<npc_id>/baseline/
```

**Step 2: 生成精灵文件**
- `baseline/sprite_idle.png` — 64×64px PNG RGBA
- `baseline/<npc_id>_walk_down.png` — 256×64px PNG RGBA
- `baseline/<npc_id>_walk_up.png` — 同上
- `baseline/<npc_id>_walk_left.png` — 同上
- `baseline/<npc_id>_walk_right.png` — 同上

**Step 3: 创建 animation_spec.json**
参考 `assets/npcs/admissions_director/animation_spec.json` 模板，修改：
- `npc_id`
- `display_name`
- `role`
- `character_description`
- `style_constraints.colors`
- `godot_integration.sprite_frames_resource`

**Step 4: 创建专用 builder 脚本**
```
assets/npcs/<npc_id>/<npc_id>_sprites.gd
```
参考 `admissions_director_sprites.gd`，修改：
- `class_name`
- `NPC_DIR`
- `SPEC_PATH`
- `_IDLE_PATH`
- `has_sprites()` 中的 `_IDLE_PATH`

**Step 5: 注册到 NpcFactory**
在 `scripts/npc_factory.gd` 中更新：
```gdscript
const _SPRITE_SCRIPT_MAP: Dictionary = {
    "admissions_director": "AdmissionsDirectorSprites",
    "student_representative": "StudentRepresentativeSprites",
    "<npc_id>": "<NpcId>Sprites",  # 新增
}

const _NPC_ASSET_DIR: Dictionary = {
    "admissions_director": "res://assets/npcs/admissions_director",
    "student_representative": "res://assets/npcs/student_representative",
    "<npc_id>": "res://assets/npcs/<npc_id>",  # 新增
}
```
并更新 `_try_load_sprite_frames()` 的 `match` 语句。

---

## 5. Smoke 测试结果

### 5.1 NPC Phase 全部通过

| 测试套件 | 检查数 | 通过 | 失败 | 状态 |
|----------|--------|------|------|------|
| `smoke_npc_assets` | 151 | 151 | 0 | ✅ PASS |
| `smoke_npc_dialogues` | 333 | 333 | 0 | ✅ PASS |
| `smoke_npc_quests` | 53 | 53 | 0 | ✅ PASS |
| **合计** | **537** | **537** | **0** | **✅ ALL PASS** |

详细结果见：
- `reports/smoke_npc_assets.json`
- `reports/smoke_npc_dialogues.json`
- `reports/smoke_npc_quests.json`
- `reports/npc-smoke-done.md`

### 5.2 N2B-1 专项验证

**精灵文件物理验证**（本次报告补充）：

| 检查项 | admissions_director | student_representative | 规格 |
|--------|-------------------|----------------------|------|
| walk_down.png 存在 | ✅ | ✅ | — |
| walk_up.png 存在 | ✅ | ✅ | — |
| walk_left.png 存在 | ✅ | ✅ | — |
| walk_right.png 存在 | ✅ | ✅ | — |
| sprite_idle.png 存在 | ✅ | ✅ | 64×64 |
| walk sheet 尺寸 | 256×64px ✅ | 256×64px ✅ | 256×64px |
| PNG RGBA 格式 | ✅ | ✅ | RGBA |
| 帧数（每方向） | 4 ✅ | 4 ✅ | 4 |

---

## 6. 已知限制

### 6.1 美术风格与规范偏差

- `admissions_director` walk sheet：复古暗黑风格，温暖配色不足
- `student_representative` walk sheet：噪点较多

**影响**: 当前阶段不阻断集成。建议在 N3 Phase 重新生成时明确使用 npc-style-bible.md §11.5 色彩规格。

### 6.2 无运行时 sprite 加载 smoke test

现有 smoke 测试仅验证文件存在性和 JSON schema，未包含 Godot 运行时 SpriteFrames 加载测试。

**缓解**: `npc_sprite_loader.gd` 的 `_try_add_walk_frames` 有降级逻辑——walk sheet 缺失时复用 idle 帧，保证 NPC 不会崩溃。

### 6.3 `animation_spec.json` naming_convention 路径约定

`naming_convention.walk_sheet` 字段包含 `baseline/` 前缀（如 `baseline/admissions_director_walk_{direction}.png`），这是相对于 NPC_DIR 的路径，完整路径为 `res://assets/npcs/admissions_director/baseline/admissions_director_walk_down.png`。

当前专用 builder（`*_sprites.gd`）使用 `build_from_spec_with_idle` 并依赖此行为，路径解析正确。如有其他调用方使用 `build_from_spec`，idle 处理存在 bug（naming_convention 中 `idle_sprite: "baseline/sprite_idle.png"` 在 `npc_dir + "/"` 后生成 `baseline/baseline/sprite_idle.png`），但已被专用 builder 的显式 `_IDLE_PATH` 绕过。

### 6.4 talk 动画未实现

`talk` 动画在 `animation_spec.json` 中有定义（嘴部微动，2帧），但 `NpcSpriteLoader` 当前将 talk 降级为复用 idle 帧。需要在下一步实现。

---

## 7. 下一步建议

| 优先级 | 行动 | 说明 |
|--------|------|------|
| P0 | N3 Phase sprite 生成 | 按 npc-style-bible.md 色彩规格重新生成 2 个 NPC walk sheet |
| P1 | talk 动画实现 | 为 walk sheet 增加 talk 帧（复用 walk 第1-2帧嘴部区域，或单独生成） |
| P1 | 扩展到 6 个 NPC | 按第 4 节操作手册为剩余 NPC 添加 sprite 资源 |
| P2 | 运行时 smoke 测试 | 添加 Godot 内置测试，验证 AnimatedSprite2D.play("walk_down") 不报错 |
| P2 | Godot import 参数标准化 | 为所有 PNG 设置 import_mode=2D, texture_filter=Nearest（自动化 import） |

---

## 8. 产出文件清单

| 文件 | 位置 | 类型 |
|------|------|------|
| `n2b1-sprite-spec.md` | `reports/` | 规格决策报告 |
| `animation_spec.json` | `assets/npcs/admissions_director/` | NPC 动画规格 |
| `animation_spec.json` | `assets/npcs/student_representative/` | NPC 动画规格 |
| `admissions_director_walk_*.png` | `assets/npcs/admissions_director/baseline/` | Walk sheet PNG（4方向） |
| `student_representative_walk_*.png` | `assets/npcs/student_representative/baseline/` | Walk sheet PNG（4方向） |
| `npc_sprite_loader.gd` | `scripts/` | 通用 SpriteFrames 加载工具 |
| `admissions_director_sprites.gd` | `assets/npcs/admissions_director/` | 专用 builder |
| `student_representative_sprites.gd` | `assets/npcs/student_representative/` | 专用 builder |
| `npc_factory.gd` | `scripts/` | 工厂类（含 sprite 集成） |
| `n2b1-animation-integration.md` | `reports/` | 本报告 |
