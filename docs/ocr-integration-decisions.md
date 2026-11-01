# OCR 接入设计确认

日期：2026-11-01。状态：开发者已确认整体边界并授权影响审查后直接实施；已本地实施，验证与未验证范围见[实施记录](ocr-integration-implementation.md)。

## 已确认

- 本地 OCR 使用 PP-OCRv6 Small 检测与识别模型，经 RapidOCR / ONNX Runtime CPU 调用；暂不支持韩文，不自动回退其他模型。
- 应用持有并复用 OCR 服务，模型首次使用时加载，同一实例串行调用；识别结果首版不缓存。依赖、模型及字典固定版本，随 Windows 成品提供，验证离线使用。
- 新增 observe.ocr Trusted Action，读取当前有效客户区截图；不隐式刷新或保存截图。沿用 observe 的角色权限、参数和返回值校验、计时、Trace 与中断边界。
- observe.ocr 接受 region（默认全图）与 min_score（默认 0.0）。无有效截图、无可用模型或推理失败明确抛错；成功但没有达标文字返回空 items。
- 统一结果包含 observation、实际 region 和 items；每项包含 text、score、box、polygon、centerxy。位置全部还原为原客户区像素坐标，结果可 JSON 序列化。score 是识别分数，不是正确概率。
- Agent 不新增 game_ocr 工具。现有 game_screenshot 的同一次原始截图同时用于原图、网格图与 OCR；辅助线不进入识别输入。
- game_screenshot 成功时附带与 observe.ocr 相同的完整 OCR 结果，不摘要、纠错、合并或额外筛选。结果需要作为工具文本内容实际送入模型，同时保留在结构化 details 与交互日志中。
- 截图成功但 OCR 加载或推理失败时，仍返回原图与网格图，并明确返回 ocr_error；不能伪装为空文字列表。observe.ocr 的对应故障仍抛错。取消、暂停或用户接管不得被转换为可继续的 OCR 降级结果。
- 推理前后检查取消和接管；失效结果不交给后续动作。脚本负责文字匹配、唯一性判断、数字解析与后续 control.click；首版不添加 OCR 点击、模糊找字或自动重试组合动作。

## 文档与实现核查

- ADR 0023：Trusted Action 归应用注册，不能由 Manifest 或 Agent 创建、替换或绕过。
- application.py 的 _match_asset：使用已有有效截图，不隐式刷新；OCR Action 沿用这一观察语义。
- RepairTools.game_screenshot：目前捕获并返回原图和网格图；新增 OCR 必须复用同一 session 的原始像素。
- RepairTools.text / image 与 pi_probe.ts 工具回传：OCR 不能只写 details，必须进入 content 的文本块，保证模型可见。

## 后续顺序与验收边界

整体理解确认 → design-impact-review → 文档与代码实施 → 针对性测试与可执行的真实 OCR 检查。

常规回归不启动真实 pi 或模型服务。替身测试、真实 OCR 静态截图检查、真实 Agent 工具循环、Windows 打包及真实游戏验收分别报告，不互相替代。影响审查和本地实现验证已完成，未验证范围以实施记录为准。
