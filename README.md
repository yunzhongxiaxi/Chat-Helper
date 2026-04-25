# ChatHelper - 微信消息回复助手

基于 AI 的微信消息回复助手，支持聊天记录分析、人物画像生成、RAG 检索与智能回复推荐。

## 功能特性

- 聊天记录上传与格式自动识别
- 人物画像生成与增量更新
- LightRAG 知识图谱检索
- 多模型支持（DeepSeek/Gemini）
- 智能回复推荐

## 技术栈

- **后端**: Python 3.10+ + FastAPI
- **前端**: React + Vite
- **数据库**: SQLite
- **RAG**: LightRAG
- **AI 模型**: DeepSeek（画像/实体提取）+ Gemini（回复生成）

## 快速开始

### 1. 安装依赖

```bash
# 后端依赖
poetry install

# 前端依赖
cd frontend
npm install
```

### 2. 配置

编辑 `config.yaml` 并填入你的 API 密钥：

```yaml
deepseek:
  api_key: "your-deepseek-api-key"
  model: "deepseek-chat"
  base_url: "https://api.deepseek.com/v1"

gemini:
  api_key: "your-gemini-api-key"
  model: "gemini-2.0-flash-exp"
```

### 3. 运行

```bash
# 启动后端
python backend/main.py

# 启动前端（新终端）
cd frontend
npm run dev
```

访问 http://localhost:5173

## 项目结构

```
ChatHelper/
├── backend/          # FastAPI 后端
│   ├── api/         # API 路由
│   ├── services/    # 业务逻辑
│   ├── models/      # 数据库模型
│   └── main.py      # 入口文件
├── frontend/        # React 前端
│   └── src/
│       ├── pages/   # 页面组件
│       └── App.jsx
├── data/            # 数据存储
│   ├── chathelper.db
│   └── lightrag/
├── config.yaml      # 配置文件
└── README.md
```

## API 文档

启动后端后访问 http://localhost:8000/docs 查看 API 文档。

## 开发状态

当前处于 MVP 开发阶段。详见 `.claude/specs/chathelper-mvp.md`
