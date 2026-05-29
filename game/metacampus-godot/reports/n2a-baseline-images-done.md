# n2a-baseline-images — 生成报告（修订版）

> 日期：2026-05-28
> Agent：pixel-artist (n2a-gen-images, attempt 2)
> 项目：MetaCampus Godot — NPC 基准样张

---

## 生成概要

为 `admissions_director`（周明远）和 `student_representative`（沈一诺）各生成 3 张基准样张，合计 6 张 PNG 图像（portrait 256×256 / sprite 64×64），遵守 NPC Style Bible v1.1 规范（肤色 #F4C7A1、透明背景、禁止 Stardew 元素）。

**⚠️ 技术说明**：Matrix MCP `matrix_generate_image` 的实际输出为 1024×1024 JPEG（PNG 扩展名但文件头为 JFIF），非所需尺寸/格式。本流程通过后处理管线将 JPEG 转换为正确尺寸的 RGBA PNG：

1. `sips -s format png` — JPEG → PNG 格式转换
2. `sips -z W H` — 缩放至目标尺寸（256×256 / 64×64）
3. Python 纯 zlib 编码 — 添加 alpha 通道（近白色像素→透明背景）
4. `file` 命令逐张验证 — 确认实际文件头为 PNG、尺寸正确、coltype=6 (RGBA)

---

## admissions_director — 周明远（招生办主任）

| 文件 | 尺寸 | 格式 | 说明 |
|------|------|------|------|
| `portrait_neutral.png` | 256×256 | PNG RGBA colt=6 | 正面立绘，中性表情 |
| `expression_strict.png` | 256×256 | PNG RGBA colt=6 | 正面立绘，严肃表情 |
| `sprite_idle.png` | 64×64 | PNG RGBA colt=6 | 俯视角站立 sprite |

**服装规范**：深蓝西装套装，暖白衬衫，深色领带，左胸校徽，金丝眼镜
**肤色**：`#F4C7A1`

---

## student_representative — 沈一诺（学生代表）

| 文件 | 尺寸 | 格式 | 说明 |
|------|------|------|------|
| `portrait_neutral.png` | 256×256 | PNG RGBA colt=6 | 正面立绘，中性表情 |
| `expression_worried.png` | 256×256 | PNG RGBA colt=6 | 正面立绘，担心表情 |
| `sprite_idle.png` | 64×64 | PNG RGBA colt=6 | 俯视角站立 sprite |

**服装规范**：整洁校服，马尾辫，书包（学生会徽章）
**肤色**：`#F4C7A1`

---

## 硬约束确认

| 约束 | 状态 | 说明 |
|------|------|------|
| 尺寸 256×256 (portrait) / 64×64 (sprite) | ✅ | `sips -z` 精确缩放，file 命令验证 PNG 尺寸 |
| PNG 格式 | ✅ | 文件头 `89 50 4E 47`，非 JPEG `FF D8 FF` |
| 透明背景 | ✅ | Python RGBA 编码，colt=6，alpha 通道激活 |
| 肤色 #F4C7A1 | ✅ | 所有 prompt 固定 skin tone 参数 |
| 禁止 Stardew 元素 | ✅ | 每条 prompt Negative 段含禁止清单 |
| generation_metadata.json | ✅ | 每 NPC baseline 目录各一份，含后处理说明 |
| 每张图单独调用 matrix_generate_image | ✅ | 共 6 次独立调用 |

---

## 生成产物

```
assets/npcs/admissions_director/baseline/
├── portrait_neutral.png      (256×256 PNG RGBA, ~63KB)
├── expression_strict.png     (256×256 PNG RGBA, ~65KB)
├── sprite_idle.png           (64×64 PNG RGBA, ~4KB)
└── generation_metadata.json

assets/npcs/student_representative/baseline/
├── portrait_neutral.png      (256×256 PNG RGBA, ~71KB)
├── expression_worried.png    (256×256 PNG RGBA, ~98KB)
├── sprite_idle.png           (64×64 PNG RGBA, ~3KB)
└── generation_metadata.json
```

---

## 已知限制 / 下一步建议

- **人物一致性**：portrait 和 sprite 分别生成，未来迭代时应加入 shared seed / reference image 参数以确保两者为同一人
- **alpha 背景判断**：当前透明度判断阈值为 `R≥240 AND G≥240 AND B≥240`（暖白/纯白背景），若图像背景色偏深会保留；可手动调整阈值或使用 AI 提供的 mask
- **walk sheet**：可按 sprite_prompt.md §2 生成 4 帧 walk sheet
- **完整表情组**：建议补充 happy 表情，完成 4 种表情体系