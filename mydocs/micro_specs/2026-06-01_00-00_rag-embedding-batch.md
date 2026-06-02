# RAG embedding 批量请求 micro-spec

## Restate
真实全量 RAG benchmark 失败，原因是一次 embedding 请求体超过 DashScope/OpenAI 兼容接口限制：`Exceeded limit on max bytes to request body : 6291456`。需要将 `_get_embeddings(texts)` 内部改为分批请求，避免全量 topic/chunk 文本一次性提交。

## Scope
- 修改 `backend/services/rag_service.py`。
- 保持 `_get_embeddings(texts)` 对外返回值不变。
- 增加 embedding batch size 配置，默认按较保守数量分批。
- 每批调用 embedding API，按原输入顺序合并结果。
- 不改变 RAG 插入、检索和父子索引逻辑。

## Done Contract
- 全量 texts 不会一次性发送到 embedding API。
- 返回 embedding 数量与输入 texts 数量一致。
- 通过语法检查。
- 通过 stub 测试：输入多条 texts 时会分批调用，且顺序保持一致。

## Evidence
- 失败命令：`PYTHONIOENCODING=utf-8 uv run python scripts/benchmark_rag_real_data.py`。
- 失败原因：HTTP 400 `BadRequest.TooLarge`，请求体超过 `6291456` bytes。

## Change Log
- `RAGService.__init__` 新增 `embedding_batch_size` 配置读取，默认 `10`，符合 DashScope `text-embedding-v4` 单次 batch size 不大于 10 的限制。
- `_get_embeddings()` 改为按 `embedding_batch_size` 分批请求 embedding API，并按输入顺序合并返回。

## Validation
- 已运行：`python -m py_compile backend/services/rag_service.py`，通过。
- 已运行 stub batch 测试：设置 `embedding_batch_size = 2`，插入 1 个 topic + 3 个 chunks，共 4 段 embedding 文本。
- 第二次真实全量 benchmark 失败原因：DashScope `text-embedding-v4` 限制单次 batch size 不大于 `10`，错误为 `batch size is invalid, it should not be larger than 10`。
- 已将默认 `embedding_batch_size` 从 `64` 调整为 `10`。

## Resume or Handoff
当前请求体过大问题已修复。下一步可重新运行 `scripts/benchmark_rag_real_data.py` 进行真实全量 RAG benchmark。
