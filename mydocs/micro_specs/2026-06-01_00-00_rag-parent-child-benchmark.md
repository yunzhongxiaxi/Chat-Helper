# RAG 父子索引提升 benchmark micro-spec

## Restate
需要量化父子索引 RAG 优化带来的提升：对比 chunk-only 检索与 parent-child topic 扩展检索，证明 query 命中父 topic 后能额外召回同话题 sibling chunks，从而提高上下文完整性。

## Scope
- 新增一个不联网 benchmark 脚本，避免真实 embedding 成本和不稳定性。
- 构造可控测试数据：一个话题被拆成多个 chunks，其中部分 chunk 不直接包含 query 关键词，但属于同一父 topic。
- 对比两种模式：
  - chunk-only：只使用 chunk 级 BM25/vector 候选。
  - parent-child：chunk 级候选 + topic 命中后扩展 sibling chunks。
- 统计指标：候选 chunk 数、命中同父 topic 的 chunk 数、相关上下文覆盖率、额外召回 sibling chunk 数。
- 本轮不跑真实聊天全量 RAG，不调用真实 embedding API。

## Done Contract
- benchmark 能直接运行。
- 输出 chunk-only 与 parent-child 的指标对比。
- 能给出可用于简历描述的提升数据。
- 通过语法检查与运行验证。

## Change Log
- 新增 `scripts/benchmark_rag_parent_child.py`。
- benchmark 使用 stub embedding，不调用真实 embedding API。
- 构造 1 个父 topic、3 个子 chunks 的可控数据集。
- 对比 chunk-only 与 parent-child 对同一父 topic 下相关 chunks 的覆盖率。

## Validation
- 已运行：`python -m py_compile scripts/benchmark_rag_parent_child.py`，通过。
- 已运行：`PYTHONIOENCODING=utf-8 uv run python scripts/benchmark_rag_parent_child.py`，通过。
- benchmark 结果：总子 chunks `3`，chunk-only 候选 `2`，parent-child 候选 `3`。
- chunk-only 相关覆盖率：`66.67%`。
- parent-child 相关覆盖率：`100.00%`。
- 额外召回 sibling chunks：`1`。
- 覆盖率提升：`33.33` 个百分点。

## Resume or Handoff
当前 benchmark 已产出可用于简历的初步量化指标。由于这是可控小样本，不应表述为全量线上收益；更稳妥写法是“在构造的长话题拆分场景中，将同 topic 相关 chunk 覆盖率从 66.7% 提升到 100%”。
