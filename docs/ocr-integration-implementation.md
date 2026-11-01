# OCR 实施与验证记录

日期：2026-11-01。依据：[设计确认](ocr-integration-decisions.md)、[影响审查](ocr-integration-impact-review.md)。

## 实施结果

- 新增应用共享 OcrService：RapidOCR 3.10.0 + ONNX Runtime 1.31.1 CPU，PP-OCRv6 Small det/rec，方向分类关闭，识别字典内嵌于 rec 模型。首次使用校验固定模型摘要、显式本地路径、懒加载串行复用，不缓存结果。
- observe.ocr 完整贯穿应用注册、RunContext、Executor、ApplicationService。读取已有有效截图，不隐式刷新或保存；保留 observe 分类、参数/返回值校验、Trace 和原始错误。
- game_screenshot 复用同次原始截图做 OCR；原图、网格保持，完整 OCR JSON 同时进入模型实际接收的 content 与结构化 details。OCR 故障返回 ocr_error；取消或窗口失效不作为识别降级成功。
- 更新 TypeScript 工具描述、Python docstring、SOP、生成类型声明、教学 Step 及现有“全部 Action”测试；未新增 Agent 工具或扩大白名单。
- Windows spec 收集固定模型、配置、运行时动态库与许可；构建和归档前验证模型摘要。更新锁文件、第三方说明及使用文档。
- 暂不支持韩文。未修改不可变 Manifest、已有素材或用户数据。

## 已执行

- 针对 OCR、截图工具、Asset 图像隔离、生成声明和 Windows 组装的测试：68 passed。
- 教学样例、动作注册及 OCR 测试：24 passed。
- 更新教学样例后的默认全量回归：**643 passed, 66 skipped**。命令：`QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest -q`。未添加 --run-agent-tests，跳过项不计通过。
- `pyright example/workflow/steps.ocr.py`：0 errors, 0 warnings。
- `git diff --check`：通过。独立构建脚本在不加载 site-packages 时可执行 --help。
- 本机 macOS CPU 真实 OCR 静态检查：生成含“战斗开始 12345”和“LIMBUS COMPANY 67890”的 720×260 图片，阻止 socket.connect / create_connection。全图识别中文与数字通过（约 0.636 秒），局部区域通过（约 0.407 秒），空白图返回空 items（约 0.140 秒）。确认识别会话有内嵌 character 字典；没有网络请求。另一次英文合成图检查中，同一服务的后续调用复用了实例。以上为单次样本观察，不能作为性能基准。

## 未验证与限制

未执行真实 pi/模型服务的 Agent 工具循环、Windows 冻结包构建与原生离线运行、真实游戏或韩文识别验收。普通回归使用 OCR/窗口替身；真实静态 OCR 检查与这些回归证据分开。

完整 OCR 文本会增加截图工具耗时和模型上下文；原生推理不能即时中断，推理返回前后的检查防止失效结果继续使用。游戏小字号、数字、描边和动画背景仍需真实截图校准。Agent 截图沿用现有取消与窗口检查；正式 Run 才拥有物理输入监听会话。
