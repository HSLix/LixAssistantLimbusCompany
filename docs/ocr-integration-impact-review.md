# OCR 接入影响审查

日期：2026-11-01。输入：[已确认设计](ocr-integration-decisions.md)。审查时只读检查源码与测试，未运行真实 OCR、Agent 或 Windows 构建。

## 设计变化

- 从模板识别扩展为模板识别与本地 OCR 并存；新增应用注册的 observe.ocr，不改变 Manifest 注册、版本或 Asset 存储。
- game_screenshot 从原图与网格图扩展为同图 OCR 完整结果；不新增 Agent 工具或权限。
- OCR 识别失败时仅截图工具允许保留图片并返回 ocr_error；脚本 Action 失败仍抛错。取消或接管不降级。
- 暂不支持韩文；不自动替换模型，不增加通用 OCR 文件读取或网络输入权限。

## 已确认的影响

1. **Action 路由与内部边界**：actions.py:application_actions → RunContext → runtime.py:trusted_action → ApplicationService 的回调。新增 OCR 需要贯穿这条路径，并保留 _active_action 的 observe 检查；单纯在 actions.py 直接调 SDK 会丢失当前截图与输入所有权边界。现有 _match_asset（application.py）明确不隐式截图，OCR 复用这一语义。runtime.py:_normalize_value 不支持 Any 作为递归返回值类型，首版 Action 使用既有 JSON 容器与具体类型的组合注解，stubgen.py 直接展开生成，不扩展整个类型校验系统。
2. **Agent 实际可见结果**：repair_tools.py:game_screenshot 已保留同一个 session 的原始图与网格副本，适合直接复用原像素。RepairTools.text 同时构造 content 与 details；pi_probe.ts 原样回传。OCR 必须进入文本 content，并在 details 保留相同对象，不能只写内部字段。工具描述、Python docstring 及 sop.md 需要同时更新。
3. **资源与依赖**：pyproject.toml:automation 尚无 OCR 依赖；LALC.spec 尚未收集 OCR 模型与推理依赖。需固定 RapidOCR、ONNX Runtime 版本及模型/字典摘要，显式本地路径加载并检查缺失资源，防止运行时隐式下载。scripts/build_windows.py:assemble 及 tests/test_windows_packaging.py 应检查新增成品资源。
4. **取消与状态有效性**：FocusedAutomationSession.check 会在窗口失效时丢弃图像；InputSession.check 会检测物理接管。OCR 计算前后必须检查，不能把 UserInterruption 当作普通 OCR 错误返回。Agent 入口沿用工具取消事件，且失败后的 checkpoint 必须仍能中止本次工具。
5. **既有测试**：tests/test_repair_tools.py 的截图测试使用平台替身；新增 OCR 后若不注入识别替身，会让普通测试加载真实模型。需保持这些测试离线，另对共享服务做坐标、阈值、无文字、资源故障、串行复用和中断测试。tests/test_stubgen.py 负责生成声明一致性与 Pyright 调用检查。
6. **实施中追踪的历史假设**：README、Stage 2 规格及 ADR 0020 原有“OCR 尚未实现”说明需要标注实施增量；example/workflow 的全部 Action 教学样例及注册清单测试需要包含 observe.ocr，保留覆盖所有应用动作的原断言，而不是删掉覆盖要求。

## 潜在风险与验证

- 模型包与运行时 DLL 在 Windows 冻结环境的组合尚未验证；补充资源收集和构建检查后，仍需 Windows 本机离线启动与首次 OCR 验收。
- 推理调用本身不能保证即时中断；前后 checkpoint 防止失效结果继续使用，实际取消延迟需在目标机器量测。首版不为硬超时另起 OCR 子进程。
- 游戏小字号、描边字体、动画背景的准确性与 CPU 争用未知；真实 OCR 静态样本检查仅证明基础链路，不等于真实游戏验收。韩文仍不在支持范围。
- 全图 OCR 增加截图工具耗时及文本上下文体积；按已确认要求完整返回，不截断或摘要。数值准确性不能由置信分数保证。

## 实施顺序

固定依赖与本地资源 → 共用 OCR 服务 → Action 调用链与生成声明 → 截图工具及描述 → 打包与文档 → 针对性测试 → 默认回归。无架构冲突或需补充确认的阻塞项；不修改现有不可变 Manifest、Asset 或其他进行中的 Stage 5 文档。

实施结果与执行证据见 [实施记录](ocr-integration-implementation.md)。
