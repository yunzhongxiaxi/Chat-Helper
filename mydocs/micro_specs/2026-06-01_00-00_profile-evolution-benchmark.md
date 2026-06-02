# 分批画像演化 benchmark micro-spec

## Restate
为简历补充“人物画像动态调整”的量化证据：将 `chat_history_sample.xlsx` 按时间顺序划分为早/中/近三个阶段，第一阶段生成初始画像，后续阶段只处理新增内容；新增内容不做代表性消息抽样，而是按话题 chunk 完整交给画像更新逻辑参考现有画像判断是否产生新特征、稳定特征或变化特征。

## Scope
- 新增一个 benchmark 脚本，输入仍使用 `chat_history_sample.xlsx`。
- 将记录按时间顺序分 3 批，模拟“初始导入 + 两次新增聊天记录”。
- 第一批生成初始画像；第二、三批作为新增内容更新画像。
- 每批新增内容先按现有 RAG 的话题切分逻辑形成 topic chunks，再让大模型围绕这些新增 chunks 和现有画像做增量更新。
- 每批保存画像快照与指标到本地 benchmark 输出文件，便于后续分析和简历取数。
- 记录指标：批次序号、批次消息数、批次 topic 数、累计消息数、时间范围、生成/更新耗时、画像 JSON 字符数、stable traits 数、changed traits 数、recent signals 数。
- 本轮不改数据库 schema，不做自动质量评价，不使用随机/代表性抽样替代完整新增 chunk。

## Done Contract
- 脚本支持 3 批阶段化处理，且每批处理完整新增阶段内容。
- 脚本每跑完一个批次就落盘结果，避免中途失败导致前面结果丢失。
- 输出能看出每批画像的 `current_profile`、`stable_traits`、`changed_traits`、`recent_signals` 是否变化。
- 输出能统计每批新增消息数、topic chunk 数、更新耗时和画像变化数量。
- 产出一组初始 benchmark 数据，可用于判断人物画像动态调整是否足够明显。

## Risks
- 每批都会调用画像生成/更新模型，真实 API 成本高于纯 DB benchmark。
- 如果直接把某阶段所有 topic chunks 一次性塞进 prompt，可能超过模型上下文，需要脚本先做 chunk 级分轮更新或压缩为每个 topic 的结构化摘要。
- 当前 `ProfileService` 会把画像写入真实数据库；这符合本轮要求，但会覆盖该联系人的当前画像。

## Checkpoint
下一步先检查现有 RAG topic chunk 切分能力是否能复用；如果可以，benchmark 脚本将按 3 个时间阶段处理完整新增 chunks，并逐阶段记录画像快照与指标。不会再采用“每批 200 条”或“抽样 2000 条代表性消息”的方案。
