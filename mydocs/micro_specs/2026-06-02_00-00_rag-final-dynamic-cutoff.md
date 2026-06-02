# RAG final chunks 动态阈值 micro-spec

## Restate
用户只选择优化方案 1：动态阈值截断。当前 RAG 固定取 `final_top_k=5`，导致 top1 命中明确时，分数明显更低的后续片段仍进入 prompt，污染上下文。需要在 rerank 后增加最终筛选：保留 top1，其余片段必须超过相对 top1 的阈值和绝对最低分阈值。

## Scope
- 修改 `backend/services/rag_service.py`。
- 新增 final chunk selection 配置读取，默认启用动态阈值。
- 在 `search()` 中将 `ranked[:self.final_top_k]` 替换为 `_select_final_chunks(ranked)`。
- `_select_final_chunks()` 规则：保留 top1；其余 chunk 需满足 `score >= top1_score * relative_threshold` 且 `score >= min_score`；最多 `final_top_k` 条。
- 不实现 salience 二次过滤、topic 去重、query-term 覆盖约束或 LLM rerank。

## Done Contract
- top1 明确高分时，低分第 4/5 条不会再进入最终 prompt。
- 如果多个 chunk 分数接近，仍可返回多个上下文。
- 语法检查通过。
- 用当前部分 RAG DB 对几个 query 验证返回条数更保守。

## Change Log
- `backend/services/rag_service.py` 新增 `final_score_relative_threshold` 与 `final_score_min` 配置读取。
- `config.yaml` 新增：`final_score_relative_threshold: 0.75`、`final_score_min: 0.38`。
- `search()` 从固定 `ranked[:final_top_k]` 改为调用 `_select_final_chunks(ranked)`。
- 新增 `_select_final_chunks()`：始终保留 top1；其余 chunk 需同时满足相对 top1 阈值和绝对最低分阈值；最多返回 `final_top_k` 条。
- 未实现 salience 二次过滤、topic 去重、query-term 覆盖约束或 LLM rerank，保持本轮范围只做方案 1。

## Validation
- 已运行：`.venv/Scripts/python.exe -m py_compile backend/services/rag_service.py`，通过。
- 基于当前部分 RAG DB 验证：`她有没有考虑过去哈尔滨读书，为什么没去` 从多条噪声结果收敛为 `1` 条。
- 基于当前部分 RAG DB 验证：`朋友圈 小号 钓鱼` 返回 `1` 条。
- 基于当前部分 RAG DB 验证：`她是不是深圳本地人，老家哪里` 返回 `2` 条。
- `深圳一日游路线怎么安排` 仍返回 `5` 条，因为第 2-5 条分数仍超过当前动态阈值；如需更激进，需要调高 `final_score_relative_threshold` 或 `final_score_min`，但这不属于本轮额外策略。

## Resume or Handoff
当前核心目标已完成：最终 prompt 不再固定塞满 5 条，而是按动态分数阈值截断。下一步如仍觉得后续片段噪声多，可以只调配置阈值，或再实现 query-term 覆盖/topic 去重等额外策略。
