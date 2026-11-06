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
- Action 只读取当前有效内存截图，不隐式刷新或保存；没有有效截图就报错。需要新画面或操作后再次判断时，显式调用 capture_screen。
- 默认模型的检测阈值与检测候选数限制仍然生效。“完整结果”表示统一 OCR 接口的全部结果，不代表能发现每个文字像素。
- 返回 `observation`、实际 `region` 和 `items`。每项有 `text`、`score`、`box`（x/y/width/height）、四点 `polygon` 和整数 `centerxy`。所有坐标均为原客户区像素，已还原区域偏移及 SDK 缩放。矩形包住四点坐标，宽高包含端点像素。
- 文字保留 SDK 输出，不额外纠错、合并、摘要或重新排序。识别成功且无达标文字时返回空 items；资源或推理故障明确抛错。
- OCR 为应用注册的 observe Trusted Action，不由 Manifest 选择实现，也不能由 Agent 修改。原始像素不穿过 Action 返回边界。

## Developer OCR 测试页

Developer 导航中 Capture 后的 **OCR 测试**页用于查看现有模型的识别效果。点击“截取图片”后自动识别全图，在整张原图上显示矩形框与编号；下方按相同编号显示原始识别文字，可选中复制。

用鼠标左键拖选，松开后自动对当前截图的选区重新 OCR，不获取新画面；本次框、编号与文字替换旧结果。点击“识别全图”恢复全图识别，每次编号按模型原顺序从 1 开始。本页截图独立于 Capture 的素材预览，识别不保存素材或结果。操作期间禁用本页截图、识别和框选，失败清除旧结果并显示错误。暂不支持韩文。

设计及影响审查见 [OCR 测试页记录](ocr-test-page-impact-review.md)。

## Agent 截图工具

`game_screenshot` 保持无参数，同时返回同一次截图的原图、40px 网格图及 `ocr`。`ocr` 就是上述完整结果，默认全图、min_score=0.0；它同时进入工具文本 content 和 details，随原有交互日志留存。网格不参与 OCR。

OCR 失败时仍返回两张图，并以 `ocr_error` 明确记录原始错误；不返回假的空识别成功。截图失败、取消或窗口失效时，不返回可继续使用的观察结果。没有单独的 game_ocr 工具，不赋予 Agent 任意文件或网络图片识别权限。preview_crop、read_run_log 等其他图像工具不自动执行 OCR。

## 模型、依赖与中断

源码环境用 `uv sync --locked --extra automation` 安装。模型来自固定 RapidOCR wheel，自带识别字典内嵌于 rec ONNX 元数据；首次使用校验两份模型的固定 SHA-256，再显式使用本地路径加载。缺失或摘要不符直接失败，不隐式下载。升级依赖或模型需要重新检查摘要、字典、预处理与坐标兼容性。

应用共用懒加载的串行实例，不缓存识别结果。推理前后检查取消与窗口状态；正式 Run 同时检查输入所有权。原生推理本身不能即时打断，中断响应可能需要等待当前推理返回，但失效结果不会用于后续操作。Agent 截图沿用现有工具取消/窗口核验，不建立正式 Run 的物理输入监听会话。

Windows 包带固定模型、配置、推理动态库和许可文本；构建与组装时校验模型摘要。见 [Windows 构建说明](windows-packaging.md)。本机静态截图检查、真实 Agent 循环、Windows 冻结包与真实游戏验收分别报告，不能相互替代。

设计记录：[确认稿](ocr-integration-decisions.md)、[影响审查](ocr-integration-impact-review.md)。

上游说明：[RapidOCR 模型列表](https://rapidai.github.io/RapidOCRDocs/main/model_list/)、[输入与输出](https://rapidai.github.io/RapidOCRDocs/main/en/install_usage/rapidocr/usage/)、[本地模型](https://rapidai.github.io/RapidOCRDocs/main/en/install_usage/rapidocr/how_to_use_offline_model/)。
