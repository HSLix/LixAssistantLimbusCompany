# User Agent 启用开关与配置编辑权影响审查

日期：2026-11-11。依据：本轮用户明确要求 Developer GUI 打开时，User GUI 仍可启用／停用 User Agent，只有具体配置冻结。

## 设计变化

- 原设计：Developer 打开时，整个 User Agent Settings 不可编辑（Stage 4「共享 Agent 配置」）。
- 新设计：User Agent 启用开关始终可操作；provider 选择、连接、模型、凭据和高级参数等具体配置继续由 Developer 独占编辑。沿用既有检查按钮冻结范围。
- 保留交接前提交、保存失败阻止打开 Developer、关闭后重读共享配置、活动快照及服务层活动互斥。无需数据迁移或新增配置。

## 已确认的影响

- `src/lalc/gui.py:GuiCoordinator.refresh_agent` 禁用 `agent_controls`，同时冻结开关与配置表单，与新要求冲突；应只禁用 `settings_page`。
- `UserWindow.save_user_enabled` → `agent_settings.save_selection` 读取当前 User provider 后，仅保存本侧选用项和启用标记，不写共享 profile；可复用，不应提交冻结的旧表单。
- `SettingsPage.submit/auto_save/save` 以表单的 `isEnabled()` 阻止旧配置回写；缩小禁用范围后必须保持表单禁用。`GuiCoordinator.closed` 已在交还编辑权前 reload，保留该流程。
- `tests/test_user_pages.py` 的交接、无效文本交接及真实进程重载测试断言整卡禁用，需同步改为表单禁用，并增加开关双向持久化、不覆盖 Developer 更新、冻结表单不回写及关闭后恢复检查。
- `docs/stage-4-extensible-user-gui.md` 和 `docs/agent-repair.md` 的独占编辑描述需明确开关例外。其他调用、数据格式与导出无需修改。

## 后续行动与验证边界

1. 同步现行规格和用法，缩小一个 UI 禁用目标。
2. 更新上述测试，执行 User 页面、双窗口及设置持久化的聚焦普通回归。
3. Windows 原生点击和真实模型／游戏行为本轮未观察，属于待验收风险；本次 UI 与持久化检查不能替代这些证据。不启动真实 Agent 测试。

## 实施与检查结果

- 已将禁用目标从整卡缩到 `settings_page`，复用现有启用开关保存路径；已同步规格、用法与当前状态入口。
- 聚焦普通回归：`QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest -q tests/test_user_pages.py tests/test_user_gui.py tests/test_agent_settings.py`：**74 passed，4 skipped**，退出 0。跳过项不计为通过，未开启 Agent 测试。
- 覆盖 Developer 打开时双向切换并持久化、保留共享 profile 与两侧 provider 选择、冻结表单不回写、关闭后恢复最新配置，以及双窗口／设置持久化既有行为。`git diff --check` 通过。
