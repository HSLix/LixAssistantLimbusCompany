# Developer 模板匹配调试页

2026-11-06，开发者逐项确认设计并授权实现。

## 设计与用法

Capture 下方的 Template Match 页提供真实算法调试。左侧按 Asset 逻辑名组织树，选择 Asset 匹配整组，选择 PNG 叶子只匹配该图；单图选择时按需读取、验哈希并预览。每次进入页面后台扫描目录及 PNG／标签文件的状态（路径、大小、纳秒修改与状态变更时间等），整体未变不重建树；变化后保留仍存在的选择及展开状态。检查不逐张读取图片内容，实际预览与匹配仍校验完整哈希。

右上手动截图并固定原始像素，展示编号匹配框和可复制的分数、坐标、图片身份。截图独立于 Capture 的保存预览；只有再次截图才观察游戏。右下设置阈值（默认 0.9）、NMS（默认开启）、NMS IoU 阈值（默认 0.5）及整组优先标签（默认空）。可在原图拖选搜索区域，或恢复全图。修改选择、参数或区域清除旧结果，点击运行才匹配。

采用正式原尺寸 BGR 匹配算法及优先标签短路／回退、跨模板 NMS 规则，不提供缩放和算法切换，不执行点击，不写素材、Trace 或 Usage Index。截图／匹配失败通过现有错误入口报告；后台活动期间禁用相关操作。

## 实现前影响审查

- **新增需求**：资源树、按需预览、进入页面的增量检查及固定截图的真实匹配调试。未废弃现有 Capture、OCR 或正式匹配需求，无已确认架构冲突。
- **确认的影响**：`gui.py:MainWindow.__init__/render_state` 显式枚举页面，导航与忙碌状态必须同时接入。原有 OCR 紧跟 Capture 的测试需要允许新页插入。
- **确认的影响**：`developer.py:DeveloperHost.capture(update_preview=False)` 已支持独立截图；`developer_gui.py:OcrView` 已提供原像素框选与编号覆盖层，可直接复用，不修改截图像素。
- **确认的不兼容点**：`assets.py:AssetLibrary.match` 对非空结果无条件写 Usage Index，直接用于调试会污染运行事实。增加默认保留原行为的只读调用选项，调试入口传入关闭值并使用空事件接收器；运行端调用不变。
- **校验边界**：单图入口必须校验逻辑名、完整 SHA-256、归属路径及文件内容。目录扫描不跟随符号链接，读图仍通过 AssetLibrary 的路径与哈希校验。
- **所需改动**：后台入口、专用 GUI 模块、导航、中文翻译、用法／当前状态和针对性测试。现有 Asset／Asset Library 术语足够，无新增领域概念；交互可逆，不新增 ADR。
- **潜在风险**：快速检查依赖文件系统状态，不提供对抗性变更检测或整个素材库的事务快照；扫描中删除文件可明确报错后再次进入重试。低阈值且关闭 NMS 可能产生大量结果。大规模素材库、Windows 包与真实游戏性能需另行验收。

## 验证

- 针对性检查：`QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest -q tests/test_template_match_lab.py tests/test_developer_gui.py tests/test_gui_language.py tests/test_assets.py`，101 passed。覆盖整组优先短路／回退与单图匹配、ROI 原坐标、NMS 参数传递、不写运行数据、原入口默认写索引、哈希／路径校验、活动互斥、元数据扫描不读图片、页面进入检查、未变化保留节点对象、变化后保留选择／折叠、图片删除、独立固定截图及结果失效／错误清理。
- 默认回归：`QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest -q`，940 passed、103 skipped、2 failed。失败为 `tests/test_example_workflow.py::test_exp_mirror_pages_feed_plan_and_shared_actions[False/True]`，仍期待三个旧 Task 结果并读取已删除的 `example/workflow/exp.py`，与[先前记录](pi-1.5-compatibility.md)一致；本次未改动示例业务。全量回归未通过，跳过项不计通过。
- 用合成截图和真实匹配结果渲染 1150 × 900 中文整窗并目视检查；调整了长哈希造成的左栏挤占，单图标题缩写哈希，悬停显示完整身份。使用与现有测试一致的 macOS 系统标题栏替身，不代表原生窗口验收。
- 本机临时目录的 3000 个空 PNG 占位文件，未变化扫描三次为 72.7／74.5／73.6 ms，签名与文件列表一致；只检查元数据，不解码。这是本机合成目录测量，不代表 Windows 或真实大型素材库性能。
- `git diff --check` 通过。未执行 Agent 测试；不涉及 Agent 接入。Windows 成品、真实游戏与大规模素材库性能尚未验收。
