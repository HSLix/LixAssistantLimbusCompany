# 截图鼠标归位与日志复制：设计及影响审查

2026-11-14，用户确认：自动归位最多尝试三次，失败记录 Warning 后继续截图，接受遮挡或悬停状态影响识别的风险。日志块复制完整文字，含时间、等级、动作名和折叠正文。

## 设计变化与已确认差距

以下为实施前的源码审查结论；后续实现已覆盖这些差距。

- 原归位失败终止观察 → 有限重试后降级继续；控制权、取消、焦点、窗口有效性、截图尺寸及 Trace 写入失败仍按原边界传播。
- `control.InputSession.park_cursor` 仅移动一次；截图所示异常来自移动后仍在客户区，不能由此证明远程软件干预。
- `focused.FocusedAutomationSession._capture` 在截图后鼠标重新进入时无限循环；需有界，并在降级后允许取得图像。
- `windows_input.WindowsInputBackend.park_cursor` 使用虚拟桌面绝对坐标 SendInput；须记录目标、窗口、桌面及 ClipCursor 范围，不能把 SendInput 返回成功当作实际归位成功。
- `run_log_gui.LogDelegate` 直接绘制文字，不能选中；复用现有完整 row.text，实现行内复制及键盘复制，不读取额外文件或复制图片。

## 影响范围与实施顺序

1. 输入归位重试及诊断 → 截图降级／重入上限 → 共用 component_log Warning，供运行窗口及历史日志消费。
2. 日志页 delegate 复制入口和键盘快捷键，使用现有翻译文案与剪贴板。
3. 更新开发教程、当前状态及日志用法，覆盖重试恢复、持续失败、异常边界、重复重入、全文复制测试。

调用范围：Trusted Action → RunContext → Runtime → Application → FocusedAutomationSession；手动开发截图和 Agent game_screenshot 共用同一截图实现。无需修改参数、Manifest、Agent 权限或存储格式。before_capture 内部钩子增加布尔结果，False 表示已警告降级。

## 潜在风险与验证边界

鼠标未移开时图像可能包含遮挡／悬停；仅归位异常可降级，用户接管及窗口异常不可吞掉。Windows 坐标、远程位置同步和鼠标裁剪的实际原因须用新增诊断在原环境复核；替身测试不能证明实机修复。无需新增术语或架构 ADR。

## 实施说明

归位失败在每次调用内最多三次移动；单独限制截图后重新进入的观察重试为三帧。移动后立即位置与等待 0.1 秒后的实际位置分开记录，可辨认“移动后又返回”，但无法仅凭位置证明是哪一个进程改变鼠标。只保留已存在的右下角目标策略，不新增其他方向、强制解除 ClipCursor 或抢夺用户控制权。

## 验证结果

串行执行，均正常退出：

- 最终截图归位及日志页专项：`QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest -q tests/test_capture_cursor.py tests/test_run_logs.py`，44 passed。
- 输入控制、窗口观察、GUI 语言、日志传输、Agent 工具替身：`QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest -q tests/test_input_control.py tests/test_focused_observation.py tests/test_gui_language.py tests/test_run_log_sharing.py tests/test_repair_tools.py`，103 passed。退出时有 Qt 对象垃圾回收 ResourceWarning，未崩溃。
- 本次修改文件的 `git diff --check` 通过；全工作区检查另发现原有 Skill 改动的行尾空白，未改动这些用户文件。

未运行全量回归、真实 pi／模型、Windows 打包或真实游戏／远程控制验收。复制交互使用离屏真实鼠标事件与标准复制快捷键验证，绘制已有像素回归通过。代码未提交。

## 追加：Agent 读取日志自动提示等级计数

用户追加要求：Agent 查看日志时自动获知 Warning 和 Error 数量。`read_run_log` 每次（含截图预览）返回 `log_counts={scope: full_run, warning, error, damaged_records}`；统计该 Run 的整份完整行快照，不依赖分页起点、limit 或筛选。仅计事件明确记录的等级，大小写归一；Trace 动作失败及正文中的 warning/error 字样不自动算等级。空日志返回零，损坏 JSON 单列，未写完尾行待完成后计入。

复用 `trace_records` 的路径校验、快照、流式读取和取消检查，不改变日志格式或工具参数；同步 Agent 提示、pi 工具描述与用法。统计需要扫描整份 Run，每次读取的耗时可能增加。`list_runs` 仍保持首尾元数据的快速读取，搜索仍返回查询命中而不冒充整份日志计数。

验证：`QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest -q tests/test_log_diagnostics.py tests/test_repair_tools.py tests/test_run_logs.py`：58 passed。覆盖整份统计与分页／筛选隔离、大小写、损坏行、尾行补齐、空日志、取消和工具文本实际返回；未启动真实 Agent／模型。

## 追加：聚焦有限重试

用户于 2026-11-14 明确要求每隔一秒尝试聚焦，合计十次仍失败则报错，替代原先单次 SetForegroundWindow 后无时限等待。提供的被动监测记录显示 14:18:37.232 游戏成为前台，14:18:41.141 前台变为运行窗口，14:18:41.203 变为 LALC；14:19:29.155 又成为游戏。不能凭该记录判定失焦原因，也不能证明曾发生 API 拒绝。

影响调用链：Application／FocusedAutomationSession.connect、InputSession 自动重新聚焦与手动恢复、game_restart 的新窗口绑定，统一落在 WindowsWindowPlatform.focus。函数签名不变；该函数内前台未取得不再无限等待。十次是总请求次数（首次立即，第十次约在第九秒），第十次后再等一秒供异步激活；返回成功仍以实际前台句柄确认。每次请求及轮询前保留检查点；窗口消失立即失败，取消／接管优先于下一次请求。用户活动等待在取得聚焦资格之前执行，其十秒计时规则不变，也不因本改动缩成十秒总运行预算。调用方继续使用原有窗口异常／暂停／运行失败处理，不新增业务恢复或强制激活手段。

失败错误附目标句柄、实际前台句柄及最后 API 返回值。现行教程、当前状态、异步聚焦和取消测试同步更新；历史输入所有权影响审查保留当时结论。无新领域术语或需独立 ADR 的难逆决定。

聚焦实施验证（串行，均正常退出）：

- `QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest -q tests/test_focused_observation.py tests/test_input_control.py tests/test_capture_cursor.py`：70 passed。包括固定时钟下十次总请求、每秒间隔及最后一秒等待、API 返回真假均以实际焦点为准、第 2／10 次异步成功、最小化恢复、检查点取消和窗口消失不再请求。
- `QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest -q tests/test_game_restart.py tests/test_developer_gui.py tests/test_error_handling.py`：117 passed。
- 本次修改文件空白检查通过。未运行全量、真实 Agent／模型或 Windows／游戏实机验证；新增重试不等于已确认此前闪烁的根因。
