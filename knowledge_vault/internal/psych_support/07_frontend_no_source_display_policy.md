---
title: 前台隐去来源说明策略
doc_id: psych_support_source_policy_v1
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
  - frontend
  - citation
  - source_policy
effective_date: 2026-05-24
expiry_date: 2027-05-24
owner: 招生运营部
review_status: approved
source_type: authored
version: 1
---

# 前台隐去来源说明策略

## 1. 用户侧输出

用户侧不显示：

- 来源
- 引用
- citation
- evidence id
- doc id
- 根据资料
- 根据知识库

回答应自然表达：

- 可以先这样理解……
- 更稳妥的做法是……
- 这个情况建议先……

## 2. 后台保留

后台必须保留：

- retrieved_doc_ids
- evidence_ids
- retrieval_score
- mode_route_reason
- primary_mode
- secondary_mode
- consultation_stage
- recommendation_id
- compliance_result
- audit_event_id

## 3. API 响应建议

**对 parent / student / visitor：**
```json
{
  "answer": "...",
  "mode": "EMOTIONAL_SUPPORT",
  "handoff_suggested": false
}
```

**对 sales / admin：**
```json
{
  "answer": "...",
  "mode": "EMOTIONAL_SUPPORT",
  "evidence_ids": ["..."],
  "mode_route_reason": "...",
  "audit_event_id": "..."
}
```

## 4. 原则

- 前台自然
- 后台可审计
- 不牺牲 RLS
- 不牺牲 compliance
- 不把引用暴露给普通用户
