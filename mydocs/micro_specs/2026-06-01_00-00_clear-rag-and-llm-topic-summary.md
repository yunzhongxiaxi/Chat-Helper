# 清空旧 RAG 数据 + LLM topic 摘要 micro-spec

## Restate
用户确认要清空原来的 RAG 数据，避免旧 topic/chunk/embedding 与新的 LLM 滑动窗口话题切分策略混用。同时，当前 topic 摘要仍是关键词模板，质量有限；可以复用本地 Ollama `qwen3.5:9b` 为每个 topic 生成更自然的语义摘要，用于展示、topic embedding 和父子索引召回。

## Scope
- 修改 `backend/services/rag_service.py`。
- 新增可选 LLM topic summary 配置，默认使用 Ollama `qwen3.5:9b`。
- topic 摘要输入为该 topic 内消息序号、发送者、内容。
- LLM 输出严格结构化 JSON，包含 `summary` 和 `keywords`。
- `_summarize_topic()` 优先使用 LLM 摘要，失败时回退当前关键词模板。
- 使用 `ollama.AsyncClient`、Pydantic schema、`think=False`、`temperature=0`。
- 修改 `config.yaml`，增加 topic summary 配置。
- 验证通过后清空实际 RAG 数据库中的 `rag_chunks` 与 `rag_topics`。
- 不删除聊天原始记录、profiles 或其他业务表。

## Done Contract
- topic summary 能用本地 qwen3.5 生成自然摘要。
- LLM 摘要失败时 RAG 构建不中断，回退关键词模板。
- 语法检查和小样本摘要验证通过。
- 旧 `rag_topics` / `rag_chunks` 已清空，准备后续重建。

## Change Log
- `backend/services/rag_service.py` 新增 `TopicSummaryResult` Pydantic schema。
- `RAGService` 新增 `topic_summary` 配置读取。
- `_summarize_topic()` 改为优先调用 Ollama SDK 结构化摘要，失败时回退关键词模板。
- 新增 `_request_topic_summary()`、`_build_topic_summary_prompt()`、`_fallback_topic_summary()`。
- `config.yaml` 新增 `hybrid_rag.topic_summary`，默认启用本地 `qwen3.5:9b`。

## Validation
- 已运行：`.venv/Scripts/python.exe -m py_compile backend/services/rag_service.py`，通过。
- 已运行小样本摘要验证，输出自然摘要：`用户表示欢迎 contact 及其父母来深圳，并强调 contact 虽非本地人但已在此长大，contact 随后透露老家在江西。`
- 已清空实际 RAG 数据库 `data/hybrid_rag/hybrid_rag.db` 中的索引表：`rag_chunks` 从 `67260` 到 `0`，`rag_topics` 从 `67153` 到 `0`。

## Resume or Handoff
当前核心目标已完成：旧 RAG 索引已清空，后续可以用 LLM 话题切分 + LLM topic 摘要重新构建 RAG。注意全量重建会对每个 topic 额外调用一次本地摘要 LLM，耗时会明显高于仅 embedding。
