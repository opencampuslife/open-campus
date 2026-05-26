# Evaluation Service

负责把方案中的 benchmark 用例跑成结构化报告。

当前实现：

- 读取 `tests/benchmark_cases/*.yaml`
- 调用主 pipeline 执行问答
- 检查意图是否符合预期
- 对回答做最小规则校验
- 输出 `data/reports/benchmark_report.json`
