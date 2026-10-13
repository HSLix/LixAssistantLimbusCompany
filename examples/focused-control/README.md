# Windows 前台输入验收

本例走正式 Manifest → ApplicationService → Step → Trusted Action 路径。
请在可手动恢复的游戏页面验收；接管后恢复会从头执行当前 Step。
fake 回归通过不代表游戏输入已经通过 Windows 验收。

## 准备

在项目根目录的 Windows PowerShell 中，将本目录内容复制进空的
`candidate/`，执行 `uv run lalc validate`、`uv run lalc publish`，记录输出的
Manifest ID。示例不定义 condition，因此 Resume 会直接重新进入 Step。
正式业务 Step 应在模块说明中写清手动准备要求，并按需要提供 condition。

```powershell
New-Item -ItemType Directory candidate
Copy-Item examples/focused-control/* candidate/
uv run lalc validate
uv run lalc publish
uv run lalc set-default <manifest-id>
uv run lalc
```

GUI 入口填写 `steps.control`，输入填写下面各项的 JSON。使用 GUI 验收
置前提示；CLI 可用 `uv run lalc run steps.control --inputs '<JSON>'`，
接管后输入 `r` 才恢复，其他输入结束。

## 验收项目

1. **三个按键**：分别运行 `{"key":"esc"}`、`{"key":"p"}`、
   `{"key":"enter"}`，确认实际游戏立即响应；自己的注入不会触发暂停。
2. **点击**：运行 `{"operation":"click","x":100,"y":100}`，
   换成当前游戏客户区内已确认的按钮坐标，确认点击生效且物理光标不移动。
3. **长动作接管**：运行
   `{"operation":"drag","x":100,"y":100,"end_x":300,"end_y":100,"seconds":5}`，
   坐标换成可拖动的游戏区域。拖动期间移动物理鼠标或按键，确认拖动停止、
   触点释放一次、结果为 unknown、软件暂停且提示仅置前一次。
4. **手动恢复**：暂停时操作游戏和其他应用，确认自动化不干扰、不重放。
   手动将游戏恢复到可重跑本 Step 的页面，再点击继续。确认重新截图，
   同一个 Step 从头进入，未跳到下一 Step。
5. **失焦与等待**：运行 `{"operation":"wait","seconds":10}`，
   切换前台或产生物理输入，应暂停而不抢回游戏；关闭运行应立即结束等待。
6. **释放与记录**：运行后按 `uv run lalc data-dir` 输出的路径查看
   `traces/<run_id>.jsonl` 与 `evidence/<run_id>/`。核对 `input_takeover`、
   `input_released`、`paused_by_user`、`input_resume_requested`、`input_quiet`、
   `input_resumed` 和 Step 重入顺序；失败应有原始异常链与 traceback。

Resume 固定等待至少 0.3 秒无物理输入且没有按住的键/鼠标按钮；最多等待
2 秒，未满足就保持暂停，用户释放后可再次点击继续。钩子只记录物理输入，
每次输入前与长动作轮询中检查窗口和所有权。Step 中不经过运行边界的长时间
纯 Python 运算仍受既有协作式暂停限制，不提供线程强制中断。

自动测试覆盖 condition 返回 false/抛错、再次接管、注入分类、取消释放、
释放失败终止 Plan；释放失败没有实机故障注入。既往实验单机 12 ms
释放结果不作为此实现的响应 SLA。
