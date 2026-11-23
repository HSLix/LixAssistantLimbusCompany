# Agent skills

## Issue tracker

Issues and specs for this repo live as GitHub issues in `HSLix/LixAssistantLimbusCompany`. Use the `gh` CLI for all operations.

#### Conventions

- **Create an issue**: `gh issue create --title "..." --body "..."`
- **Read an issue**: `gh issue view <number> --comments`, also fetching labels.
- **List issues**: `gh issue list --state open --json number,title,body,labels,comments` with appropriate label and state filters.
- **Comment on an issue**: `gh issue comment <number> --body "..."`
- **Apply or remove labels**: `gh issue edit <number> --add-label "..."` or `--remove-label "..."`
- **Close an issue**: `gh issue close <number> --comment "..."`

Infer the repository from the configured Git remote. The expected repository is `HSLix/LixAssistantLimbusCompany`.

#### Pull requests as a triage surface

**PRs as a request surface: no.**

When enabled later, pull requests use the corresponding `gh pr` commands. GitHub shares one number space across issues and pull requests, so resolve an ambiguous reference such as `#42` by checking the pull request first and falling back to the issue.

#### When a skill says “publish to the issue tracker”

Create a GitHub issue.

#### When a skill says “fetch the relevant ticket”

Run `gh issue view <number> --comments`.

#### Wayfinding operations

The map is a single issue with child issues as tickets.

- **Map**: an issue labelled `wayfinder:map`, containing Notes, Decisions-so-far, and Fog.
- **Child ticket**: a GitHub sub-issue linked to the map. If sub-issues are unavailable, add it to the map’s task list and put `Part of #<map>` at the beginning of the child issue.
- **Ticket types**: use `wayfinder:research`, `wayfinder:prototype`, `wayfinder:grilling`, or `wayfinder:task`.
- **Blocking**: prefer GitHub’s native issue dependencies. If unavailable, use a `Blocked by: #<n>` line.
- **Frontier**: select the first open, unassigned child ticket without an open blocker.
- **Claim**: assign the issue to the current GitHub user.
- **Resolve**: comment with the result, close the child issue, and add a context pointer to the map’s Decisions-so-far section.

## Domain docs

本仓库采用单一领域上下文。本地讨论用根目录 `CONTEXT.md` 记录共享术语，用 `docs/adr/` 记录架构决定与取舍。两个路径均由 Git 忽略，存在时可结合源码和测试阅读。需要查阅旧规范和验收证据时，可从 Git 历史或本地备份读取。

核对设计时区分已接受的决定、当前实现与已执行的验收。发现冲突时应列明来源与实际影响。

- 已发布 Manifest 和正式源码保持不可变；Candidate、Default 与运行中的 Working Manifest 职责不同。Publish 与 Default 选择分开。
- Assets 独立于 Manifest；旧图像不覆盖，Agent 删除仅走开发策略已授权的专用归档路径。Candidate 单文件确认删除限 Developer GUI 及其受控远程 MCP 审批入口；Runtime 无删除权限，不继承 Workbench 工具。远程 MCP 入口仅在人工授权的独占开发工作台内工作。
- Trusted Actions 由应用登记，经 `ctx.action()` 保留权限、校验、Trace、错误与中断边界，不能改为直接后端调用。
- Session 的固定模式、来源与草稿独立于手工 Candidate；历史附件及日志不构成授权。页面安装仍需专用人工审批。

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
- 需要验证 Agent 接入时，从项目根目录按改动范围选择测试文件。例如 `uv run --frozen pytest -q --run-agent-tests tests/test_agent_repair_agent.py tests/test_developer_session_agent.py`。HTTP 替身结果、真实模型、Windows 成品及游戏验收分别记录；跳过的测试不得报告为已通过。

## 工作目录与文件权限

- 产品与脚本使用普通工作目录及普通待提交文件，继承父目录权限；复用 `lalc.work_files`，不得通过 tempfile 创建目录或发布带临时文件受限权限的产物。没有明确、记录在案的理由，不允许使用临时目录。
- 工作数据默认位于应用数据目录的 `work/`，同盘提交仍在目标父目录创建；保留清理、活动互斥、路径校验、原子替换和失败回滚。恢复失败时不得清理唯一旧副本。
- pytest 的 `tmp_path`／`tmp_path_factory` 等测试隔离设施允许保留；ProcessLock 的系统共享锁文件路径继续用于跨实例互斥，不作为工作目录。
