# 用户画像时间演变 micro-spec

## Restate
当前 `ProfileService` 只用现有画像和新增记录做一次增量合并，长跨度聊天容易把早期与近期特征平均化。核心目标是让画像结构和提示词显式表达“当前画像、长期稳定特征、变化轨迹、近期信号”，并在生成当前回复时优先使用近期特征。

## Scope
- 修改 `backend/services/profile_service.py` 的画像生成/更新 schema 与 prompt。
- 轻量适配回复生成与反馈记录，使其优先读取 `current_profile` 与 `recent_signals`。
- 保持现有 `profiles.user_profile/contact_profile` 存储方式，不做数据库迁移。
- 必要时保持旧画像可继续作为输入被新 prompt 升级。

## Done Contract
- 新建画像和增量更新都会要求输出 `current_profile/stable_traits/changed_traits/recent_signals`。
- 更新 prompt 明确比较旧画像与新增记录，区分保留、削弱、转变和近期状态。
- 通过至少语法检查证明代码可加载；若未能运行完整应用，需说明。

## Plan
1. 在 `ProfileService` 中集中定义演变画像 JSON schema 文本。
2. 更新 `_create_profile` prompt，让首次生成也带时间演变结构。
3. 更新 `_update_profile` prompt，让增量更新维护变化轨迹且近期加权。
4. 轻量适配回复生成与反馈记录，使当前回复优先使用近期画像。
5. 运行轻量验证。

## Change Log
- `backend/services/profile_service.py` 新增演变画像 schema，并更新创建/增量更新 prompt。
- `backend/api/reply.py` 的回复生成 prompt 明确优先使用 `current_profile` 和 `recent_signals`。
- `backend/services/evaluator_service.py` 的评估 prompt 与反馈摘要兼容新旧画像结构。

## Validation
- 已运行：`python -m py_compile backend/services/profile_service.py backend/api/reply.py backend/services/evaluator_service.py`
- 结果：通过，无编译错误。

## Resume or Handoff
当前核心目标已由代码修改和语法检查证明完成。未运行完整应用或端到端上传/回复流程；如需更强证据，下一步应启动服务并用一段跨时间聊天样例验证输出 JSON 结构。