# #335 — CLI Repair Session 本地实施

2026-10-31。依据[已确认的本票影响审查](stage-5-335-design-impact-review.md)与[Stage 5 规格](stage-5-agent-workbench.md)实施。状态：本地实现和下述检查完成，开发者已明确接受回归证据并授权关闭 [#335](https://github.com/HSLix/LixAssistantLimbusCompany/issues/335)。GUI 历史及 CLI / GUI 互通由 #336 实现，未提前宣称通过。

## 可用行为

```sh
# 从明确已发布 Manifest 创建独立 Repair Session，先输出 session_id
uv run --frozen lalc repair --from <saved-manifest-uuid> --problem '检查并修复这个流程' --chat

# 退出或重启后继续；两个来源参数必须二选一
uv run --frozen lalc repair --session <session-uuid> --problem '检查已保存证据和实际状态后继续'
```

原有图片附件、模型连接设置、逐轮额度、受限编辑、专用新增、完整校验、Publish、明确已发布版本试运行和日志查看继续可用。创建来源不隐式选用 Default；发布不改变 Default。模型请求失败后，已成功创建的 Session 仍保留，可按输出 ID 继续。

Session 保存在 `lalc data-dir` 下的 `developer-sessions/<session-uuid>/`：

- `session.json` 保存格式版本、Session ID、Repair 模式和固定来源。
- `candidate/` 为独立草稿，`.candidate-baseline.json` 保存初始化来源及固定基线。
- `log/` 保留自包含日志、原图、内容引用、工具产物、逐轮快照及结果。

源码位于 `src/lalc/developer_session.py`；`agent_repair.py` / `repair_tools.py` 复用原对话与工具核心，`__main__.py` 路由 CLI。新存储为后续 GUI 复用，不在本票增加独立存储框架、会话删除或清理功能。旧草稿 / 旧日志不迁移，手工 init / validate / publish / clear 仍使用原 Candidate。当前 GUI 的旧 Candidate 生命周期暂不迁移。

## 恢复及互斥

主动输入、模型消息、请求额度通知及实际工具事件按原始关联保存。恢复从事件重建消息；已有 pi 工具结果保持原样，只有宿主实际结果时补入其真实内容，没有结果时补入明确的宿主中断 / 结果未知记录，不补造成功、不假定未执行。原始事件仍保留。只有再次主动发送消息才请求模型，由 Agent 根据证据与现状判断后续行动。

每轮先取得同一 Candidate 真实路径的跨进程锁，再读取最新状态；执行及取消后的落盘都在锁内。CLI 等 input 时不占锁，其他入口可继续，旧对象再次发送前会重读。现有全局 game 锁保持，因此独立 Candidate 不意味着并行操作游戏。进程退出由操作系统释放锁，不删除锁文件。

恢复保留轮次、已保留的工具编号和产物；工具执行前先记录编号预留，避免中断后重用编号。预览 ID 只存在当前工具对象中，重启后明确失效，不自动截图。已保存的 Asset / Manifest 不回滚。CLI 拒绝 Construct 元数据，实际工具声明与分发仍为固定 CLI Repair 能力，历史内容不赋予额外权限。

创建先在不可见的临时目录准备 Candidate、基线、元数据和日志格式，成功后整体提交。失败不破坏已有 Session。路径 / 符号链接 / 基线边界与日志内容引用校验有效；完整记录或引用损坏明确报错。进程退出造成的未完成 JSONL 尾部另存原字节后隔离，完整历史不删除；有效但未写换行的末条只补换行。不保证断电或未保存内容恢复。意外退出时的未提交临时目录不被当作可用 Session，也不自动清扫。

## 检查证据

- 普通全量回归：`QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest -q -x -ra`，**587 passed，58 skipped**。跳过项含默认不执行的 Agent、Windows DPAPI、原生焦点及当前环境不允许的 IPC / 重载检查，均不计通过。
- 显式 Agent 回归：`QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest --run-agent-tests -q -x -ra tests/test_agent_repair_agent.py tests/test_developer_session_agent.py`，**42 passed，4 skipped**。通过项使用真实 pi + 本机 HTTP 替身；跳过两项真实模型、一项 Windows DPAPI、一项 Windows 游戏现场。
- 最后调整恢复时的原图引用复用后，针对性重跑 `QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest --run-agent-tests -q -x tests/test_developer_session_agent.py`，**4 passed**。该调整后普通全量结果为上述 587 / 58。
- 普通 Session 用例覆盖两会话与手工草稿隔离、创建 / 元数据写入失败、来源参数互斥、Construct / 无效路径 / 符号链接拒绝、损坏引用、真实进程竞争、进程意外退出、锁竞争不分配轮次、空闲 CLI 被另一入口推进后续聊、已知 / 未知工具结果、重复工具 ID 跨轮关联及产物保留。
- 新增 Agent 用例覆盖重建对象后的真实传输载荷、七种附件原字节与历史关联、悬空工具调用实际载荷、无恢复自动请求 / Publish 重放、CLI 创建与按 ID 恢复，并复用既有发布及明确版本试运行验收。

首次全量与 Agent 回归同时运行，因共享 game 锁发生检查间竞争，改为串行后消除；另发现旧附件参数测试缺少新必需来源参数，已同步。最初本机 HTTP 替身监听受环境限制，允许本机监听后完成检查；这些失败未计为通过证据。

未调用真实模型、pi-probe 或真实游戏，未进行 Windows 成品 / DPAPI / 原生 GUI 验收。当前 GUI 尚不能打开 Session，CLI / GUI 完整往返及模式扩展留 #336；Session 保留带来的磁盘增长是已接受限制。本轮未提交 Git。开发者随后明确要求基于回归结果关闭本票，并说明 CLI 为顺带增量、重点为 GUI；已发布关闭记录并将 #335 关闭为 completed。上述未验证项不作为本票关闭前置，也不计为通过，后续重点为 #336。
