# ChatHelper - 智能微信消息回复助手

基于 AI 的智能回复助手，通过分析聊天记录生成人物画像，结合 RAG 检索和实时信息，为你推荐符合个人风格的回复内容。

## 核心特性

### 智能解析
- **零成本解析**：优先使用硬编码规则解析结构化聊天记录，大幅降低 API 调用
- **格式自适应**：支持微信 TXT/HTML/CSV/JSON 等多种导出格式
- **AI 兜底**：无法识别时自动生成解析器并缓存，下次直接使用

### 人物画像
- **双向画像**：同时生成用户和联系人的性格、语气、说话风格画像
- **增量更新**：新聊天记录自动更新画像，无需重新生成
- **持久化存储**：画像存入 SQLite，避免重复调用大模型

### 智能检索（RAG）
- **语义分片**：基于消息相似度智能分片，同一话题的对话保持完整
- **知识图谱**：使用 LightRAG 提取实体和关系，构建对话知识图谱
- **精准检索**：检索与当前对话相关的历史片段作为上下文

### 智能回复生成
- **实时信息**：自动判断是否需要搜索互联网获取最新信息（天气、新闻等）
- **回复评估**：每条推荐回复自动评估是否符合用户人设
- **智能重试**：评估不通过时，分析消息潜台词并重新生成（最多 2 次）
- **自我改进**：记录不合适的回复案例，持续优化生成质量

### 灵活配置
- **多模型支持**：支持 OpenAI 兼容（DeepSeek、Ollama、OpenAI）、Gemini 等
- **按用途配置**：画像生成、实体提取、回复生成、Embedding 可分别配置不同模型
- **成本优化**：高 token 消耗任务用便宜模型，回复生成用强模型

## 技术架构

```
┌─────────────────────────────────────────────────────────┐
│                      前端 (React)                        │
│  上传聊天记录 | 查看画像 | 生成推荐回复 | 提交反馈      │
└─────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────┐
│                   后端 (FastAPI)                         │
├─────────────────────────────────────────────────────────┤
│  解析 Agent → 画像服务 → RAG 服务 → 回复生成 → 评估器  │
│     ↓            ↓          ↓           ↓          ↓     │
│  硬编码规则   DeepSeek   LightRAG    Gemini   自改善   │
└─────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────┐
│              数据层 (SQLite + 向量数据库)                │
│  聊天记录 | 画像 | 知识图谱 | 反馈记录 | 解析器缓存     │
└─────────────────────────────────────────────────────────┘
```

## 快速开始

### 1. 环境要求

- Python 3.10+
- Node.js 16+
- Poetry（Python 依赖管理）

### 2. 安装依赖

```bash
# 后端依赖
poetry install

# 前端依赖
cd frontend
npm install
```

### 3. 配置模型

编辑 `config.yaml`，按用途配置不同的模型：

```yaml
models:
  # 画像生成（高 token 消耗，使用便宜模型）
  profile_generation:
    provider: "openai_compatible"
    api_key: "your-deepseek-api-key"
    base_url: "https://api.deepseek.com/v1"
    model: "deepseek-chat"
    temperature: 0.7

  # 实体/关系提取（LightRAG，高 token 消耗）
  entity_extraction:
    provider: "openai_compatible"
    api_key: "your-deepseek-api-key"
    base_url: "https://api.deepseek.com/v1"
    model: "deepseek-chat"
    temperature: 0.3

  # 推荐回复生成（使用强模型）
  reply_generation:
    provider: "gemini"
    api_key: "your-gemini-api-key"
    model: "gemini-2.0-flash-exp"
    temperature: 0.8

  # Embedding 模型
  embedding:
    provider: "openai_compatible"
    api_key: "your-openai-api-key"
    base_url: "https://api.openai.com/v1"
    model: "text-embedding-3-small"

# LightRAG 配置
lightrag:
  working_dir: "./data/lightrag"

# 数据库配置
database:
  path: "./data/chathelper.db"
```

**配置示例**：

```yaml
# 使用 Ollama（本地免费）
entity_extraction:
  provider: "openai_compatible"
  api_key: "ollama"
  base_url: "http://localhost:11434/v1"
  model: "llama3"

# 使用 OpenAI
reply_generation:
  provider: "openai_compatible"
  api_key: "sk-xxx"
  base_url: "https://api.openai.com/v1"
  model: "gpt-4"
```

### 4. 启动服务

```bash
# 启动后端（终端 1）
python backend/main.py

# 启动前端（终端 2）
cd frontend
npm run dev
```

访问 http://localhost:5173

## 使用流程

### 1. 上传聊天记录

- 支持格式：微信 TXT/HTML、CSV、JSON
- 系统自动识别格式并解析
- 首次上传生成画像，后续上传增量更新

### 2. 查看画像

- 查看用户和联系人的画像
- 包含性格、语气、说话风格、回复习惯等

### 3. 生成推荐回复

- 输入对方最新消息
- 系统结合画像 + 历史上下文 + 实时信息生成推荐回复
- 每条回复显示评分和评估结果

### 4. 提交反馈

- 对不合适的回复点击"反馈"按钮
- 系统记录并学习，避免重复错误

## 项目结构

```
ChatHelper/
├── backend/                    # FastAPI 后端
│   ├── api/                   # API 路由
│   │   ├── upload.py          # 上传聊天记录
│   │   ├── profile.py         # 画像管理
│   │   └── reply.py           # 推荐回复
│   ├── services/              # 业务逻辑
│   │   ├── ai_client.py       # AI 模型调用抽象层
│   │   ├── parser_agent.py    # 聊天记录解析（智能分层）
│   │   ├── profile_service.py # 画像生成与增量更新
│   │   ├── rag_service.py     # RAG 检索（语义分片）
│   │   ├── evaluator_service.py # 回复评估器
│   │   ├── message_rewriter_agent.py # 消息重写（潜台词分析）
│   │   └── web_search_tool.py # 实时信息检索
│   ├── models/                # 数据库模型
│   │   └── db.py              # SQLite 操作
│   ├── config.py              # 配置管理
│   └── main.py                # 入口文件
├── frontend/                  # React 前端
│   ├── src/
│   │   ├── pages/
│   │   │   ├── Upload.jsx     # 上传页面
│   │   │   ├── Profile.jsx    # 画像管理页面
│   │   │   └── Reply.jsx      # 推荐回复页面
│   │   ├── App.jsx            # 路由配置
│   │   └── main.jsx
│   ├── package.json
│   └── vite.config.js
├── data/                      # 数据存储
│   ├── chathelper.db          # SQLite 数据库
│   ├── lightrag/              # LightRAG 知识图谱
│   ├── parsers/               # 解析器缓存
│   └── feedback/              # 反馈记录
├── config.yaml                # 配置文件
├── pyproject.toml             # Python 依赖
└── README.md
```

## API 文档

启动后端后访问 http://localhost:8000/docs 查看完整 API 文档。

### 主要接口

- `POST /api/upload` - 上传聊天记录
- `GET /api/profile/{contact_id}` - 获取画像
- `POST /api/reply` - 生成推荐回复
- `POST /api/reply/feedback` - 提交反馈

## 核心算法

### 智能解析（分层策略）

1. **缓存解析器**（零 LLM 调用）
2. **内置解析器**（零 LLM 调用）
3. **LLM 生成解析器**（1 次调用，缓存后零调用）
4. **LLM 直接解析**（兜底方案）

### 语义分片

```python
# 计算相邻消息的 embedding 相似度
similarity = cosine_similarity(embedding[i-1], embedding[i])

# 相似度 ≥ 0.75 → 同一 chunk（同一话题）
# 相似度 < 0.75 → 新 chunk（话题切换）
# 限制 chunk 大小：3-20 条消息
```

### 智能重试

```
生成回复 → 评估 → 不合适？
                ↓ 是
     分析消息潜台词（重写消息）
                ↓
     附加失败原因 → 重新生成 → 评估
                            ↓ 仍不合适？
                     再次重试（最多2次）
```

## 成本优化建议

1. **画像生成**：使用 DeepSeek（便宜）
2. **实体提取**：使用 DeepSeek 或 Ollama（本地免费）
3. **回复生成**：使用 Gemini 或 GPT-4（强模型）
4. **Embedding**：使用 OpenAI `text-embedding-3-small`（便宜且高质量）

**预估成本**（以 DeepSeek + Gemini 为例）：
- 上传 1000 条聊天记录：~0.1 元（画像生成 + 实体提取）
- 生成 1 次推荐回复：~0.01 元（RAG 检索 + 回复生成）

## 常见问题

### 1. 如何使用本地模型（Ollama）？

```yaml
entity_extraction:
  provider: "openai_compatible"
  api_key: "ollama"
  base_url: "http://localhost:11434/v1"
  model: "llama3"
```

### 2. 如何切换不同的模型？

修改 `config.yaml` 中对应用途的模型配置即可，无需修改代码。

### 3. 聊天记录格式不支持怎么办？

系统会自动让 LLM 生成解析器并缓存，下次直接使用。

### 4. 如何提高回复质量？

- 上传更多聊天记录，丰富画像
- 对不合适的回复提交反馈
- 使用更强的模型（如 GPT-4、Claude）

## 开发计划

- [ ] 支持多联系人管理
- [ ] 支持自定义画像字段
- [ ] 支持回复模板
- [ ] 支持微信直接对接（需要协议支持）
- [ ] 支持更多聊天平台（QQ、Telegram 等）

## 技术栈

- **后端**: Python 3.10+ + FastAPI + SQLite
- **前端**: React 18 + Vite
- **RAG**: LightRAG（GraphRAG）
- **AI 模型**: 支持 OpenAI 兼容、Gemini 等
- **依赖管理**: Poetry + npm

## 许可证

MIT License

## 贡献

欢迎提交 Issue 和 Pull Request。

## 致谢

- [LightRAG](https://github.com/HKUDS/LightRAG) - 强大的 GraphRAG 框架
- [FastAPI](https://fastapi.tiangolo.com/) - 现代化的 Python Web 框架
- [React](https://react.dev/) - 用户界面库
