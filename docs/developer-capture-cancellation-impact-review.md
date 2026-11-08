# Developer 截图被旧 Run 取消状态阻断

## 已确认边界（2026-11-08）

开发者确认：停止请求仍须等待 Run 输入释放与收尾；收尾完成后，Capture、OCR／模板调试取图及窗口尺寸调整独立于上次 Run 的取消状态。运行中及暂停中仍排斥这些开发操作。

这是修复生命周期泄漏，不改变 CONTEXT 的 Run Context、Developer GUI 或 Developer Trial 含义，也不新增 ADR。

## 影响审查（实施前源码检查）

- **已确认**：`ApplicationService._complete` 和 `_worker` 的异常收尾清理 `_focused_session`、`_input_session`，却保留 `_gate`。`_window_platform` 因旧 gate 非空而给新的 Windows 平台注入 `_input_checkpoint`；后者调用旧 gate 的 `checkpoint()`，已取消时抛出 `UserInterruption`。
- **已确认**：Windows `focus` 等待异步前台激活及 `resize_client` 等待尺寸生效时调用上述 checkpoint，因此失败与是否经过等待有关。旧 Run 结束后不能继续约束新开发操作。
- **直接调用链**：Developer GUI Capture、OCR 和 Template Match → `DeveloperHost.capture` → `service.activity` → `_window_platform` → `FocusedAutomationSession.capture` → Windows `focus`。`connect`、`crop_developer_asset`、`DeveloperHost.resize_window` 也共享平台工厂。被动坐标读取虽使用工厂，但不经过这些等待。
- **保留契约**：Stage 4 的宿主排他和 ADR 0030 的停止后等待试运行收尾不变；不能通过提前清除 gate 或吞掉 `UserInterruption` 来恢复截图，否则会破坏活动 Run 的取消。
- **潜在风险**：现有 FakeWindowPlatform 不执行构造时注入的 checkpoint，单用该替身可能漏掉 Windows 特有的传播路径。需在回归替身聚焦时执行真实工厂传入的 checkpoint；Windows 真实窗口仍需现场验收。

## 实施顺序与范围

1. 在正常及异常终态发布之前清除本次 `_gate`，保持执行和输入清理期间原 gate 有效。
2. 覆盖取消后重新截图（含不更新 Capture 预览的 OCR／模板路径）、连接及尺寸调整，并覆盖收尾异常路径；检查活动 Run 的暂停／取消和错误处理回归。
3. 不改 GUI、权限、Manifest、导出、配置或素材格式，不迁移用户数据。验证结果在实施后补充。

## 实施与验证

- `_complete` 与 `_worker` 异常终态分支在输入会话清理完成后、通知观察者前清除 `_gate`，共两行产品代码。
- `tests/test_focused_observation.py::test_cancelled_run_does_not_cancel_later_developer_observation` 覆盖正常收尾和收尾异常：清理前取消仍有效、Capture 仍互斥；清理后两类取图、连接和尺寸调整均可调用，原 Trace 不被改写。修复前两种情况均在后续 Capture 抛出 `UserInterruption`，修复后通过。
- 本地串行执行：`QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest -q tests/test_focused_observation.py tests/test_input_control.py tests/test_input_activity.py tests/test_error_handling.py tests/test_developer_assets.py tests/test_developer_gui.py tests/test_user_gui.py`，结果 **193 passed, 2 skipped**，退出码 0。跳过项不计通过；未开启 Agent 测试。
- `git diff --check` 通过。未运行全量回归、真实 pi／模型、Windows 成品或真实游戏；窗口行为由执行注入 checkpoint 的替身验证，不代表原生验收。
