# RAG 父子索引召回优化 micro-spec

## Restate
当前 RAG 主要直接检索 chunk。用户希望引入 topic-chunk 父子索引思想：如果 query 隶属于某个历史 topic，召回该父 topic 下的子 chunks 更合理，可以提高长聊天记录场景下的上下文召回完整性。

## Scope
- 修改 `backend/services/rag_service.py`。
- `rag_topics` 增加 topic 级可检索信息：terms 与 embedding。
- 插入记录时，为 topic 摘要生成 terms 与 embedding，并写入 topic 表。
- 查询时增加 topic 级召回：query 同时召回 topic 与 chunk。
- 命中 topic 后，将该 topic 下的 sibling chunks 扩展进候选集。
- 保留原有 chunk 级 BM25/vector 召回与 rerank，不改变上层 `search(query, mode="hybrid")` 接口。
- 不做数据库迁移脚本；通过 `ALTER TABLE ... ADD COLUMN` 兼容已有本地 SQLite。

## Done Contract
- 新旧数据库都能初始化运行。
- 新插入 topic 会写入 `terms_json` 与 `embedding_json`。
- `search()` 会合并 chunk 级候选与 topic 扩展候选。
- 通过语法检查。
- 通过一个不联网的 smoke test：stub embedding，插入少量记录，查询能返回来自同一父 topic 的上下文片段。

## Risks
- 旧 topic 没有 topic embedding，只能参与新数据写入后的 topic 召回；本轮不做全量 backfill。
- topic 扩展候选过多可能增加 rerank 成本，因此需要限制 topic top-k 与每个 topic 扩展 chunks 数。
- topic summary 当前是规则摘要，不是 LLM 摘要，topic 召回质量会受关键词质量影响。

## Change Log
- `rag_topics` schema 增加 `terms_json` 与 `embedding_json`，并在初始化时对旧库执行 `ALTER TABLE ... ADD COLUMN` 兼容。
- 新增配置读取项：`topic_top_k` 与 `topic_expand_chunk_limit`，用于限制父 topic 召回和 sibling chunk 扩展规模。
- 插入 RAG 数据时，同时构造 topic 文本与 chunk 文本，一次 embedding 请求中写入 topic embedding 与 chunk embedding。
- `search()` 现在同时计算 chunk 级 BM25/vector 分数和 topic 级 BM25/vector 分数。
- 命中 topic 后，通过 `_expand_topic_chunks()` 把该 topic 下的子 chunks 加入候选集。
- rerank 增加 parent topic score 权重，保留 BM25、向量、近期性和 topic bonus。

## Validation
- 已运行：`python -m py_compile backend/services/rag_service.py`，通过。
- 已运行导入测试：`uv run` 导入 `RAGService` 成功。
- 已运行真实配置库 schema 兼容测试：`rag_topics` 已包含 `terms_json` 与 `embedding_json`。
- 已运行不联网 smoke test：stub embedding，强制 5 条消息形成 1 个父 topic、3 个子 chunks，topic 命中后成功扩展出 3 个 sibling chunks。
- smoke test 输出：`topics 1`、`chunks 3`、`expanded_chunks 3`，检索结果包含 `面试` 与 `offer`。
- 全量测试脚本输出：`ALL TESTS PASSED`。

## Resume or Handoff
当前核心目标已完成：RAG 检索已从单纯 chunk 检索增强为 topic-chunk 父子索引检索。后续若要量化简历指标，可新增 benchmark 对比 chunk-only 与 parent-child 两种模式的候选扩展数、召回覆盖率和查询耗时。
