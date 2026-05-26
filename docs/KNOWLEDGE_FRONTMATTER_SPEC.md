# Frontmatter 字段规范

## 必填字段

```yaml
---
title: "文档标题"
doc_id: "全局唯一标识符"
visibility: public | protected | internal | admin
allowed_roles: [visitor, student, parent, sales]
data_level: L1 | L2 | L3 | L4
data_level_int: 1 | 2 | 3 | 4
campus_scope: [all, zhengzhou, ...]
business_tags: [标签1, 标签2]
effective_date: "YYYY-MM-DD"
expiry_date: "YYYY-MM-DD"
owner: "负责部门"
review_status: draft | pending_review | approved | rejected | archived
source_type: "wiki" | "official" | "transcript" | ...
version: 1
---
```

## 字段详细说明

### title
文档的可读标题，会出现在检索结果和引用中。

### doc_id
全局唯一字符串标识符。推荐格式：`{domain}_{brief_topic}_{year}`。
示例：`course_fulltime_repeat_2026`、`faq_student_common_2026`

### visibility
- `public`：面向所有访客，无需登录即可查看
- `protected`：面向已认证的用户（学生、家长），需登录
- `internal`：面向招生顾问和校区管理员，不可对外发送
- `admin`：面向系统管理员，高度敏感

### allowed_roles
允许访问该文档的角色列表。有效值：
`visitor`、`student`、`parent`、`sales`、`teacher`、`operator`、`campus_admin`、`admin`

规则：
- public 文档：建议包含 `visitor`、`student`、`parent`、`sales`
- protected 文档：建议包含 `student`、`parent`，可选 `sales`
- internal 文档：至少包含 `sales`，可选 `campus_admin`、`admin`
- admin 文档：至少包含 `admin`

### data_level
- `L1`：公开信息
- `L2`：保护信息
- `L3`：内部信息
- `L4`：敏感/管理员信息

### data_level_int
数字级别，必须与 `data_level` 对应：
- `L1` → `1`
- `L2` → `2`
- `L3` → `3`
- `L4` → `4`

### campus_scope
适用校区列表。使用 `all` 表示全部校区适用。特定校区使用校区标识符如 `zhengzhou`。

### business_tags
业务标签列表，用于分类检索。每个标签用中文或英文短词。建议 2-5 个标签。

常用标签：
- 学校介绍、课程体系、班型、报名流程
- 费用政策、管理制度、住宿、FAQ
- 招生话术、内部定价、异议处理、跟进规则
- 权限管理、安全策略、Prompt配置

### effective_date / expiry_date
文档的生效和失效日期。过期的文档自动从检索结果排除。
日期格式：`YYYY-MM-DD`

### owner
负责该文档的部门或人员。用于追溯和审核沟通。

### review_status
- `draft`：编写中，不参与检索
- `pending_review`：待审核，可在测试环境检索
- `approved`：已通过审核，参与正式检索
- `rejected`：审核未通过，不参与检索
- `archived`：已归档，不参与检索

### source_type
文档来源类型标识：
- `wiki`：通过知识库管理维护
- `official`：官方政策文件
- `transcript`：会议记录转换
- 其他自定义类型

### version
文档版本号，从 1 开始。每次实质性内容修改递增 1。

## 校验规则

`make validate` 和 `make validate-knowledge` 自动执行以下检查：

1. 所有必填字段存在
2. `visibility` 为有效值
3. `data_level` 为有效值
4. `data_level_int` 与 `data_level` 对应
5. `allowed_roles`、`campus_scope`、`business_tags` 为列表类型
6. `allowed_roles` 中的角色均为有效角色
7. `version` 为数字类型
8. `review_status` 为有效状态
9. `effective_date` 不晚于 `expiry_date`
10. `visibility` 与文件所在目录一致
11. `doc_id` 全局唯一
12. 公开文档不含禁止性承诺表述
13. 公开文档不含内部话术泄漏
14. 禁止性表述仅出现在"不得/禁止"上下文或 internal/admin 文档中
