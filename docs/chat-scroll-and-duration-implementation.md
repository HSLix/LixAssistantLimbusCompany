# 聊天贴底与结束耗时

2026-11-12，依据本次用户确认的简化方案及结束耗时需求。

## 决定与影响

- 原来每次渲染、缩放分别判断是否位于底部，计时刷新固定保留旧位置；改为由聊天区保留跟随状态，排版改变滚动范围时沿用该状态置底。用户上滚停止跟随，回到底部恢复；主动展开详情及补载历史仍保留阅读位置。
- 运行时“已工作”（Working for）只在 GUI 计时；新增轮次结束耗时“耗时”（Worked for）。`RepairConversation.run` 用单调时钟记录本轮验证输入后、准备与执行直至收尾产物检查的耗时，包含工具执行和人工等待。
- `duration_seconds` 是轮次 `result.json`、最新 `result.json` 及 `round_finished` 事件的可选新增字段；正常完成、错误及正常取消共用收尾路径。宿主崩溃后恢复的中断记录没有完整耗时，不补算。
- `RepairPage.show_event` 在现场及历史回放中读取结束耗时，停止对应现场计时；`RepairChat.activity_html` 按轮显示记录，零秒有效，缺失或无效值不显示。最新轮次和上滚补载的旧轮次共用事件恢复路径。
- 不改变折叠选择、工具执行及合并规则、模型消息、权限或会话生命周期；旧数据不迁移。新增英文文案及中文翻译已同步。

## 证据与验证

- 原实现离屏观察到：`render` 已恢复滚动位置后，滚动范围仍会变化；`documentSize()` 不能视为排版已经稳定。另复现计时 9 秒变 10 秒时标题换行，位置仍为 1565，底部变为 1580，导致后续停止跟随。
- 回归覆盖过程区展开／收起、工具生命周期事件、缩放、阅读历史位置、计时刷新引起标题增高、键盘上滚与回到底部恢复跟随。
- 耗时检查覆盖未启动真实 pi 的失败收尾持久化、现场结束、最新历史恢复、旧轮次补载、零秒与缺失／无效记录。
- `QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest -q tests/test_repair_chat.py tests/test_raw_output.py tests/test_chat_ui.py tests/test_agent_diagnostics.py tests/test_gui_language.py tests/test_developer_gui.py tests/test_developer_session.py`：189 passed，进程正常退出。
- 最后补充自动置底不触发历史补载的信号保护后，串行重跑 `tests/test_repair_chat.py tests/test_chat_ui.py`：49 passed，与前一组重叠，不累加。
- 中文 `.ts` 已同步编译为 `.qm`。未运行全量回归、真实 pi／模型／游戏或 Windows 原生检查；离屏验证不等同于实机闪帧验收。
