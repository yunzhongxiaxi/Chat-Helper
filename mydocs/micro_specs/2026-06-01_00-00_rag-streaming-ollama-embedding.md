# RAG 边 embedding 边写库 + Ollama embedding micro-spec

## Restate
当前 RAG 全量构建会先对所有新增 topic/chunk 完成 embedding，再统一写库；一旦中途失败，数据库没有任何已完成结果。需要改为每个 embedding batch 成功后立即写库，支持断点式重复运行。同时用户希望使用本地 Ollama embedding 模型，降低外部 API 成本和账号依赖。

## Scope
- 修改 `backend/services/rag_service.py`。
- `insert_records` 改为边 embedding 边写库：topic/chunk 元数据先去重，缺失项按 batch embedding，每个 batch 成功后立即 insert。
- 保持 topic/chunk id 规则不变，重复运行仍跳过已写入数据。
- `_get_embeddings` 支持现有 OpenAI-compatible provider。
- 新增 Ollama embedding provider 支持，读取 `models.embedding.provider: "ollama"`。
- 不引入新依赖，使用 Python 标准库 HTTP 调用 Ollama `/api/embeddings` 或 `/api/embed`。
- 不改搜索接口和父子索引检索逻辑。

## Done Contract
- 外部 API 或本地 embedding 中途失败时，已经成功的 batch 已落库。
- 重跑时已落库 topic/chunk 不重复 embedding。
- OpenAI-compatible embedding 仍可用。
- Ollama embedding provider 可用，配置后能调用本地模型。
- 通过语法检查和 stub 测试。

## Risks
- Ollama 不同版本 embedding API 返回结构可能不同，需要兼容 `/api/embed` 与 `/api/embeddings` 常见返回。
- 本地 embedding 模型维度可能与已有向量库中旧 embedding 维度不同；若混用不同模型，检索质量会受影响，建议同一数据库使用同一 embedding 模型。
- 真正全量构建时仍可能耗时较长，但失败后可通过重跑继续补缺失项。

## Change Log
- `insert_records` 改为生成 pending topic/chunk 后，按 `embedding_batch_size` 分批 embedding。
- 每个 embedding batch 成功后立即调用 `_insert_embedded_items()` 写入 `rag_topics` / `rag_chunks`。
- 新增 `_embedding_item_batches()` 与 `_insert_embedded_items()`。
- `_get_embeddings()` 根据 `models.embedding.provider` 分发到 OpenAI-compatible 或 Ollama。
- 新增 Ollama 调用：优先 `/api/embed` 批量接口，失败时回退 `/api/embeddings` 单条接口。
- `config.yaml` 的 embedding provider 已改为 `ollama`，默认 `base_url: http://localhost:11434`，`model: nomic-embed-text`。

## Validation
- 已运行：`python -m py_compile backend/services/rag_service.py`，通过。
- 已运行 streaming write stub 测试：模拟第二批 embedding 失败后，第一批已成功落库，输出 `after_failure topics 1`、`after_failure chunks 1`。
- 已运行 Ollama provider path stub 测试：fake `/api/embed` 返回 embedding，`_get_embeddings(['a', 'bb', 'ccc'])` 正确返回 3 条向量。

## Resume or Handoff
当前核心目标已完成：RAG 构建支持边 embedding 边写库，并支持本地 Ollama embedding provider。下一步如果本地 Ollama 已启动且模型已 pull，可以重新运行真实全量 RAG benchmark。
