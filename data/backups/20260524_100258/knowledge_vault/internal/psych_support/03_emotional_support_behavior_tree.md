---
title: 情绪支持模式行为树
doc_id: psych_support_behavior_tree_v1
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
  - behavior_tree
  - bt
  - 情绪支持
effective_date: 2026-05-24
expiry_date: 2027-05-24
owner: 招生运营部
review_status: approved
source_type: authored
version: 1
---

# 情绪支持模式行为树

## 1. BT 结构

```
EmotionalSupportBT
├── DetectCrisisRisk
│   ├── IfCrisis → CrisisEscalationAnswer
│   └── IfNoCrisis → Continue
├── DetectEmotionSignal
├── ClassifyEmotionTheme
├── ValidateEmotion
├── NormalizeExperience
├── ChooseSupportStrategy
│   ├── ParentAnxietySupport
│   ├── StudentPressureSupport
│   ├── ParentChildConflictSupport
│   ├── RepeatFailureReframe
│   ├── MotivationSupport
│   └── BoundarySettingSupport
├── AskLowPressureQuestion
├── OptionalAdmissionsBridge
├── CheckCompliance
├── FinalizeAnswer
└── WriteAudit
```

## 2. 情绪主题分类 (Emotion Theme)

| 主题 | 说明 |
|---|---|
| parent_anxiety | 家长焦虑 |
| student_pressure | 学生压力 |
| parent_child_conflict | 亲子冲突 |
| repeat_failure_fear | 复读失败恐惧 |
| learned_helplessness | 习得性无助 |
| low_self_efficacy | 低自我效能感 |
| avoidance | 逃避行为 |
| shame | 羞耻感 |
| anger | 愤怒 |
| decision_ambivalence | 决策矛盾 |

## 3. 支持策略 (Support Strategy)

### 3.1 ParentAnxietySupport
**目标：** 降低家长焦虑，避免把焦虑转化为控制
**策略：** 承认担心 → 区分"关心"和"施压" → 建议降低对话强度 → 给出一个低冲突沟通动作

### 3.2 StudentPressureSupport
**目标：** 承接学生压力，恢复可控感
**策略：** 承认累和怕 → 减少宏大目标 → 聚焦小步骤 → 强调可调整而非一次定终身

### 3.3 ParentChildConflictSupport
**目标：** 减少亲子互动中的防御和对抗
**策略：** 避免追问式沟通 → 避免比较 → 先问感受再谈计划 → 把"你必须"换成"我们先看看哪一步最难"

### 3.4 RepeatFailureReframe
**目标：** 把复读失败恐惧从人格否定转为策略问题
**策略：** 区分结果和能力 → 区分努力和方法 → 强调需要复盘而非简单重复一年

### 3.5 MotivationSupport
**目标：** 恢复学生的自我效能感
**策略：** 从可完成任务开始 → 记录小进展 → 避免空泛打鸡血

### 3.6 BoundarySettingSupport
**目标：** 帮助家长建立支持性边界
**策略：** 表达关心 → 减少控制 → 约定沟通时间 → 允许孩子保留选择感

## 4. OptionalAdmissionsBridge

只有在情绪已被承接后才进入轻量招生桥接。

**话术示例：** 如果你愿意，我们可以先不急着定班型，先看孩子现在最卡的是状态、科目，还是管理方式。

**禁止：**
- 情绪未承接时直接推班
- 高焦虑时直接报价
- 亲子冲突时直接要求报名
