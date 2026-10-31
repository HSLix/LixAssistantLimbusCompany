# #336 — 工作台、模式与 Manifest 参考的实施前影响审查

2026-10-31：开发者已明确“开始实施”，本轮评审及修订已获确认；当前实现与验证见[实施记录](stage-5-336-implementation.md)。下文等待确认 / 尚未实施的描述保留为审查时点证据。

2026-10-31。依据开发者在本轮逐项确认的[决定](stage-5-336-decisions.md)、[Stage 5 规格](stage-5-agent-workbench.md)及 [ADR 0034](adr/0034-extend-developer-agent-with-reviewed-page-drafts.md)。本轮设计确认已收口，影响审查等待开发者确认后实施；本报告不表示产品功能已完成。已阅读实际源码、调用方和相关测试，未修改产品源码 / 测试，未运行产品或 Agent 测试。

本报告更新 #336 的当前实施依据。早先[全阶段审查](stage-5-design-impact-review.md)中的 CLI 未接入 Session 描述已由 #335 实现替代，Selected 折叠区由本轮删除入口的决定替代；[Manifest 参考专项审查](stage-5-manifest-reference-impact-review.md)的只读安全及恢复要求仍适用。

## 设计变化

| 原设计 / 当前行为 | 本轮已确认目标 |
| --- | --- |
| 曾收紧为创建成功即固定 | 开发者重新明确：首条用户消息提交前可调整模式和来源，首次提交时才固定 |
| 共用固定 Repair Prompt / 工具集 | Construct / Repair 分别定义 Prompt 与白名单，本票已实现工具集合可以相同；Repair 保留专用新增能力 |
| Developer 共用顶部选择 / 人工试运行，曾计划移到工作台折叠区 | 删除整个人工入口，不新增“应用到 User GUI”；User GUI 普通启动保持 |
| Agent 试运行与人工入口共用 GUI 状态处理 | 保留 Agent 完整 Validate → Publish → 显式版本 trial_run → Run 结果 / 日志，以及互斥、取消和日志窗口 |
| CLI 已有独立 Repair Session，GUI 仍使用手工 Candidate | GUI 创建 / 恢复独立 Construct / Repair Session，CLI-GUI Repair 续聊；空白 Construct 不读取 Default |
| 图片附件 / 当前 Candidate 读取 | 保留图片，增加多 Manifest 提示和任意已发布版本的专用纯只读查看；不依赖先附加 |

保留：手工 Candidate 与旧日志原样、Session 不重建 / 删除 / 自动清理、同会话跨入口互斥、恢复不重放、共享全局 Asset 副作用、正式源码不可变、Publish 不改 Default。#337–#340 和 Stage 6 不提前接入。

## 已确认差距与影响

### 1. 删除人工入口时不能删除 Agent 的试运行控制

证据：`src/lalc/gui.py:MainWindow.__init__ / _runner_selected / _refresh_runner / start_selected_plan / render_state` 创建、持久化并启动人工所选版本，render_state 还负责 `entry.developer_trial` 的 TrialDialog。`src/lalc/developer.py:DeveloperHost.runner_selection / select_runner` 读写 `developer-settings.json`；已检查调用方仅此 GUI 与相关测试使用该选择 API。

独立 Agent 路径是 `RepairTools.trial_run` → `ApplicationService.start_plan / start`（`_developer_trial=True`）→ `MainWindow.render_state` → `TrialDialog`；工具自身等待实际 Run 完成，取消时 stop 并等待收尾。删除人工按钮不能连带删除此窗口、活动门控、pause / resume / stop 或日志返回。

实施：删除人工控件、选择偏好 API 及无调用的状态分支；旧设置文件保留但停止读写，不迁移。Session 初始化来源和参考附件仍需要选择已发布版本的界面，不能因删除运行选择而一并删去。User GUI 的 Default 选择和 start_plan 路径不改。

测试：`tests/test_developer_gui.py:test_selected_plan_trial_uses_shared_service_without_changing_default` 和 Runner 持久化用例验证的是被取消的功能，应替换为入口移除 / 不读取旧偏好检查；保留 Agent trial modal、互斥、取消等独立断言。`tests/test_gui_language.py` 直接引用 `developer.trial_button`，包含子进程语言 / reload 检查，必须同步，不能只改主 GUI 测试。

### 2. GUI 的状态与宿主仍绑定手工 Candidate

证据：`src/lalc/gui.py:GuiCoordinator.__init__ / open_window` 共享 DeveloperHost；`MainWindow.__init__` 以它创建 CapturePage / SettingsPage / RepairPage。`src/lalc/developer_gui.py:RepairPage.initialize / new / send / show_event / validate / publish / open_workspace` 使用单个 host.conversation 和原 Candidate，仍提供重建与独立 New Conversation。`MainWindow._interact` 从同一 host 收集密钥并写诊断。

影响：仅替换 Candidate 路径不能完成会话隔离。聊天、累计 Diff、Validate 事件、Publish、错误、请求计数、文件夹入口及回调都要绑定所发起 Session。不能把全局共享 host 简单替换成当前 Session host：SettingsPage 和 CapturePage 已保存原 host，且 GuiCoordinator / UserWindow 继续使用共享临时凭据。

实施：保留全局服务、设置和凭据职责；工作台明确管理当前 Session 的宿主和对话，复用共享凭据，不能把密钥写进 Session 元数据。后台执行到实际取消收尾期间禁止新建 / 切换，回调仍绑定原 Session；空闲 GUI 每次执行前重新锁内读取，兼容另一 CLI 入口推进状态。历史 UI 按保存的事件及消息重建，不请求模型、不重放工具。

### 3. #335 的 Session 存储需要扩展入口边界，不能全局解除 Construct 拒绝

证据：`src/lalc/developer_session.py:DeveloperSession.create / check / conversation / restore` 固定 Repair 模式及非空 source_manifest_id，检查路径、基线、日志并在 Candidate 锁内恢复；`tests/test_developer_session.py:test_reject_construct_symlink_and_corrupt_reference` 明确验证 Construct 被拒绝。`src/lalc/agent_repair.py:run_repair` 复用该入口。

实施：共用存储支持 GUI 的两种模式，CLI 单独继续拒绝 Construct；恢复授权按当前模式与入口计算，不根据历史工具记录扩权。保留已实现的中断未知结果、锁竞争、工具编号及旧裁剪预览失效语义。首条用户消息提交前的选择是可调整的准备状态；首次提交时按最终选择建立 Candidate、固定基线及模式，开始对话后不提供模式 / 来源修改或重建 API；初始化失败保持输入及已有会话完整。建议延后真正的 Session 初始化到首次发送，复用既有原子创建，避免为了未开始的聊天反复重建草稿。固定不依赖模型回答成功，首条消息已提交后模型失败也不允许改来源。

### 4. 空白 Construct 不能沿用 None 的 Default 语义

证据：`src/lalc/manifest.py:ManifestManager.initialize_candidate` 在存在已保存版本时把 `manifest_id=None` 解释为 load_default；只有没有版本时才提供 `EMPTY_PLAN`。`DeveloperHost.add_source` 拒绝新增 automation_plan，要求初始化已经存在一个 Plan。`tests/test_python_plan.py:test_empty_initial_plan_publishes_and_runs` 仅覆盖没有已发布版本时的空白情况。

实施：提供明确空白创建路径，复用 EMPTY_PLAN 和现有 Manifest 结构 / 原子物化，不为此改变手工 init 的 None 行为。空白仅含 Manifest 与最小 Python Plan，不预置示例业务或隐式引用 Default；固定基线记录真正的空白来源。验证已有 Default 时空白仍为空白、首次发送前切换模式 / 来源采用最终选择、Repair 选空白被拒绝、初始化失败保留输入、首次提交后即使模型失败也不解锁；继续验证可新增 Task / Step、完整校验及 Publish 后明确版本试运行。

### 5. 权限路径分散，工具列表相同也必须分别执行策略

证据：`src/lalc/agent_repair.py:RepairConversation.run` 使用固定 SYSTEM_PROMPT / REPAIR_TOOLS，validate 在 extension_ui_request 的专用分支执行；`src/lalc/repair_tools.py:RepairTools.call` 通过方法表派发宿主工具。`src/lalc/pi_probe.ts` 的 read / checkedEdit / validate / 通用宿主转发分别注册，setActiveTools 使用固定列表；原生 read / edit 不经过 RepairTools.call。

实施：模式与当前入口交集贯穿 Prompt、模型声明、TypeScript 工具实际 execute 和 Python validate / 宿主分发，不只限制可见列表。维持只读参考与 Candidate edit 分开、专用新增后同轮可编辑。更新 Prompt 内残留的“JSON Plan”试运行描述，不改变 Python Plan 契约。#337 知识库、#338 人工反馈、#339 页面能力未实现前不暴露。

### 6. 已发布版本的读取必须绕开执行加载链

证据：`ManifestManager.load / validate` 最终经过 `_load / _load_module`，后者执行 `exec(compile(...))`。`_stored_source` 已校验 Component ID 和字节哈希，但直接 read_bytes，不能单独代表完整真实路径 / 符号链接边界；`list_manifests` 仅提供索引摘要，也不代表版本全部有效。当前 `REPAIR_TOOLS` / TypeScript 注册清单无跨 Manifest 内容查看；图片附件的 `image_attachments` 仅接受真实图片。

实施：复用索引及哈希规则，增加按明确 Manifest ID / 分区 / 逻辑名定位的纯读取核心，核对身份、成员、路径及哈希，分页并标出来源与截断，不导入源码。GUI / CLI 复用工具，不扩大通用 read 根目录。Manifest 附件以用户消息中的版本提示持久保存，不走图片解码，不自动注入全部源码；未附加版本也可查看。

验证：同名不同版本、不存在 / 损坏版本、未登记成员、符号链接 / 越界 / 哈希异常、读取不导入或执行、分页续读、不改 Candidate / 基线 / Default / Working Manifest；保留原图字节、多图片及恢复关联。Runtime 只保留已接受的可复用接口承诺，Stage 6 再接入。

## 潜在风险与验证

- **跨入口并发和回调归属**：当前 CLI 的锁内恢复有代码和既有测试，但新增 GUI 的切换、手动 Validate 及关闭竞争尚未验证；针对同 Session CLI 推进、锁竞争、取消后迟到事件及重启做验证。
- **凭据丢失或诊断泄漏**：新增 Session host 不会自动继承共享内存凭据；检查非 Windows 已配置密钥仍可用、切会话不丢失、错误和历史均脱敏。Windows DPAPI / 成品另行验证。
- **界面与真实行为**：offscreen 可以检查路由和禁用状态，不能证明 Windows 实际布局、焦点、取消或游戏动作；真实模型 / 游戏和 Windows 验收单列，不把替身结果计入。
- **资源增长**：Session / 自包含历史持续保留，磁盘占用增长是既有接受限制，本票不加入清理或迁移。

## 实施与检查顺序

1. 开发者确认本审查后，同步远端 #336 正文（替换折叠运行区要求、补充首次消息提交才固定，保留参考增量、标签及原生依赖）；不关闭 issue。
2. 扩展共用 Session 的模式 / 入口与明确空白来源；实现模式 Prompt / 白名单和纯只读 Manifest 核心，保留 CLI 拒绝 Construct。
3. 将 GUI 迁移到独立 Session 工作台，接入历史 / 附件 / Diff / Validate / Publish / 诊断；删除人工 Runner 控件及废弃偏好接口，保留 Agent trial_run、日志窗口、设置和 Capture。
4. 普通针对性验证覆盖 Session / Manifest / GUI / 图片 / 聊天 / 语言 / User GUI；回归稳定后运行普通全量。真实 pi / 工具循环检查必须标记 agent，显式选择相关文件和 --run-agent-tests，串行运行避免共享 game 锁竞争；本机 HTTP 替身与真实服务证据分开。
5. 记录结果及未验证项，交开发者试用；仅在开发者明确验收并授权后关闭 #336，不自动关闭后续票。

审查没有发现必须另起架构方案才能实施的阻塞决策；工具名、分页参数及会话列表展示等可在上述边界内选择最小实现。未运行测试、真实模型、pi-probe、Windows 或游戏；未更新远端 issue。本轮只新增 / 同步设计文档，保留工作区既有 #335 及其他前序改动。

文档检查：14 份相关设计文档的 125 个本地链接目标存在，git diff --check 通过；未检查全部历史文档或外部链接可用性。
