# 本地 OCR

LALC 使用 RapidOCR 3.10.0、ONNX Runtime 1.31.1 CPU 与 PP-OCRv6 Small 检测/识别模型。支持中、英、日等模型覆盖的文字，**暂不支持韩文**，不会自动回退其他模型。OCR 置信分数不是识别正确概率。

## Workflow

```python
ctx.action("observe.capture_screen", save=True)
result = ctx.action(
    "observe.ocr",
    region={"x": 100, "y": 200, "width": 400, "height": 160},
    min_score=0.9,
)
matches = [item for item in result["items"] if item["text"] == "战斗开始"]
if len(matches) != 1:
    raise ExecutionFailure("无法唯一确认战斗开始按钮")
ctx.action("control.click", centerxy=matches[0]["centerxy"])
```

本例在 Step 内使用，并从 `lalc` 导入 `ExecutionFailure`。阈值只是示例，需用真实游戏截图校准；识别到文字不保证所在位置就是可点击按钮。

- `region=None` 默认全客户区；非空区域必须含整数 x/y/width/height，且完整位于截图内。无效区域报错，不自动裁边。
- `min_score=0.0` 默认不过滤识别分数；必须是 0–1 的有限数值。
- Action 只读取当前有效内存截图，不隐式刷新；没有有效截图就报错。需要新画面或操作后再次判断时，显式调用 capture_screen。2026-11-06 起，共用执行器为该动作自动记录 Debug 并保存所用帧的证据，不额外截图；Developer 识别调试页不受此运行日志行为影响，见[运行日志页](user-run-logs.md)。
- 默认模型的检测阈值与检测候选数限制仍然生效。“完整结果”表示统一 OCR 接口的全部结果，不代表能发现每个文字像素。
- 返回 `observation`、实际 `region` 和 `items`。每项有 `text`、`score`、`box`（x/y/width/height）、四点 `polygon` 和整数 `centerxy`。所有坐标均为原客户区像素，已还原区域偏移及 SDK 缩放。矩形包住四点坐标，宽高包含端点像素。
- 文字保留 SDK 输出，不额外纠错、合并、摘要或重新排序。识别成功且无达标文字时返回空 items；资源或推理故障明确抛错。
- OCR 为应用注册的 observe Trusted Action，不由 Manifest 选择实现，也不能由 Agent 修改。原始像素不穿过 Action 返回边界。

## Developer 识别调试页

Developer 导航中的 **识别调试**页通过顶部“模板匹配／OCR”标签切换方式。
两种方式共用一张固定截图与一个画布；截图后不自动识别。OCR 模式隐藏模板素材和参数区，扩大截图区域。

点击“识别全图”清除 OCR 自己的选区并立即识别全图；鼠标拖选松开后自动识别选区，不获取新画面。
矩形框、编号和下方可复制文字按 OCR 原顺序对应，每次识别替换本方式的旧结果，编号从 1 开始。
切换标签不执行，恢复各方式自己的选区与结果。模板匹配的选区不会传给 OCR。

新截图成功后，清除两种方式的选区与结果，保留参数和模板选择；截图失败保留旧图及全部状态并报错。
本页不改变 Capture 素材保存预览，不保存素材或结果。后台操作期间禁用截图、标签切换、参数和框选；
识别失败清除本次 OCR 结果，保留截图与选区并提示错误。暂不支持韩文。

设计见 [确认记录](recognition-lab-decisions.md)，影响及验证见 [合并审查](recognition-lab-impact-review.md)。
[旧 OCR 测试页记录](ocr-test-page-impact-review.md) 保留历史设计与验证，不再代表现行截图触发规则。

## Agent 截图工具

`game_screenshot` 保持无参数，同时返回同一次截图的原图、40px 网格图及 `ocr`。`ocr` 就是上述完整结果，默认全图、min_score=0.0；它同时进入工具文本 content 和 details，随原有交互日志留存。网格不参与 OCR。

OCR 失败时仍返回两张图，并以 `ocr_error` 明确记录原始错误；不返回假的空识别成功。截图失败、取消或窗口失效时，不返回可继续使用的观察结果。没有单独的 game_ocr 工具，不赋予 Agent 任意文件或网络图片识别权限。preview_crop、read_run_log 等其他图像工具不自动执行 OCR。

## 模型、依赖与中断

源码环境用 `uv sync --locked --extra automation` 安装。模型来自固定 RapidOCR wheel，自带识别字典内嵌于 rec ONNX 元数据；首次使用校验两份模型的固定 SHA-256，再显式使用本地路径加载。缺失或摘要不符直接失败，不隐式下载。升级依赖或模型需要重新检查摘要、字典、预处理与坐标兼容性。

应用共用懒加载的串行实例，不缓存识别结果。推理前后检查取消与窗口状态；正式 Run 同时检查输入所有权。原生推理本身不能即时打断，中断响应可能需要等待当前推理返回，但失效结果不会用于后续操作。Agent 截图沿用现有工具取消/窗口核验，不建立正式 Run 的物理输入监听会话。

Windows 包带固定模型、配置、推理动态库和许可文本；构建与组装时校验模型摘要。见 [Windows 构建说明](windows-packaging.md)。本机静态截图检查、真实 Agent 循环、Windows 冻结包与真实游戏验收分别报告，不能相互替代。

设计记录：[确认稿](ocr-integration-decisions.md)、[影响审查](ocr-integration-impact-review.md)。

上游说明：[RapidOCR 模型列表](https://rapidai.github.io/RapidOCRDocs/main/model_list/)、[输入与输出](https://rapidai.github.io/RapidOCRDocs/main/en/install_usage/rapidocr/usage/)、[本地模型](https://rapidai.github.io/RapidOCRDocs/main/en/install_usage/rapidocr/how_to_use_offline_model/)。
