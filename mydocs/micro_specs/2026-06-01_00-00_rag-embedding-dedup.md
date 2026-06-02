# RAG 重复 embedding 成本优化 micro-spec

## Restate
当前 `insert_records` 会先为本批 topic/chunk 生成 embedding，再通过 `INSERT OR IGNORE` 写库；重复运行全量数据时，即使 topic/chunk 已存在，也会重复调用 embedding。需要调整顺序：先判断哪些 topic/chunk 缺失，再只对缺失项生成 embedding，从而降低重复运行成本。

## Scope
- 修改 `backend/services/rag_service.py`。
- 保持 `insert_records(contact_id, records)` 对外接口不变。
- 构建 topic/chunk 元数据后，先查询数据库中已存在的 topic/chunk id。
- 只对缺失 topic 和缺失 chunk 生成 embedding。
- 已存在 topic/chunk 不重复生成 embedding、不重复写入。
- 保留父子索引字段写入逻辑。

## Done Contract
- 首次插入仍能生成并写入 topic/chunk embedding。
- 重复插入同一批 records 时，embedding 调用文本数为 0。
- 部分重复、部分新增时，只对新增 topic/chunk 调用 embedding。
- 通过语法检查和不联网 stub 测试。

## Risks
- 如果旧库里已有 topic/chunk 但缺少 topic embedding，本轮按“存在即跳过”可能不会 backfill；后续可单独做 backfill 脚本。
- topic 与 chunk 去重依赖当前 id 生成规则，若切分参数变化，同一批消息可能生成不同 id 并重新 embedding。

## Change Log
- `insert_records` 现在先生成 topic/chunk id，再查询已有 `rag_topics` 与 `rag_chunks`。
- 只对新 topic 和新 chunk 生成 embedding。
- 已存在 topic/chunk 不再进入 embedding 请求，也不再写库。
- 新增 `_existing_ids()`，按批查询已有 id，避免 SQL 参数过多。
- 插入日志增加新增 topic/chunk 数与实际 embedding 文本数。

## Validation
- 已运行：`python -m py_compile backend/services/rag_service.py`，通过。
- 已运行不联网 stub 测试：同一批 records 连续插入两次。
- 首次插入：`新增 1 个话题 / 2 个 chunk，embedding 3 段文本`。
- 第二次重复插入：`新增 0 个话题 / 0 个 chunk，embedding 0 段文本`。
- stub 计数结果：`embedding_text_counts [3]`，证明第二次没有调用 embedding。

## Resume or Handoff
当前核心目标已完成：重复运行全量 RAG 构建时，已存在 topic/chunk 不会重复产生 embedding 成本。下一步可以继续实现并运行真实 `chat_history_sample.xlsx` 全量 RAG benchmark。
