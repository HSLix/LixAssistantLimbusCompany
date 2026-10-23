# 三层 Workflow 与全部 Trusted Actions

本样例展示当前正式格式及调用方式，不承担真实游戏业务验收。默认入口为：

```text
tasks.example
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
uv run lalc run tasks.example
uv run lalc run-plan example/trusted-actions/plan.json
```

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

未准备模板时可直接运行 `steps.crop`，它会重新截图并返回 image_path、完整哈希和来源。可选 tags 默认为空列表；图片保存后就参与匹配。检查裁剪图后，可继续追加标签：

```bash
uv run lalc add-asset ui/claim --image <crop返回的image_path> --tags zh event
```

无需 Candidate、publish 或重新 set-default。标签追加合并去重，省略标签不清空已有列表。图片使用 `assets/ui/claim/<完整哈希>.png`，标签位于同目录的 asset-tag.json；缺记录也按无标签参与匹配，不接受任意外部 PNG 导入。

直接运行 steps.match，输入文件可为 `{"asset":"ui/claim","priority_tags":["zh"],"threshold":0.9}`。优先组内全部模板匹配，命中则不匹配其余组；未命中才尝试剩余全部模板。priority_tags 默认为 None，无优先条件时全部匹配。结果统一 NMS 和分数排序，标签是普通描述，不自动根据游戏语言选择。

crop-asset CLI 可现场裁剪并配置 tags；observe.crop_asset 也能传 tags。每次匹配重新读取目录及标签，同一个 Run 内新增图片或改标签从下一次匹配生效，Manifest 切换不切换素材。

完整示例回归使用生产动作注册和平台替身，覆盖三层调用、全部动作、裁剪→加标签→直接匹配及 Trace/Ledger；不代表 Windows 游戏或包内业务验收。
