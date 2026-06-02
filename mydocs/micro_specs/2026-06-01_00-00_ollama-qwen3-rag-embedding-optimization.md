# Ollama qwen3 embedding + RAG embedding text optimization micro-spec

## Restate
用户已在本地启动 Ollama，并有 `qwen3-embedding:4b` 用于文本嵌入。当前 RAG 已支持 Ollama provider 和边 embedding 边写库；下一步要把配置切到该本地模型，并减少 embedding 输入文本体积，避免把展示用格式、时间戳、重复 topic summary 等内容都送去向量化。

## Scope
- 修改 `config.yaml`，将 embedding model 改为 `qwen3-embedding:4b`。
- 修改 `backend/services/rag_service.py`，区分展示文本和 embedding 文本。
- chunk 入库仍保留完整 `chunk_text` 供回复上下文展示。
- chunk embedding 使用更紧凑的消息内容文本，避免重复 topic summary、时间戳和冗余标题。
- topic embedding 使用 topic summary 与关键词/高频词等紧凑语义信息，不使用完整 topic 展示文本。
- 不改变 topic/chunk id 规则、父子索引检索流程、BM25 使用的展示文本和外部搜索接口。

## Done Contract
- 配置默认使用 Ollama `qwen3-embedding:4b`。
- RAG 构建时 topic/chunk 写库内容不丢失，但 embedding 输入显著更短。
- 重复运行仍跳过已入库 topic/chunk，不重复 embedding。
- OpenAI-compatible provider 和 Ollama provider 分发逻辑继续可用。
- 通过语法检查与轻量 stub 验证。

## Risks
- 已有数据库中旧 embedding 可能来自不同模型或不同 embedding 文本策略；真实检索效果应使用同一模型/策略重建或清空旧 RAG 库后重跑。
- qwen3 embedding 维度可能与旧模型不同；同一个向量库内混用会影响 cosine 检索。
- embedding 文本过度压缩会损失语义，因此 chunk embedding 保留消息正文和少量发送者信息，不只用关键词。

## Change Log
- `config.yaml` 的 embedding model 已从 `nomic-embed-text` 改为 `qwen3-embedding:4b`。
- `insert_records` 为 topic/chunk 分别生成 `text` 与 `embedding_text`：`text` 继续用于入库展示和 BM25，`embedding_text` 仅用于向量化。
- 新增 `_format_topic_embedding_text()`：topic embedding 仅包含 topic summary 与关键词。
- 新增 `_format_chunk_embedding_text()`：chunk embedding 仅包含发送者和消息正文，不包含时间范围、消息数量、标题和重复 topic summary。

## Validation
- 已运行：`python -m py_compile backend/services/rag_service.py`，通过。
- 已运行 compact text stub：样例 chunk 展示文本 203 字符，embedding 文本 48 字符；topic 展示文本 165 字符，embedding 文本 112 字符。
- 已运行本地 Ollama path 检查：`qwen3-embedding:4b` 返回 1 条 embedding，维度 2560。

## Resume or Handoff
当前优化已完成。下一步如果要跑真实全量 benchmark，建议确认是否要先清空或重建 `data/hybrid_rag/hybrid_rag.db`，避免混用旧模型/旧 embedding 文本策略造成检索结果不可比。
