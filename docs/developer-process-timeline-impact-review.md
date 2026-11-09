# Developer GUI 详情、Skills 目录与过程时间线

2026-11-09。经交互讨论确认后实施；这是可逆的展示增量，不新增领域概念或 ADR。

## 接受的变化

- 错误详情复制后，按钮短暂显示“复制成功”（1.5 秒，可重复点击）。
- 运行中日志继续复用详情弹窗，但使用“复制详情”、展开／收起详情等中性文案，不提示截图或报告错误。
- Session “+”→工作区与页面增加“打开 Skills 文件夹”，打开当前数据目录的持久化 `skills/`；缺失时按既有规则初始化，存在时不覆盖或补齐。
- 每轮一个默认收起的“思考与工具”区，标题显示当前进度。展开后，思考段落和工具调用按发生顺序，以左侧竖线和节点串联；每个工具的参数与结果独立默认收起，最终业务回答显示在外部。
- 工具失败仅该行标红且保留失败文字，不自动展开，不在标题增加失败统计。已有错误详情入口保留。用户自行展开后，后续更新尊重其选择。

## 影响审查

已确认的原实现差异与路径：

| 位置 | 原行为与影响 | 实施 |
| --- | --- | --- |
| `gui.ErrorDialog` | 复制直接写剪贴板，无反馈；提示、按钮都假定是错误 | 增加短暂按钮反馈；默认保留错误语义，日志显式选择中性详情 |
| `developer_gui.TrialDialog.show_log_details` | 普通日志打开同一错误弹窗，标题虽覆盖，内容仍提示报告错误 | 选择中性详情，原始记录和详情展开方式保持 |
| `gui.NotificationList.notify` | 持久通知详情也复用错误弹窗 | 同步使用中性详情 |
| `developer_gui.RepairPage.build_menus/open_skills` → `agent_skills.initialize_skills` | 已有知识库入口但没有 Skills 入口；初始化已能创建持久化源目录并保护现有内容 | 复用已有初始化与系统目录打开，不复制出新的可编辑临时目录 |
| `repair_chat.RepairChat`、`RepairPage.update_raw_output/show_event/replay_history` | 每轮原始输出集中收起，工具摘要在外；缺少交错顺序 | 完整消息提取思考／过程段落，按工具首次出现位置关联节点；后续宿主/pi 事件继续更新同一调用 |
| `RepairPage.load_older_history` | 补载后重排聊天 entries | 每次渲染重新绑定工具详情索引，防止打开其他轮次详情 |

Skills 源目录原本就是持久化的；`skill_snapshot` 临时目录是每轮内容固定和取消清理机制，不是源目录。此次保留快照、路径映射、只读权限及下一条消息生效语义。

不改 Agent 事件、工具返回值、日志格式、模型上下文、调用计数、权限、Session/Candidate 生命周期，不迁移历史。历史从完整消息和已有工具事件恢复，未完成流式内容仍不恢复。工具参数不再重复出现在思考正文中；完整最终 JSON 业务回答由外层消息呈现，底层原始日志仍完整保留。

## 检查与限制

定向检查覆盖：两级折叠、事件顺序、失败红色与文字、不自动展开、宿主/pi 合并与重复调用、历史恢复和补载索引、滚动与长行换行、持久目录初始化／保留手工修改、详情复制反馈、普通日志中性文案及中英文资源。

Windows 原生 DPI、系统文件管理器及真实模型／游戏未验收；不把 offscreen 检查当作实机证据。执行结果见本次交付记录。

## 本地执行证据

- `QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest -q tests/test_repair_chat.py tests/test_raw_output.py tests/test_error_handling.py tests/test_gui_language.py tests/test_chat_ui.py tests/test_user_gui_p0.py tests/test_developer_gui.py tests/test_agent_skills.py`：195 passed。
- 随后补充历史重排索引刷新、重排详情链接测试、实际日志详情入口的中性文案／复制反馈断言，执行 `QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest -q tests/test_repair_chat.py tests/test_raw_output.py tests/test_developer_gui.py`：91 passed。与上一组有重叠，不累加为独立用例数。
- 中文 `.ts`／`.qm` 已同步；首轮新文案未写入目录导致的翻译检查失败已修正，后续上述回归通过。
- offscreen 截图检查展开／收起：左侧竖线与节点、失败工具行红色及最终回答独立展示符合决定。长行换行／缩放及阅读位置由相关回归覆盖。
- `git diff --check` 通过。未运行真实 pi、模型或游戏测试，未做 Windows 原生验收。
