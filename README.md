# ChatHelper

基于 Hybrid RAG 与人物画像演进的微信聊天智能回复助手。

ChatHelper 面向长期微信聊天记录中的三个核心问题：历史上下文分散、闲聊噪声高、双方关系和表达风格会随时间变化。项目通过聊天场景专用 RAG、可演进人物画像、回复评估与重试机制，为当前对话生成更贴近用户说话风格、关系语境和近期状态的候选回复。

## 项目亮点

- **聊天场景专用 Hybrid RAG**：融合 BM25、Embedding、Topic-Chunk 父子索引、时间新鲜度、salience 信息价值评分与动态 Top-K 截断。
- **可演进人物画像**：将用户与联系人画像拆分为 `current_profile`、`stable_traits`、`recent_signals`、`changed_traits`，支持随新增聊天记录持续更新。
- **低噪声上下文注入**：话题摘要、关键词、salience 只作为索引元数据；最终 prompt 仅注入原始聊天片段，避免摘要和标签污染回复生成。
- **动态上下文筛选**：不固定塞满 Top-K；当 top1 命中足够明确时，只保留少量高置信片段，降低低相关上下文对 prompt 的干扰。
- **流式索引构建**：长耗时 RAG 构建任务按话题分段边处理边写入，支持中断后基于已构建数据继续测试和调试。
- **回复评估与重试**：生成候选回复后进行画像一致性评估；不合适时分析对方消息潜台词并重新生成。
- **多模型配置**：画像生成、回复生成、Embedding、话题切分、话题摘要可分别配置不同模型，兼顾质量、成本和本地化。

## 离线实验结果

> 以下为当前项目在真实聊天记录样本上的离线实验与阶段性评测结果，用于验证系统设计方向。

- 在约 **22 万条微信聊天记录** 上进行离线实验和索引构建验证。
- 阶段性构建 **1,600+ topic/chunk**，用于验证 RAG 检索质量和画像演进效果。
- 动态 Top-K 截断后，高置信查询的最终上下文可由固定 **5 条** 收敛至 **1-2 条**。
- salience/indexable 降权机制用于减少寒暄、表情、无实质闲聊进入最终 prompt，估算降低 **40%-60%** 低信息量片段注入。
- 相比单纯向量 Top-K，Hybrid RAG + Topic-Chunk 父子索引在跨话题历史问题上估算提升 **30%+** 有效召回能力。
- 人物画像演进 benchmark 中，按时间分批处理 **24 个 chunk / 190 条消息 / 3 批** 后，stable/recent/changed traits 均出现渐进更新，并在第 3 批开始生成 changed traits。

## 系统架构

```text
┌──────────────────────────────────────────────────────────────┐
│                         Frontend                             │
│          上传聊天记录 | 查看画像 | 生成回复 | 提交反馈          │
└───────────────────────────────┬──────────────────────────────┘
                                │
┌───────────────────────────────▼──────────────────────────────┐
│                         FastAPI Backend                       │
│                                                              │
│  Upload API                                                  │
│    └─ Parser Agent → 增量入库 → Profile 更新 → RAG 增量构建    │
│                                                              │
│  Reply API                                                   │
│    └─ Profile + Hybrid RAG + Feedback Memory + MCP Tools      │
│       → Candidate Replies → Evaluator → Subtext Retry         │
└───────────────────────────────┬──────────────────────────────┘
                                │
┌───────────────────────────────▼──────────────────────────────┐
│                          Storage                             │
│                                                              │
│  SQLite: chat_records / profiles                             │
│  Hybrid RAG DB: rag_topics / rag_chunks                       │
│  Feedback files: bad replies and evaluator feedback           │
└──────────────────────────────────────────────────────────────┘
```

## 核心流程

### 1. 聊天记录增量上传

上传聊天记录后，系统会解析消息并写入 SQLite。数据库使用 `(contact_id, timestamp, sender, message)` 作为自然键，避免重复上传造成重复数据。

```text
聊天记录文件
   ↓
Parser Agent
   ↓
insert_new_chat_records()
   ↓
仅对新增消息执行画像更新与 RAG 增量构建
```

### 2. Hybrid RAG 构建

ChatHelper 不直接把所有消息做平铺向量化，而是先构建 Topic-Chunk 层级索引。

```text
聊天记录
   ↓
强边界切分
   ↓
LLM 滑窗话题切分
   ↓
话题摘要 / 关键词 / salience / indexable
   ↓
Topic 父节点 + Chunk 子节点
   ↓
BM25 索引 + Embedding 向量
```

设计要点：

- **Topic**：承载话题摘要、语义关键词、信息价值评分，用于提升召回和话题级扩展。
- **Chunk**：保留原始聊天文本，作为最终注入回复模型的上下文。
- **Index Metadata**：摘要、关键词、时间范围、salience 只参与索引和重排，不直接进入最终 prompt。
- **Raw Context**：最终传给回复模型的历史上下文只包含原始聊天行。

### 3. Hybrid RAG 检索

检索阶段融合多路信号：

1. BM25 关键词召回。
2. Embedding 语义召回。
3. Topic 父节点召回。
4. 父子索引扩展到相关 chunks。
5. 时间新鲜度评分。
6. salience/indexable 信息价值重排。
7. 动态 Top-K 截断。

动态截断规则：

```text
始终保留 top1。
其余 chunk 必须同时满足：
  score >= top1_score * relative_threshold
  score >= min_score
最多返回 final_top_k 条。
```

这样可以避免 top1 已经非常明确时，仍然把低分第 4/5 条上下文塞进 prompt。

### 4. 人物画像演进

画像不是一次性静态总结，而是随时间持续更新的结构化记忆。

```json
{
  "current_profile": {
    "personality": "当前性格特点",
    "speaking_style": "当前说话风格",
    "interests": "当前关注点",
    "tone": "当前语气特点"
  },
  "stable_traits": ["长期稳定特征"],
  "recent_signals": ["近期明显信号"],
  "changed_traits": [
    {
      "field": "变化字段",
      "from": "早期表现",
      "to": "近期表现",
      "period": "变化时间段",
      "confidence": "low/medium/high",
      "evidence": ["证据"]
    }
  ]
}
```

回复生成时：

- `current_profile` 和 `recent_signals` 优先影响当前回复。
- `stable_traits` 作为长期人设约束。
- `changed_traits` 用于避免把早期特征误当成当前状态。

### 5. 回复生成、评估与重试

```text
当前消息
   ↓
读取双方画像
   ↓
Hybrid RAG 检索历史上下文
   ↓
合并历史负反馈
   ↓
生成候选回复
   ↓
Evaluator 评估是否符合人设和场景
   ↓
不合适 → 分析对方消息潜台词 → 带失败原因重试
```

系统最多进行 2 次重试，避免反复生成明显不符合用户风格的回复。

## 技术栈

- **Backend**：Python 3.10+、FastAPI、SQLite
- **Frontend**：React、Vite
- **RAG**：BM25、Embedding、jieba、Topic-Chunk 父子索引、自定义 rerank
- **Local Model Runtime**：Ollama
- **LLM Providers**：OpenAI Compatible、DeepSeek、Gemini
- **Tool Calling**：MCP tool registry
- **Config**：YAML + MCP JSON

## 项目结构

```text
ChatHelper/
├── backend/
│   ├── api/
│   │   ├── upload.py              # 聊天记录上传与增量处理
│   │   ├── profile.py             # 人物画像查询
│   │   └── reply.py               # 推荐回复生成与反馈
│   ├── models/
│   │   └── db.py                  # SQLite 数据访问
│   ├── services/
│   │   ├── ai_client.py           # 多模型调用抽象
│   │   ├── parser_agent.py        # 聊天记录解析
│   │   ├── profile_service.py     # 人物画像生成与更新
│   │   ├── rag_service.py         # Hybrid RAG 构建与检索
│   │   ├── evaluator_service.py   # 回复质量评估与反馈记忆
│   │   ├── message_rewriter_agent.py # 潜台词分析与重写
│   │   └── mcp_tool_registry.py   # MCP 工具注册与调用
│   ├── config.py
│   └── main.py
├── frontend/
│   └── src/
├── scripts/
│   ├── benchmark_rag_real_data.py
│   ├── benchmark_rag_parent_child.py
│   ├── benchmark_rag_topic_segmentation.py
│   ├── benchmark_incremental_upload.py
│   └── benchmark_profile_evolution.py
├── data/
│   ├── chathelper.db
│   └── hybrid_rag/
│       └── hybrid_rag.db
├── config.yaml
├── pyproject.toml
└── README.md
```

## 快速开始

### 1. 安装依赖

```bash
uv sync
```

如果不使用 uv，也可以在虚拟环境中安装 `pyproject.toml` 中的依赖。

### 2. 配置模型

编辑 `config.yaml`。

```yaml
models:
  profile_generation:
    provider: "openai_compatible"
    api_key: "your-api-key"
    base_url: "https://api.deepseek.com"
    model: "deepseek-v4-flash"
    temperature: 0.7

  reply_generation:
    provider: "openai_compatible"
    api_key: "your-api-key"
    model: "deepseek-v4-pro"
    temperature: 0.8

  embedding:
    provider: "ollama"
    base_url: "http://localhost:11434"
    model: "qwen3-embedding:4b"

hybrid_rag:
  working_dir: "./data/hybrid_rag"
  final_top_k: 5
  final_score_relative_threshold: 0.75
  final_score_min: 0.38
  topic_segmentation:
    provider: "ollama"
    base_url: "http://localhost:11434"
    model: "qwen3.5:9b"
    enabled: true
  topic_summary:
    provider: "ollama"
    base_url: "http://localhost:11434"
    model: "qwen3.5:9b"
    enabled: true

database:
  path: "./data/chathelper.db"
```

建议：

- 画像生成使用低成本模型。
- 回复生成使用更强模型。
- Embedding、话题切分、话题摘要优先使用本地 Ollama 控制成本。
- 不要将真实 API Key 提交到公开仓库。

### 3. 启动服务

```bash
.venv/Scripts/python.exe backend/main.py
```

启动后访问：

```text
http://localhost:8000/docs
```

如需启动前端：

```bash
cd frontend
npm install
npm run dev
```

## API

### 上传聊天记录

```http
POST /api/upload
```

表单参数：

- `file`：聊天记录文件。
- `contact_id`：联系人 ID；XLSX 可从文件前置信息中自动解析，非 XLSX 必填。

返回信息包括：

- `records_count`
- `new_records_count`
- `skipped_records_count`
- `contact_id`
- `metadata`

### 获取人物画像

```http
GET /api/profile/{contact_id}
```

### 生成推荐回复

```http
POST /api/reply
```

请求体：

```json
{
  "contact_id": "wxid_xxx",
  "current_context": "对方刚发来的消息"
}
```

### 提交反馈

```http
POST /api/reply/feedback
```

## Benchmark 脚本

### RAG 真实数据评测

```bash
.venv/Scripts/python.exe scripts/benchmark_rag_real_data.py
```

### Topic 父子索引评测

```bash
.venv/Scripts/python.exe scripts/benchmark_rag_parent_child.py
```

### 话题切分评测

```bash
.venv/Scripts/python.exe scripts/benchmark_rag_topic_segmentation.py
```

### 画像演进评测

```bash
.venv/Scripts/python.exe scripts/benchmark_profile_evolution.py --batch-chunks 8 --max-batches 3
```

该脚本会复用已有 RAG chunks，按时间顺序分批调用画像生成/更新流程，并输出：

- chunk 数
- 消息数
- 批次数
- 每批耗时
- current profile 字段覆盖数
- stable/recent/changed 数量变化
- 最终 user/contact profile 预览

## 配置说明

### Hybrid RAG 关键参数

| 参数 | 作用 |
| --- | --- |
| `time_gap_minutes` | 强时间间隔切分阈值 |
| `topic_similarity_threshold` | 话题相似度阈值 |
| `max_topic_messages` | 单个 topic 最大消息数 |
| `max_chunk_messages` | 单个 chunk 最大消息数 |
| `bm25_top_k` | BM25 候选召回数量 |
| `vector_top_k` | 向量候选召回数量 |
| `final_top_k` | 最终最多注入的 chunk 数 |
| `final_score_relative_threshold` | 相对 top1 的动态截断阈值 |
| `final_score_min` | 最终 chunk 最低分数阈值 |

### 数据库

- `data/chathelper.db`：业务数据库，存储聊天记录和人物画像。
- `data/hybrid_rag/hybrid_rag.db`：RAG 索引数据库，存储 topics 和 chunks。

## 设计原则

1. **索引信息和最终上下文分离**  
   摘要、关键词、salience 用于检索；最终回复模型只看原始聊天片段。

2. **不固定塞满上下文**  
   高置信查询保留少量强相关片段，避免低相关 chunk 稀释 prompt。

3. **人物画像必须可演进**  
   聊天关系会变化，因此画像需要表达长期稳定、近期信号和明确变化。

4. **长任务必须流式可观测**  
   大规模聊天记录索引不能长时间无写入，构建过程应支持部分结果验证。

5. **成本按任务拆分控制**  
   高 token 任务使用低成本模型或本地模型；回复生成使用更强模型。

## 注意事项

- 当前 RAG 构建和画像生成会调用配置中的模型服务，运行 benchmark 前请确认成本可接受。
- 大规模聊天记录构建耗时较长，建议先用小批次验证配置和效果。
- 如果终端中文输出乱码，通常是 Windows shell 编码问题，不影响 SQLite 中保存的 JSON 内容。
- `config.yaml` 中可能包含 API Key，请避免提交真实密钥。

## License

MIT License
