# RAG LLM topic segmentation 小样本 benchmark micro-spec

## Restate
滑动窗口 LLM 话题切分已经在单段真实聊天中可用。下一步需要在多段真实聊天上做小样本 benchmark，不进行 embedding、不重建 RAG，只评估 qwen3.5:9b 话题切分的速度、topic 数量和人工可读质量，再决定是否用于全量 RAG 重建。

## Scope
- 新增一个 benchmark 脚本。
- 输入仍使用 `chat_history_sample.xlsx`。
- 从真实记录中抽取多段连续窗口，默认每段 40 条消息。
- 调用当前 `RAGService._split_topics()`，即使用强规则 + Ollama SDK 结构化输出。
- 不写 RAG 数据库，不调用 embedding。
- 输出指标：样本窗口数、总消息数、总耗时、平均每窗口耗时、topic 总数、平均 topic 消息数、每窗口 topic 数分布。
- 输出每个窗口的 topic 预览：时间范围、消息数、关键词、前几条消息。

## Done Contract
- 脚本能成功解析 XLSX 并抽样多个窗口。
- 脚本能调用本地 qwen3.5:9b 完成话题切分。
- 输出足够判断切分质量和速度。
- 通过语法检查并实际运行一次。

## Risks
- 真实样本中不同时间段质量差异较大，小样本只能作为趋势判断。
- 本地 qwen3.5:9b 推理速度依赖当前机器负载。
- benchmark 结果用于决定是否重建索引，不直接代表最终检索提升。

## Change Log
- 新增 `scripts/benchmark_rag_topic_segmentation.py`。
- 脚本会将项目根目录加入 `sys.path`，支持直接从 `scripts/` 运行。
- 默认抽取 `6` 个真实聊天窗口，每个窗口 `40` 条消息。
- 每个窗口调用当前 `RAGService._split_topics()`，不写数据库、不调用 embedding。

## Validation
- 已运行：`.venv/Scripts/python.exe -m py_compile scripts/benchmark_rag_topic_segmentation.py`，通过。
- 已运行：`PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe scripts/benchmark_rag_topic_segmentation.py`，通过。
- 样本窗口数：`6`。
- 总消息数：`240`。
- 总耗时：`10.87s`。
- 平均每窗口耗时：`1.76s`。
- topic 总数：`21`。
- 平均每窗口 topic 数：`3.50`。
- 平均 topic 消息数：`11.43`。
- 每窗口 topic 数分布：`[3, 4, 7, 3, 1, 3]`。
- 深圳自我介绍窗口中，`我不是本地人 / 爸妈来深圳 / 深圳长大 / 来了就是深圳人 / 江西老家` 被归入同一 topic。

## Resume or Handoff
小样本 benchmark 表明 qwen3.5:9b + `think=False` 的结构化切分速度可接受，40 条窗口平均约 `1.76s`。下一步若要进入全量重建，需要先决定是否清空或另建 RAG 数据库，避免旧 topic/chunk/embedding 与新切分策略混用。
