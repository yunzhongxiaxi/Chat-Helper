# DashScope Embedding 配置 micro-spec

## Restate
用户希望把 embedding API 配置为阿里云百炼 OpenAI 兼容接口：`base_url=https://dashscope.aliyuncs.com/compatible-mode/v1`，`model=text-embedding-v4`。用户提供了 API key，但核心目标是不把密钥硬编码进仓库，而是让配置读取 `DASHSCOPE_API_KEY` 环境变量。

## Scope
- 修改 `config.yaml` 的 `models.embedding` 为 DashScope embedding 配置。
- 修改 `backend/config.py`，支持配置值中的 `${ENV_VAR}` 环境变量展开。
- 不把真实 API key 写入任何 tracked 配置文件。

## Change Log
- `config.yaml` 的 `models.embedding` 已改为 DashScope OpenAI 兼容配置：`text-embedding-v4` + `https://dashscope.aliyuncs.com/compatible-mode/v1`。
- `backend/config.py` 新增 `${ENV_VAR}` 展开逻辑，当前通过 `${DASHSCOPE_API_KEY}` 读取密钥。
- 未将用户提供的真实 API key 写入仓库文件。

## Validation
- 已运行：`python -m py_compile backend/config.py backend/services/rag_service.py`，通过。
- 因当前环境缺少 `pyyaml`，直接 import 真实 config 的 smoke test 无法运行；已用 yaml stub 验证 `${DASHSCOPE_API_KEY}` 能展开为运行时环境变量。

## Resume or Handoff
当前核心目标已完成。运行服务前需要在 shell 环境中设置：`export DASHSCOPE_API_KEY='你的 key'`；Windows PowerShell 使用 `$env:DASHSCOPE_API_KEY='你的 key'`。