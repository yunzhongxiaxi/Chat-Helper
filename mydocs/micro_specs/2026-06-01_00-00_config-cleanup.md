# 配置清理 micro-spec

## Restate
用户希望配置风格保持一致：embedding 的 API key 不再走环境变量，而是和其他模型一样直接写在 `config.yaml`；同时 LightRAG 已移除，`entity_extraction` 不再使用，需要从配置和说明中清理。

## Scope
- 修改 `config.yaml`：删除 `models.entity_extraction`；将 `models.embedding.api_key` 改为用户提供的 DashScope key。
- 修改 `backend/config.py`：去掉环境变量展开逻辑与用途注释中的 `entity_extraction`。
- 保持 DashScope embedding 的 `base_url` 与 `model=text-embedding-v4` 不变。

## Done Contract
- `config.yaml` 中不再有 `entity_extraction` 配置。
- `embedding.api_key` 与其他模型一样直接来自 YAML。
- 通过语法检查；grep 不应在主配置代码中发现 `entity_extraction`。

## Change Log
- `config.yaml` 删除 `models.entity_extraction`。
- `config.yaml` 的 `models.embedding.api_key` 已改为直接 YAML 配置，并保留 DashScope `text-embedding-v4` 与兼容 OpenAI `base_url`。
- `backend/config.py` 移除 `${ENV_VAR}` 展开逻辑，并清理用途说明。
- `backend/services/parser_agent.py` 的 LLM 解析 fallback 改用 `profile_generation` 配置。
- `backend/services/message_rewriter_agent.py` 的潜台词分析改用 `reply_generation` 配置。
- `backend/services/ai_client.py` 清理 `entity_extraction` 注释。

## Validation
- 已运行：`python -m py_compile backend/config.py backend/services/parser_agent.py backend/services/message_rewriter_agent.py backend/services/ai_client.py`，通过。
- 已 grep 主配置/服务代码：不再出现 `entity_extraction` 或 `DASHSCOPE_API_KEY`；剩余 `import re/os` 是其他模块正常使用。

## Resume or Handoff
当前核心目标已完成。注意真实 API key 已写入 `config.yaml`，不要提交到公开仓库或截图外发。