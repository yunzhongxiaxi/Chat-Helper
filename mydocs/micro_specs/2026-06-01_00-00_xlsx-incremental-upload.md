# XLSX 解析与增量上传 micro-spec

## Restate
当前上传接口默认把文件按 UTF-8 文本解码，无法解析 `chat_history_sample.xlsx`。样例文件是 WeFlow 导出的 XLSX：第 5 行为表头 `序号/时间/发送者身份/消息类型/内容`，第 6 行开始是消息数据，约 22 万行。核心目标是内置 XLSX 解析，并在同一联系人重复上传包含历史+新增内容的文件时，只对新增消息做入库、画像更新和 RAG 插入。

## Scope
- 修改 `backend/api/upload.py`，按文件扩展名处理 `.xlsx`，避免二进制文件走 UTF-8 解码。
- 修改 `backend/services/parser_agent.py`，添加零 LLM 的内置 XLSX 解析，输出统一 `timestamp/sender/message`。
- 修改 `backend/models/db.py`，添加重复消息去重能力；优先用 `(contact_id, timestamp, sender, message)` 判重。
- 上传流程只把新增记录传给 `ProfileService.generate_profile` 和 `RAGService.insert_records`。
- 不做数据库破坏性迁移；用兼容式 `CREATE UNIQUE INDEX IF NOT EXISTS`，若旧库已有重复数据导致索引创建失败，则仍用查询过滤保证本次上传不重复处理。

## Done Contract
- `chat_history_sample.xlsx` 可被解析出消息记录，且无需 LLM。
- 重复上传同一文件时，第二次应返回 0 条新增记录，并跳过画像/RAG 更新。
- 通过语法检查和一个本地临时库去重验证证明核心逻辑有效。

## Change Log
- `backend/services/parser_agent.py` 新增内置 XLSX 解析器，直接读取 OpenXML zip，支持 WeFlow 表头 `时间/发送者身份/内容`。
- `backend/api/upload.py` 按扩展名分流 `.xlsx`，并只把新增记录传给画像更新和 RAG 插入。
- `backend/models/db.py` 新增 `insert_new_chat_records`，用 `(contact_id, timestamp, sender, message)` 判重；保留 `insert_chat_records` 兼容旧调用。

## Validation
- 已运行：`python -m py_compile backend/services/parser_agent.py backend/models/db.py backend/api/upload.py`，通过。
- 已运行样例解析：`chat_history_sample.xlsx` 解析出 220778 条记录，首条为 `2025-02-16 18:56:30/contact/我是💯`，末条为 `2026-06-01 10:16:24/contact/小红书真给我发免单券了`。
- 已运行临时 SQLite 去重验证：首次插入 2 条，重复插入 0 条，追加 1 条时只返回 1 条新增。

## Resume or Handoff
当前核心目标已完成：XLSX 可内置解析，重复上传只处理新增记录。未启动 FastAPI 做真实 HTTP 上传验证；如需下一步，建议用 `/run` 或手动启动服务上传样例文件检查接口响应。