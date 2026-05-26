# 知识库审核发布流程

## 流程总览

```
编写 (draft)
  → 提交审核 (pending_review)
  → 审核通过 (approved)
  → 发布到生产索引
  → 更新 (新版本 draft)
  → 归档 (archived)
```

## 1. 编写阶段

1. 在对应 visibility 目录下创建或修改 Markdown 文件
2. 填写完整 frontmatter，`review_status` 设为 `draft`
3. 运行 `make validate` 检查 frontmatter 完整性
4. 运行 `make validate-knowledge` 检查内容合规性

## 2. 提交审核

1. 将 `review_status` 改为 `pending_review`
2. 递增 `version` 号
3. 提交变更，附审核说明（变更原因、影响范围）
4. 审核人对变更内容进行审阅

## 3. 审核要点

审核人需确认：
- [ ] frontmatter 字段完整且正确
- [ ] `doc_id` 全局唯一
- [ ] `visibility` 与文件所在目录匹配
- [ ] `data_level` 与 `data_level_int` 一致
- [ ] `allowed_roles` 和 `campus_scope` 范围合理
- [ ] `effective_date` 和 `expiry_date` 在合理范围内
- [ ] 公开文档不含禁止性承诺表述
- [ ] 公开文档不泄露内部话术或定价
- [ ] internal 文档包含"不可原样对外发送"提示
- [ ] admin 文档确实需要管理员权限
- [ ] 学生案例已充分脱敏
- [ ] 未脱敏的手机号、姓名已移除

## 4. 发布

1. 审核通过后，将 `review_status` 改为 `approved`
2. 运行 `make index` 重建知识索引
3. 运行 `make validate-knowledge` 最终确认
4. 部署到生产环境

## 5. 下线

需要下线的文档：
1. 将 `review_status` 改为 `archived`
2. 重新运行 `make index`
3. 归档后的文档不再出现在检索结果中

过期的文档（当前日期 > `expiry_date`）自动被检索排除，无需手动下线。

## 6. 版本管理

- `version` 从 1 开始
- 每次实质性内容修改递增 1
- 仅修正拼写或格式不升级版本
- 修改 `effective_date` 或 `expiry_date` 不升级版本

## 验证命令

```bash
make validate           # 检查 frontmatter 完整性
make validate-knowledge  # 检查 frontmatter + 内容合规
make index              # 重建知识索引
make test               # 运行全部测试（含安全回归）
make release-check      # 发布前完整门禁
```
