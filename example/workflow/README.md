# exp、mirror：页面、Plan、三层 Workflow 与 Recovery Rule

本样例展示当前正式格式及调用方式，不承担真实游戏业务验收。默认入口为：

```text
tasks.exp
  → subworkflows.observe
      → steps.capture → observe.capture_screen
  → steps.wait → control.wait
```

默认只截图、保存证据及协作等待，不点击、按键或拖动。所有正式 Run 仍会连接并聚焦游戏、启动物理输入监听，直到完成清理。需已启动唯一可用的 Limbus Company 窗口。

## 准备 Developer Candidate

在项目根目录先检查是否已有 `candidate/`，保留现有工作。仅当该目录不存在或为空时运行 `uv run lalc init`；在这个新工作台中用本目录的 `manifest.json` 及全部 `.py` 文件替换初始化内容。不要覆盖已有开发草稿。

`manifest.json` 只声明正式 Component，不登记 Trusted Actions；动作由应用提供。Asset 独立于 Manifest；本样例不附模板或素材映射文件。

```bash
uv run lalc validate
uv run lalc publish
uv run lalc set-default <publish输出的UUID>
uv run lalc run tasks.exp
uv run lalc run-plan
```

`plan.py` 是正式源码，随本样例 Manifest 一起校验和发布；不能直接执行源码文件路径。它声明 `SUPPORTED_TASK_IDS = ["exp", "mirror"]`，读取对应页面的消息和 Dashboard 重复次数，分别调用 `tasks.exp`、`tasks.mirror`。普通任务失败后可继续，CLI 对含失败的已完成 Plan 返回 1。

先安装 [exp、mirror 页面](../pages/README.md)，再在 GUI 选择发布的 Default Manifest，填写教学消息、勾选任务并设置次数，开始运行。每个 Task 都通过 `subworkflows.observe` → `steps.capture` 截图，再调用 `steps.wait`，最后返回含页面消息与观察证据的结果；每次 Task 调用均保留结果。运行中修改配置只影响下次执行。

CLI 无页面配置快照时，直接 `run-plan` 的重复次数默认为 0；可用 `run tasks.exp` / `run tasks.mirror` 配合 `--inputs-file` 传入 `{"message":"教学消息"}`。也可独立运行下面的 Step，学习全部应用动作。

后续命令使用 Default Manifest，省略 `--manifest`。每次重新发布并希望使用新版本时，再执行一次 `set-default`；临时运行其他保留版本时才用 `--manifest <UUID>`。

Run Result 的 `output` 含观察标识及证据路径；详细记录保存在数据目录 `traces/`、`ledger/` 和 `evidence/`。`save=false` 时证据路径为空。`lalc data-dir` 查看实际数据目录。

## 动作入口

| Step | Trusted Action | 输入 |
| --- | --- | --- |
| `steps.capture` | `observe.capture_screen` | `save`，默认 true |
| `steps.wait` | `control.wait` | `seconds`，默认 0 |
| `steps.click` | `control.click` | 必填 `x`, `y` |
| `steps.key_press` | `control.key_press` | 必填 `key`：esc / p / enter |
| `steps.drag` | `control.drag` | 必填 `x`, `y`, `end_x`, `end_y`；`seconds` 默认 2.5 |
| `steps.crop` | `observe.crop_asset` | 必填 `asset` 和矩形 `region`；可选 `tags` |
| `steps.match` | `observe.match_asset` | 必填 `asset`；可选 `region`, `threshold`, `nms`, `nms_iou_threshold` |

点击、按键、拖动会产生真实输入，坐标须按实际客户区测量。编辑一个 UTF-8 JSON 对象输入文件后，通过 `uv run lalc run <Step逻辑名> --language <实际语言> --inputs-file <文件路径>` 运行。坐标均为完整客户区像素；region 形如 `{"x":2,"y":1,"width":2,"height":2}`，此处数字只是格式示意。

控制样例在动作前后显式截图，展示调用和观察顺序，不判断领取成功等业务含义。它们也不具备真实任务的安全续跑判断；被接管后应先检查游戏，无法确认适用状态就 Stop。新业务 Step 应自己识别部分完成/已完成状态，决定是否发送输入。

## 裁剪、标签、匹配

未准备模板时可直接运行 `steps.crop`，它会重新截图并返回 image_path、完整哈希和来源。可选 tags 默认为空列表；图片保存后就参与匹配。检查裁剪图后，可继续设置标签：

```bash
uv run lalc tag-asset ui/claim --image <crop返回的image_path> --tags zh event
```

无需 Candidate、publish 或重新 set-default。标签用新列表整体覆盖，保留输入顺序及重复项；省略标签或传空列表将清空已有标签。图片使用 `assets/ui/claim/<完整哈希>.png`，标签位于同目录的 asset-tag.json；缺记录也按无标签参与匹配，不接受任意外部 PNG 导入。

直接运行 steps.match，输入文件可为 `{"asset":"ui/claim","priority_tags":["zh"],"threshold":0.9}`。优先组内全部模板匹配，命中则不匹配其余组；未命中才尝试剩余全部模板。priority_tags 默认为 None，无优先条件时全部匹配。结果统一 NMS 和分数排序，标签是普通描述，不自动根据游戏语言选择。

crop-asset CLI 可现场裁剪并配置 tags；observe.crop_asset 也能传 tags。每次匹配重新读取目录及标签，同一个 Run 内新增图片或改标签从下一次匹配生效，Manifest 切换不切换素材。

完整示例回归使用生产动作注册和平台替身，覆盖三层调用、全部动作、裁剪→加标签→直接匹配及 Trace/Ledger；不代表 Windows 游戏或包内业务验收。

## Trusted Action 类型补全

样例使用 `from lalc import RunContext` 和 `ctx: RunContext` 注解，在项目 Python 环境中提供 Action 名称、参数和返回类型补全。应用注册、Action 签名或 Context 公开接口变化后，在源码根目录运行 `uv run lalc generate-stubs` 并提交更新后的声明；详见[开发教程](../../docs/developer-workflow-tutorial.md#trusted-action-类型补全)。

## 确定性恢复

同一 Manifest 的 `steps.check_popup` 与 `recovery.close_popup` 演示外部弹窗打断 Step → 公共规则 detect → recover → 重试当前 Step。它们使用现有 `observe.capture_screen`、`observe.match_asset`、`control.click`，不注册新 Trusted Action。Trusted Actions 仍由应用统一注册，目录中的 Step 只是调用示例。

先用裁剪工具为 `tutorial/recovery-popup` 保存可安全点击的关闭按钮模板，再显式运行 `lalc run steps.check_popup`。无弹窗时正常返回；匹配时 Step 失败，恢复规则重新观察，只在关闭目标唯一时点击。多目标、多条匹配规则、点击无效均停止并保留 Trace。该入口独立触发，不在 exp、mirror 默认演示中发送真实点击。

这不是实际游戏业务的完成判定；默认示例不包含游戏素材，真实 Windows 游戏与打包验收需另行执行。
