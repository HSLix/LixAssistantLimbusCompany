# Agent 会话标题与管理影响审查

2026-11-11。先完成源码审查，再按[确认记录](session-management-decisions.md)实施。

## 设计变化与已确认差距

- `developer_gui.py:RepairPage.show_event` 每轮 `workbench_session` 都覆盖标题缓存，与已接受的首条消息标题规则及本轮固定标题要求冲突。`saved_title` 则读取首条用户消息，导致当前与重新打开的显示不同。修正实时缓存初始化，不更改消息正文。
- `DeveloperSession.check/create` 的元数据只有身份、模式和来源；人工标题需要增加可选展示字段。旧会话不批量迁移；不改变 UUID、Candidate 或模型上下文。`RepairPage.saved_title` 应优先读取人工名称，标题缓存不得覆盖已保存名称。
- `RepairPage.history` 当前为文本列表，无逐会话管理入口。增加复用 Fluent 更多图标的悬停入口和重命名／删除菜单，并提供键盘入口；菜单与动作均重新检查 `is_busy`，已有 `render` 继续控制运行、试跑及清理期间的互斥。
- 会话目录持有 `candidate/`、固定基线、`page-drafts/` 和 `log/`。`AgentHistory` 独立 SQLite 索引的 `rounds` 持有同一 UUID；仅删除目录会留下可检索的失效记录。删除须同时处理目录和索引，保留其他 UUID 以及已发布／安装／共享对象。
- `DeveloperHost.candidate_lock` 是按稳定 Candidate 路径生成的跨进程锁；`AgentHistory.lock` 协调索引更新和重建。管理操作必须复用锁及服务活动门槛，不能只靠按钮禁用。

## 实施范围与边界

1. 在 `DeveloperSession` 增加重命名及删除入口。人工标题以可选 `title` 写入 `session.json`，原子保存、单行非空校验；名称不构成日志指令或权限。
2. 删除时持有 Candidate 与历史索引锁，使用普通同盘工作目录隔离待删会话。索引事务失败恢复原目录；恢复失败保留唯一旧副本并明确报错，不自动清理。索引提交后删除隔离数据，清理失败明确报告残留路径，不伪称已完整清除。
3. GUI 用子弹窗提供取消／保存和不可恢复的删除确认。删除当前会话后清空准备状态；删除其他会话不切换当前对话。改名不改排序依据，避免单纯改名把旧会话顶到最新。
4. 同步中英文资源、当前规格和针对性测试。历史索引的原始观测标题仍是当时留证，不因界面改名重写；删除则清除该 UUID 的索引项。导出的历史副本及已有运行记录中对 Session 的引用不追溯改写，不因删除而自动重建会话。

## 潜在风险与验证计划

- SQLite 与文件系统不能跨资源原子提交；同盘隔离及异常恢复覆盖进程内失败，但强制断电可能留下隐藏隔离目录。清理失败不能静默忽略。本次不建设通用崩溃恢复服务。
- 删除与其他进程使用同一会话的竞争需通过真实 ProcessLock 竞争测试；路径校验及原子写失败、索引失败回滚也须覆盖。
- GUI 测试覆盖两轮标题不变、人工名称重开、悬停与键盘菜单、空标题／取消、确认删除／取消、当前与其他会话、忙碌及清理门槛。普通测试不启动真实 Agent，不添加 `--run-agent-tests`；Windows 原生验收另计。

## 实施与验证

已按上述范围实施。人工名称作为可选元数据兼容旧会话；自动标题仍本地提取且不批量写回。标题按纯文本显示，改名保留原目录时间，避免改变历史排序。重命名和删除均走后台任务，子设置复用 Fluent 菜单和更多图标，支持悬停、右键及键盘菜单键。

Fluent `RoundMenu.exec` 实际为非阻塞显示，菜单由页面持有至下次替换或页面销毁，避免显示后立即释放；新增真实菜单显示及动作检查，未仅依赖菜单替身。忙碌期间统一禁用列表子设置，已打开菜单的动作及重命名保存也同步禁用。

已执行的相关回归（`QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest -q ...`，各套串行、正常退出）：

| 文件 | 结果 |
| --- | --- |
| `tests/test_session_management.py`、`tests/test_gui_language.py` | 最终组合 38 passed（新增会话管理 15 项，语言 23 项） |
| `tests/test_developer_session.py`、`tests/test_agent_history.py` | 32 passed（与当时新增管理测试组合共 46 passed；此处排除已另计的 14 项） |
| `tests/test_chat_ui.py`、`tests/test_workbench.py`、`tests/test_repair_chat.py`、`tests/test_raw_output.py` | 74 passed |
| `tests/test_developer_gui.py` | 52 passed |

去重共 196 passed。检查覆盖真实跨进程 Candidate 锁竞争、原子改名失败、索引事务失败回滚、恢复失败保留唯一副本、文件清理失败报告残留、符号链接拒绝、发布／安装／共享数据保留、当前与其他会话删除，以及中英文弹窗和取消默认项。默认回归未启动真实 Agent。

中文 `.qm` 已重新编译，`git diff --check` 通过。最终菜单／语言组合有 6 条依赖内部 `QHoverEvent` 弃用警告，未修改依赖。未执行全量回归、Windows 成品、真实模型或游戏验收；强制断电时文件系统与索引之间的恢复限制仍按上文保留。
