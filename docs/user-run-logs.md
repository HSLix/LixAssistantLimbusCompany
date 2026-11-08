# User GUI 运行日志

2026-11-08：运行弹窗的实时展示独立限制为最近 300 条，超出部分仍完整保存并在本页按原规则读取；历史页的筛选、固定快照和分页契约不变。见[高频日志专项记录](run-ui-performance-design-impact-review.md)。

2026-11-08 增量：列表名称、时间、排序及单日志导入导出按[单日志传输设计与影响审查](run-log-sharing.md)更新，其他阅读契约保持。

2026-11-06，经 grill-with-docs 逐项确认、只读 design-impact-review 和开发者最终授权实施。本页记录本次接受范围，不代表 Windows 或真实游戏验收。

## 已接受的交互

- General Settings 上方新增 Logs。左侧每项对应一个顶层 Run 的 Trace，包含正式运行、CLI 运行和 Developer Trial；默认选最新 Run，同一 Plan 的多个 Task 不拆分。
- 从最新开始倒序按需读取。展示 `component_log` 和 Trusted Action 的成功／失败／中断结束事件；其他 Trace、Agent 对话和独立 Developer 操作不混入。
- 默认 Error、Warning、Info 开启，Debug 关闭。关键词不区分大小写、连续文本匹配消息、组件／动作名及完整详情，包括参数、OCR 文字、匹配结果和错误。仅图片保留有截图引用的项，图片缺失仍显示占位与文字。
- 筛选以顶部日志及屏幕偏移为锚点；该项被过滤则定位到附近较旧匹配项，该侧无匹配才寻找附近较新项。不要求还原条件后恢复此前位置。
- 不监控文件、不自动刷新、无刷新按钮。首次选择运行读取最新快照；再次点击当前运行检查文件，未变化保持原样，有新增可展示日志则提示“有新日志 · 回到最新”，点击才接受新快照并置顶。纯内部 Trace 增长不触发提示；切换运行直接读取最新。
- 浏览及继续翻页固定于已接受的文件边界。未换行的尾记录待完整后再接受；文件缺失、替换或截断不假装正常追加，重新选择时重读或报告不可用。
- 与运行窗口共用等级颜色色块：Info 蓝色、Warning 黄色、Error 红色、Debug 中性色，适配深浅主题。记录时间按本机时区显示为 `YYYY-MM-DD HH:MM:SS`，缺失或损坏时显示“—”。
- 正文默认三行，展开／收起保持阅读位置，搜索始终使用全文。图片先按原图尺寸比例预留位置，接近视口才解码；成功或失败均不改变占位高度。点击图像打开大图。

## Trusted Action Debug 与标注

所有经过共用执行器的实际 Trusted Action 调用自动有 Debug 记录。沿用 `trusted_action_returned/failed/interrupted`，不重复复制成 `component_log`；保留参数、结果、错误和调用关系。开始事件也带 Debug 元数据，但页面只显示结束事件。校验前被拒绝的调用不冒充已执行。`ctx.log()` 仍不开放给正在执行的 Trusted Action。

Click／Drag 固定动作前已有帧；OCR／Match Asset 关联实际识别帧，不额外截图。无帧标记 `image_unavailable`，不因此阻止操作；有帧则保存正式证据，证据／Trace 写入失败仍沿原失败边界传播。采集时间与记录时间分开保存，同一 observation 复用已保存证据，不重复编码。

| 动作 | 展示 |
| --- | --- |
| Click | 横纵十字线定位点击坐标 |
| Drag | 起点至终点的细红箭头 |
| Match Asset | 按返回顺序编号画框，全文列出编号与原始 score；称为匹配分数，不声称统计准确率 |
| OCR | 完整保留本次返回 items，不重跑 OCR 或绕过 min_score |

失败／中断项标为 attempted，标注不证明动作成功。原图不改写，不另存永久标注图。

共用接口 `image_annotations.action_annotations(record)` 从已有结构化参数／结果提取标注；`paint_annotations(painter, target, image_size, annotations)` 按原图像素坐标绘制 cross／box／arrow。绘制接口不依赖日志页、Run 或执行器，可在其他页面直接复用；本次不改变独立调试操作的日志归属。

## 影响审查与实现

确认可复用：`runtime.trusted_action/_invoke` 已统一管理动作权限、输入、返回、异常和中断；应用层已有 Trace 与 observation 证据路径。无需更改 `TrustedAction` 登记类、Manifest、RunContext 接口、Ledger 或 Agent 权限。

确认不适合直接复用：Agent `RepairTools.read_run_log` 整文件正序读取，公共 `service.state` 深拷贝完整运行状态。新页不用它们分页；新增 `run_logs.py` 双向分块扫描与 `run_log_gui.py` 虚拟列表，最多保留 240 项、12 张缩略图缓存。旧页可重新读取，原始 Trace 不删减。原 Agent 工具接口保持不变，Sharing 现有递归 evidence_id 收集可携带新增引用。

`focused.py` 补记采集时间；`application.py` 复用已保存证据；`runtime.py` 关联指定动作的截图。`gui.py` 新增导航，同步导航测试和中英文资源。自有界面文字随 GUI 语言，原始日志及错误详情不翻译。

潜在成本：自动 Debug 使 OCR／Match Asset 使用帧也可能落盘，增加磁盘用量。首版不建持久搜索索引，稀疏搜索可能扫描全文件；后台扫描，条件改变取消过期任务，不承诺超大日志即时返回。图片读取和解码不在主线程，仍受原图尺寸、可用内存与磁盘速度影响。

## 验证

针对性回归覆盖双向分块分页、UTF-8 边界、固定快照、半行追加、截断、损坏记录、完整正文搜索、证据路径及尺寸、GUI 更新提示／筛选锚点、文字折叠、标注缩放，以及执行器成功／失败／中断与同帧复用。

```sh
QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest -q tests/test_run_logs.py tests/test_workflow_observability.py tests/test_user_gui.py tests/test_user_pages.py tests/test_gui_language.py tests/test_workflow.py tests/test_ocr.py
QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest -q
```

本次默认全量回归：977 passed、106 skipped、2 failed。两项失败均为原有 `tests/test_example_workflow.py::test_exp_mirror_pages_feed_plan_and_shared_actions`，仍依赖已移除的 exp.py 和 exp 调度；本次不修复示例，也不报告全量回归通过。新页离屏预览已检查文字折叠、原图与十字线显示。

相关功能／导航／语言组合复测 134 passed、3 skipped；随后增加跨屏长项收起的位置保护，最终 `tests/test_run_logs.py` 单独复测 12 passed，含解码资源不足回退。全量计数来自此最后边界修订之前，不冒充最终版本再次全量执行。

本机合成样本 200,000 条、48,977,780 字节：首批 60 条约 0.0031 秒，无匹配词的全文件搜索约 0.3544 秒。仅代表此机器／样本，不是 Windows 或任意日志的性能保证。

本次不启用 Agent 测试。offscreen／替身与 Windows、真实模型、真实游戏验收分别报告。

## 2026-11-07 折叠重叠修复

经只读影响审查及开发者确认后修复：折叠检测创建第 4 行后未设置宽度和位置，默认坐标 (0, 0) 导致隐藏文字叠到首行。现在先定位溢出行，再结束可见三行的排版，使现有裁剪正确生效；不改变全文搜索、图片占位及视角保持。

新增真实 delegate 绘制像素对比，覆盖显式换行、自动折行及反复展开／收起。串行分进程验证：日志专项 14 passed；User GUI／业务页面 38 passed、3 skipped，均正常退出，`git diff --check` 通过。未运行全量、Agent 或 Windows 实机验收。

上述三个文件合并运行时，用例执行结束后在 pytest 清理的垃圾回收阶段出现原生崩溃（退出码 139）。临时使用 HEAD 原排版方法并排除新增用例后仍复现同一崩溃，未修改基线文件；不将该合并运行报告为通过，也不在本次折叠修复中扩展处理 Qt 清理问题。
