# NPC Persona Prompts — 完成标记

> 版本: v1 | 日期: 2026-05-28 | 作者: Narrative Designer

## 任务概述

为 MetaCampus Godot 项目的 8 个 MVP NPC 创建了完整的 Persona Prompt 文件，每个文件包含：身份与背景、性格关键词、对话风格、核心冲突、禁止行为、游戏功能、指标影响、典型对话示例（含正确/错误分支）、LLM System Prompt 片段。

## 完成清单

| # | NPC ID | 文件名 | 状态 |
|---|--------|--------|------|
| 1 | `admissions_director` | `data/personas/admissions_director.md` | ✅ |
| 2 | `compliance_officer` | `data/personas/compliance_officer.md` | ✅ |
| 3 | `homeroom_teacher` | `data/personas/homeroom_teacher.md` | ✅ |
| 4 | `it_operator` | `data/personas/it_operator.md` | ✅ |
| 5 | `logistics_manager` | `data/personas/logistics_manager.md` | ✅ |
| 6 | `parent_representative` | `data/personas/parent_representative.md` | ✅ |
| 7 | `principal` | `data/personas/principal.md` | ✅ |
| 8 | `student_representative` | `data/personas/student_representative.md` | ✅ |

## 质量自检

| 检查项 | 结果 |
|--------|------|
| 每个 persona 与对应 NPC profile JSON 一致 | ✅ |
| 身份与背景 | ✅ 8/8 |
| 性格关键词 ≥2 | ✅ 8/8 |
| 对话风格类型明确 | ✅ 8/8 |
| 核心冲突（想要X但不能Y） | ✅ 8/8 |
| 禁止行为 ≥3 | ✅ 8/8 |
| "不得承诺录取结果" | ✅ 8/8（根据 NPC 角色做了差异化上下文处理） |
| 游戏功能 | ✅ 8/8 |
| 指标影响（正面/负面） | ✅ 8/8 |
| 典型对话示例 ≥2 | ✅ 8/8（正确/错误分支均覆盖） |
| LLM System Prompt 片段 | ✅ 8/8 |
| 任务覆盖 T1–T8 | ✅ 全部绑定 |

## 注意事项

1. **"不得承诺录取结果"的处理**: 对于招生相关 NPC（周明远、林澈），直接关联其核心职责；对于非招生 NPC（许航、赵启山、沈一诺等），嵌入为"若被询问则引导至招生办"的辅助约束，避免生硬套用。
2. **LLM System Prompt**: 每个片段均设计为可直接用于 ApiClient 调用的独立 prompt，包含角色背景、对话规则、指标约束三部分。
3. **与上游一致性**: 所有 persona 文件基于 `data/npcs/npc_*.json` 和 `reports/npc-roster-v1.md` 的角色定义，确保延续性。

---

*NPC Persona Prompts v1 — Complete*
