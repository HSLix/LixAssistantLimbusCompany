# Asset 检测与现场裁剪

本例使用正式 Manifest、Step 和 observe Trusted Action，Windows 上需要已经运行的游戏窗口；不会点击游戏。先在项目根目录安装 `uv sync --all-extras`。游戏语言通过 `run`／`run-plan` 的 `--language` 指定，默认 `en`；程序不会自动检测语言。

若当前 `candidate/` 为空或尚不存在，可复制本例作为 Developer Candidate；已有草稿请先自行保留，避免覆盖：

```sh
mkdir -p candidate
cp examples/asset-recognition/*.py examples/asset-recognition/manifest.json candidate/
uv run --extra automation lalc validate
uv run --extra automation lalc publish
```

发布后使用输出的 Manifest ID。先从当前游戏画面裁剪一个模板（矩形为客户区像素 `x, y, width, height`；坐标必须按实际画面填写）：

```sh
uv run --extra automation lalc run steps.crop --manifest <ID> --language zh --inputs '{"asset":"ui/mailbox/claim","region":{"x":100,"y":100,"width":80,"height":30}}'
```

每次裁剪请求都会重新截图，返回 `image_path` 供检查，以及相对 `path`、完整 `sha256`、实际 `observation` 和裁剪区域。图片保存在 `lalc data-dir` 所示目录的 `assets/`，来源记录在 `asset-provenance/`。不读取已保存截图作为来源，不自动添加任何语言映射，不覆盖旧 Asset 或旧 Manifest。未来 Agent 的请求／看图往返及 Turn 计数是 Stage 3 TODO。

检查图片后，在可编辑的 `candidate/manifest.json` 的 `assets` 中加入返回的相对路径和完整哈希，再发布一份新的 Manifest：

```json
{
  "ui/mailbox/claim": {
    "zh": {
      "path": "ui/mailbox/claim-zh-<short-hash>.png",
      "sha256": "<完整的64位哈希>"
    }
  }
}
```

随后使用新 Manifest ID 检测：

```sh
uv run --extra automation lalc run steps.detect --manifest <NEW_ID> --language zh --inputs '{"asset":"ui/mailbox/claim","threshold":0.9}'
```

`region` 可选，默认完整客户区。结果始终使用完整客户区坐标；返回全部达标目标，按分数降序、同分按 `y, x` 排序。模板按原尺寸进行 BGR 匹配，分数为 `1 - TM_SQDIFF_NORMED`；全黑模板使用按最大像素平方差归一化的误差。不会自动缩放模板；阈值需用实际游戏截图校准。默认 `nms=true`、`nms_iou_threshold=0.5`，只抑制 IoU 严格超过阈值的框；关闭 NMS 返回全部达标候选。

当前语言有映射时仅使用该模板；没有映射才比较其他语言，最高达标分数胜出，同分按相对路径排序。回退结果记录来源语言，但不改 Manifest。每次非空结果直接保存到独立的 `asset-usage.json`，包含全部返回命中、归一化区域、时间和 Run／Trace／观察关联；空结果不更新，后续 Step 失败也不撤销已记录的成功匹配。历史记录不改变检测范围。

截图像素默认留在内存。Trace 和 Usage Index 中的观察编号不代表存在完整截图文件；只有显式 `save=True` 才写入完整截图证据。裁剪图片本身属于新增 Asset。图片损坏、哈希不符和检测异常向上传递原始 traceback，只有有效检测无命中时返回空列表。

Agent（包括生成代码及委托执行器）只能新增 Asset 和 Manifest，不能修改、覆盖、重命名或删除旧文件。人工 GUI 管理、OCR 和自定义模型检测均未在本例实现。
