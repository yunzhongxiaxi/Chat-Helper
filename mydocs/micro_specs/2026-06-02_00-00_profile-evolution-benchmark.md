# 人物画像功能测评 micro-spec

## Restate
接下来需要测评人物画像功能，不再追求一次性全量处理所有聊天记录。测评应尽量复用已经流式构建出的 RAG topic/chunk，把完整 topic chunks 分批送入画像生成/更新流程，观察画像是否能随着新增话题逐步形成稳定特征、近期信号和变化记录，并输出可量化指标。

## Scope
- 新增 `scripts/benchmark_profile_evolution.py`。
- 输入优先使用当前实际 RAG DB 中已构建的 `rag_chunks`，而不是从原始消息中抽样。
- 按时间顺序分批处理完整 chunks；每批包含多个 chunks，以降低 LLM 调用次数。
- 使用正式 `config.database.path` 指向的现有 SQLite 保存 profile 测评结果，便于后续继续调试。
- 调用现有 `ProfileService.generate_profile()`，测评当前画像功能本身，不先重构画像逻辑。
- 输出指标：chunk 数、消息数、批次数、耗时、每批画像字段覆盖情况、stable/recent/changed 数量变化。
- 输出最终 user/contact profile 摘要预览，便于人工判断质量。

## Done Contract
- 脚本能基于已有 RAG chunks 分批生成/更新画像。
- 脚本能输出画像演化相关量化指标。
- 画像结果保存到现有正式 SQLite 的 `profiles` 表，方便后续调试复用。
- 语法检查通过，并先用小批次数运行一次。

## Risks
- 当前 `ProfileService` 仍把 records 直接拼成 prompt，长 chunk 批次可能导致 token 较多；默认先限制批次数做小规模测评。
- DeepSeek profile_generation 会产生外部 API 成本；通过按 chunk 批处理和小规模运行控制成本。

## Change Log
- 新增 `scripts/benchmark_profile_evolution.py`。
- 脚本从当前 Hybrid RAG SQLite 的 `rag_chunks` 读取已构建 chunk，按 `start_time/end_time/id` 排序。
- 将 raw-only `chunk_text` 解析回 `{timestamp, sender, message}` records，再分批调用 `ProfileService.generate_profile()`。
- 默认写入正式 `config.database.path` 指向的 `profiles` 表；可通过 `--profile-contact-id` 指定写入画像使用的 contact_id。
- 输出每批 chunk 数、消息数、耗时、user/contact 当前字段覆盖数、stable/recent/changed 数量，并输出最终画像预览。

## Validation
- 已运行：`.venv/Scripts/python.exe -m py_compile scripts/benchmark_profile_evolution.py`，通过。
- 已运行小规模测评：`.venv/Scripts/python.exe scripts/benchmark_profile_evolution.py --batch-chunks 3 --max-batches 1`。
- 小规模测评读取 `3` 个 chunk，解析 `30` 条消息，调用画像生成耗时约 `7.78s`。
- 小规模测评写入现有 `data/chathelper.db` 的 `profiles` 表，contact_id 为 `wxid_mvznizhwxiju22`。
- 首批结果：user 当前画像字段 `5`，stable `2`，recent `2`，changed `0`；contact 当前画像字段 `5`，stable `2`，recent `2`，changed `0`。
- 扩大测评首次运行到第 2 批时暴露 profile_generation 偶发返回非纯 JSON / Markdown 包裹内容，`json.loads(response)` 直接失败。
- 已在 `backend/services/profile_service.py` 增加 `_parse_profile_response()`，先解析纯 JSON，失败后提取 fenced JSON 或首个 JSON 对象再解析。
- 已运行：`.venv/Scripts/python.exe -m py_compile backend/services/profile_service.py scripts/benchmark_profile_evolution.py`，通过。
- 已运行扩大测评：`.venv/Scripts/python.exe scripts/benchmark_profile_evolution.py --batch-chunks 8 --max-batches 3`。
- 扩大测评读取 `24` 个 chunk，解析 `190` 条消息，处理 `3` 批，总耗时约 `73.54s`。
- 扩大测评演进指标：Batch 1 user/contact stable `5/5` recent `3/3` changed `0/0`；Batch 2 stable `5/5` recent `3/4` changed `0/0`；Batch 3 stable `6/5` recent `5/5` changed `1/1`。
- 终端中文预览在当前 Windows bash 输出中出现编码乱码，但指标与写库流程已完成；如需人工审阅画像正文，可直接读取 SQLite 中 JSON 或调整终端编码后重跑。

## Resume or Handoff
当前小规模画像演化测评已经跑通并写入正式 SQLite。下一步若要观察“逐步稳定/近期信号/变化记录”的演化质量，可以增加 `--max-batches`，例如保持 `--batch-chunks 8` 并逐步从 `--max-batches 3` 扩到更多批次，以控制 DeepSeek API 成本。
