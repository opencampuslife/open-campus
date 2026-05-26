---
title: Prompt 策略与模型使用规范
doc_id: prompt_policy_2026
visibility: admin
allowed_roles:
  - admin
  - campus_admin
data_level: L4
data_level_int: 4
campus_scope:
  - all
business_tags:
  - prompt
  - 模型配置
  - LLM安全
effective_date: 2026-01-01
expiry_date: 2026-12-31
owner: 技术开发部
review_status: approved
source_type: wiki
version: 1
---

# Prompt 策略与模型使用规范

## System Prompt 管理

1. System prompt 在 `llm-gateway/src/gateway.py` 中定义
2. 任何修改需经安全评审
3. system prompt 禁止包含具体价格、优惠信息或内部规则
4. 新 prompt 需通过 prompt injection 和 evidence contamination 测试

## 模型选择

当前生产模型：DeepSeek V4 Flash
模型切换需经过：
1. 合同测试通过
2. Prompt injection 测试通过
3. Benchmark 回归通过
4. 合规检查通过

## Evidence 注入规则

1. LLM 只能看到 RLS 过滤后的 evidence
2. evidence 中的 chunk_id、doc_id、source_uri 不暴露给最终用户
3. external 角色不可接收 internal/L3 及以上级别的 evidence

## 日志与审计

1. 所有 LLM 调用写入脱敏日志
2. API Key、手机号、学生信息自动脱敏
3. 日志保留周期：至少 90 天
