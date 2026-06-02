# RAG 滑动窗口 LLM 话题切分 micro-spec

## Restate
用户希望使用本地 Ollama `qwen3.5:9b` 做话题归属/切分判断。方向从逐条边界询问升级为“滑动窗口批量裁决”：每次给 LLM 一段连续聊天记录，让它输出窗口内应切分的位置，从而兼顾语义切分质量和调用成本。

## Scope
- 修改 `backend/services/rag_service.py`。
- 新增可选 LLM topic segmentation 配置，默认启用本地 Ollama chat/generate provider。
- 使用规则先按强边界预切大段：长时间间隔、最大 topic 长度仍直接切。
- 对每个大段使用滑动窗口批量 LLM 裁决话题边界。
- LLM 输入只包含窗口内消息序号、发送者、内容，不传 embedding 或数据库内容。
- LLM 输出严格 JSON，包含 `split_after_indices`，表示窗口内哪些消息后切分。
- 增加 JSON 提取/容错解析；解析失败时回退规则切分或保守合并。
- 保持后续 chunk 切分、embedding、搜索接口、数据库 schema 不变。

## Done Contract
- 深圳自我介绍样例在 stub LLM 返回不切分时保持为同一 topic。
- stub LLM 返回指定切分点时，topic 分组正确。
- LLM 解析失败时不会中断 RAG 构建。
- 语法检查通过。
- 配置中可指定 `topic_segmentation.provider: ollama`、`model: qwen3.5:9b`。

## Risks
- 全量 22 万消息即便按窗口批量，也会产生一定本地推理耗时；应先用较小窗口验证效果。
- LLM 输出可能不稳定，必须严格约束 JSON 并做容错。
- 窗口边界可能造成跨窗口话题断裂；第一版先用简单窗口，后续可加 overlap 或 carry summary。
- 本地模型质量和速度依赖机器性能。

## Change Log
- `config.yaml` 已新增 `hybrid_rag.topic_segmentation`，默认启用 Ollama `qwen3.5:9b`，窗口大小已调整为 `10`，超时 `120s`。
- `RAGService.__init__` 已读取 topic segmentation 配置。
- `_split_topics()` 改为两阶段：先 `_split_by_strong_boundaries()` 按时间间隔/最大长度预切，再 `_split_segment_by_llm()` 对每段做滑动窗口裁决。
- `_request_topic_segmentation()` 已改为官方 `ollama.AsyncClient.chat()`，使用 Pydantic `TopicSplitResult.model_json_schema()` 做结构化输出。
- 已添加 `think=False`，避免 qwen3.5 将结果放入 thinking 导致 `message.content` 为空或超时。
- 新增 `_build_topic_segmentation_prompt()`、`_valid_topic_split_indices()`。
- LLM 失败或解析失败时打印警告并保守合并当前窗口，不中断 RAG 构建。

## Validation
- 已运行：`.venv/Scripts/python.exe -m py_compile backend/services/rag_service.py`，通过。
- stub LLM 返回 `{"split_after_indices": []}` 时，深圳自我介绍 3 条消息保持 1 个 topic。
- stub LLM 返回 `{"split_after_indices": [1]}` 时，3 条消息正确切为 `[2, 1]`。
- stub LLM 返回非法 JSON 时，构建不中断并保守合并为 1 个 topic。
- 真实样本 10 条窗口在 `think=False` 后无超时，输出 1 个 topic。
- 真实样本 20 条窗口耗时 `0.83s`，输出 1 个 topic。
- 真实样本 40 条窗口耗时 `0.86s`，输出 3 个 topic，大小为 `[9, 17, 14]`；深圳自我介绍相关消息被归入同一 topic。

## Resume or Handoff
滑动窗口 LLM 话题切分已可用，关键参数是 `think=False`。下一步应补一个专门的小样本 benchmark 脚本，批量抽取多段真实聊天，统计平均窗口耗时、topic 数、平均 topic 消息数，并人工检查若干切分结果后再决定是否重建全量 RAG 索引。
