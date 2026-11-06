# Developer OCR 测试页：设计与影响审查

2026-11-06，开发者逐项确认以下设计后授权实现。

## 设计变化

新增 Capture 后的 OCR 测试页。截图后自动识别全图；鼠标拖选结束后只重新识别当前截图的选区，不重新截图。保留整图，识别矩形框与编号、下方可复制文字整体替换旧结果，编号按 OCR 原顺序从 1 开始。“识别全图”恢复全图结果。

本页独立持有截图，复用现有模型与默认分数。识别期间禁用本页操作，失败清除旧结果并明确提示。不增加图片导入、结果保存、模型设置、Agent 工具或运行权限。

## 已确认的影响（实现前源码检查）

- `developer.py:DeveloperHost.capture` 会替换 Capture 使用的共享 `preview`；新增不更新该预览的调用方式，防止 OCR 截图影响素材保存。现有调用默认行为保留。
- `developer_gui.py:CropView` 已处理等比展示、原图坐标换算、框选及放大镜，可用子类增加识别框展示；只对松开鼠标后的非空区域触发 OCR。
- `ocr.py:OcrService.recognize` 已接受内存 BGR 图及区域，输出原图坐标；通过 `recognition.client_image` 转换原始截图，复用校验及模型，不修改识别契约。静态截图复识别不要求游戏窗口仍存在。
- `gui.py:MainWindow` 的导航和 `render_state` 显式枚举页面，需要同时接入新页；后台工作继续走 `launch` 与服务活动互斥。
- 更新中英文翻译、`docs/ocr.md` 用法及 GUI 测试。共享术语没有新增领域概念，且本交互易于调整，不新增 glossary 项或 ADR。

## 潜在风险与验证

需验证选区偏移、缩放后框位置、独立截图、空结果、失败清理及操作互斥。现有模型不支持韩文；原生 OCR 不能即时取消。替身 GUI 测试不等于真实模型、Windows 成品或游戏验收，执行证据在实现后补充。

## 实现及验证

- 已接入四页导航、OCR 静态截图后台服务、原图框与编号、可复制结果、全图恢复及中英文文案；原有 Capture 默认行为保留。
- 导航测试只检查必要入口存在及 OCR 紧跟 Capture，不限定页面总数或完整导航列表，允许后续扩展页面。
- 针对性检查：`QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest -q tests/test_developer_gui.py tests/test_gui_language.py tests/test_ocr.py`，81 passed。包含鼠标按下／移动不识别、松开后传入原像素选区、只截图一次、预览隔离、空结果、错误清理及绘制不修改原图。
- 合成图整窗布局已渲染并目视检查。macOS offscreen 无真实 NSWindow，预览采用现有测试同样的系统标题栏替身；未经替身直接预览在第三方 macOS 无边框窗口库崩溃，不据此声称原生窗口验收。
- 本机真实 OCR 模型静态选区检查成功：合成图中的 `Start battle` 识别为 `Start`、`battle` 两项，返回坐标已含选区偏移。模型可能拆分文字，本页保留原始输出，不合并。
- 未执行 Agent 测试；本改动不涉及 Agent 接入。Windows 成品与真实游戏待验收。
- 默认回归：`QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest -q`，925 passed、98 skipped；跳过项不计通过。首次回归暴露旧导航断言及新增测试对单例方法的替换残留，已更新导航契约并改为在类上替换方法后重跑通过。
- 按开发者反馈去掉完整导航列表断言后，串行复跑 `tests/test_developer_gui.py tests/test_user_gui.py`：55 passed、2 skipped。
