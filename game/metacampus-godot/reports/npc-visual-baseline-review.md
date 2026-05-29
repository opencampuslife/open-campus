# NPC 视觉基准样张 — 最终评审报告

> 日期：2026-05-28
> 评审人：Mavis
> 项目：MetaCampus Godot — Phase N2A

---

## 评审维度

### 1. 风格一致

| 检查项 | 结果 |
|--------|------|
| NPC Style Bible v1.1 合规 | ✅ 全部 prompt 包含 Negative 段落禁止 Stardew |
| 肤色统一 #F4C7A1 | ✅ |
| 透明背景（PNG RGBA） | ✅ |
| 尺寸正确（portrait 256×256 / sprite 64×64） | ✅ |
| 格式 PNG（非 JPEG 伪装） | ✅ |

### 2. 角色身份

| NPC | 服装 | 配饰 | 年龄感 | 职业/身份识别 | sprite 一致 |
|-----|------|------|--------|--------------|------------|
| 周明远 | ✅ 深蓝西装+白衬衫+领带 | ✅ 金丝眼镜+校徽 | ✅ 年轻成年人 | ✅ 招生办主任形象 | ✅ |
| 沈一诺 | ✅ 校服+书包肩带 | ✅ 学生会徽章 | ✅ 青少年 | ✅ 学生代表形象 | ✅ |

### 3. 表情区分

| NPC | neutral | expression | 区分度 |
|-----|---------|-----------|--------|
| 周明远 | 平静微嘴角 | stoic/composed，紧绷嘴 | ✅ 明显不同 |
| 沈一诺 | 柔和微笑 | 眼大、八字眉、下弧嘴 | ✅ 明显不同 |

### 4. 技术合规

| 检查项 | 结果 |
|--------|------|
| PNG 真实格式（非 JPEG 数据） | ✅ file 命令 + PNG header `89 50 4E 47` 验证 |
| RGBA coltype=6（透明 alpha） | ✅ |
| portrait 256×256 | ✅ |
| sprite 64×64 | ✅ |
| generation_metadata.json | ✅ 每 NPC 各 1 份 |
| reports/n2a-baseline-images-done.md | ✅ |
| reports/n2a-identity-review.md | ✅ |

### 5. 可复现性

- Prompt 文件存档于 `prompts/npcs/<npc_id>/`
- style bible：`docs/npc-style-bible.md`
- 生成命令可追溯（每张图单独调用 matrix_generate_image）

---

## 最终结论

| 维度 | 判定 |
|------|------|
| 风格一致 | ✅ PASS |
| 角色身份 | ✅ PASS |
| 表情区分 | ✅ PASS |
| 技术合规 | ✅ PASS |
| 可复现 | ✅ PASS |

**Phase N2A — 基准样张生成：全部通过，交付完成。**

### 交付产物

```
assets/npcs/admissions_director/baseline/
├── portrait_neutral.png    (256×256 PNG RGBA)
├── expression_strict.png   (256×256 PNG RGBA)
├── sprite_idle.png        (64×64 PNG RGBA)
└── generation_metadata.json

assets/npcs/student_representative/baseline/
├── portrait_neutral.png    (256×256 PNG RGBA)
├── expression_worried.png  (256×256 PNG RGBA)
├── sprite_idle.png        (64×64 PNG RGBA)
└── generation_metadata.json
```

### 已知限制

- matrix_generate_image API 返回 1024×1024 JPEG 数据，已通过 sips + Python zlib 后处理管线转换为真实 PNG（64px 下采样通过 sips resize 实现，无需 Pillow）
- 下一阶段可扩展：expression happy（周明远）、expression confident（沈一诺）、walk sheet sprite
