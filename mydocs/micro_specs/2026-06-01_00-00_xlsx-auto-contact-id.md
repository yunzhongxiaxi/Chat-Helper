# XLSX 自动联系人 ID micro-spec

## Restate
当前 `/api/upload` 要求调用方通过 form-data 传 `contact_id`。用户选择改为：XLSX 上传时从文件前置信息自动解析微信 ID 作为 `contact_id`，如果请求显式传了 `contact_id` 则优先使用请求值；非 XLSX 文件仍要求传 `contact_id`。

## Scope
- 修改 `backend/api/upload.py`：`contact_id` 改为可选，XLSX 解析后确定最终联系人 ID。
- 修改 `backend/services/parser_agent.py`：提供 XLSX metadata 解析能力，读取 `微信ID` 与 `昵称`。
- 返回结果包含最终使用的 `contact_id`，以及能解析到的联系人 metadata。
- 不改数据库 schema，不持久化昵称。

## Done Contract
- 上传 `chat_history_sample.xlsx` 时，即使不传 `contact_id`，也能解析出 `wxid_mvznizhwxiju22` 并继续入库流程。
- 如果 form-data 传了 `contact_id`，使用传入值覆盖文件内微信 ID。
- 非 XLSX 且未传 `contact_id` 时返回明确错误。
- 通过语法检查与样例文件 metadata 解析 smoke test。

## Change Log
- `backend/api/upload.py` 将 `contact_id` 改为可选表单字段。
- XLSX 上传改为调用 `parser_agent.parse_xlsx(content)`，同时取得 `records` 与 `metadata`。
- XLSX 最终联系人 ID 使用 `请求 contact_id > 文件 metadata.contact_id` 的优先级。
- 非 XLSX 上传仍在缺少 `contact_id` 时返回明确 400 错误。
- 上传响应新增最终 `contact_id` 与解析到的 `metadata`。
- `backend/services/parser_agent.py` 新增 XLSX metadata 解析，读取 `微信ID`、`昵称`、`导出工具`、`导出时间`。

## Validation
- 已运行：`python -m py_compile backend/api/upload.py backend/services/parser_agent.py`，通过。
- 已对 `chat_history_sample.xlsx` 做 smoke test：解析 metadata 为 `{'contact_id': 'wxid_mvznizhwxiju22', 'nickname': '萍萍', 'export_tool': 'WeFlow', 'export_time': '2026-06-01 10:26:33'}`。
- 同一 smoke test 解析出 `220778` 条聊天记录。

## Resume or Handoff
当前核心目标已完成：XLSX 可以不传 `contact_id`，系统会从文件前置信息解析微信 ID；请求显式传入时仍优先使用请求值；非 XLSX 仍要求传入 `contact_id`。尚未做真实 HTTP multipart 上传端到端测试，如需更严格验收可补一个 FastAPI 测试。
