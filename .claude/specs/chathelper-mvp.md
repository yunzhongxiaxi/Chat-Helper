---
name: ChatHelper MVP
description: 微信消息回复助手最小可用原型，包含聊天记录解析、画像生成与增量更新、LightRAG 集成、多模型支持、推荐回复生成
type: standard
status: implemented
created: 2026-04-23
updated: 2026-04-23
---

# 微信消息回复助手 MVP

## 核心目标

搭建微信消息回复助手的最小可用原型（MVP），支持：
1. 聊天记录上传与格式自动识别解析（子 Agent）
2. 画像生成与增量更新（持久化存储）
3. LightRAG 集成（GraphRAG：实体/关系提取 + 检索）
4. 多厂商 AI 模型支持（DeepSeek/Gemini，配置文件切换）
5. 推荐回复生成（结合画像 + RAG 上下文）
6. 简单 Web 界面（React）

---

## 功能模块

### 1. 聊天记录上传与解析
- **输入**：用户上传文件（任意格式：txt/csv/json/微信导出等）
- **处理**：
  - 子 Agent 调用 AI 识别文件格式
  - 生成解析逻辑，提取统一结构：`{timestamp, sender, message}`
  - 存入 SQLite（`chat_records` 表）
- **输出**：解析成功/失败反馈

### 2. 画像生成与增量更新
- **首次上传**：
  - 调用 DeepSeek 分析聊天记录
  - 生成双方画像（对方 + 用户自己）
  - 画像内容：性格、说话风格、关注点、回复习惯等
  - 存入 SQLite（`profiles` 表）
- **后续上传**：
  - 基于新记录 + 旧画像，调用 DeepSeek 增量更新
  - 更新画像并覆盖数据库记录
- **输出**：画像 JSON 结构

### 3. LightRAG 集成
- **导入记录**：
  - 聊天记录导入 LightRAG
  - 自动提取实体与关系（调用 DeepSeek）
  - 构建知识图谱并向量化
- **检索**：
  - 用户输入当前对话时，检索相关历史片段（Top-K）
  - 返回相关上下文（文本 + 实体/关系）
- **输出**：检索结果列表

### 4. AI 推荐回复生成
- **输入**：
  - 当前对话内容
  - 双方画像（从数据库读取）
  - RAG 检索的历史上下文
- **处理**：
  - 调用 Gemini 生成 1-3 条推荐回复
  - Prompt 包含：画像 + 上下文 + 当前对话
- **输出**：推荐回复列表

### 5. 多模型支持
- **配置文件**：`config.yaml`
  - DeepSeek 配置：`deepseek.api_key`、`deepseek.model`、`deepseek.base_url`
  - Gemini 配置：`gemini.api_key`、`gemini.model`
- **抽象层**：`ai_client.py`
  - 统一接口：`generate_text(prompt, model_type)`
  - 支持切换模型厂商

### 6. Web 界面（React）
- **页面**：
  1. 上传聊天记录页面
  2. 画像管理页面（查看/编辑）
  3. 推荐回复页面（输入当前对话 + 展示推荐回复）
- **交互**：
  - 上传文件 → 显示解析进度 → 成功/失败反馈
  - 输入对话 → 显示加载状态 → 展示推荐回复

---

## 技术栈

- **后端**：Python 3.10+ + FastAPI
- **数据库**：SQLite
- **RAG 框架**：LightRAG（https://github.com/HKUDS/LightRAG）
- **AI 模型**：
  - DeepSeek（画像生成、实体/关系提取）
  - Gemini（推荐回复生成）
- **前端**：React + Vite
- **依赖管理**：Poetry

---

## 目录结构

```
ChatHelper/
├── backend/
│   ├── main.py              # FastAPI 入口
│   ├── api/                 # API 路由
│   │   ├── __init__.py
│   │   ├── upload.py        # 上传聊天记录
│   │   ├── profile.py       # 画像管理
│   │   └── reply.py         # 推荐回复
│   ├── services/
│   │   ├── __init__.py
│   │   ├── parser_agent.py  # 子 Agent：格式识别与解析
│   │   ├── profile_service.py  # 画像生成与更新
│   │   ├── rag_service.py   # LightRAG 封装
│   │   └── ai_client.py     # AI 模型调用抽象层
│   ├── models/              # 数据库模型
│   │   ├── __init__.py
│   │   └── db.py
│   └── config.py            # 配置管理
├── frontend/                # React 前端
│   ├── src/
│   │   ├── App.jsx
│   │   ├── pages/
│   │   │   ├── Upload.jsx
│   │   │   ├── Profile.jsx
│   │   │   └── Reply.jsx
│   │   └── main.jsx
│   ├── package.json
│   └── vite.config.js
├── data/
│   ├── chathelper.db        # SQLite 数据库
│   └── lightrag/            # LightRAG 数据目录
├── config.yaml              # 配置文件
├── pyproject.toml           # Python 依赖
└── README.md
```

---

## 数据库设计

### `chat_records` 表
| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER PRIMARY KEY | 记录 ID |
| contact_id | TEXT | 联系人标识（用于区分不同聊天对象） |
| timestamp | DATETIME | 消息时间 |
| sender | TEXT | 发送者（user/contact） |
| message | TEXT | 消息内容 |
| created_at | DATETIME | 创建时间 |

### `profiles` 表
| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER PRIMARY KEY | 画像 ID |
| contact_id | TEXT UNIQUE | 联系人标识 |
| user_profile | TEXT | 用户画像（JSON） |
| contact_profile | TEXT | 联系人画像（JSON） |
| updated_at | DATETIME | 更新时间 |

---

## API 设计

### 1. 上传聊天记录
- **路由**：`POST /api/upload`
- **请求**：
  - `file`: 上传的文件
  - `contact_id`: 联系人标识
- **响应**：
  ```json
  {
    "success": true,
    "message": "解析成功",
    "records_count": 100
  }
  ```

### 2. 获取画像
- **路由**：`GET /api/profile/{contact_id}`
- **响应**：
  ```json
  {
    "contact_id": "friend_001",
    "user_profile": {...},
    "contact_profile": {...},
    "updated_at": "2026-04-23T10:00:00"
  }
  ```

### 3. 生成推荐回复
- **路由**：`POST /api/reply`
- **请求**：
  ```json
  {
    "contact_id": "friend_001",
    "current_context": "对方刚发了一条消息：明天一起吃饭吗？"
  }
  ```
- **响应**：
  ```json
  {
    "replies": [
      "好啊，几点？",
      "明天有点忙，改天吧",
      "可以，想吃什么？"
    ]
  }
  ```

---

## Done Contract

### 完成标准
1. **能上传并解析聊天记录** → 子 Agent 识别格式，解析后存入数据库
2. **能生成并持久化画像** → 首次生成 + 增量更新，数据库可查询
3. **LightRAG 可用** → 聊天记录导入，实体/关系提取成功，检索返回相关片段
4. **能生成推荐回复** → 结合画像 + RAG 上下文，Gemini 返回合理回复
5. **多模型可切换** → 修改配置文件后，系统调用对应模型
6. **Web 界面可用** → 本地启动服务，完整走通流程

### 证明方式
- **手动测试**：
  1. 上传不同格式聊天记录，验证解析正确
  2. 多次上传同一对象的记录，验证画像增量更新
  3. 输入当前对话，查看 RAG 检索结果与推荐回复
  4. 修改配置文件，验证不同模型调用成功
- **日志验证**：后端打印解析结果、画像更新、RAG 检索、AI 请求/响应
- **数据库验证**：查询 SQLite，确认数据正确存储

### 仍未完成的情况
- 子 Agent 无法识别某种格式
- 画像更新逻辑错误（如覆盖而非增量）
- LightRAG 实体提取失败或检索结果不相关
- AI 返回回复与人设明显不符
- 切换模型后调用失败

---

## 风险

1. **LightRAG 集成复杂度**：GraphRAG 实体/关系提取可能需要调优
2. **子 Agent 格式识别准确率**：AI 可能无法完美识别所有格式
3. **画像增量更新质量**：增量更新的 prompt 设计复杂
4. **DeepSeek API 限制**：国内厂商 API 可能有调用频率限制
5. **Gemini API 访问**：Gemini 在国内可能需要代理
6. **成本控制**：频繁调用 AI 可能产生高费用
7. **数据隐私**：聊天记录敏感，需明确告知用户

---

## 验证方式

- **单元测试**：子 Agent 解析、画像更新、RAG 检索、AI 调用
- **集成测试**：端到端流程（上传 → 解析 → 画像 → RAG → 推荐回复）
- **人工评审**：实际使用，判断推荐回复是否符合预期

---

---

## 实现记录

### 已完成（2026-04-23）

1. **项目骨架** ✅
   - 创建完整目录结构（backend/、frontend/、data/）
   - 配置文件 `config.yaml` 已创建

2. **后端核心模块** ✅
   - `backend/models/db.py`：SQLite 数据库模型（chat_records、profiles 表）
   - `backend/services/ai_client.py`：AI 调用抽象层（DeepSeek + Gemini）
   - `backend/services/parser_agent.py`：子 Agent 格式识别与解析
   - `backend/services/profile_service.py`：画像生成与增量更新
   - `backend/services/rag_service.py`：LightRAG 集成
   - `backend/api/upload.py`：上传聊天记录 API
   - `backend/api/profile.py`：画像管理 API
   - `backend/api/reply.py`：推荐回复 API
   - `backend/main.py`：FastAPI 入口，集成所有路由

3. **前端应用** ✅
   - React + Vite 项目结构
   - `frontend/src/pages/Upload.jsx`：上传页面
   - `frontend/src/pages/Profile.jsx`：画像管理页面
   - `frontend/src/pages/Reply.jsx`：推荐回复页面
   - `frontend/src/App.jsx`：路由配置
   - `frontend/vite.config.js`：Vite 配置（API 代理）
   - 完整样式（App.css）

4. **依赖配置** ✅
   - `pyproject.toml`：Python 依赖（FastAPI、LightRAG、OpenAI、Google Generative AI）
   - `frontend/package.json`：前端依赖（React、Vite、Axios）

5. **文档** ✅
   - `README.md`：项目说明、快速开始、API 文档

---

## 下一步：验证与测试

### 1. 安装依赖
```bash
# 后端
poetry install

# 前端
cd frontend
npm install
```

### 2. 配置 API 密钥
编辑 `config.yaml`，填入真实的 API 密钥：
```yaml
deepseek:
  api_key: "your-deepseek-api-key"
  
gemini:
  api_key: "your-gemini-api-key"
```

### 3. 启动服务
```bash
# 后端
python backend/main.py

# 前端（新终端）
cd frontend
npm run dev
```

### 4. 手动测试
1. 访问 http://localhost:5173
2. 上传聊天记录文件（测试格式识别与解析）
3. 查看画像（验证生成与持久化）
4. 输入当前对话（验证 RAG 检索与推荐回复）

### 5. 验证点
- [ ] 子 Agent 能识别并解析不同格式的聊天记录
- [ ] 画像生成成功并存入数据库
- [ ] 多次上传同一联系人记录，画像增量更新
- [ ] LightRAG 实体提取与检索正常
- [ ] Gemini 生成的推荐回复符合人设
- [ ] 切换配置文件中的模型后，系统调用对应模型

---

## 已知风险与待优化

1. **LightRAG Embedding 配置**：当前使用 OpenAI Embedding，需要 DeepSeek API 支持或切换到本地模型
2. **错误处理**：当前错误处理较简单，生产环境需增强
3. **日志系统**：缺少结构化日志，调试困难
4. **测试覆盖**：缺少单元测试与集成测试
5. **前端体验**：UI 较简陋，可优化交互与样式
6. **性能优化**：大文件上传、长聊天记录解析可能超时
