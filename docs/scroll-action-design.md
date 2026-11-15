# 滚轮 Trusted Action 设计

## 已确认

- 2026-11-15：开发者确认 PowerShell 实验在游戏客户区 `(890, 350)` 上下滚轮可行。该结果是独立注入实验的人工反馈，不代表正式执行器接入已验收。
- 新增应用登记的 `control.scroll`，参数表达客户区坐标、上下方向及滚动格数 `steps`，默认 1。
- 格数表示滚轮刻度，不表示游戏界面移动的像素距离；实际滚动效果由游戏决定。
- `steps` 仅接受 1–10 的整数，默认 1。
- 格与格之间固定间隔 0.2 秒，不提供自定义速度参数。

## 完整契约（已确认）

- 方向仅接受 `up`、`down`，必填；每格对应 Windows 滚轮增量 ±120。
- 坐标支持互斥的 `centerxy=(x, y)` 或完整 `x/y`，使用当前游戏客户区原图像素，必须位于客户区内。
- 移动鼠标后滚动，不点击；完成后光标保留在目标处。后续截图沿用默认光标归位。
- 返回 `None`，不表示业务目标完成；调用者须重新观察。
- 保持现有 control 权限、Trace、暂停、接管和取消边界。已滚动部分不可撤销，Step 重入后须重新观察，不承诺从剩余格数继续。

## 实现前影响审查

- 设计变化：由不支持滚轮增量新增 `control.scroll`；不替代或废弃已有 Action，不修改 Manifest 格式和权限矩阵，符合 ADR 0023 的应用统一注册边界。
- 已确认：`actions.application_actions` 决定动作列表，`repair_tools` 的 `action_contracts` 读取注册签名/docstring，`stubgen` 生成 Context 声明。新增注册及完整 docstring 后，重新生成 `run_context.pyi`，同步声明测试中的固定 overload 数量。
- 已确认：执行路径为 `ctx.action` → `WorkflowExecutor.trusted_action` → `RunContext.control_input` → `InputSession.execute` → `WindowsInputBackend`。现有输入分支只支持等待、按键、点击和拖动，需新增滚轮分支、绝对鼠标移动及滚轮注入，逐格校验焦点、所有权和光标位置。
- 已确认：Runtime 仅为点击、拖动和 OCR 附带已有观察诊断图；滚轮同属坐标动作，应加入同一集合，不触发额外截图。
- 已确认：物理输入钩子已识别滚轮接管，并忽略注入输入；无需更改钩子或接管规则。滚动期间应标记动作进行中，使失焦按既有中断语义处理，不在中途自动取回焦点继续滚动。
- 后续工作：实现注册/输入/诊断图，生成类型声明，同步开发教程及当前状态；覆盖参数拒绝、双向刻度、固定间隔、接管/取消/失焦、注入失败和真实分发路径。
- 潜在风险：Windows 权限差、光标裁剪、多屏和游戏处理节奏可能影响效果；模拟测试无法证明真实游戏接受全部刻度。独立实验人工成功与正式接入验收分别记录。

## 实施与验证

- 已接入 `control.scroll`、Win32 绝对移动/滚轮注入及逐格所有权检查；移动后先协作等待 0.2 秒稳定悬停，相邻格间隔 0.2 秒，光标偏离目标超过 2 像素则中断，避免继续滚动其他区域。
- 动作签名/docstring 自动进入 Agent `action_contracts`，已重新生成 Context 类型声明，并补充开发教程。不新增 ADR 或领域术语，沿用既有 Trusted Action 模型。
- 普通定向回归首次为 131 passed、1 failed；失败为既有 `tests/test_input_activity.py::test_evidence_path_follows_refreshed_observation_after_focus_wait` 仍断言 PNG，而 `ApplicationService._capture_screen` 已输出 AVIF，与本次滚轮修改无关，未修改该测试。
- 完成补充用例后运行：`QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest -q tests/test_scroll_action.py tests/test_stubgen.py tests/test_input_control.py tests/test_capture_cursor.py tests/test_input_activity.py tests/test_repair_tools.py tests/test_manifest.py tests/test_workflow.py -k 'not test_evidence_path_follows_refreshed_observation_after_focus_wait'`，结果 **174 passed、1 deselected**。
- 覆盖坐标两种形式、默认格数、1/10 边界、非法参数、上下刻度补码、虚拟桌面映射、注入失败、接管/暂停/取消/失焦/光标偏移中断、手动恢复后 Step 重入、Trace、Agent 契约可见性及类型检查。
- 未运行全量回归或真实 pi/模型测试；未完成正式接入后的 Windows 与真实游戏验收。
