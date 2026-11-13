# 上下文用量融入输入工具栏：影响审查与实施

2026-11-13。开发者已选择“融入输入框工具栏”并要求审查后实现。本文替代既有上下文压缩设计中关于显示位置的要求，不改变 ADR 0041 的上下文所有权及压缩策略。

## 设计变化

- 输入框下方独立数字与短进度条 → 输入框工具栏附件按钮旁的小图标与 Caption 文本，删除独立行与进度条。
- 未知状态的“上下文：未知” → “上下文 —”；悬停仍明确未知，不显示为 0%。
- 保留按压缩触发线计算的百分比、50%／80% 颜色边界、实际超过 100% 的文本以及估算 token／分母说明。颜色分别适配明暗主题，未知恢复中性色。
- 图标为只读状态，不新增点击操作、@ 按钮或压缩控制。图中数值为示意，不增加数据来源。

## 证据与影响

| 来源 | 已确认影响 |
| --- | --- |
| `src/lalc/developer_gui.py:RepairPage.__init__` | 原 `context_row` 在 composer 外，改为 composer 工具栏内的小组件；复用 Fluent IconWidget 和 CaptionLabel。 |
| `RepairPage.show_context_usage` | 保留数值校验及计算，删除进度条写入；标签与容器同步悬停说明。原未知分支未清除标签旧 tooltip，需同时修正。 |
| `RepairPage.show_event`、`show_empty_chat`、`activate_session`、设置变更 | 均沿用 `show_context_usage`；事件顺序与会话重置不变，无后端或存储迁移。 |
| `tests/test_chat_ui.py:test_context_usage_uses_compaction_threshold_and_color` | 原断言依赖进度条，需迁移到文本颜色、未知重置及说明；增加工具栏归属、窄窗口和明暗主题检查。 |
| `src/lalc/translations/lalc_zh_CN.ts`／`.qm` | 增加紧凑未知文案并重新编译。 |
| `docs/agent-repair.md` | 当前用法更新；原审查和实施记录保留历史位置说明，引用本文说明后续替代。 |

## 潜在风险与检查

- 工具栏可用宽度减少，英文和大百分比可能挤压发送按钮：检查窄窗口和两种语言的实际几何布局。
- 小号文字在暗色主题可能难读：使用 Fluent CaptionLabel 的明暗双颜色，检查主题切换与高用量／未知状态。
- 模型估算可能超过触发线，仍需显示实际百分比；不得因移除进度条而把文本限制到 100%。

## 实施顺序与边界

先迁移布局及状态刷新，再同步翻译与用法，最后运行聊天界面与翻译普通定向回归，并生成离屏实装预览。无需新增依赖、配置、ADR 或修改 Agent 测试。实际执行结果在本文末尾补充；真实 Windows 与游戏验收另行进行。

## 实施与验证结果

- 已完成上述布局、颜色、未知提示清理、中英文翻译及用法同步。小号文字采用更深的亮色主题文字色和更亮的暗色主题文字色；绿／黄／红语义边界保持。
- `QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest -q tests/test_chat_ui.py tests/test_gui_language.py`：54 passed。新增覆盖中英文用量文本、两种主题、760px 窗口工具栏布局、未知回退和 tooltip 清理；既有颜色边界及 110% 文本断言通过。
- 已查看 `.generated/context-toolbar-preview/light.png`、`dark.png`、`unknown.png`，确认图标、文字与附件／更多／发送按钮同处工具栏，无独立底行。截图由实际 Qt 窗口裁出，不是生成式示意图。
- 首次独立截图脚本未替代 macOS 原生标题栏操作而退出 139；随后复用测试的 offscreen 平台替身完成截图。此替身不构成原生 macOS／Windows 验收。未运行全量回归、真实 pi／模型或游戏。
