# RAG topic 显著性降权 micro-spec

## Restate
用户选择“保留低信息量聊天，但在检索时降权”的方案。当前 topic keywords 仍可能缺乏信息量，且闲聊寒暄类 topic 不应频繁被 RAG 召回；需要让 LLM topic 摘要同时判断 topic 的信息价值，并在检索排序中使用该信号。

## Scope
- 修改 `backend/services/rag_service.py`。
- LLM topic summary schema 增加 `salience`、`category`、`indexable`。
- `rag_topics` 表增加 `salience`、`category`、`indexable` 列。
- topic 构建时保存显著性元数据；chunk 加载时从父 topic 继承这些元数据。
- 检索 rerank 时对低 salience / 非 indexable 的 topic chunk 降权，而不是删除。
- fallback 摘要默认可索引但中等显著性，避免 LLM 失败导致构建中断。

## Done Contract
- 低信息量 topic 仍入库，但有较低 `salience` 或 `indexable=false`。
- rerank 对低信息量 chunk 降权，减少闲聊寒暄被召回。
- 语法检查通过。
- 小样本验证能写入 salience/category/indexable，并可读取到 chunk 上。

## Change Log
- `TopicSummaryResult` 增加 `salience`、`category`、`indexable` 字段。
- `rag_topics` 表增加 `salience`、`category`、`indexable` 列，并通过 `_ensure_column()` 兼容旧库。
- LLM topic summary prompt 增加信息价值评分规则：寒暄/表情/无实质内容低分，偏好/经历/地点/关系/计划/事件高分。
- topic 写库时保存显著性元数据。
- `_load_chunks()` 通过 JOIN 父 topic 读取 salience/category/indexable，让 chunk 继承父 topic 信息价值。
- `_load_topics()` 读取显著性元数据。
- `_rerank()` 对低 salience 或 `indexable=false` 的 chunk 做降权，不做硬删除。

## Validation
- 已运行：`.venv/Scripts/python.exe -m py_compile backend/services/rag_service.py`，通过。
- 已运行 40 条真实 XLSX 样本构建验证：写入 `4` 个 topic / `4` 个 chunk，embedding `8` 段文本。
- 验证样例：朋友圈/小号解释 topic 写入 `salience=0.55`、`category=生活偏好`、`indexable=1`。
- 验证样例：父母来深/江西/深圳身份 topic 写入 `salience=0.65`、`category=地点经历`、`indexable=1`。
- 验证 chunk 能从父 topic 读取 salience/category/indexable。
- 验证后已清空测试写入的 `rag_topics` / `rag_chunks`。

## Resume or Handoff
当前核心目标已完成：低信息量聊天会保留入库，但检索排序时会按 topic salience/indexable 降权。下一步可以重新正式流式构建 RAG。
