# #337 — 外部知识库与受控 Git 本地实施

2026-11-01。开发者确认[关键决定](stage-5-337-decisions.md)及[影响评审](stage-5-337-design-impact-review.md)后授权实施。开发者已人工验收通过并明确要求关闭，#337 已按 completed 关闭。

## 使用

Developer GUI → Agent Workbench → More → Workspace and pages → **打开外部知识库文件夹**。目录为应用数据目录下的 `knowledge/`，缺失时创建空目录后打开；不需要先创建 Session。已存在目录保留原内容，普通文件占位、路径链接或系统打开失败时明确报错。

开发者在目录中准备普通资料或自行 clone 好的普通 Git 仓库。GUI Construct / Repair 均可按需使用工具，不要求附件或逐 Session 授权；CLI / Runtime 不获得这些新工具。

| 工具 | 内容 |
| --- | --- |
| `knowledge_list` | 按目录列出资料，可分页；不触发 fetch，不解析 PDF / Office |
| `knowledge_read` | 读取 UTF-8 文本或查看原图；文本按字符分页，返回路径、内容哈希与来源 |
| `knowledge_search` | 字面、不区分大小写的文本检索，返回文件、行号、内容哈希、摘录及同步结果 |
| `knowledge_git` | 结构化 fetch / show / log / diff；无任意选项、终端、clone、push 或工作区更新 |

图片按实际内容识别，原始字节和 MIME 随工具结果留存；不做 OCR，不改变游戏截图的 OCR 行为。PDF / Word 等可列出但不解析，需先转换。文本及图片单文件最大 2 MiB；文本须为支持后缀或 README / LICENSE 等常见无后缀文件的 UTF-8 内容。

## 同步与版本

- 每条用户消息是一轮；每轮每仓库首次内容读取、检索或 Git 查看自动尝试同步一次，失败不自动重试；显式 fetch 可再次执行，列目录及打开文件夹不触发。
- 使用当前分支配置的 upstream，返回参考引用、fetch 前后提交、HEAD、同步结果和随后 status 的独立结果。status 返回是否有变更、条目数与未跟踪条目数的摘要，不倾倒全量路径。
- 更新时返回完整 before / after 提交对，使用 `knowledge_git(operation="diff", before=..., after=...)` 查看整个区间，支持远端回退；不只比较最后一条提交。
- `show` 默认 HEAD；提供 `path` 可读取指定提交中的文本 / 图片。普通 read / search 读取工作区，哈希标识实际内容；无更新不意味着 HEAD 已追上 upstream 或工作区干净。
- 无 upstream / detached HEAD 不猜分支或远端，保留本地读取。系统 Git 不可用时跳过、记日志，不弹安装窗口、不下载安装，结果保留“未检查远端”。
- 文本 / diff 默认每页 8000 字符、最多 16000；目录 / 检索每页最多 200 条。续读传 `offset`、上一页的 `version`，来源变化明确拒绝；省略 version 视为新的独立读取。
- log 每批最多 200 条提交；批内按字符续读，下一批使用 `next_history_offset` 作为 `history_offset`，并将返回的 `ref_commit` 作为固定 `ref`，保留合并历史。Git 输出最多 4 MiB，超过则要求缩小路径或提交范围，不伪称完整输出。
- 检索最多扫描 5000 个支持文本文件、约 32 MiB，最多收集 10000 个命中；跳过超大 / 非 UTF-8 / 无法读取资料或触及上限时明确报告扫描不完整。可缩小子目录继续查，不建设复杂索引。

## 安全与取消

知识库真实路径受数据目录约束，不跟随符号链接，不遍历普通资料中的 `.git`。首版支持内含真实 `.git/` 的普通仓库，不支持 Git worktree / submodule 的 `.git` 指针、外部共享对象目录或符号链接元数据；需要时由开发者准备独立普通 clone。

Git 通过系统程序和固定参数调用，不使用 shell 拼接；分支 / 标签先解析为明确提交 ID，文件路径独立校验。保留开发者正常 Git 连接与认证，不修改其配置；禁用 pager、hooks、fsmonitor、外部 diff / textconv，以及工作区比较的 clean / process 转换器等非必要扩展。连接协议限常规 HTTP(S)、SSH、Git，不允许 ext / 本地文件传输，防止借远端 URL 执行任意助手或跨根读取。Git 配置仍属于开发者可信环境，不宣称提供操作系统隔离。

认证非交互；fetch 最长 30 秒，其余单次 Git 命令有 10 秒上限。后台轮询取消事件和输出大小，超时 / 取消时回收进程组（Windows 走系统 taskkill 进程树清理），宿主等待实际清理再收尾。每次同步采集使用同一真实仓库的 ProcessLock；竞争非阻塞报告，不遗留锁等待。URL 认证信息在诊断进入模型、GUI 和日志前清理。

模型工具启用、最终模型请求声明与 Python 实际分发均执行当前模式 / 入口权限。历史 GUI 工具结果可在 CLI 续聊中保留，但不恢复其调用权限；未完成操作不自动重放。复用既有日志格式，无数据迁移或新依赖。

## 验证与限制

最终验证按组串行执行，避免共享游戏环境锁竞争：

- 普通全量：`QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest -q` → **669 passed, 68 skipped in 32.55s**。默认跳过 Agent 测试，跳过项不计通过。
- 真实 pi / 本机 HTTP 替身：`QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest --run-agent-tests -q tests/test_developer_session_agent.py tests/test_agent_repair_agent.py` → **52 passed, 4 skipped in 70.57s**。覆盖 GUI 两种模式实际声明 / 调用、JPEG 原字节、历史恢复及 CLI 声明与调用拒绝；没有调用真实模型。四个真实服务 / Windows 验收项未执行，不计通过。
- `pyright --pythonpath .venv/bin/python src/lalc/knowledge.py src/lalc/agent_policy.py` → **0 errors, 0 warnings**；`git diff --check` 通过。Qt 中文翻译已重新生成，目录入口与翻译目录覆盖随普通回归通过。

普通测试包含临时 Git 仓库与假 fetch / 假进程，验证目录不 fetch、每轮一次与显式同步、跨库检索、超时失败后 status / 本地读取、upstream 多提交与回退区间、无 upstream / detached HEAD / 无 Git、工作区不更新、提交原图、分页变化拒绝、路径 / 引用边界、转换器不执行、输出上限、URL 脱敏及 POSIX 取消回收。没有访问真实远端。

首轮曾误将普通回归与 Agent 集成并行执行，造成全局游戏锁竞争，结果作废；后续串行普通回归另定位并修正新测试对 OCR 单例的替换方式，避免干扰既有 OCR 测试，未修改产品 OCR 行为。上述数字均为最终修正后的串行结果。

2026-11-01 开发者反馈：“人工验收没有大问题，通过并关闭”。已将验收及验证结果记录到 [issue 评论](https://github.com/HSLix/LixAssistantLimbusCompany/issues/337#issuecomment-6554623167)，并将 #337 按 completed 关闭；#336 亦已关闭。本次反馈未说明测试平台或专项检查明细，不据此新增 Windows 成品、真实远端认证、真实模型或真实游戏专项通过证据。Git worktree / submodule 指针及非 UTF-8 文本 / Office 解析不在首版支持范围，限制见上文。
