# 新聊天默认来源与历史选中状态影响审查

2026-11-14，依据本次用户明确需求，先完成只读审查，再实施修改。

## 设计变化

- 新聊天来源由默认空白改为默认选择最新已发布 Manifest；第一项仍保留空白入口，无版本时保持该项。最新按既有 `ManifestManager.list_manifests()` 发布时间倒序确定，不等同于 Default。
- 新聊天不对应任何历史 Session，侧栏不得残留上一个 Session 的选中样式。
- 手动选择空白后刷新列表仍保留选择；恢复历史 Session 仍使用其固定来源。Construct 可空白、Repair 必须有来源、首条消息才创建 Session 的规则不变，无数据迁移。

## 已确认的影响与差距（修改前源码证据）

- `src/lalc/developer_gui.py:RepairPage.__init__ / new / set_manifests`：初始化填充列表保留 None，`new()` 又显式选第 0 项，故有版本时也默认空白。`src/lalc/manifest.py:ManifestManager.list_manifests` 已按 `saved_at` 倒序排序，无须新增排序或更改存储。
- `src/lalc/developer_gui.py:SessionHistory.clear / RepairPage.refresh_sessions`：刷新会清空并重建列表，只有当前 Session 才重新选中；但 `SessionHistory.clear()` 未同步 Fluent 列表委托的选中行、悬停行和按下行。已检查安装的 qfluentwidgets `ListBase.clearSelection / updateSelectedRows` 与 `TableItemDelegate`：委托独立缓存行号，Qt 列表清空不足以清除绘制状态。
- 直接调用链已检查：初始化、刷新按钮、重命名、删除当前／其他会话、`new()`、`activate_session()` 和历史恢复。应在 `SessionHistory.clear()` 统一清理，刷新当前会话时再由既有 `setCurrentItem()` 恢复正确选中状态。
- `RepairPage.send()` 将控件选中的来源传给 `DeveloperSession.create()`，`activate_session()` 读取持久来源；默认选择只能用于初始化及新聊天，不能放入每次列表刷新中强制替换来源。发布、Default、CLI 和 Runtime 无须改变。
- 现行规格 `docs/stage-5-agent-workbench.md` 与用法 `docs/agent-repair.md` 允许首条消息前调整来源，尚未规定最新默认值，应补充本次规则；ADR 0034 的 Session 固定来源与权限边界不受影响。

## 后续实施与验证

1. 初始化及新聊天选择列表中最新版本，保留第 0 项和手动选择；统一清理历史绘制状态。
2. 补充 GUI 回归：初次打开、多个版本且 Default 较旧、无版本、手动空白刷新、历史来源恢复、新建后无高亮、重开历史后选中正确。
3. 同步上述现行规格及用法，运行聊天、开发者 GUI、Session 管理相关默认测试，不启动真实 pi 或模型。

潜在风险：第三方组件的绘制状态与平台主题相关，离屏测试可检查缓存及 Qt 选择状态，但 Windows 原生视觉效果仍需实际验收。审查阶段仅检查源码，未执行 GUI 或真实模型／游戏验证；实施结果在下方另行记录。

## 实施与验证

已按上述范围完成。`SessionHistory.clear()` 同步清除 Qt 选择及委托的选中、悬停和按下状态；初始化及 `new()` 从既有倒序列表选择第一个已发布版本。新聊天先重置旧来源再刷新，避免已无可用版本时仍带入上一会话的来源。手动空白刷新和历史来源恢复继续沿用既有逻辑。

验证命令：`QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest -q tests/test_chat_ui.py tests/test_developer_gui.py tests/test_session_management.py tests/test_chat_attachments.py`。

结果：110 passed，1 条既有 qfluentwidgets `QHoverEvent` 弃用警告。新增测试覆盖初次打开及 New Chat 的最新来源、Default 保持、空白首项与手动保留、无版本、历史固定来源恢复及委托状态清理。`git diff --check` 通过。未运行全量回归、真实 Agent／模型／游戏或 Windows 原生视觉验收。
