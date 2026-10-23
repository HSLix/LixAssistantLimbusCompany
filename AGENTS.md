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
- `lalc pi-probe` 会实际调用模型，同样仅在需要验证 Agent 功能时执行，不能作为普通回归的附带步骤。
- 具体命令和验收边界见 `docs/pi-probe.md`；跳过的 Agent 测试不得报告为已通过。
