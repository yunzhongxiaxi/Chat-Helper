# 真实聊天数据 RAG benchmark micro-spec

## Restate
使用 `chat_history_sample.xlsx` 对 RAG 父子索引优化做真实数据测试。用户确认使用真实 embedding、真实 RAG 数据库，并处理全量 XLSX 数据；跑一次成本较高但结果要保留下来，供后续调试和简历指标复用。

## Scope
- 新增真实数据 benchmark 脚本。
- 输入使用 `chat_history_sample.xlsx` 全量记录。
- 使用真实 RAG topic/chunk 切分逻辑。
- 使用真实 embedding API 构建 topic/chunk embedding 与 query embedding。
- 使用项目配置的实际 RAG 数据库，保留索引结果。
- 输出指标：记录数、topic 数、chunk 数、topic 扩展候选数、chunk-only 覆盖率、parent-child 覆盖率、额外召回 sibling chunks、embedding 文本数、构建耗时、查询耗时。
- benchmark 可以重复运行；底层 RAG 使用 `INSERT OR IGNORE` 避免重复插入已有 topic/chunk。

## Done Contract
- 脚本能读取真实 XLSX 全量数据。
- 脚本能用真实记录构建实际 RAG 索引。
- 脚本能使用真实 embedding API 完成构建与查询。
- 脚本能选择若干真实 query 或自动从真实 topic 生成 query。
- 输出 chunk-only vs parent-child 的对比指标。
- 通过语法检查与运行验证。

## Risks
- 全量 XLSX 约 22 万条记录，真实 embedding 会产生较多 API 调用和耗时。
- 当前 `insert_records` 会为 topic 与 chunk 一起生成 embedding，即使已有记录因 `INSERT OR IGNORE` 跳过，也仍可能先产生 embedding 调用。
- 真实聊天内容可能主题零散，自动 query 不一定代表真实用户提问。
- 真实 embedding API 当前返回 `Arrearage`：`Access denied, please make sure your account is in good standing`，说明阿里云百炼账号欠费或不可用。
- 在账号恢复前，无法完成真实 embedding 全量 RAG benchmark。

## Change Log
- 已切换到本地 Ollama `qwen3-embedding:4b` 后完成真实全量 benchmark。
- 实际 RAG 数据库 `data/hybrid_rag/hybrid_rag.db` 已写入索引结果。
- 本次构建处理 `220778` 条记录，生成 `67227` 个话题与 `67260` 个 chunk，新增 embedding 文本 `134487` 段。

## Validation
- 全量 benchmark 命令已完成且 exit code 为 0。
- XLSX 解析：`220778` 条记录，零 LLM 调用。
- 构建耗时：`4012.85s`。
- embedding 调用次数：`13449`，embedding 文本数：`134487`。
- 查询评估耗时：`732.40s`，query 数：`5`。
- 平均 chunk-only 覆盖率：`20.00%`。
- 平均 parent-child 覆盖率：`20.00%`。
- 平均覆盖率提升：`0.00` 个百分点。
- 总额外召回 sibling chunks：`22`。

## Resume or Handoff
当前真实全量 benchmark 已完成，但自动生成 query 质量较差，多数 query 是时间/数字片段，导致覆盖率指标不能代表真实用户检索效果。下一步应优化 benchmark 的 query 生成方式，使用真实消息内容或人工挑选语义 query，再重新评估父子索引带来的召回提升。
