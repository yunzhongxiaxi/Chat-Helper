# RAG topic 切分优化 micro-spec

## Restate
当前 RAG topic 切分过度依赖相邻消息词重合度，短句聊天很容易被误切成多个小 topic。用户给出的深圳自我介绍上下文语义连续，却被拆成多个 topic/chunk。第一步已完成 jieba 关键词优化；下一步单独优化 topic boundary 规则，让连续短消息默认合并，只有时间断开、明确转场、或长度上限才切分。

## Scope
- 修改 `backend/services/rag_service.py`。
- 新增最小 topic 消息数/字符数配置默认值。
- 在未达到最小 topic 大小前，不因词重合度低而切 topic。
- 只对较长、信息量足够的新消息使用相邻 overlap 判断，并降低其切分优先级。
- 保留强切分条件：时间间隔超过阈值、topic 达到最大消息数/字符数。
- 明确转场词仅在当前 topic 已达到最小大小后切分，避免开头短句被误切。
- 不改 chunk 长度切分、不改 embedding provider、不改数据库 schema。

## Done Contract
- 深圳自我介绍样例能保持在同一个 topic 中。
- topic 切分仍会在长时间间隔或超过最大 topic 长度时发生。
- 现有 RAG service 语法检查通过。
- micro-spec 回写变更与验证结果。

## Risks
- topic 合并更积极后，部分真实话题边界会变粗；后续可用更强的语义模型或 LLM summary 做二阶段切分。
- 已有 RAG 数据库仍是旧 topic/chunk 切分结果；要看到真实效果需要重建 RAG 索引。
