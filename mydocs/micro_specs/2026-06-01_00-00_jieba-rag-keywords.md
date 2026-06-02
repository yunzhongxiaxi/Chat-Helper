# jieba 关键词提取优化 micro-spec

## Restate
当前 RAG topic summary 和 BM25 词项使用字符/bigram 频率，导致关键词出现 `我就`、`就是`、`妈他` 等噪声。用户希望一步步优化，第一步先引入 `jieba` 做中文分词和停用词过滤，提升关键词质量；暂不同时改 topic 切分策略，避免一次改动过大。

## Scope
- 在依赖中加入 `jieba`。
- 修改 `backend/services/rag_service.py` 的 `_tokenize()` / `_top_terms()`。
- 中文文本使用 jieba 分词，英文/数字仍保留基础 token。
- 增加中文停用词和无效 token 过滤，避免人称代词、语气词、功能词、纯数字时间片段进入关键词。
- 保持 RAG 表结构、父子索引检索流程、embedding provider 不变。
- 本轮不修改 topic/chunk 切分规则。

## Done Contract
- 深圳自我介绍样例不再产出 `我就`、`就是`、`是我`、`妈他` 等 bigram 噪声关键词。
- `_top_terms()` 能产出更接近语义的词，如 `深圳`、`爸妈`、`长大`。
- 现有 RAG 构建/search 代码能正常语法检查。
- 轻量样例验证通过。

## Risks
- jieba 分词会改变 BM25 terms，已有数据库中的 `terms_json` 仍是旧策略；要让检索完全使用新策略，需要重建 RAG 索引。
- 停用词表过 aggressive 可能过滤掉部分有用短词；先采用保守规则，后续可根据样例继续调整。

## Change Log
- `pyproject.toml` 已加入 `jieba>=0.42.1`，并通过 `uv add jieba` 安装到当前虚拟环境。
- `backend/services/rag_service.py` 已引入 jieba。
- `_tokenize()` 改为英文/数字基础 token + jieba 中文分词。
- 新增 `STOPWORDS`、`_is_valid_term()`、`_is_valid_number_term()` 过滤人称代词、语气词、功能词、短数字时间片段和无效符号。
- `_top_terms()` 直接基于过滤后的分词结果统计高频词。

## Validation
- 已运行：`.venv/Scripts/python.exe -m py_compile backend/services/rag_service.py`，通过。
- 已运行样例验证：`我就是我爸妈他们来深圳了 我就在深圳长大的 来了就是深圳人` 输出关键词 `['深圳', '爸妈', '长大']`。
- 样例中 `我就`、`就是`、`是我`、`妈他`、`他们` 均未进入关键词。

## Resume or Handoff
第一步关键词提取优化已完成。下一步可以单独优化 topic 切分策略：移除短句相邻 overlap 强切分，增加最小 topic 消息数/字符数，让自我介绍这类连续上下文更容易归入同一 topic。
