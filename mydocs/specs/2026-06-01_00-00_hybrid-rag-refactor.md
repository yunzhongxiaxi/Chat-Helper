# Hybrid RAG 重构 spec

## Restate
当前 `RAGService` 依赖 LightRAG 做实体/关系抽取和图谱式检索，对微信短文本聊天场景过重。核心目标是在保留 `insert_records(contact_id, records)` 与 `search(query, mode='hybrid')` 上层接口的前提下，替换为轻量的“话题优先 chunk + BM25 + embedding cosine 多路召回 + 规则重排序”。

## Scope
- 重写 `backend/services/rag_service.py`，移除 LightRAG 运行时依赖。
- 使用 SQLite 文件维护 `rag_topics` 与 `rag_chunks`，支持增量插入新记录产生的新 topic/sub-chunk。
- 话题切分优先使用时间间隔、短文本字符 n-gram 相似度、转场词；话题过长按消息数/字符数拆成 sub-chunk，保留同一个 `topic_id` 与 `topic_summary`。
- 检索时对 chunk 做 BM25 与 embedding cosine 召回，合并去重后用 BM25、cosine、recent、topic 多命中奖励重排序。
- 保留当前 embedding 配置；只对 sub-chunk 做 embedding，不对单条消息做 embedding。
- 不在本轮修改上传/回复接口；它们继续调用原 RAGService 方法。

## Done Contract
- `RAGService.insert_records(contact_id, records)` 可把记录写入本地 hybrid RAG 存储。
- `RAGService.search(query, mode='hybrid')` 可返回格式化历史片段字符串。
- 代码不再 import `lightrag`。
- 通过语法检查；在无真实 embedding 依赖的情况下，用 stub 验证插入和检索主流程。

## Change Log
- `backend/services/rag_service.py` 已重写为 SQLite 存储的 Hybrid RAG：`rag_topics` 保存话题，`rag_chunks` 保存可检索 sub-chunk、BM25 terms 和 embedding。
- 新增话题优先切分：时间间隔、话题长度上限、转场词、字符 n-gram overlap；长话题继续按消息数/字符数拆 sub-chunk。
- 新增 BM25 检索、embedding cosine 检索、hybrid 合并和规则重排序，结果保留 topic summary。
- `backend/config.py` 让旧 `config.lightrag` 属性优先读取 `hybrid_rag`，兼容现有调用。
- `config.yaml` 新增 `hybrid_rag` 阈值配置。
- `pyproject.toml` 移除 `lightrag-hku` 依赖；当前实现直接使用 `openai.AsyncOpenAI` 调 embedding。

## Validation
- 已运行：`python -m py_compile backend/services/rag_service.py backend/config.py`，通过。
- 已运行 stub 流程验证：插入 4 条测试消息，切成 2 个话题/2 个 chunk；`search('想吃火锅', 'bm25')` 与 `search('想吃火锅', 'hybrid')` 均返回火锅相关片段。
- 已确认主 `backend/services/rag_service.py` 不再 import `lightrag`；搜索结果中的旧引用来自 `.claude/worktrees` 临时工作树，不属于主代码路径。

## Resume or Handoff
当前核心目标已完成：RAG 模块已从 LightRAG 替换为话题 chunk + BM25 + embedding cosine + rerank。未用真实 embedding API 对大样本跑端到端上传检索；下一步建议用 `chat_history_sample.xlsx` 上传后抽几个查询验证召回质量与耗时。