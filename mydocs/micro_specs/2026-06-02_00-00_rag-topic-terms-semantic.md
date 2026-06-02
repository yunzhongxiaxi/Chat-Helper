# RAG topic terms 语义化 micro-spec

## Restate
当前 `rag_topics.terms_json` 是从格式化后的 topic 展示文本中分词得到的，导致表头标签、时间、重复词和摘要提示词混入关键词；这会污染 topic BM25 召回，也让 topic 表中的关键词不可读。需要改为优先使用 LLM topic summary 返回的 `keywords`，并且只从原始消息/自然摘要中补充去重后的少量语义词。

## Scope
- 修改 `backend/services/rag_service.py`。
- topic 摘要生成保留 LLM 结构化输出中的 `summary` 和 `keywords`，不要把二者过早拼成一个字符串后再分词。
- `rag_topics.terms_json` 优先写入 LLM `keywords`，必要时用原始消息 top terms 补足。
- topic/chunk BM25 terms 不再从带标题、时间范围、消息数量的展示文本中提取。
- `rag_chunks.chunk_text` 只保存原始聊天消息行，不再包含话题摘要、关键词、时间范围、消息数量等索引/展示噪声。
- 停止并清理本次已开始的错误关键词构建结果，修复后再正式重建。

## Done Contract
- topic terms 不再包含 `历史/话题/摘要/时间/范围/消息/数量/关键词/2025` 等格式化标签或时间噪声。
- topic terms 去重，并优先体现 LLM 语义关键词。
- 语法检查通过，小样本写库后检查 `rag_topics.terms_json` 可读。
- 修复后清空旧的错误 RAG 索引，准备重新正式构建。

## Change Log
- 停止了正在运行的正式构建，避免继续写入污染后的 topic terms / chunk_text。
- `backend/services/rag_service.py` 中 `_summarize_topic()` 改为返回结构化 dict：`summary` 与 `keywords` 分离。
- `rag_topics.topic_summary` 只保存自然摘要正文，不再把关键词拼入摘要字段。
- `rag_topics.terms_json` 改为优先使用 LLM keywords，并用原始消息 top terms 补足、去重。
- `rag_chunks.chunk_text` 改为只保存原始聊天消息行，不再包含标题、摘要、时间范围、消息数量等模板噪声。
- chunk terms 改为从原始消息行/原始消息内容派生，不再从带模板的 chunk 展示文本派生。
- 已保存用户反馈：RAG chunk_text 必须保持原始聊天文本，摘要/关键词只作为索引元数据。

## Validation
- 已运行：`.venv/Scripts/python.exe -m py_compile backend/services/rag_service.py`，通过。
- 已运行 40 条真实 XLSX 样本构建验证：写入 `4` 个 topic / `4` 个 chunk，embedding `8` 段文本。
- 验证样例中 `topic_summary` 为自然摘要：`用户承认刚偷偷查看朋友圈，并解释自己平时很少发动态。`
- 验证样例中 `terms_json` 不再包含 `历史/话题/摘要/时间/范围/消息/数量/关键词/2025` 等模板噪声。
- 验证样例中 `chunk_text` 只包含原始消息行，例如 `[2025-02-16 18:59:27] user: 我自首，刚刚偷偷看了眼朋友圈`。
- 验证后已清空测试写入的 `rag_topics` / `rag_chunks`。

## Resume or Handoff
当前核心目标已完成：索引元数据与最终上下文文本已拆开。下一步可以重新正式流式构建 RAG；运行早期应能看到 DB 增长，且 topic terms / chunk_text 不再被模板噪声污染。
