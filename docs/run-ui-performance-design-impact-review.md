# 运行窗口高频日志：设计与影响审查

2026-11-08。开发者已接受四项方向：状态与日志分离、合并界面更新、有限近期展示、仅在相关变化时刷新设置及版本。开发者进一步确认运行弹窗最多展示最近 300 条可见日志，完整 Trace 保留并通过 Logs 页回看。最终共同理解已确认，开发者已授权实施；本地实现与验证见文末，不代表 Windows 或游戏验收。

## 事实与问题边界

- 提供的 Run 85 Trace 为 1,668,008 字节、3171 条记录。网络错误弹窗中的一轮空检测匹配 10 组素材，通常新增 74 条 Trace。连续业务日志间隔由约 4.71 秒增长至约 8 秒；`observe.wait(seconds=0.5)` 只是检测之后的额外等待。
- `ApplicationService._record_locked` 追加单条 JSONL，不重写整个文件，但每次打开和关闭文件。`_changed_locked` 在服务锁内深拷贝包括全部 Trace 的状态，再调用 GUI 回调。
- `StateBridge.changed` 将完整状态排入 GUI 线程。`UserWindow.render_state` 每次刷新版本卡片和读取 Agent 设置；`TrialDialog.render` 每次遍历全部 Trace，即使本次只有内部事件且不显示。
- 本地使用提供的网络弹窗截图与 10 组素材，解码和匹配约 0.35 秒；不等于 Windows 性能。Action 计时之外的耗时包含多条路径，不能全部归于日志。
- 原失焦竞争异常、原生聚焦等待以及模板匹配本身是独立问题。本项四点优化不改变输入所有权、Step 恢复和窗口前台安全检查。

## 接受的决定与实施边界

1. Execution Trace 是完整执行证据，运行弹窗是有限投影；300 条上限只计算 Info／Warning／Error 业务日志与现有可见运行状态，内部检查和 Debug 不占名额。
2. 正式运行与 Developer Trial 共用同一实现。保留颜色、时间、转义及详情入口；移出近期窗口的记录仍在完整 Trace 中。提示更早记录到 Logs 页查看。
3. 位于底部时跟随新增；回看时尽量保留原记录和偏移。若正在看的记录已经移出 300 条范围，则定位到仍保留的最早记录。运行结束仍沿现有流程关闭弹窗。
4. GUI 获取不包含完整 Trace 的轻量状态，以及自上次序号之后的新增可见日志；每次拉取和展示的条目有界。GUI 长时间落后或晚打开时取最近 300 条，不为补画旧记录阻塞界面。原始 Trace 不因 GUI 合并而丢失。
5. 用 GUI 定时器每 100 毫秒合并处理最新状态，不为每个底层事件排入完整状态快照。暂停、恢复、停止请求直接进入既有控制路径，不依赖日志展示进度；持久化失败及输入释放失败边界不变。100 毫秒是刷新目标，不是系统响应的硬时限。
6. 设置和版本信息只在相关状态变化或既有版本检查时更新，不在每条窗口检查、截图或素材匹配事件后重新读取。保留双窗口、活动切换、默认版本变化及设置变更后的正确刷新。
7. 保留完整 `service.state` 查询的诊断／测试语义，GUI 高频路径改用轻量接口；现有完整 Trace、序号、日志格式、Sharing 和 Agent 读取接口不迁移。
8. 本次不加入日志分卷、后台写盘、匹配缓存或新依赖。先消除已确认的历史长度相关开销，再根据测量决定其他优化。

## 影响审查（源码已检查）

| 路径 | 确认影响与实施要求 |
| --- | --- |
| `src/lalc/application.py:state/_changed_locked/_record_locked` | 新增轻量状态和有界增量读取；高频通知不能再复制全部 Trace。记录追加和持久化失败行为保留，复核暂停恢复期间的独立回调路径。 |
| `src/lalc/gui.py:StateBridge/run_gui/GuiCoordinator` | 合并 GUI 通知，定时读取最新状态；两个窗口共用一次读取，打开、关闭和重载时正确管理生命周期。 |
| `src/lalc/gui.py:MainWindow.render_state/UserWindow.render_state` | 两类入口都消费轻量状态；避免无变化的设置与版本读取；保留最终结果和致命错误处理。 |
| `src/lalc/developer_gui.py:TrialDialog` | 有界增量展示和详情缓存，最多 300 条；暂停按钮避免获取完整 `service.state`。 |
| `src/lalc/repair_tools.py:trial_run/read_run_log` | 试运行的 50 毫秒轮询改用轻量状态及最后序号；工具输出契约、完整日志读取保持。不是对模型／pi 工具循环的改造。 |
| `src/lalc/page_preview.py:wait_for_restart` | 重启等待只读轻量活动状态，不复制完整历史。 |
| `src/lalc/run_logs.py/run_log_gui.py/run_log_sharing.py` | 历史读取已经分块；保持完整证据、固定快照、搜索和传输格式。 |
| `tests/test_user_gui.py/test_user_pages.py` | 现有测试直接连接状态信号，须同步正式通知入口，不能只修生产初始化。 |
| `tests/test_developer_gui.py/test_input_control.py` | 同步弹窗数据来源、详情及暂停按钮断言；保留接管和输入释放检查。 |

已确认的不一致：接受的新设计要求有界增量更新，当前通知和弹窗仍重复处理全量历史；既有运行窗口文档明确暂未限制累积展示，需用本设计替代这一点。

潜在风险：合并状态不能吞掉最终结果；晚订阅和切换 Run 不能混入旧日志；裁剪富文本不能破坏详情链接及回看位置；缓存更新条件不能遗漏外部发布或设置变化。需要定向测试，而不能仅凭吞吐量判断正确。

## 实施与验证顺序

1. 轻量状态、有界可见日志读取及通知契约，覆盖快照隔离、序号、跨 Run、最终结果和完整 Trace 保留。
2. GUI 合并更新及设置／版本刷新，覆盖事件突发、双窗口、定时器清理和控制请求。
3. 弹窗 300 条限制、详情与滚动锚点，同步中英文资源和相关文档。
4. 用提供的 Trace 或同结构合成记录比较不同历史长度的通知工作量，验证每次载荷和展示条目有界；普通 GUI、执行及日志测试串行执行。不启用 Agent 测试。

## 本地实现

- `status` 排除历史 Trace 并提供最后序号；`ui_snapshot(run_id, after_sequence)` 在同一锁内取得状态及最多 300 条新增可见记录。运行建立时清空近期投影，不删除完整 Trace。
- `on_change` 改为无参数失效通知；实际 GUI 回调只设置线程安全标记，不复制状态、不投递逐事件 Qt 信号。`StateBridge` 每 100 毫秒合并读取一次快照，关闭时停止定时器及通知订阅。新打开窗口独立取得近期日志，两个已有窗口共用同一批更新。
- `TrialDialog` 按新增序号追加，裁剪色块和详情索引到 300 条；超限重建固定大小文档并恢复仍存在的阅读项及偏移。纯内部事件不占近期条目。
- Agent 设置的就绪状态在既有配置变更路径更新；既有两秒版本检查也只比较设置文件的身份、修改时间及大小，发现外部替换或修改才重读配置。版本卡片沿此检查及明确选择刷新，不跟随底层 Trace 扫描文件。
- GUI 普通状态检查、页面重启等待、Developer Trial 轮询均不再读取完整 `service.state`；完整查询与文件证据契约保留。没有新增依赖、分卷、后台写盘或匹配缓存。

### 性能测量

本机使用 Run 85 记录结构扩充为不同长度的独立字典，近期投影固定为 300 条简短业务日志，各操作测量五次取中位数：

| 历史记录数 | 原全量状态复制 | 新界面快照（含 300 条） |
| --- | --- | --- |
| 3,000 | 12.06 ms | 0.272 ms |
| 30,000 | 129.78 ms | 0.282 ms |
| 100,000 | 460.87 ms | 0.284 ms |

这是快照成本对比，不能换算为 Windows 每轮检测时间或按钮延迟保证。完整 `service.state` 仍按既有约定持有并复制全部 Trace，极长运行的总体证据内存不在本次有界 GUI 投影的保证内。

### 验证

三组普通回归串行执行，均正常退出：

```sh
QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest -q tests/test_workflow.py tests/test_input_control.py tests/test_input_activity.py tests/test_focused_observation.py tests/test_game_restart.py tests/test_developer_policy.py tests/test_repair_tools.py tests/test_error_handling.py tests/test_manifest_transition.py tests/test_ocr.py tests/test_page_drafts.py
# 238 passed
QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest -q tests/test_run_logs.py tests/test_run_log_sharing.py tests/test_workflow_sharing.py tests/test_sharing_resources.py
# 49 passed
QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest -q tests/test_run_ui_updates.py tests/test_developer_gui.py tests/test_user_gui.py tests/test_user_gui_p0.py tests/test_user_pages.py tests/test_gui_language.py
# 145 passed, 3 skipped
```

合计 432 passed、3 skipped。新检查覆盖：历史 Trace 禁止扫描和复制时轻量接口仍可用、万条内部事件不挤出业务日志、完整落盘一致、快照隔离及跨 Run、两万次工作线程通知合并、读取期间再次变更不会丢失、真实定时器消费及幂等退出、300 条裁剪、详情索引、阅读锚点／底部跟随、按钮不读取完整 Trace、配置及版本不随事件重读、外部配置更新和主题背景。

中途组合 GUI 检查曾以 139 退出；独立复现及 HEAD 临时副本对照后，补齐新增 `StateBridge` 的应用级父对象、解除订阅和主线程销毁，原先单独异常退出的 P0 检查及上述最终组合均正常结束。此前失败或异常退出的运行不计入通过数。日志组正常退出时另有 Python 的不可回收对象 ResourceWarning，未将其记为功能失败或现场验收。

浅色和深色离屏截图已检查。新增历史提示暴露了原生弹窗背景不随 Fluent 主题变化的问题，运行弹窗现沿用已有 CustomStyleSheet 机制设置对应背景，并以实际绘制像素验证，确保提示与控制文字可读。中英文资源已编译，`git diff --check` 通过。

未执行全量回归或 `--run-agent-tests`，未调用真实 pi／模型服务。Windows、打包成品、真实游戏、真实输入钩子和按钮端到端延迟仍未验收；本项不修复原失焦竞争异常，也不承诺每轮检测仅耗时 0.5 秒。
