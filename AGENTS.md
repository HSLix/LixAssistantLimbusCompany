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
