# Windows Interaction Lab

本实验工具用于验证 Limbus Company 在**窗口未最小化但没有焦点**时的截图与输入能力，不接入现有任务流水线。

## 当前边界

- 支持：游戏在前台、未激活、被其他窗口部分或完全遮挡。
- 暂不支持：Windows 真正最小化。Unity 窗口最小化后客户区可能变为 `0x0`，命令会给出明确提示。
- 已确认：窗口被遮挡时，`PrintWindow` 截图仍能得到正常画面。
- 已观察：异步 `PostMessage` 键盘消息会在未聚焦时积累，并在游戏重新获得焦点后集中执行。
- 已观察：异步 `PostMessage` 鼠标消息未被游戏响应。

## 前提

- Windows 10 或 Windows 11。
- Limbus Company 已启动，窗口标题为 `LimbusCompany`，窗口类为 `UnityWndClass`。
- 在 `lalc_backend` 目录中运行命令。

## 查看目标窗口

```powershell
uv run python -m experiments.windows_interaction_lab info
```

`foreground=False` 表示当前焦点不在游戏，正是本轮实验所需状态。

## 后台截图

保持窗口未最小化；可以让其他窗口完全遮挡游戏：

```powershell
uv run python -m experiments.windows_interaction_lab screenshot --output screenshots/lab.png
```

## 实时鼠标坐标

```powershell
uv run python -m experiments.windows_interaction_lab mouse-position
```

输出中的 `client=(x, y)` 是鼠标操作所需的客户区坐标。按 `Ctrl+C` 停止。

## 消息投递模式

- `--delivery post`：原有异步方式，只把消息加入 Unity 线程队列；保留为对照组。
- `--delivery send`：使用带超时的同步发送，直接调用目标窗口过程；这是下一轮应优先测试的方式。

两种方式都不会移动真实鼠标，也不会调用 `SetForegroundWindow` 或主动夺取焦点。

## 本轮建议测试

先把焦点放在 PowerShell 或其他窗口，并确认 `info` 显示 `foreground=False`。然后测试同步键盘：

```powershell
uv run python -m experiments.windows_interaction_lab key-press p --delivery send
uv run python -m experiments.windows_interaction_lab key-press esc --delivery send
uv run python -m experiments.windows_interaction_lab key-press enter --delivery send
```

再测试同步鼠标：

```powershell
uv run python -m experiments.windows_interaction_lab click 640 360 --delivery send
uv run python -m experiments.windows_interaction_lab long-press 640 360 --duration 1.5 --delivery send
uv run python -m experiments.windows_interaction_lab drag 400 500 900 500 --duration 0.8 --steps 40 --delivery send
```

如果命令超时，可调整等待上限：

```powershell
uv run python -m experiments.windows_interaction_lab click 640 360 --delivery send --timeout-ms 3000
```

最后用 `post` 重复同一坐标，作为对照：

```powershell
uv run python -m experiments.windows_interaction_lab click 640 360 --delivery post
uv run python -m experiments.windows_interaction_lab key-press p --delivery post
```

## 结果判断

每项分别记录“命令成功”和“游戏立即产生预期变化”。如果 `send` 调用成功但游戏仍无反应，说明限制位于 Unity 的焦点/输入层，而不是 Windows 消息是否进入窗口过程；下一步再单独实验激活消息包络，不直接并入正式输入实现。

| 状态 | 截图 | 鼠标 post | 鼠标 send | 键盘 post | 键盘 send |
|---|---|---|---|---|---|
| 前台可见 | 待记录 | 待记录 | 待记录 | 待记录 | 待记录 |
| 未激活且无遮挡 | 已确认正常 | 无响应 | 待测试 | 获焦后集中执行 | 待测试 |
| 被其他窗口完全遮挡 | 已确认正常 | 无响应 | 待测试 | 获焦后集中执行 | 待测试 |
