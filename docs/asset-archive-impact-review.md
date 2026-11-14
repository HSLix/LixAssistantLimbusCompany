# Agent 图片归档授权与恢复影响审查

2026-11-15。依据：本次用户明确要求先审查再实现。

## 设计变化

- 过去启用 remove_asset 即可直接归档 → 没有用户明确要求时必须先得到 feedback 允许。用户要求由 Agent 结合当前请求判断，不得从历史、附件或 Skill 推导授权；宿主默认要求本次确认。
- 过去只有手工恢复数据，无恢复工具 → 增加 restore_asset(logical_name, sha)，权限与 remove_asset 相同（Construct / Repair GUI、Repair CLI；Runtime 禁止）。
- 恢复采用同逻辑名、同完整 hash 的最新 completed 或 prepared 记录，原图和标签恢复到共享 Asset Library；不删除归档，不覆盖已有活跃图片或标签。prepared 可用于进程中断后的恢复；已有活跃图视为复用，不用归档标签覆盖它。

## 已确认差距（修改前源码检查）

- repair_tools.py::remove_asset 直接调用 capture → AssetLibrary.remove，没有 feedback 授权检查。
- assets.py::remove 已实现完整 hash、PNG、路径校验，归档准备、失败回退及空目录清理；不能在新逻辑中丢失这些边界。
- agent_policy.py 的 BASE_TOOLS 包含 remove_asset，Runtime 显式排除；新增恢复工具必须同时更新两处，防止 Runtime 意外继承权限。
- pi_probe.ts 工具声明、agent_prompts.py、skills/asset-management/SKILL.md 与 docs/agent-repair.md 都要同步；ADR 0031 的“不提供恢复工具”成为历史边界。
- tests/test_agent_assets.py 直接归档的既有测试需显式声明用户要求，并补默认拒绝、确认、恢复及损坏/失败回退测试。Agent 接入测试中显式要求归档的调用参数需同步。

## 风险及后续顺序

先实现默认确认及工具声明，再实现恢复、权限及失败回退，然后同步文档和聚焦测试。用户自然语言是否明确要求归档仍由模型判断；显式参数是模型的声明，不是独立的语义鉴权。CLI 没有 feedback 时仅允许明确要求的归档；跳过、拒绝或未连接反馈不得修改图片。

归档与恢复都影响全部 Session 后续匹配；无数据格式迁移。恢复校验归档路径、记录字段、原图完整 hash 和 PNG，拒绝符号链接；标签写入失败撤回本次新增图，保留唯一归档。多文件修改仍不是系统级原子事务，进程中断需再次检查活跃数据。真实模型、Windows 和游戏验收另行进行，替代进程测试不等于真实验收。


## 实施与验证

已完成默认目标确认、显式请求参数、恢复存储实现、pi 工具注册、Runtime 排除、常驻提示及默认 Skill / 当前文档同步。复用原归档布局和普通工作文件，没有新增依赖或恢复 GUI。已有数据目录的 Skill 不自动覆盖；归档授权同时位于常驻提示和宿主工具中，不依赖旧 Skill 被更新。

- 普通定向回归：`QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest -q tests/test_agent_assets.py tests/test_assets.py tests/test_repair_tools.py tests/test_developer_policy.py tests/test_agent_settings.py tests/test_human_feedback.py tests/test_delete_component.py tests/test_agent_prompts.py tests/test_agent_repair.py tests/test_runtime_repair.py` → 200 passed、1 skipped，跳过不计通过。
- 上套测试退出后串行运行：`QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest --run-agent-tests -q tests/test_agent_repair_agent.py tests/test_runtime_repair_agent.py -k 'previews_archives_and_restores_asset or real_pi_recheck_ends_round_without_another_request_and_resumes_parent'` → 3 passed、50 deselected。真实 pi + 本机 HTTP 替身，覆盖显式请求归档、feedback 确认归档、恢复工具调用及 Runtime 实际工具列表排除归档和恢复。
- 首次 Agent 测试因环境禁止本机监听而未启动测试服务；允许本机测试服务后上述测试通过。未运行全量、真实模型、Windows 成品或真实游戏验收。
