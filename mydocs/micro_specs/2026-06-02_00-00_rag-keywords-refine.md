# RAG keywords 精简 micro-spec

## Restate
当前 `terms_json` 虽然已去掉模板噪声，但仍混入 `引用/罅隙/链接/知道/本来` 等低信息词，也会把 `第二故乡` 拆成 `第二/故乡` 这类重复碎片。需要进一步精简关键词数量，提高语义密度，让 topic terms 更像检索标签而不是分词结果。

## Scope
- 修改 `backend/services/rag_service.py`。
- topic `terms_json` 只保留少量高信号语义标签，优先使用 LLM keywords。
- topic fallback terms 只用于 LLM keywords 太少时补足，且补足数量严格限制。
- chunk `terms_json` 也限制数量并过滤低信息词。
- 扩展停用词/噪声词，过滤引用、链接、泛化动词、碎片词。
- 避免同时保留复合词及其子词，例如已有 `第二故乡` 时不再保留 `第二`、`故乡`。

## Done Contract
- topic terms 数量明显减少，默认不超过 6 个。
- chunk terms 默认不超过 8 个。
- 示例中应倾向保留 `深圳/哈尔滨/第二故乡/读书/离家/家人建议`，去掉 `引用/罅隙/链接/知道/第二/故乡/本来`。
- 语法检查通过，小样本验证 terms 更精简。
- 清空已污染的 RAG 数据，准备重新正式构建。

## Change Log
- 停止正在运行的正式构建，避免继续写入低质量 `terms_json`。
- `RAGService` 增加 `TOPIC_TERM_LIMIT = 6`、`CHUNK_TERM_LIMIT = 8`。
- LLM topic summary prompt 明确要求 keywords 只保留可用于未来查询的人物、地点、事件、偏好、关系、计划、经历标签。
- 扩展停用词，过滤 `引用/罅隙/链接/知道/本来/表情/图片/聊天/开始/用户/对方/双方` 等低信息词。
- 新增 `_semantic_terms()`，对关键词去重、限量，并在已有复合词时移除子词。
- `_topic_terms()` 优先使用 LLM keywords，只有少于 3 个时才从原始消息补足。
- `_chunk_terms()` 限制 chunk terms 数量，避免变成完整分词列表。

## Validation
- 已运行：`.venv/Scripts/python.exe -m py_compile backend/services/rag_service.py`，通过。
- 已运行 80 条真实 XLSX 样本构建验证：topic terms 明显精简，示例包括 `['QQ 空间', '微信', '非本地人', '好友添加']`、`['江西', '深圳', '本地人', '包容性', '宣传语']`。
- 已针对用户示例直接验证：`['深圳', '哈尔滨', '第二故乡', '读书', '家人建议', '离家', '引用', '罅隙', '链接', '知道', '回去', '第二', '故乡', '猜哈', '工程', '本来']` 被精简为 `['深圳', '哈尔滨', '第二故乡', '读书', '家人建议', '离家']`。
- 验证后已清空测试写入的 RAG 数据。

## Resume or Handoff
当前核心目标已完成：`terms_json` 已从分词候选列表收敛为少量高信号语义标签。下一步可以重新正式流式构建 RAG。
