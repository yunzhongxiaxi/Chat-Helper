# RAG 流式构建 micro-spec

## Restate
当前全量 RAG 重建会先完成所有 topic 切分与 LLM topic 摘要，再进入 embedding 和写库，导致长时间运行时 `rag_topics` / `rag_chunks` 仍为空。需要改成流式构建：分段处理、分段摘要、分段 embedding、分段写库，保证数据库能持续增长并支持中断后保留已完成部分。

## Scope
- 修改 `backend/services/rag_service.py`。
- `insert_records()` 不再先构造完整 `topics` / `chunks` 列表后统一写入。
- 按 strong segment 或小批 topic 增量执行：话题切分 → topic 摘要 → chunk 构造 → 去重 → embedding → 写库。
- 保留已有 `_insert_embedded_items()` 和 embedding 批处理逻辑。
- 测试脚本后续尽量使用真实流式构建路径，不再依赖全量预构造后写入。

## Done Contract
- 全量构建运行早期即可看到 `rag_topics` / `rag_chunks` 增长。
- 中断构建后，已完成 embedding 的 topic/chunk 保留在实际 RAG DB 中。
- 重复运行仍跳过已存在 topic/chunk，避免重复 embedding。
- 语法检查通过，并用小样本流式构建验证 DB 会增量写入。

## Change Log
- 已停止旧的全量重建后台任务，避免继续运行非流式构建。
- `backend/services/rag_service.py` 的 `insert_records()` 改为按 strong segment 流式处理。
- 每个分段内执行 LLM 话题切分、LLM topic 摘要、chunk 构造、去重、embedding、写库。
- 保留 topic/chunk ID 生成逻辑，重复运行仍通过 `_existing_ids()` 跳过已写入数据。
- 增加分段级进度日志，显示已处理分段数和已写入 topic/chunk 数。
- 已保存用户反馈：以后长耗时测试/benchmark 尽量使用流式构建，避免全量预计算后才写入。

## Validation
- 已运行：`.venv/Scripts/python.exe -m py_compile backend/services/rag_service.py`，通过。
- 已运行 80 条真实 XLSX 样本流式构建验证：构建期间写入 `9` 个 topic / `9` 个 chunk，embedding `18` 段文本。
- 验证后已清空测试写入的 `rag_topics` / `rag_chunks`，保持 RAG DB 为空，等待正式全量重建。

## Resume or Handoff
当前核心目标已完成：RAG 构建已改为流式写库。下一步可以重新运行 `scripts/benchmark_rag_real_data.py`，这次应能在运行早期看到 `hybrid_rag` 数据库持续增长；如中断，已完成 embedding 的 topic/chunk 会保留。
