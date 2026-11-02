## Agent skills

### Issue tracker

Issues are tracked in GitHub Issues for `HSLix/LixAssistantLimbusCompany`. See `docs/agents/issue-tracker.md`.

### Domain docs

This repository uses a single-context domain documentation layout. See `docs/agents/domain.md`.

## Code comments

- Python 类和关键函数应提供简洁的中文 docstring，说明职责、重要边界或副作用。
- 行内注释只解释无法从代码直接看出的原因、约束或安全边界，不逐行复述实现。
- 不要求每个函数都有 docstring，也不要为了满足形式添加没有信息量的注释。
- `tests/test_*.py` 文件开头应有简短的中文模块 docstring，说明测试覆盖范围，并给出从项目根目录运行该文件的完整命令。

## Agent tests

- 涉及真实 pi 进程、Agent 工具循环或模型服务的测试必须标记 `pytest.mark.agent`，默认回归跳过；不得因为本机已安装 pi 就自动运行。
- 仅当本次改动涉及 Agent 接入或确实需要检查 Agent 功能时，才显式添加 `--run-agent-tests`，并选择相关测试文件。普通功能改动、全量回归或例行检查不添加此参数。
- 默认回归与显式开启的 Agent 接入测试必须分开串行执行，等待前一套测试进程退出后再启动下一套，不得同时启动两个测试进程并跑这两套测试。它们可能共用当前系统用户的 `ProcessLock("game")`，不同临时数据目录也不隔离该锁；即使不操作真实游戏，也可能因活动锁竞争而失败。这不表示所有测试均禁止并行，但未验证资源隔离前，不应并行运行会申请该锁的测试。
- 独立 `lalc pi-probe` 已移除；正式 Agent 集成测试仍仅按需显式运行，不作为普通回归的附带步骤。
- 具体命令和验收边界见 `docs/pi-probe.md`；跳过的 Agent 测试不得报告为已通过。
