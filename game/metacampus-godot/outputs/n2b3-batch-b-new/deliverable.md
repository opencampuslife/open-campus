# N2B-3 Batch B 最终报告：家长代表 + 校长资产

**时间**：2026-05-29 01:54 (UTC+8)
**批次**：Batch B（parent_representative + principal）
**状态**：✅ 完成

---

## 产出

| NPC | 文件 | 数量 | 规格 |
|---|---|---|---|
| parent_representative（顾兰） | portrait×4 + sprite_idle + walk×4 | 9 PNG | portrait 256×256 / sprite 64×64 / walk 256×64，RGBA color_type=6 |
| principal（唐毓） | portrait×4 + sprite_idle + walk×4 | 9 PNG | 同上 |

---

## 独立验证结果

**验证方法**：Python struct 解析 PNG 头 + IHDR chunk，不依赖 PIL
**结果**：18/18 文件通过

| 文件 | 尺寸 | 色深 | 通道 |
|---|---|---|---|
| parent_representative portrait (neutral/happy/worried/strict) | 256×256 | 8bit | RGBA |
| parent_representative sprite_idle | 64×64 | 8bit | RGBA |
| parent_representative walk (down/left/right/up) | 256×64 | 8bit | RGBA |
| principal portrait (neutral/happy/worried/strict) | 256×256 | 8bit | RGBA |
| principal sprite_idle | 64×64 | 8bit | RGBA |
| principal walk (down/left/right/up) | 256×64 | 8bit | RGBA |

---

## Pipeline 说明

参考 Batch A 报告（`reports/n2b3-full-asset-batch.md`）。Batch B 同样使用：

1. **Matrix 生成 1:1 JPEG** → sips 转 PNG（portrait 缩至 256×256，sprite 缩至 64×64）
2. **walk sheet**：4 帧 1:1 JPEG → 64×64 PNG → Python stdlib 实现 PNG filter 解码（无 PIL）→ nearest-neighbor 缩放 → RGBA 透明化 → 水平拼接为 256×64 → 镜像 4 方向
3. **pipeline 修复**：sips resize 64×64 小图时出现 MA chunk + truncated rows，改用纯 stdlib PNG filter 解码解决

---

## JSON 元数据

- `animation_spec.json` ✅（已在 batch-b 任务启动前由 owner 预先写入）
- `generation_metadata.json` ✅（已在 batch-b 任务启动前由 owner 预先写入）

---

## 与 Batch A 对齐

- 目录结构：`assets/npcs/<npc_id>/baseline/`（同 Batch A）
- 命名规范：`{npc_id}_{type}_{variant}.png`（同 Batch A）
- 规格：portrait 256×256 RGBA、sprite 64×64 RGBA、walk 256×64 RGBA（与 Batch A 一致）
- 美术风格：warm campus，参考 `docs/npc-palette-guide-v1.md`（同 Batch A）