# 开发者面板入口与运行记录列表影响审查

2026-11-11，按本轮用户要求先审查、后实施。本节记录实施前的源码检查，验证结果另附。

## 设计变化

- User GUI 打开 Developer GUI：移除用途提醒弹窗，直接沿原协调器打开或激活窗口。
- Developer GUI 中文显示名统一为“开发者面板”，覆盖入口、窗口标题和编辑权提示；英文名称与内部标识不变。
- 左侧运行记录从一次创建全部项改为首次最近 10 条，滚动到底每次追加 10 条；本机／导入／全部各自先过滤再分页。右侧正文分页与快照规则保留。
- 采用最小范围实现：后台仍扫描完整简要目录以维持原始时间混排，只按需创建左侧列表项。不是磁盘目录分页；不新增持久索引或改动日志格式。

## 已确认的影响

- `gui.py:UserWindow.open_developer` 在 `coordinator.open_window(True)` 前弹用途提醒；Stage 4 的 General Settings 规格也要求该提示，需同步替代。协调器负责提交 User Agent 配置、窗口复用和编辑互斥；删除提醒不绕过这些边界。
- `translations/lalc_zh_CN.ts` 的 `Developer GUI`、`Open Developer GUI`、`Edit in Developer GUI`、`LALC — Developer` 当前译名不统一；需同步编译 `.qm`，更新中文断言并删除不再使用的弹窗文案。
- `run_log_gui.py:RunLogPage.refresh_runs` 调用 `run_log_sharing.list_logs` 后循环创建全部 `QListWidgetItem`。`list_logs` 枚举本机及导入目录、读取开始时间并排序；右侧 `read_page` 已独立分页。此次只拆分列表项追加，不改 Agent 的 `list_runs`、导入导出、Trace 或 Ledger。
- 切换来源／重新进入页面／导入后重建列表，首批回到 10 条；此前选择仍在首批则保留，否则选择最新。继续追加不得切换当前运行、重读正文或跳动已有滚动位置。

## 潜在风险及验证计划

- 大量记录时，完整时间扫描的启动成本仍存在，且损坏日志可能需要扫描多行才能找到时间；若成为瓶颈，再单独设计可重建索引。本次不声称磁盘读取量已限制为 10 条。
- 滚动信号可能在插入项目时重入；批量追加期间屏蔽滚动条信号，测试首批 10 条、后续 10 条、尾批、反复到底、来源切换与过期后台结果。
- 运行记录与用户窗口涉及 Qt 生命周期，相关测试分进程串行执行。验证直接打开／复用窗口与中英文资源；不启用 Agent 测试，不将离屏测试算作 Windows 原生验收。

## 实施顺序

1. 更新 Stage 4、日志用法和当前状态入口，记录本轮取代范围。
2. 删除入口提醒、统一中文资源并编译；增加左侧十条追加及来源重置。
3. 执行针对性日志、窗口与语言回归，记录结果及未验收边界。

## 实施与验证

上述改动已实施。首批不足以产生滚动条时也支持向下滚轮，以及在末项按向下／PageDown／End 继续加载；追加不移动已有位置、不切换右侧运行。

以下命令均从根目录执行，分进程串行运行，均正常退出：

```sh
QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest -q tests/test_run_log_sharing.py
QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest -q tests/test_run_logs.py
QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest -q tests/test_user_gui_p0.py
QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest -q tests/test_gui_language.py
QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest -q tests/test_user_gui.py
```

结果依次为 12 passed、25 passed、21 passed、23 passed、16 passed / 2 skipped，共 97 passed / 2 skipped。左侧新增测试覆盖时间倒序、十条分批、尾批、追加位置、右侧不重读、重建首批、来源先过滤、过期请求、无滚动条时的滚轮及键盘加载。窗口测试覆盖点击中文入口不弹用途提醒并复用窗口；语言回归检查已编译资源和英文启动路径。日志传输测试退出时有 Qt 对象不可回收的 ResourceWarning，但退出码为 0；未据此宣称 Qt 生命周期问题已解决。

中文 `.qm` 已重新编译，`git diff --check` 通过。未运行全量回归、Agent、Windows 成品或真实游戏验收；后台完整时间扫描的成本保留。
