---
title: 情绪支持模式状态机
doc_id: psych_support_state_machine_v1
visibility: internal
allowed_roles:
  - sales
  - campus_admin
  - admin
data_level: L3
data_level_int: 3
campus_scope:
  - all
business_tags:
  - psych_support
  - state_machine
  - fsm
  - 情绪支持
effective_date: 2026-05-24
expiry_date: 2027-05-24
owner: 招生运营部
review_status: approved
source_type: authored
version: 1
---

# 情绪支持模式状态机

## 1. 状态定义

| 状态 | 说明 |
|---|---|
| EMOTION_DETECTED | 识别到用户存在明显情绪压力 |
| VALIDATING | 承认对方情绪有其现实基础 |
| NORMALIZING | 把情绪放回高考/复读压力情境中，减少羞耻和孤立感 |
| CLARIFYING | 只问低压力、关键问题，每轮最多 1-2 个 |
| REAPPRAISING | 帮助用户换一个解释框架 |
| PROBLEM_SOLVING | 进入可执行的小步骤 |
| MOTIVATION_SUPPORT | 支持学生恢复自主感和可控感 |
| BOUNDARY_SETTING | 帮助家长减少控制和冲突升级 |
| HANDOFF_RECOMMENDED | 适合转人工顾问温和接入 |
| CRISIS_ESCALATION | 疑似自伤、伤人、严重抑郁、极端绝望 |

## 2. 状态详细说明

### EMOTION_DETECTED
**典型输入：** 我快崩溃了 / 孩子完全不听 / 他一提学习就发火 / 我不知道还要不要让他复读

**系统动作：** 降低信息密度，不直接推班型，进入情绪承接

### VALIDATING
**话术方向：** 这确实会让人很着急 / 你现在不是单纯在问班型，而是在担心孩子还能不能重新进入状态

### NORMALIZING
**话术方向：** 复读前后的波动很常见，尤其是刚经历一次结果不理想后，学生和家长都会更敏感

### CLARIFYING
**优先问题：** 孩子最近主要是抗拒学习，还是抗拒和家长沟通？/ 这种状态持续多久了？

### REAPPRAISING
**示例：** 孩子现在的沉默不一定是不在乎，也可能是害怕再次失败，所以先把自己保护起来

### PROBLEM_SOLVING
**示例：** 今晚先不谈报名和分数，可以先问他：你最不想重来的是哪一部分？

### MOTIVATION_SUPPORT
**示例：** 先从一个能做到的小目标开始，比直接谈一年逆袭更容易启动

### BOUNDARY_SETTING
**示例：** 可以表达担心，但尽量避免把谈话变成追问、比较或否定

### HANDOFF_RECOMMENDED
**触发条件：** 家长明确希望有人帮忙沟通 / 涉及到校测评 / 涉及具体班型费用 / 持续高焦虑但无危机信号

### CRISIS_ESCALATION
**触发条件：** 自伤、自杀、严重抑郁、极端绝望表达

**系统动作：** 停止招生咨询，建议联系线下可信成年人、学校老师、当地紧急救助或专业心理医疗资源，同时触发人工介入

## 3. 状态转移

```
EMOTION_DETECTED → VALIDATING
VALIDATING → NORMALIZING
NORMALIZING → CLARIFYING
CLARIFYING → REAPPRAISING
REAPPRAISING → PROBLEM_SOLVING
PROBLEM_SOLVING → MOTIVATION_SUPPORT
MOTIVATION_SUPPORT → ADMISSIONS_CONSULTATION
BOUNDARY_SETTING → CLARIFYING
任意状态 → HANDOFF_RECOMMENDED
任意状态 → CRISIS_ESCALATION
```
