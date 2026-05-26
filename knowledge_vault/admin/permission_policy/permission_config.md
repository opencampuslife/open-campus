---
title: 权限策略配置说明
doc_id: permission_policy_2026
visibility: admin
allowed_roles:
  - admin
  - campus_admin
data_level: L4
data_level_int: 4
campus_scope:
  - all
business_tags:
  - 权限管理
  - 系统配置
  - 安全策略
effective_date: 2026-01-01
expiry_date: 2026-12-31
owner: 技术开发部
review_status: approved
source_type: wiki
version: 1
---

# 权限策略配置说明

## 角色定义

系统预定义角色：visitor, student, parent, sales, teacher, operator, campus_admin, admin

角色权限由 `configs/roles.yaml` 定义，不得在代码中修改角色与权限的对应关系。

## RLS 策略

PostgreSQL RLS 策略由数据库迁移脚本管理。所有知识表需启用 RLS，按 `app.role` 变量强制执行权限隔离。

公共表可使用 security definer 函数暴露过滤后的视图，但 base table 上必须有 RLS 强制。

## 权限变更流程

1. 权限变更须在 `configs/roles.yaml` 中修改
2. 修改后需通过 `make test-permission` 验证
3. 新角色默认最小权限：仅 `visitor` 级别
4. 升权需评审并在 release note 中说明

## 审计要求

- 所有角色变更写入审计日志
- 管理员操作需要双因素认证
- 权限异常访问自动告警
