# Windows Interaction Lab

本实验工具用于单独验证 Limbus Company 的 Win32 后台截图与输入能力，不接入现有任务流水线。

## 前提

- Windows 10 或 Windows 11。
- Limbus Company 已启动，窗口标题为 `LimbusCompany`，窗口类为 `UnityWndClass`。
- 在 `lalc_backend` 目录中运行命令。

## 查看目标窗口

```powershell
uv run python -m experiments.windows_interaction_lab info
```

## 后台截图

先分别在窗口正常、被完全遮挡和真正最小化三种状态下执行：

```powershell
uv run python -m experiments.windows_interaction_lab screenshot --output screenshots/lab.png
```

命令成功只表示 `PrintWindow` 返回成功；还需要人工确认图像不是黑帧、旧帧或错误尺寸。

## 实时鼠标坐标

保持游戏窗口未最小化，将鼠标移动到需要测试的位置：

```powershell
uv run python -m experiments.windows_interaction_lab mouse-position
```

输出中的 `client=(x, y)` 是以下鼠标操作所需的客户区坐标。按 `Ctrl+C` 停止。

## 后台鼠标操作

```powershell
uv run python -m experiments.windows_interaction_lab click 640 360
uv run python -m experiments.windows_interaction_lab long-press 640 360 --duration 1.5
uv run python -m experiments.windows_interaction_lab drag 400 500 900 500 --duration 0.8 --steps 40
```

这些操作使用客户区坐标发送窗口消息，不移动真实鼠标，也不会主动恢复或聚焦游戏窗口。

## 后台键盘操作

支持 `esc`、`p`、`enter`：

```powershell
uv run python -m experiments.windows_interaction_lab key-press esc
uv run python -m experiments.windows_interaction_lab key-press p
uv run python -m experiments.windows_interaction_lab key-press enter
```

按下和抬起可以分开测试：

```powershell
uv run python -m experiments.windows_interaction_lab key-down p
uv run python -m experiments.windows_interaction_lab key-up p
```

执行 `key-down` 后务必执行对应的 `key-up`。

## 建议记录

每种操作分别记录以下四种窗口状态：

| 状态 | 截图 | 点击 | 长按 | 拖动 | 键盘 |
|---|---|---|---|---|---|
| 前台可见 | | | | | |
| 未激活且无遮挡 | | | | | |
| 被其他窗口完全遮挡 | | | | | |
| Windows 真正最小化 | | | | | |

每项应记录“调用成功”和“游戏产生预期变化”两个结果，因为 Windows 接受消息不代表 Unity 一定处理消息。
