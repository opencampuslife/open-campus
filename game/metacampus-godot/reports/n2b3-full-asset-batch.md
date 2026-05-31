# N2B-3 Batch A 最终报告

> 日期：2026-05-28 | 前置：n2b3-batch-a-new + n2b3-batch-a-existing 均完成

---

## 1. 执行摘要

Batch A 计划 8 NPC × 11 文件 = 88 个资产。实际盘点范围为 6 个已创建目录的 NPC（admissions_director / student_representative / compliance_officer / it_operator / homeroom_teacher / logistics_manager）。

| 状态 | 计数 |
|------|------|
| ✅ 完成 | 37 PNG + 6 animation_spec.json + 6 generation_metadata.json = **49 文件** |
| ⏳ 阻塞（Matrix 配额耗尽） | portrait_worried × 1 + walk sheet × 16 = **17 文件** |
| ❌ 未创建目录 | teacher_guide / parent_rep = **2 NPC 待确认** |

---

## 2. 完整资产清单（6 NPC × 11 文件）

### 2.1 admissions_director（周明远）— 9/9 ✅

| 文件 | 尺寸 | RGBA |
|------|------|------|
| `baseline/portrait_neutral.png` | 256×256 | ✅ |
| `baseline/portrait_happy.png` | 256×256 | ✅ |
| `baseline/portrait_worried.png` | 256×256 | ✅ |
| `baseline/portrait_strict.png` | 256×256 | ✅ |
| `baseline/sprite_idle.png` | 64×64 | ✅ |
| `baseline/admissions_director_walk_down.png` | 256×64 | ✅ |
| `baseline/admissions_director_walk_up.png` | 256×64 | ✅ |
| `baseline/admissions_director_walk_left.png` | 256×64 | ✅ |
| `baseline/admissions_director_walk_right.png` | 256×64 | ✅ |
| `animation_spec.json` | NPC root | ✅ |
| `generation_metadata.json` | NPC root | ✅ |

### 2.2 student_representative（沈一诺）— 8/9 ⚠️

| 文件 | 尺寸 | RGBA |
|------|------|------|
| `baseline/portrait_neutral.png` | 256×256 | ✅ |
| `baseline/portrait_happy.png` | 256×256 | ✅ |
| `baseline/portrait_worried.png` | — | ❌ **缺失**（配额） |
| `baseline/portrait_strict.png` | 256×256 | ✅ |
| `baseline/sprite_idle.png` | 64×64 | ✅ |
| `baseline/student_representative_walk_down.png` | 256×64 | ✅ |
| `baseline/student_representative_walk_up.png` | 256×64 | ✅ |
| `baseline/student_representative_walk_left.png` | 256×64 | ✅ |
| `baseline/student_representative_walk_right.png` | 256×64 | ✅ |
| `animation_spec.json` | NPC root | ✅ |
| `generation_metadata.json` | NPC root | ✅ |

### 2.3 compliance_officer（林澈）— 5/11 ⚠️

| 文件 | 尺寸 | RGBA |
|------|------|------|
| `portrait_neutral.png` | 256×256 | ✅ |
| `portrait_happy.png` | 256×256 | ✅ |
| `portrait_worried.png` | 256×256 | ✅ |
| `portrait_strict.png` | 256×256 | ✅ |
| `sprite_idle.png` | 64×64 | ✅ |
| `walk_down.png` | — | ⏳ pending |
| `walk_up.png` | — | ⏳ pending |
| `walk_left.png` | — | ⏳ pending |
| `walk_right.png` | — | ⏳ pending |
| `animation_spec.json` | NPC root | ✅ |
| `generation_metadata.json` | NPC root | ✅ |

### 2.4 it_operator（许航）— 5/11 ⚠️

| 文件 | 尺寸 | RGBA |
|------|------|------|
| `portrait_neutral.png` | 256×256 | ✅ |
| `portrait_happy.png` | 256×256 | ✅ |
| `portrait_worried.png` | 256×256 | ✅ |
| `portrait_strict.png` | 256×256 | ✅ |
| `sprite_idle.png` | 64×64 | ✅ |
| `walk_down.png` | — | ⏳ pending |
| `walk_up.png` | — | ⏳ pending |
| `walk_left.png` | — | ⏳ pending |
| `walk_right.png` | — | ⏳ pending |
| `animation_spec.json` | NPC root | ✅ |
| `generation_metadata.json` | NPC root | ✅ |

### 2.5 homeroom_teacher（陈芷）— 5/11 ⚠️

| 文件 | 尺寸 | RGBA |
|------|------|------|
| `portrait_neutral.png` | 256×256 | ✅ |
| `portrait_happy.png` | 256×256 | ✅ |
| `portrait_worried.png` | 256×256 | ✅ |
| `portrait_strict.png` | 256×256 | ✅ |
| `sprite_idle.png` | 64×64 | ✅ |
| `walk_down.png` | — | ⏳ pending |
| `walk_up.png` | — | ⏳ pending |
| `walk_left.png` | — | ⏳ pending |
| `walk_right.png` | — | ⏳ pending |
| `animation_spec.json` | NPC root | ✅ |
| `generation_metadata.json` | NPC root | ✅ |

### 2.6 logistics_manager（赵启山）— 5/11 ⚠️

| 文件 | 尺寸 | RGBA |
|------|------|------|
| `portrait_neutral.png` | 256×256 | ✅ |
| `portrait_happy.png` | 256×256 | ✅ |
| `portrait_worried.png` | 256×256 | ✅ |
| `portrait_strict.png` | 256×256 | ✅ |
| `sprite_idle.png` | 64×64 | ✅ |
| `walk_down.png` | — | ⏳ pending |
| `walk_up.png` | — | ⏳ pending |
| `walk_left.png` | — | ⏳ pending |
| `walk_right.png` | — | ⏳ pending |
| `animation_spec.json` | NPC root | ✅ |
| `generation_metadata.json` | NPC root | ✅ |

---

## 3. PNG 验证汇总

### 验证方法
Python struct 解析 PNG IHDR chunk：签名 `\x89PNG\r\n\x1a\n` → IHDR → width/height/color_type → IDAT 存在性。

### 结果（37/37 全部通过）

| NPC | portrait×4 | sprite_idle | walk×4 | 合计 |
|-----|-----------|------------|--------|------|
| admissions_director | 4×256×256 RGBA | 1×64×64 RGBA | 4×256×64 RGBA | **9** |
| student_representative | 3×256×256 RGBA | 1×64×64 RGBA | 4×256×64 RGBA | **8** |
| compliance_officer | 4×256×256 RGBA | 1×64×64 RGBA | — | **5** |
| it_operator | 4×256×256 RGBA | 1×64×64 RGBA | — | **5** |
| homeroom_teacher | 4×256×256 RGBA | 1×64×64 RGBA | — | **5** |
| logistics_manager | 4×256×256 RGBA | 1×64×64 RGBA | — | **5** |
| **总计** | **23** | **6** | **8** | **37 ✅** |

---

## 4. 风格合规检查

### Palette Guide 合规（docs/npc-palette-guide-v1.md）

| NPC | 主色 | 服装色 | 肤色 |
|-----|------|--------|------|
| admissions_director | #2D4A6B（深蓝西装） | #F5E6D3（衬衫） | #F4C7A1 |
| student_representative | #F5E6D3（校服） | #2D4A6B（外套） | #F4C7A1 |
| compliance_officer | #6B7280（灰套装） | #F5E6D3（衬衫） | #F4C7A1 |
| it_operator | #374151（深灰polo） | #6B7280（休闲裤） | #F4C7A1 |
| homeroom_teacher | #60A5FA（浅蓝衬衫） | #1E3A5F（深色西裤） | #F4C7A1 |
| logistics_manager | #C4A77D（卡其工装） | #5C4033（深棕工装裤） | #F4C7A1 |

### Stardew Valley 漂移防护

所有 `generation_metadata.json` 包含：
```json
"constraints_verified": {
  "stardew_forbidden": true,
  "transparent_background": true,
  "skin_tone": "#F4C7A1",
  "style": "modern pixel art, NOT 8-bit retro"
}
```

---

## 5. Godot Loader 兼容性

### 路径可解析性

| 检查项 | 结果 |
|--------|------|
| animation_spec.json 在 NPC root 层级 | ✅ 全部 6 NPC |
| generation_metadata.json 在 NPC root 层级 | ✅ 全部 6 NPC |
| JSON 无 regression（从 baseline/ 移至 root） | ✅ admissions_director / student_representative 已修正 |
| sprite_idle 路径（npc_sprite_loader.gd 默认 `baseline/sprite_idle.png`） | ⚠️ 新建 4 NPC 在 NPC root |

### ⚠️ 路径兼容性问题

`npc_sprite_loader.gd` 的 `build_from_spec()` 默认查找 `npc_dir + "/baseline/sprite_idle.png"`。新建 4 NPC 的 sprite_idle 在 NPC root，调用 `build_from_spec()` 会找不到。

**修复方案**：统一将 4 个新建 NPC 的 `sprite_idle.png` 移入 `baseline/` 子目录。

### animation_spec.json portraits 字段

`admissions_director/animation_spec.json` 缺少 `portraits` 字段（仅有 `source_sprites`），其余 5 NPC 均正确引用 `portrait_*.png`。

---

## 6. 已知限制

| 限制 | 影响 | 处理 |
|------|------|------|
| `student_representative portrait_worried.png` 缺失 | 关键表情帧缺失 | cron 重试 |
| 16 张 walk sheet pending | 4 NPC 无法移动 | cron 重试 |
| Matrix 配额耗尽（code 402） | 全部阻塞项根源 | 配额恢复后重试 |
| teacher_guide / parent_rep 目录不存在 | 2 NPC 完全缺失 | 确认 Batch B 范围 |
| 新建 NPC sprite 路径不兼容 loader | idle 动画无法播放 | Batch B 修复（移入 baseline/） |

---

## 7. Batch B 启动条件

### 通过条件

1. `student_representative/portrait_worried.png` 生成并验证（256×256 RGBA）
2. 16 张 walk sheet 生成并验证（256×64 RGBA）
3. teacher_guide / parent_rep 目录状态确认
4. 新建 NPC sprite 路径修复（sprite_idle.png 移入 `baseline/` 子目录）

### Batch B 资产清单（预期）

| NPC | 需生成 | 数量 |
|-----|--------|------|
| student_representative | portrait_worried | 1 |
| compliance_officer | walk×4 | 4 |
| it_operator | walk×4 | 4 |
| homeroom_teacher | walk×4 | 4 |
| logistics_manager | walk×4 | 4 |
| teacher_guide | portrait×4 + sprite_idle + walk×4 + JSON×2 | 11 |
| parent_rep | portrait×4 + sprite_idle + walk×4 + JSON×2 | 11 |
| **合计** | | **39** |

### 路径修复操作（Batch B 前置）

```bash
# 将 4 个新建 NPC 的 sprite_idle.png 移入 baseline/ 子目录
for npc in compliance_officer it_operator homeroom_teacher logistics_manager; do
  mkdir -p "assets/npcs/$npc/baseline"
  mv "assets/npcs/$npc/sprite_idle.png" "assets/npcs/$npc/baseline/"
done
# 更新 animation_spec.json source_sprites 路径为 baseline/sprite_idle.png
```

---

*报告生成：general agent — N2B-3 Batch A final report，2026-05-28*