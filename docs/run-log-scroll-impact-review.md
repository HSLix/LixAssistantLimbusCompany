# 历史日志补页阅读位置修复

## 设计与确认（2026-11-16）

用户确认：允许滚动条滑块的位置、长度随已加载日志数量变化；屏幕中的当前日志及偏移必须稳定，读取期间继续滚动时，以最新阅读位置为准。

沿用 `user-run-logs.md` 的阅读锚点：顶部可见日志及其屏幕偏移。补充明确异步补页的锚点取值时机，不改变最新在上、筛选回退顺序、固定快照、60 条分页、240 条展示上限或原始 Trace。此处没有新增领域概念或难以逆转的架构取舍，不新增词汇或 ADR。

## 只读影响评审（修改代码前）

- **已确认**：`RunLogPage.more` 在请求开始时捕获锚点，结果返回后仍恢复旧锚点；期间用户继续滚动会被拉回。调用链为滚动条 `valueChanged` → `scrolled` → `more` → 后台 `read_page` → `shown` → `model.replace`／`restore`。
- **已确认**：`restore` 通过零延时回调执行两次滚动条位置调整，而 `more.shown` 已解除 `loading`；程序恢复位置时的 `valueChanged` 可以再次触发分页。延迟恢复也没有代际保护，可能覆盖稍后的阅读位置。
- **已确认**：补页固定淘汰远端行，未核对结果返回时的阅读锚点；读取期间若滚向远端，当前阅读行也可能被淘汰。
- `restore` 同时被筛选重载、展开／收起、窗口缩放使用，必须保持长项收起时的偏移限制。`read_page`、日志格式、导入导出、Agent 与运行弹窗不需要修改。
- 既有 `tests/test_run_logs.py` 覆盖筛选定位、分页淘汰与折叠；基线运行 28 passed。需要新增连续滚动、补页期间继续移动、程序恢复不递归补页，以及淘汰边界覆盖。

附件 `log-278` 只作为诊断数据读取：11,130,220 字节、两条 Warning（sequence 12414、1724）。离屏验证 Warning → Info → 小幅滚动触发向上补入 60 条；该次观察中内容偏移仍稳定，不能以滑块数值变化单独断言内容跳动。

## 实施顺序与风险

1. 在补页结果提交前捕获最新锚点，选择保留该锚点的最多 240 行，并同步两侧可继续加载状态。
2. 同步完成列表排版和锚点恢复，屏蔽恢复期间的滚动信号，避免程序定位引发递归分页和旧回调覆盖。
3. 增加定向回归，复测筛选、折叠、分页和相邻 User GUI 功能；补充附件离屏验证。

潜在风险：Qt 原生平台的排版与滚轮时序可能不同，离屏通过不能代替 Windows 成品验收。无需迁移用户数据，不改写附件。

## 实施与验证

- 补页提交前重新获取顶部锚点及底部可见行；最多保留 240 行的窗口避开当前可见区域，并按实际淘汰方向恢复可翻页状态。
- `restore` 同步排版并在 `QSignalBlocker` 内完成定位，移除零延时位置恢复。保留长项收起时的偏移限制；缩放回归通过。
- 新增 5 个用例：双向补页期间滚向淘汰边界（参数化两项）、Warning → Info 连续滚动、恢复不触发补页或延迟移动、窗口缩放。前三个核心边界用例在旧代码上均失败；旧分页淘汰测试同步改为先浏览到旧侧再请求旧页，符合保护当前可见内容的新边界。
- 最终日志专项：`QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest -q tests/test_run_logs.py`，33 passed。
- 最终日志组合：`QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest -q tests/test_run_logs.py tests/test_run_log_sharing.py tests/test_log_diagnostics.py`，57 passed；`git diff --check` 通过。
- 相邻 GUI：`tests/test_user_gui.py tests/test_user_pages.py tests/test_gui_language.py`，69 passed、3 skipped、1 failed。失败为 `test_single_editor_handoff_autosaves_and_restores_independent_selection` 的用户 provider 隔离断言；在独立进程中加载 `HEAD` 原版 `run_log_gui.py` 后，同一用例仍以相同断言失败，不扩大本次修复范围。
- 附件只读离屏复测：Warning → Info 后连续 12 次小幅滚动，逐次核对顶部日志字节位置及像素偏移，全部稳定，最终加载 120 行。
- 未运行全量、Agent、Windows 成品或真实游戏验收。离屏 Qt 仍有字体／平台提示；相邻日志组合测试曾在退出时出现不影响退出码的对象回收警告，不将其解释为原生平台验收。

## 设置隔离测试后续修订

用户指出默认服务商已改为 DeepSeek，要求 Developer GUI 切换至 llama.cpp 后检查 User GUI 仍为 DeepSeek。核对 `agent_settings.DEFAULTS` 后确认原测试预期过时；同步调整关闭 Developer GUI 后的地址与请求上限检查：DeepSeek 保持原值，切换至 llama.cpp 后才显示此次修改的地址及上限 7。产品设置逻辑不变。

修订后串行重跑 `tests/test_user_gui.py tests/test_user_pages.py tests/test_gui_language.py`：70 passed、3 skipped。替代上节相邻 GUI 的失败状态；保留上节作为修订前的验证记录。
