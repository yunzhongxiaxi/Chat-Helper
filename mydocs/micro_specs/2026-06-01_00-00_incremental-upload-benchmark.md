# 增量上传 benchmark micro-spec

## Restate
为简历补充量化指标，先只测试 XLSX 解析与数据库去重效果，不启动完整 FastAPI 服务，不调用画像生成、RAG 或 LLM。用户明确要求不要使用临时数据库，而是写入项目配置的真实数据库，便于后续调试复用。

## Scope
- 新增一个可重复运行的 benchmark 脚本。
- 输入使用项目根目录的 `chat_history_sample.xlsx`。
- 使用项目配置的 SQLite 数据库，保留导入结果供后续画像、RAG、接口调试使用。
- 统计首次/当前导入与重复导入的记录数、耗时、跳过率。
- 本轮不测试真实 HTTP 上传、不测试画像/RAG、不测试 embedding。

## Done Contract
- 脚本能解析样例 XLSX。
- 导入使用 XLSX metadata 中的 `contact_id`。
- 重复运行时应能体现新增数下降、跳过数上升。
- 连续执行两次插入检查时，第二次新增数应为 0，跳过数应等于解析记录数。
- 输出可直接用于简历措辞的核心指标。

## Change Log
- 新增 `scripts/benchmark_incremental_upload.py`。
- benchmark 读取 `chat_history_sample.xlsx`，解析 XLSX metadata 中的 `contact_id` 与昵称。
- benchmark 使用 `config.yaml` 配置的 SQLite 数据库路径，直接调用 `Database.insert_new_chat_records`。
- benchmark 输出解析耗时、当前导入新增/跳过/跳过率/耗时，以及紧接着重复导入的同类指标。

## Validation
- 已运行：`python -m py_compile scripts/benchmark_incremental_upload.py`，通过。
- 直接 `python` 与 `.venv/Scripts/python.exe` 缺少 `yaml` 依赖，改用 `uv run` 按 `pyproject.toml` 环境执行。
- Windows 默认 GBK 输出会因 `✓` 字符报编码错误，已用 `PYTHONIOENCODING=utf-8` 执行成功。
- 成功命令：`PYTHONIOENCODING=utf-8 uv run python scripts/benchmark_incremental_upload.py`。
- 样例解析记录数：`220778`。
- XLSX 解析耗时：`3.55s`。
- 当前导入：新增 `220615` 条，跳过 `163` 条，跳过率 `0.07%`，入库耗时 `0.92s`。
- 紧接着重复导入：新增 `0` 条，跳过 `220778` 条，跳过率 `100.00%`，入库耗时 `4.50s`。

## Resume or Handoff
当前核心目标已完成：已有可重复运行的增量导入 benchmark，并已产出一组可用于简历的真实数据。后续如果要继续量化，建议下一步单独测“chunk 级 embedding 相比逐消息 embedding 的请求数/成本下降”。
