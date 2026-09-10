# Windows Interaction Lab

本实验工具用于验证 Limbus Company 在**窗口未最小化、焦点位于其他程序**时的截图和输入能力。实验代码与正式任务流水线隔离。

## 当前目标和边界

- 当前目标：游戏继续显示和运行，但 `foreground=False` 时仍能输入。
- 截图：已确认游戏被其他窗口遮挡时，`PrintWindow` 仍能取得正常画面。
- 暂不支持真正最小化：Unity 窗口最小化后客户区可能变为 `0x0`。
- 原始 `PostMessage` 鼠标消息：已确认游戏没有反应。
- 原始 `PostMessage` 键盘消息：已确认未聚焦时积累，游戏重新获得焦点后集中执行。
- `activate-cursor-click`：已确认在未聚焦、无遮挡和被遮挡两种状态下都能立即完成点击。
- `touch-click`：未聚焦时不会立即处理，焦点切回游戏后才开始处理，与原始消息方式表现相同。
- `managed-key`：由于当前游戏状态没有适合观察的键盘反馈，尚未实测。
- 新输入方法仍属于实验实现，必须经过 Windows 实机验证后才能选择正式后端。

## 新增的三种输入方法

### 1. `activate-cursor`：兼容性基线

向游戏同步发送一次伪 `WM_ACTIVATE`，把真实鼠标临时移动到目标屏幕位置，再向游戏窗口同步发送鼠标消息，最后恢复鼠标位置和非激活提示。

- 优点：最接近 ahab、ok-script 等现有项目已经使用的 Unity 兼容方案。
- 不会调用 `SetForegroundWindow`，正常情况下不会把游戏切到前台。
- 鼠标会短暂移动；执行点击、长按或拖动时不要同时操作实体鼠标。
- 可测试遮挡状态，因为鼠标按键消息只发给目标窗口，不会点击遮挡窗口。

### 2. `managed-key`：受守护的真实键状态

先用全局热键临时截住对应按键，向游戏发送伪激活提示，再通过 `SendInput` 产生真实的按下/抬起状态。这样可供 Unity 的全局按键状态轮询读取，同时尽量阻止当前前台程序收到按键。

- 仅支持完整的按下再抬起：`esc`、`p`、`enter`。
- 如果热键注册失败，命令会在注入前退出，避免误操作前台程序。
- 清理逻辑保证已按下的键会尝试抬起，并注销临时热键。
- 这是针对“窗口消息已进入队列，但 Unity 未聚焦时不消费”的实验路径。

### 3. `touch`：锚定合成触摸

使用 Windows 合成指针 API。一个微小且不激活的置顶窗口承接第一根锚定触点，第二根触点在游戏坐标执行点击、长按或拖动。

- 不移动真实鼠标，不调用 `SetForegroundWindow`。
- 需要 Windows 10 1809 或更高版本。
- 当前是安全验证版：执行前检查整条路径是否属于游戏；如果被其他窗口遮挡，会明确拒绝执行，避免把合成触摸送入遮挡窗口。
- 第一轮只在“游戏可见但未聚焦”状态测试。确认 Limbus Company 接受合成触摸后，再单独研究遮挡时临时借用目标区域的方案。

## 前提

- Windows 10 1809 或 Windows 11。
- Limbus Company 已启动且没有最小化。
- 默认窗口标题为 `LimbusCompany`，窗口类为 `UnityWndClass`。
- 在 `lalc_backend` 目录中运行命令。

先检查目标窗口：

```powershell
uv run python -m experiments.windows_interaction_lab info
```

输出应包含有效的 `client=宽x高`。测试后台输入时应确认 `foreground=False`。

## 坐标与截图

实时读取客户区坐标，按 `Ctrl+C` 停止：

```powershell
uv run python -m experiments.windows_interaction_lab mouse-position
```

`client=(x, y)` 是所有鼠标和触摸命令使用的坐标。建议先选一个结果明确、误操作风险低的按钮。

被其他窗口遮挡时截图：

```powershell
uv run python -m experiments.windows_interaction_lab screenshot --output screenshots/lab.png
```

## 推荐测试顺序

每轮测试前都把焦点切回 PowerShell 或记事本，并重新运行 `info` 确认 `foreground=False`。先用点击测试一个容易恢复的界面，再测试长按和拖动。

### 第一轮：验证 `activate-cursor` 兼容性

先让游戏可见但不聚焦：

```powershell
uv run python -m experiments.windows_interaction_lab activate-cursor-click 640 360
uv run python -m experiments.windows_interaction_lab activate-cursor-long-press 640 360 --duration 1.5
uv run python -m experiments.windows_interaction_lab activate-cursor-drag 400 500 900 500 --duration 0.8 --steps 40
```

通过标准：游戏立即响应；命令结束后鼠标回到原位；输出仍为 `foreground=False`。

随后用另一个普通窗口遮挡目标坐标，重复一次点击。遮挡窗口不应被点击，游戏应继续响应。这一步验证同步消息和真实光标位置是否足以绕过当前 Unity 限制。

### 第二轮：验证 `managed-key`

焦点放在不会因按键造成损失的记事本空白页或 PowerShell：

```powershell
uv run python -m experiments.windows_interaction_lab managed-key-press p
uv run python -m experiments.windows_interaction_lab managed-key-press esc
uv run python -m experiments.windows_interaction_lab managed-key-press enter
```

通过标准：游戏立即响应；当前前台程序没有收到字符、换行或 Esc；游戏没有变成前台；重新聚焦游戏时不会补执行旧按键。

若看到“无法注册临时全局热键”，该次没有注入按键。关闭占用该全局热键的软件后重试，不建议绕过守护直接运行。

若旧版本曾报告 `SendInput 失败，Win32 error=87`，原因是 `INPUT` 联合体尺寸不完整；当前实现已经补全 Win32 要求的鼠标、键盘和硬件联合体布局。更新代码后直接重复上述命令即可。

### 第三轮：验证 `touch`

保持游戏目标区域完全可见，但让 PowerShell 或一个不遮挡目标坐标的小窗口获得焦点：

```powershell
uv run python -m experiments.windows_interaction_lab touch-click 640 360
uv run python -m experiments.windows_interaction_lab touch-long-press 640 360 --duration 1.5
uv run python -m experiments.windows_interaction_lab touch-drag 400 500 900 500 --duration 0.8
```

通过标准：游戏立即响应；真实鼠标完全不动；游戏没有变成前台。若提示目标点被遮挡，请移动前台窗口后再测试，这属于当前安全边界而不是注入失败。

实测结果：`touch-click` 未达到通过标准。游戏失焦时不会立即处理触摸，重新获得焦点后才开始处理。该结果说明当前阻塞点位于 Unity 的焦点输入处理，而不是桌面 Z 序命中；因此暂不继续实现触摸遮挡借用。

### 第四轮：与原始消息方式对照

原始方法保留为对照组：

```powershell
uv run python -m experiments.windows_interaction_lab click 640 360 --delivery post
uv run python -m experiments.windows_interaction_lab click 640 360 --delivery send
uv run python -m experiments.windows_interaction_lab key-press p --delivery post
uv run python -m experiments.windows_interaction_lab key-press p --delivery send
```

`post` 是异步入队；`send` 是带超时的同步窗口过程调用。两者都不产生真实的全局鼠标或键盘状态。

## 推荐记录表

不要只记录“命令没有报错”，还要观察游戏是否立即变化、前台是否被切换，以及输入是否泄漏给其他程序。

| 方法 | 游戏状态 | 预期游戏响应 | 光标移动 | 抢占前台 | 输入泄漏 | 实测 |
|---|---|---|---|---|---|---|
| `activate-cursor-click` | 可见、未聚焦 | 立即 | 短暂，结束后恢复 | 否 | 否 | **通过** |
| `activate-cursor-click` | 被遮挡、未聚焦 | 立即 | 短暂，结束后恢复 | 否 | 遮挡窗口不响应 | **通过** |
| `managed-key-press p` | 可见、未聚焦 | 立即 | 否 | 否 | 前台程序不响应 | 待记录 |
| `managed-key-press esc` | 可见、未聚焦 | 立即 | 否 | 否 | 前台程序不响应 | 待记录 |
| `managed-key-press enter` | 可见、未聚焦 | 立即 | 否 | 否 | 前台程序不响应 | 待记录 |
| `touch-click` | 可见、未聚焦 | 立即 | 否 | 否 | 否 | **失败：获焦后才处理** |
| `touch-drag` | 可见、未聚焦 | 立即 | 否 | 否 | 否 | 待记录 |

## Python 调用

三个后端都保留了可独立调用的函数，也封装在 `WindowsInteractionLab` 中：

```python
from experiments.windows_interaction_lab import WindowsInteractionLab

lab = WindowsInteractionLab()
lab.activate_cursor_click(640, 360)
lab.activate_cursor_long_press(640, 360, 1.5)
lab.activate_cursor_drag(400, 500, 900, 500, duration=0.8, steps=40)

lab.managed_key_press("p")

lab.anchored_touch_click(640, 360)
lab.anchored_touch_long_press(640, 360, 1.5)
lab.anchored_touch_drag(400, 500, 900, 500, duration=0.8)
```

实验底层实现位于 `experiments/windows_interaction_methods.py`。正式系统在实机结果明确前不应直接依赖它。

## 如何选择下一步

- `activate-cursor` 已成功：将其作为当前鼠标首选方案，下一步测试连续调用、坐标边界、长按和拖动的稳定性。
- `managed-key` 成功：键盘无需再使用会积累的 `PostMessage`，继续测试连续调用和按住时长。
- `touch` 当前失败：表现仍受游戏焦点门控，暂停遮挡保护和目标区域临时置顶工作。
- 三者都失败：限制更可能来自游戏自身输入模块或保护逻辑，应先记录窗口模式、Unity 输入路径和系统版本，不要直接开始构建状态图系统。
