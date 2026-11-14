# 图片编号由 pi 扩展在内存中管理：影响与实施

2026-11-14，开发者同意移除跨进程共享图片索引，要求先评估维护成本与影响范围，再尝试实施。本文承接[前次 EOF 排查](agent-image-index-error-investigation.md)，不改变 ADR 0041 的上下文归属或 ADR 0033 的原始日志证据边界。

## 原因证据与决定

- 原方案：LALC 按业务日志事件生成 `sequence:image_number` 编号，每个含图事件重写工作目录下的 `image-index.json`；pi 在工具循环结束及压缩时读取。
- 前次为避免半截 JSON 改成关闭待提交文件后原子替换。本次用户日志显示截图和宿主工具结果已保存，随后在 `Path.replace` 处发生 WinError 5，整轮中断；本轮 Construct 没有源码差异。文件创建和之前一次替换已成功，不能据此认定目录始终不可写。
- 用户在 Windows 的对照实验：无 pi 读取时替换 1000 次无失败；真实 pi 持续 `readFile` 时 31 次替换中 30 次 WinError 5，30 次均能短暂等待后重试成功；pi 成功读取及解析 2396 次，无读取错误。已确认此机制足以复现同类故障；没有原事故瞬间的句柄记录，不声称排除了其他占用者。
- 新方案：LALC 继续依据已落盘业务日志生成编号；pi 扩展持有本轮编号表的内存副本。初始表来自既有 bootstrap；工具循环安全边界只查询尚未缓存的图片 SHA-256，先取得有效编号再编辑图片上下文。移除共享索引文件和对应环境变量。

## 影响与维护评判

结论：实现范围集中，行为覆盖所有 Agent 入口，风险主要在编号同步时序；适合实施。不是新增持久存储系统，也不需要新增依赖或修改 pi 上游。

| 位置 | 变更与边界 |
| --- | --- |
| `agent_repair.py / RepairLog` | 删除共享索引发布；保留既有图片哈希、编号和原始事件落盘。新增只读编号查询，拒绝格式错误或未记录的哈希。 |
| `agent_repair.py / RepairConversation.run` | 复用 `extension_ui_request/response` 内部通道，增加 `lalc.image_ids:` 分支；同步错误结束本轮，不冒充模型服务错误。 |
| `pi_context.ts / installContext` | 从 bootstrap 初始化内存表；`turn_end` 扫描上下文图片，只为缺失编号发一次批量查询，验证响应后更新缓存；窗口裁剪和压缩直接查内存。 |
| `pi_process.py` | 从每轮配置字段移除 `IMAGE_INDEX`，进程复用仍刷新 bootstrap 和扩展状态。 |
| 测试与文档 | 用编号查询、恢复及真实 pi 通道回归替换“原子发布索引”测试；旧修复记录标明被替代。 |

GUI Construct、GUI Repair、CLI Repair、Runtime Repair 共用这条调用链。原生 `read`、宿主截图、素材、知识库和历史图片均通过实际事件登记，不需要给每个工具添加专用编号字段。业务工具 Schema、权限、图片原字节、Sharing 格式、历史编号、原有 Session 文件均不变；没有历史数据迁移或清理任务。

维护成本增加的是一个内部请求和响应校验；删除的是共享文件发布、反复读文件、环境变量及相关生命周期状态。纯文字或已缓存图片不发请求，新图片每个工具循环最多一次批量查询；不占模型请求额度。同步仍依赖宿主存活，不是脱离 LALC 的独立 pi 运行能力。

## 时序与失败边界

1. pi 先发出工具／消息图片事件，再进入 `turn_end` 查询缺失编号。
2. 宿主从同一 FIFO 队列逐条处理并落盘，查询排在此前事件之后；无需把 UI 请求当成用户操作，也不增加模型可调用的工具。
3. 宿主只返回已登记图片的原编号；pi 验证请求的每个哈希都得到合法编号，再更新内存，之后才提交图片编辑和压缩结果。
4. 缺失／非法响应直接记录上下文错误并中止，不提交不可回读的图片引用；取消后丢弃进程，不重放工具。
5. 跨轮、切换 Session 或进程重启时重新加载该 Session 的 bootstrap 表，不继承上轮内存缓存。原始日志仍是图片编号恢复依据，不能据此重建并覆盖已压缩的有效 pi 历史。

此方案消除了本次故障中的共享 `image-index.json` 替换操作；其他文件的 Windows 权限或占用问题不在此结论范围内。

## 验证

普通回归与真实 pi／本机 HTTP 替身回归串行执行，结果如下；跳过不计通过。

- 普通定向组：`QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest -q tests/test_agent_context.py tests/test_agent_repair.py tests/test_pi_process.py tests/test_repair_tools.py tests/test_agent_log.py tests/test_agent_history.py tests/test_developer_session.py tests/test_runtime_repair.py tests/test_sharing.py`：171 passed。
- 图片与压缩专项：`QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest --run-agent-tests -q tests/test_context_compaction_agent.py`：18 passed。覆盖宿主／原生图片、原字节回读、编号缓存、图片窗口、带图压缩、跨轮进程复用、重启、错误响应不提交编辑，以及同步时取消后续聊不重放工具。
- 共享入口回归：`QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest --run-agent-tests -q tests/test_agent_repair_agent.py tests/test_developer_session_agent.py tests/test_runtime_repair_agent.py tests/test_agent_skills_agent.py`：95 passed、4 skipped。覆盖开发／Runtime 接入、Session、Skills 图片及既有权限边界。
- `git diff --check` 通过。没有新增依赖、改动 pi 上游或要求清理历史数据。

以上集成验证使用本机真实 pi 和 HTTP 模型替身，不证明模型质量、Windows 成品或真实游戏验收。用户先前 Windows 实验验证的是旧方案的竞争机制，新方案仍需在同一 Windows 环境实际续聊、截图和回读历史图片后验收。未执行整个仓库全量回归。
