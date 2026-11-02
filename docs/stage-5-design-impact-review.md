# Stage 5 设计影响审查

#336 当前实施请以[专项审查](stage-5-336-design-impact-review.md)为准：#335 已完成 CLI Session 基础，Developer 人工运行入口已决定删除；下文对应代码状态与折叠选择区保留为当时审查证据。

2026-10-31，依据开发者逐项确认的 [Stage 5 规格](stage-5-agent-workbench.md)、[ADR 0034](adr/0034-extend-developer-agent-with-reviewed-page-drafts.md)及[讨论记录](stage-5-2026-10-31-decisions.md)。本记录替代 2026-10-30 的双入口 / 独立进程审查结论。已读取相关实际调用路径、源码和针对性测试内容，统一正式文档；未修改产品源码或测试，未执行产品回归、真实 pi、模型、Windows 或游戏。下列“已确认”指源码可建立的差距，不把尚未实现的已接受目标当作现有实现的回归 bug。

## 设计变化

| 旧决定 | 已接受的替代 |
| --- | --- |
| Repair / Workbench 两个页面，曾讨论共享 Candidate | 一个 Agent 工作台，固定 Construct / Repair 模式，各有初始 Prompt 和工具白名单；每 Session 独立 Candidate / 固定基线 / 聊天 / 页面草稿 |
| New Conversation 保留同一 Candidate，允许显式重建 | Session 可持久恢复，换基线就新建，不提供 Session 重建 / 删除或自动清理；手工 Candidate 保留开发者命令职责 |
| CLI Repair 直接操作手工 Candidate | CLI / GUI 共用 Session 存储，CLI 仅 Repair、无 GUI 弹窗工具，同一 Session 执行互斥；旧草稿和日志不迁移 |
| 全窗口顶部 Selected / 刷新 / 试运行 | 仅工作台折叠区；打开列表前刷新，选择仍全局，不随 Session / Publish 自动切换 |
| 独立进程预览，主要看草稿 | 同进程应用级模态双页对比，正式页 / 拟安装页分别实例及内存配置，锁住其他 LALC 窗口，由人确认预览版本 |
| 实施时考虑正式页变化检查 | 明确不做自动版本冲突检测或智能合并，由人检查覆盖；可让 Agent 只读重读正式页后适配草稿 |
| 人工交互仅新工作台入口 | GUI Construct / Repair 均开放，CLI 不开放；Stage 6 Runtime 仅有人值守开放，无人值守不开放 |
| Git 触发频率和参考分支未定 | 每轮首次访问每仓库自动 fetch 一次，每次后 status，以当前分支 upstream 比较更新，无 upstream / detached HEAD 报告不确定 |

完整 Validate、专用源码 / Asset 工具、不可变 Publish 后试运行、Default 人工选择、共享 Asset / 页面 / 配置以及 Stage 6 当前 Step / Working Manifest 契约均未被放宽。未选定检索索引或具体外部项目，不前置完整业务交付。

## 已确认的实现差距与直接影响

### 1. 草稿路由和 Session 生命周期需要一起替换

证据：`src/lalc/gui.py:97,806` 创建单个 DeveloperHost 并使用 default_candidate_root；`src/lalc/__main__.py:239-245` 把同一手工 Candidate 交给 run_repair；`src/lalc/agent_repair.py:481` 每次 CLI 启动创建新对话；`src/lalc/developer.py:97,214` 初始化 / 重建和 new_conversation 都写单个 host.conversation。

结果：仅加历史列表或给 Candidate 加目录前缀不能完成隔离；初始化、Diff 基线、人工 Validate 回写、Publish、Agent 请求、错误脱敏和退出都需路由到明确 Session。手工 init / validate / publish / clear 不应跟随 GUI 当前 Session 改目标。`ManifestManager.initialize_candidate`（`src/lalc/manifest.py:307`）在有 retained 版本时把 None 解释为 Default，故 Construct 空白必须有明确路径，不能仅复用 None。

可复用：原子草稿物化、固定基线和失败恢复；`DeveloperHost.candidate_lock` 与 `ProcessLock` 的跨进程排他机制。创建 / 恢复须先取得会话身份与锁再读取可变状态，不能在锁外加载后覆盖另一入口已完成的更新。

测试证据：`tests/test_agent_repair.py:test_explicit_rebuild_preserves_draft_until_success_and_resets_conversation` 和 `test_cumulative_diff_and_new_conversation_keep_baseline` 验证的是旧 Agent 生命周期；手工初始化失败恢复的价值保留，但 GUI / CLI Agent 的新建 Session 不可继续以这些旧断言为验收。需覆盖两 Session 隔离、空白与指定来源、跨重启 / CLI-GUI 恢复、重复打开及锁竞争，确认手工草稿字节未变。

### 2. 日志保存不等于会话恢复

证据：`RepairConversation.__init__`（`src/lalc/agent_repair.py:254`）每次令 history=[] 并新建 RepairLog；`RepairLog`（同文件 :50）创建新 UUID 目录；`run` 在 finally（:450 起）保存 context.json、快照、结果和 round_finished。当前 GUI 事件通过 `gui.py:143` 固定送往 repair_page。

结果：需要保存及恢复 Session 模式、来源、基线、历史与轮次 / 日志引用，并重建当前聊天视图。不能把任意旧日志自动当作可继续 Session。真实交互仍按 ADR 0033 自包含留存，不能为了 Session 列表改变日志压缩、脱敏或旧数据。

中断恢复验收：已保存工具副作用不重放、不回滚；未完成调用不补造成功结果，重启不自动请求模型。除保存 JSON 外，需用中断在“模型工具请求已记录 / 工具结果未记录”等位置的用例核验恢复后协议有效、证据不丢失。此为新协议工作，不以现有连续上下文用例证明已完成。

### 3. 模式 / 入口授权不能只改 Prompt

证据：`RepairConversation.run`（`src/lalc/agent_repair.py:326,358`）使用固定 SYSTEM_PROMPT 和 REPAIR_TOOLS；`src/lalc/repair_tools.py:17,39` 是固定 Python 工具集及分发；`src/lalc/pi_probe.ts:99,180-265` 固定注册编辑 / 工具并 setActiveTools；read / edit 由 TypeScript 原生文件工具处理，validate 在 Python 特殊分支处理。

结果：模式 + 入口权限需覆盖所有分支，不能只在 RepairTools.call 外加过滤而漏掉 read / edit / validate。新知识库只读根目录和当前正式页读取不得扩大编辑权限；旧 GUI 工具历史不为 CLI 再授权。分别核验越权请求的模型声明不可见和宿主拒绝，包括绕过界面直接调用。

可复用：checkedPath / checkedEdit、每轮冻结已有文件及专用新增登记、结束快照越权检查。`tests/test_agent_repair_agent.py` 的真实 pi + HTTP 替身覆盖原工具循环，标记 agent；本轮只读测试源码，未执行。实施后需显式选择相关文件，替身证据不等于真实服务验收。

### 4. 工作台布局牵涉选择、活动状态和全部事件消费者

证据：`src/lalc/gui.py:110-160` 把 Runner 控件放在共用 root；`_runner_selected / _refresh_runner`（:190,214）保存选择、刷新列表并回写 repair_page；`render_state`（:348）直接启停这组控件和三页。`DeveloperHost.runner_selection / select_runner`（`developer.py:223,232`）已有独立的全局偏好。

结果：移动控件时保留已有全局选择和错误不回退，扩展“打开列表先刷新”，不在刷新信号中自动改选 / 试运行。历史、错误日志密钥收集、工具错误、请求计数、Validate 和关闭清理都需从单个 host.conversation 改为准确会话归属。保留当前启动语言 / 翻译和 Capture / Agent Settings 职责。

现有 `tests/test_developer_gui.py:test_runner_selection_independent_and_invalid_not_fallback`、`test_selected_plan_trial_uses_shared_service_without_changing_default` 可保留语义；三页文案、旧重建和全局刷新控件的断言要按新工作台更新，不能全删。活动门控复用 `ApplicationService.activity`（`application.py:103`）和现有游戏锁，独立 Candidate 不授权多 Session 并行。

### 5. 正式页加载器不能直接作为对比预览

证据：`src/lalc/user_pages.py:19,49,82` 的 UserSettings.save 原子写 user-settings.json，PageContext.save 委托正式存储；discover_pages 为模块使用独立 UUID 并直接编译当前字节，但会按正式目录发现和重复 ID 规则创建页面。`src/lalc/developer_gui.py:69-76` 的 TrialDialog 使用 WindowModal，`tests/test_developer_gui.py:test_trial_modal_blocks_main_window_without_topmost_and_closes_on_result` 也只断言窗口级模态。

结果：复用页面契约和新模块加载方式，但要为单个页面提供两套独立内存配置 / 实例，允许对比的相同 PAGE_ID，不把它们加入正式导航注册。ApplicationModal 才符合锁住 User / Developer 的需求，不能因现有试运行模态测试通过就宣称满足。读取原页 / 草稿、退出、异常、安装确认和被锁窗点击提示应有针对性检查。

安装校验仍保留路径 / 页面 / Task ID 边界和失败保留原页，不做自动正式版本冲突检查。确认绑定实际预览字节；安装不能读取已变化草稿却沿用旧确认。旧配置不被预览或安装试填覆盖。现有 `tests/test_user_pages.py` 覆盖正式发现、配置、Dashboard / Plan 和重载，可复用，但不证明双预览内存零落盘或全应用模态。

### 6. 人工等待与 Git 为明确新增路径

证据：`RepairConversation.run` 的 extension_ui_request（`agent_repair.py:385`）目前只支持内部 validate / lalc.tool 转发，调用后台线程；`Operation.cancel`（`developer_gui.py:31`）取消后台 asyncio 任务。`RepairTools.call` 的实际方法表和 TypeScript 注册清单没有本轮人工交互 / 知识库工具；RepairPage.open_pages / open_workspace 只打开正式页与 Candidate。

结果：需要 GUI 线程展示人工请求、后台可取消等待、同 Session 结果记录和请求额度保持；等待应允许切到游戏并禁止自动输入。页面模态预览和人工操作请求不是同一种锁定交互，不能误把操作请求做成阻挡游戏切换的顶置窗口。取消、关闭、Esc、空答复及迟到回调不产生授权。

Git 工具需独立的真实路径和参数边界，自动 fetch 的每轮去重、upstream / before-after、status、离线失败、本地 HEAD / 未提交文件来源标识及输出分页均属于可观察行为。首版仍无通用终端或参考库写入。本轮未对参考仓库实际 fetch、未选择来源或核验外部许可证。

## 潜在风险与所需验证

- **模态锁定与取消死锁**：若预览由 Agent 工具等待，而唯一取消按钮在被锁主窗，整轮可能无法取消。需在对比窗内提供可结束审查的关闭 / 取消路径，所有异常路径解除模态和等待；不要求新确认流程。
- **页面代码副作用**：同进程页面可卡住 GUI 或绕过配置接口，模块依赖不完全卸载。按新字节加载、双实例隔离、普通异常后可关闭及 Windows 焦点行为需实测，不承诺对任意 Python 沙箱隔离。
- **人工覆盖和共享资源**：人可能批准覆盖其他 Session 的页面改动，Asset 归档也影响所有 Session；这些是接受的边界，不在实施时擅自加入自动冲突阻断或按会话自动回滚。
- **恢复工具状态**：crop preview_id 等当前保存在内存中的工具资源不一定能跨重启复用。需检查恢复遇到旧 ID 时明确报不可用并重新观察，不把旧确认或旧截图 ID 当作仍有效的授权；不强行自动重放截图 / crop。
- **Git 副作用**：受控 fetch 可能涉及本地 Git 配置、凭据交互和参数解释。实现时需验证取消可收尾、无交互卡住、不接受任意外部命令 / 写出路径；本轮未执行新 Git 工具，不宣称这些边界已验证。
- **持久化权限与设置变化**：Session 模式固定不等于永久保存全部入口权限；GUI→CLI、白名单 / Prompt 更新后恢复需使用当前宿主授权并记录实际 Prompt 和能力。认证不写入 Session 元数据，日志沿现有脱敏。

## 文档应用与实施顺序

已统一 Stage 5 规格、ADR 0034、术语表、路线图、README、领域导航及 Developer GUI / Repair 指南的当前目标；ADR 0029 / 0032、Stage 4 规格的后续覆盖提示同步替换。讨论记录收口，Stage 6 人工值守边界保留。历史 Stage 3/4 实现证据不改写为新方案已完成；旧日志存储契约不变，Session 历史是本阶段新增用途，不回填 ADR 0033 的历史范围。

1. 先提供可用的 Repair Session 创建 / 恢复 / CLI-GUI 续聊闭环，保护手工 Candidate；同时处理 Agent 身份、事件和锁的路由，保持原修复工具可用。
2. 在同一工作台交付 Construct 空白 / 指定来源、模式与入口权限、历史导航、Selected 折叠区及刷新 / 试运行，验证完整创建到发布 / 已发布试运行路径。
3. 交付只读知识库 / 受控 Git、GUI 两种模式人工请求两个可独立验证的增量。
4. 交付 Construct 页面草稿、双实例模态内存预览及人工版本确认安装 / 重载，验证一次真实配置到 Dashboard / Plan 的接入；不拆成无法独立使用的“只有 schema / 只有 UI”票。

票据粒度已按 to-tickets 获开发者确认，原 GUI 工作台与 Construct 模式票合并，统一验收。发布前读取 GitHub 开放议题，未发现已有 Stage 5 票；用户确认合并原第 2 / 3 票后，已创建 #335–#340，并回读核验正文、ready-for-agent 标签与五条原生阻塞关系。#317 仍为延期业务 / Windows 验收，不作为工具增量前置，未修改或关闭。

## 检查范围

本轮只进行源码 / 测试内容阅读、文档检查和 GitHub 开放议题读取；不运行产品回归或 Agent 测试。已检查同步文档的本地链接、过期目标描述和差异空白；旧双入口 / 独立进程只保留在明确被替代的历史说明。Windows 成品、真实模型和真实游戏无新增验收证据；无产品代码改动，不需要用广泛回归冒充新功能验证。

审查后的 [tickets 拆分](stage-5-implementation-slices.md)经开发者确认，原第 2 / 3 票合并，其余通过，共六个可验证增量；已按此依赖发布为 #335–#340。

## 2026-10-31 Manifest 参考补充

已完成[专项影响审查](stage-5-manifest-reference-impact-review.md)：附件是上下文提示，GUI / CLI 可只读查看任意已发布 Manifest，Runtime 白名单单独明确授予、实际 Stage 6 接入。#336 承担附件及共享只读工具增量，#335 的本地实现不因此被改写或宣称覆盖本能力；#337 外部知识库范围和既有阻塞边不变。
