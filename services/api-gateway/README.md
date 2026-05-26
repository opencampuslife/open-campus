# API Gateway

零依赖 BFF/API Gateway 基线实现，覆盖方案文档要求的三条接口合同：

- `POST /api/gaokao/chat`
- `GET /api/gaokao/sessions`
- `POST /api/gaokao/handoff`

设计约束：

- 只信任认证会话中的身份，不信任前端提交的 `role`、`model`、`evidence`、`system_prompt`
- 会话与审计落本地文件，便于演示和回归测试
- 网关只编排，不直接接触 LLM provider
