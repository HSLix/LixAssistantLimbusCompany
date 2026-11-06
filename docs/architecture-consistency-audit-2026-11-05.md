# 架构一致性审计与文档维护 — 2026-11-05

## 结论与范围

确认的问题主要是现行入口和指南残留旧契约，并非所查能力仍未实现。本次已修正文档；没有修改代码、测试、ADR 决定、议题状态、业务数据或验证资源。

审计基线：`7e4b309072e2a360f87b497d878340c4a936b25e`，开始时工作树干净。范围为 README、代理领域指南、重建规划、Stage 5、Agent 使用指南，以及 Sharing／页面包、外部搜索／进程复用、Windows 构建的相关决定、代码和普通测试。Stage 1–4 仅核对入口与后续替代关系，未重审整个执行器、所有旧 ADR 或 Stage 6 实现。

权威来源：根目录 `AGENTS.md`、`CONTEXT.md`；已接受的 ADR 0034（Session、权限和人审）、0036（整包页面与 Sharing）、0037（可用资源预算）、0038（A/B 参考版本和进程复用）；Stage 5 已确认的页面试用修订。ADR 0034 的 fetch-only、原单文件页面限制分别只在 ADR 0038、0036 明确声明的范围内被替代。#339 关闭的开发者确认见[页面修订记录](page-review-tabs-implementation.md)及其中的原议题评论。

2026-11-05 首次只读回查 GitHub：#331–#339 CLOSED，#340 OPEN，当时 #317 OPEN。随后开发者取消并关闭 #317，本轮已回读[关闭评论](https://github.com/HSLix/LixAssistantLimbusCompany/issues/317#issuecomment-6652564769)：不再要求独立邮箱验收，当前验收由 #340 推进。议题状态只证明跟踪状态；未据此扩大人工验收范围。此次所修订的规则未发现尚需另作设计决定的权威冲突；Stage 6 新方案仍属未定范围。

## 确认问题与第二次复检

以下旧文档行号均指上述基线，可用 `git show 7e4b309:<路径>` 还原。第二次复检回到接受来源、代码调用／执行边界和实际测试断言，排除仅由词语命中造成的误报。

| 问题／影响 | 初查证据 | 复检依据与结论 | 处理 |
| --- | --- | --- | --- |
| P2：当前状态与旧时间线混排，导致已实现工具被误判为缺失 | `README.md:35` 仍写 Page tools pending，`:96` 写 GUI integration follows；代理指南反复前置状态覆盖 | GitHub #335–#339 已关闭；`DeveloperSession.conversation`、`agent_policy.PAGE_TOOLS`、`RepairTools.call`、`PageDrafts` 及相关测试证实接入；#340 未关闭不能反推安装代码不存在 | 新增[集中状态与入口](current-state.md)，精简 README 和代理指南；历史设计／拆分明确标为对应时点记录 |
| P2：Stage 5 自称当前完整规格，但仍禁止资源包和参考副本更新 | `stage-5-agent-workbench.md:125` 单文件无资源，`:115` fetch 不修改工作区，`:119` BM25／Embedding 未定 | ADR 0036／0038 明确替代；`PageDrafts.write_resource`、`PagePreviewDialog.load_pages` 读完整快照；`KnowledgeLibrary.synchronize` 在 B 内 reset／建索引／查询后才替换 active 指针。不是以代码擅自推翻设计 | 就地更新当前规格及规划的 Stage 5 摘要；历史 #337 清单保留并标明被替代范围 |
| P2：Agent 当前指南仍指向已删除的操作和过时生命周期／存储路径 | `agent-repair.md:45` 人工 Selected Manifest，`:141` 每轮回收 pi，`:130` 所有对话位于 agent-interactions，`:145` 重建共享基线，`:291` 强制预检指导 | ADR 0034／0038；`RepairConversation.__init__` 为 Session 指定 `session.path / "log"`，`DeveloperSession.create` 单独保存基线，`PiProcess.session` 按签名复用，`ApplicationService.shutdown` 负责退出清理。原始输出决定已取消强制推理预检 | 改为 Session 工作台用法、实际日志路径和宿主生命周期；旧验证段明确标历史，Prompt 小节修正预检说明 |
| P2：构建入口遗漏新增必备资源，页面导入仍被描述为未来工作 | `README.md:124` 只要求 pi ZIP；`windows-packaging.md:57` 写导入导出以后另做 | `build_windows.check_codesearch`／`assemble` 已要求 codesearch 和固定模型，输出 with-agent／without-agent；ADR 0036 与 Sharing GUI／`import_selected` 已提供导入 | README 补充资源前置链接和当前包名；打包说明改指 Sharing |

维护还将 Sharing“检查限额”的旧措辞改为“检查可用资源”，与同页无固定准入上限及 ADR 0037 一致；并未删除安全路径、登记、哈希或资源检查。

## 需求、实现与验证分别判断

以下状态仅覆盖本行限定范围；Verified 不向真实模型、Windows 或游戏环境外推。测试名称为可搜索的稳定符号。

| 要求／来源 | 实现证据 | 测试／实际结果证据 | Implementation | Verification |
| --- | --- | --- | --- | --- |
| 按模式与入口限权，CLI 不继承 GUI／Construct；ADR 0034 | `agent_policy.allowed_tools`、`RepairTools.call`；`RepairConversation` 按入口配置 | `test_workbench.test_mode_entry_policy_and_host_reject_before_dispatch`、`test_construct_empty_ignores_default_and_cli_cannot_resume` 本次通过；仅宿主边界 | Implemented | Verified（普通测试范围） |
| 完整页面资源及失败替换保护；ADR 0036 | `PageDrafts.write_resource`／`snapshot`／`install`、`page_packages.install_page_package` | `test_page_packages` 的完整资源替换、失败恢复、旧单文件兼容与路径断言本次通过 | Implemented | Verified（临时目录及离屏 Qt） |
| 三 Tab、固定审批、试填不改正式配置；已确认试用修订 | `PagePreviewDialog.load_pages`／`install`、`MemorySettings`，拟安装页失败 `fail_preview` | `test_page_drafts.test_preview_independent_memory_no_submit_and_install_exact_version`、`test_invalid_proposed_never_shows_approval`、`test_preparation_and_tab_switches_execute_proposed_once` 本次通过 | Implemented | Verified（离屏 Qt） |
| A/B 切换失败保留 A、首次无索引仍可读；ADR 0038 | `KnowledgeLibrary.synchronize`／`active`／`path`，失败路径不替换指针 | `test_knowledge.test_disk_failure_keeps_a_and_reports_error`、`test_build_failure_keeps_a_and_first_failure_still_reads` 本次通过；Git 更新／索引含替身 | Implemented | Verified（本地替身故障范围） |
| 混合命中绑定哈希读取、旧工具更名；ADR 0038 | `KnowledgeLibrary.search_hybrid`／`read`、`RepairTools.call`、`pi_probe.ts` 工具声明 | `test_knowledge.test_hybrid_returns_hash_bound_reads_and_rejects_changed_content` 本次通过；真实搜索历史结果见[实施记录](external-code-search-implementation.md)，本次未运行真实服务 | Implemented | Verified（哈希绑定读取）；工具命名仅静态核对，真实服务 Insufficient Evidence |
| pi／codesearch 跨轮复用、故障不重放、退出关闭；ADR 0038 | `PiProcess.session`／`close`、`ApplicationService.shutdown`、`pi_probe.ts` 最终请求工具集合过滤 | `test_pi_startup.test_dead_reused_process_restarts_once_before_prompt` 及启动／回退测试本次通过；`test_external_search_agent` 的真实进程测试仅查阅、未执行，既往记录未绑定本次审计修订 | Implemented（所查路径） | Insufficient Evidence（本次未执行完整真实进程生命周期） |
| Sharing 按对象提交、失败保留已完成对象，不还原 Session 权限；ADR 0036 | `sharing.import_selected`／`import_history`、`page_selection_errors` | `test_sharing.test_four_type_roundtrip_without_execution_or_session_restore`、`test_import_stops_after_first_failure_and_keeps_completed`、固定暂存／篡改测试本次通过 | Implemented | Verified（普通临时目录范围） |
| 双包包含规定资源，公共应用相同；ADR 0038 | `scripts/build_windows.py:check_codesearch`／`assemble` | `test_windows_packaging.test_two_archives_share_application_and_keep_complete_pi_runtime`、模型／程序篡改拒绝测试本次通过；使用合成冻结资源 | Implemented（组包逻辑） | Verified（合成归档范围）；Windows 原生成品 Not Run |

Stage 6 Runtime 闭环不在本次代码审计范围，Implementation 为 Uncertain，Verification 为 Not Run；[规划](reconstruction-plan.md)及 [Runtime TODO](stage-3.5-agent-runtime-step-recovery-and-maintenance.md#stage-6-todo-repair-integration)明确待推进，不能用 Workbench 测试证明已经接入。

## 执行与证据边界

在上述源码基线、macOS 本地虚拟环境及离屏 Qt 中串行执行一套普通检查；本次仅改 Markdown，未在检查后改变被测源码或测试：

```sh
QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest -q tests/test_workbench.py tests/test_page_drafts.py tests/test_knowledge.py tests/test_codesearch.py tests/test_pi_startup.py tests/test_windows_packaging.py tests/test_sharing.py tests/test_page_packages.py
```

实际结果：**155 passed，30.73s**。没有加 `--run-agent-tests`，没有启动第二套测试；未请求真实／付费模型或操作游戏。没有把历史全量数字作为本次结果，也没有把未执行的 Agent 用例算作通过。

修改后核对本次变更 Markdown 的本地目标和标题／显式锚点，并执行 `git diff --check`。历史文档中临时截图路径、旧命令和旧测试数字是原时点记录，未为了“全部链接可点”伪造或重建历史产物。

## 复检排除项与剩余工作

- **排除“旧 ADR 出现 fetch-only 就是冲突”**：ADR 0034 开头已明确 ADR 0038 的限定替代；历史理由继续保留。问题在于当前规格正文和用法仍呈现旧规则，已针对这些入口维护。
- **排除“页面可跳过 Review 就能绕过 Agent 安装审批”**：ADR 0036 的例外仅限人工 Sharing，`import_selected` 的 `allow_unreviewed` 与 Agent 专用 `page_preview` 路径不同；未发现需要取消该例外的依据。
- **排除“仍有限制数值就是违反无固定资源上限”**：知识库分页／扫描界限、工具传输单位不等于 Sharing／页面资源准入上限；ADR 0037 没有取消所有子系统的限制。本次未机械删除常量。
- **排除“#340 OPEN 就是安装未实现／#339 CLOSED 就是 Windows 已验收”**：代码、测试、议题跟踪及人工环境验收是不同事实。
- **P1 验收工作，开发者负责环境与关闭决定**：保留 #340 的 Windows 页面安装／重载验证，按[现有矩阵](windows-packaging.md#验收矩阵与记录)和[页面修订记录](page-review-tabs-implementation.md)收集实际证据后再决定关闭，不由本次审计代签。
- **P2 环境验证，开发者在目标环境推进**：外部搜索真实远端认证、大仓库与磁盘增长、Windows DLL／子进程／mmap 清理和离线资源加载，按[既有实施记录的未验收项](external-code-search-implementation.md#未验收与保留)验证；新增问题需绑定具体版本与结果。
- **后续设计工作**：Runtime 的 Working Manifest／Recheck、值守及预算等继续在 Stage 6 逐项确认；不因本次整理默认接受候选设计。
- **文档维护约定**：当前状态在 `current-state.md` 更新，现行规则就地更新相关规格／用法；决定、影响审查和实施证据保留为历史来源。暂不批量移动、归档或删除文档，避免破坏现有引用。

## 开发者反馈后的维护修订

同日开发者要求 README 仅保留基础介绍、部署和协议；已删除阶段状态、架构时间线、验收说明、测试命令及内部诊断说明，使用细节链接到专门指南。状态集中在 `current-state.md`。

#317 的取消不解释为旧验收项通过，也不把完整旧清单机械搬入 #340；按开发者明确要求，以当前 #340 验收推进收尾。现行入口与教程同步更新，旧阶段清单保留并紧邻标题标明历史适用范围。教程中复查发现的“Stage 3 不含 Agent Asset 新增”和 GUI 重建手工 Candidate 两项旧说明，已按 ADR 0028–0034 的明确决定修正，无须另行设计裁决。

本轮继续复核了当前规格、旧 ADR 的明确替代说明和 Stage 6 的 Confirmed scope／候选方案／TODO 分界。未发现需要开发者另行指定权威来源的现行冲突；未来 Stage 6 尚未接受的设计不借本次维护定案。未修改 ADR 本身或自动创建／关闭议题。
