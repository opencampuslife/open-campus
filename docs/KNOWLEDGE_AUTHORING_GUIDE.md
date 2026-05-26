# 知识库编写规范

## 目录结构与可见性

知识库按文档可视等级分四个顶级目录，物理隔离：

```
knowledge_vault/
├── public/      # L1 — 公开内容，面向所有访客
├── protected/   # L2 — 保护内容，面向已认证学生/家长
├── internal/    # L3 — 内部内容，限招生顾问和校区管理员
└── admin/       # L4 — 管理员内容，限系统和管理员
```

文档必须放在匹配其 `visibility` 的目录下。`visibility: public` 的文档放入 `public/` 子目录，以此类推。

## Frontmatter 必填字段

每个 Markdown 文档必须包含以下 YAML frontmatter：

| 字段 | 类型 | 说明 |
|------|------|------|
| `title` | string | 文档标题 |
| `doc_id` | string | 全局唯一标识符，推荐格式：`{domain}_{topic}_{year}` |
| `visibility` | enum | `public` / `protected` / `internal` / `admin` |
| `allowed_roles` | list | 允许访问的角色列表 |
| `data_level` | enum | `L1` / `L2` / `L3` / `L4` |
| `data_level_int` | int | 数字级别 1-4，须与 `data_level` 一致 |
| `campus_scope` | list | 适用校区列表，`all` 表示全部校区 |
| `business_tags` | list | 业务标签，用于检索和过滤 |
| `effective_date` | date | 生效日期，格式 `YYYY-MM-DD` |
| `expiry_date` | date | 失效日期，格式 `YYYY-MM-DD` |
| `owner` | string | 负责部门或负责人 |
| `review_status` | enum | `draft` / `pending_review` / `approved` / `rejected` / `archived` |
| `source_type` | string | 来源类型，如 `wiki` / `official` / `transcript` |
| `version` | number | 版本号，每次实质性修改递增 |

## 内容编写规范

### 禁止表述（所有公开和保护文档）

以下表述禁止出现在 public 和 protected 文档的正文中：

- 保证提分、保证录取
- 一定上本科、一定能冲一本
- 内部名额、内部优惠
- 优惠底价、最低价、最低成交价
- 100%、包过、包录取、一定能

这些表述仅在以下情况可以出现：
1. 以 "不得"、"禁止"、"不应"、"不能" 开头的禁止性说明句中
2. internal/admin 级别的内部参考资料中

### 学生案例脱敏

涉及学生案例时，须隐去：
- 学生真实姓名
- 手机号等联系方式
- 具体高考成绩（可用分数段描述）
- 录取院校全称（可用院校类型替代）

### 费用表述（public 文档）

公开文档中的费用相关表述应遵循：
1. 说明费用构成和影响因素
2. 不透露具体优惠金额或折扣
3. 引导预约顾问进行一对一咨询
4. 以学校正式政策为准

### 引用来源

回答引用知识库内容时使用文档标题和来源类型。不暴露文件路径或内部标识符。

## 审核状态说明

| 状态 | 可被检索 | 说明 |
|------|---------|------|
| `draft` | 否 | 编写中，尚未提交审核 |
| `pending_review` | 是 | 已提交审核，可在测试环境检索 |
| `approved` | 是 | 审核通过，进入生产环境 |
| `rejected` | 否 | 审核未通过，需修改后重新提交 |
| `archived` | 否 | 已归档，不再有效 |

## 过期文档

超过 `expiry_date` 的文档自动从检索结果中排除。如需延长有效期，更新 `expiry_date` 并递增 `version`。
