# NPC Prompt 生成完成报告

> 生成时间：2026-05-28
> 生成者：pixel-artist agent
> 状态：全面重新生成（基于 npc_*.json visual_keywords 和 npc-style-bible.md v1.1）

---

## 概述

为 MetaCampus 全部 8 个 NPC 生成了三类 prompt 文件（共 24 个），严格从 npc_*.json 的 visual_keywords 字段提取外观描述，所有变量使用模板中的 `{{VAR}}` 格式，风格约束强制禁止 Stardew Valley / 农场 / 田园。

---

## NPC 列表

| NPC ID | 显示名 | 角色 |
|--------|--------|------|
| `admissions_director` | 周明远 | 招生办主任 |
| `compliance_officer` | 林澈 | 合规专员 |
| `it_operator` | 许航 | IT运维 |
| `homeroom_teacher` | 陈芷 | 班主任 |
| `logistics_manager` | 赵启山 | 后勤主管 |
| `parent_representative` | 顾兰 | 家长代表 |
| `student_representative` | 沈一诺 | 学生代表 |
| `principal` | 唐毓 | 校长 |

---

## 数据来源对应关系

| NPC | visual_keywords（来源） | CLOTHING | HAIR_STYLE | ACCESSORY |
|----|------------------------|----------|------------|-----------|
| 周明远 | 深蓝色西装，金丝眼镜，招生简章堆满桌面，保温杯旁的红色印章 | 深蓝西装套装，暖白衬衫，深色领带，左胸佩戴校徽 | 黑色短发 | 金丝眼镜 |
| 林澈 | 白色衬衫，黑框眼镜，手边放着《招生合规手册》，显示屏上实时监控AI对话记录 | 白色衬衫，灰色职业套装 | 黑色短发 | 黑框眼镜 |
| 许航 | 灰色连帽衫，双显示器满屏终端命令，机架上闪烁的LED灯，键盘旁的能量饮料罐 | 灰色连帽衫，深色休闲裤 | 黑色短发 | 黑框眼镜 |
| 陈芷 | 浅绿色连衣裙，低马尾辫，办公桌上放着学生合照，手写批注堆在教案旁 | 浅绿色连衣裙 | 低马尾辫 | none |
| 赵启山 | 深灰工作服，黄色安全帽挂墙，腰间一大串钥匙，办公桌上的对讲机和对账单 | 深灰工作服 | 短发平头 | 腰间对讲机 |
| 顾兰 | 碎花连衣裙，帆布袋里装着家长联名信，手机屏幕常亮家长群，保温杯和文件夹从不离手 | 碎花连衣裙 | 棕色中长发 | 帆布袋 |
| 沈一诺 | 整洁校服，白色运动鞋，书包上别着学生会徽章，随身携带的意见收集本 | 整洁校服 | 马尾辫 | 书包（学生会徽章） |
| 唐毓 | 藏青色套装，珍珠耳环，办公桌上整齐的文件，大显示器显示运营驾驶舱，窗边绿植打理得很用心 | 藏青色套装 | 挽起发髻 | 珍珠耳环 |

---

## 生成文件清单

```
prompts/npcs/
├── admissions_director/    portrait_prompt.md / sprite_prompt.md / video_prompt.md
├── compliance_officer/     portrait_prompt.md / sprite_prompt.md / video_prompt.md
├── it_operator/            portrait_prompt.md / sprite_prompt.md / video_prompt.md
├── homeroom_teacher/       portrait_prompt.md / sprite_prompt.md / video_prompt.md
├── logistics_manager/      portrait_prompt.md / sprite_prompt.md / video_prompt.md
├── parent_representative/ portrait_prompt.md / sprite_prompt.md / video_prompt.md
├── student_representative/ portrait_prompt.md / sprite_prompt.md / video_prompt.md
└── principal/             portrait_prompt.md / sprite_prompt.md / video_prompt.md
```

---

## 风格约束遵守情况

| 约束项 | 状态 |
|--------|------|
| 禁止 Stardew Valley / 农场 / 田园 | ✅ 所有 prompt Negative 段均包含 |
| 现代校园 / 教育科技风格 | ✅ 使用 `modern campus`, `contemporary Chinese international school` |
| 柔和暖色调色板 | ✅ 所有颜色取自色板，肤色统一 #F4C7A1 |
| 64px / 1:4 头身比 | ✅ sprite prompt 中标注 `head 16px (1/4 height)` |
| 每 sprite ≤ 5 色 | ✅ Technical 段标注 |
| Negative Prompt 追加 | ✅ 每 prompt 末尾均追加 |
| `{{EXPRESSION}}` 已填充表情名称 | ✅ expression transition prompt 已填入具体表情 |

---

## 变量填充规范

- `{{HAIR_STYLE}}`：仅含发型，不含配饰
- `{{ACCESSORY}}`：仅含配件（如眼镜、工牌等），不含面部特征
- `{{CLOTHING}}`：严格来自 npc-style-bible.md 11.5 节服装规范
- `visual_keywords`：仅用于 video prompt 的 Action/Environment 描述段落，不可填入 [Appearance] 段

---

## 版本

- 模板：npc_image_prompt_template.md v1.0, npc_video_prompt_template.md v1.0
- 风格规范：npc-style-bible.md v1.1
- 生成 prompt 版本：v1.0