# #339 / #340 — 页面草稿、对比及人工安装影响审查

2026-11-02 试用后的三 Tab 和失败自动返回决定见[修订审查](page-review-tabs-design-impact-review.md)。本文保留初版审查证据；双栏及拟安装页失败禁用安装 / 等待关闭的描述已被修订替代。

2026-11-01。输入为本轮[逐项确认](stage-5-339-340-decisions.md)、[Stage 5 规格](stage-5-agent-workbench.md)、[ADR 0034](adr/0034-extend-developer-agent-with-reviewed-page-drafts.md)，并读取 GitHub #339 / #340 正文及评论（两票均 OPEN，无评论）。本报告为源码与测试阅读结果，未执行测试、模型请求或页面代码；实现须等待开发者确认。

## 设计变化

| 既有要求 / 拆分 | 本轮确认 |
| --- | --- |
| #339 草稿及预览，#340 人工安装及重载接入分别交付 | 合并设计、实现和验收，保留两票全部验收项；开发者确认后才关闭 |
| Session 保留页面草稿，存储细节未定 | `developer-sessions/<id>/page-drafts/` 内单文件 Python 页；正式页仍在 `pages/`，复制编辑记录原文件名作为目标；新增不能误覆盖 |
| 兼容检查结果反馈 Agent | 不建设固定配置兼容检查，不自动调用 submit()，不增加检查配置按钮；宿主检查加载 / 页面契约 / 必要路径与 ID 边界，Agent 总结字段变化、旧配置及 Plan 影响 |
| 人工确认实际预览版本 | 一个窗口提供安装此版本、关闭不安装、取消本轮；前者安装预览代码，关闭继续 Agent，取消结束本轮 |
| 两侧加载异常处理未细化 | 旧页失败独立显示错误，不阻止安装有效修复页；草稿失败禁用安装 |

保持同进程应用级模态、两份旧配置内存副本、安装不采用试填值、人工覆盖而无自动版本冲突检测、不自动重载 / 改 Default / 清空旧配置、破坏兼容先获明确授权、CLI / Repair / Runtime 不继承页面工具权限。CONTEXT.md 的 Page Draft / Page Preview 已涵盖概念，不新增领域术语；ADR 0034 的取舍未改变，无需新 ADR。

## 确认的影响与实施差距

以下“确认”指已读代码建立的差距，不表示旧代码违反当时已交付范围。

### 1. 页面必须走专用工具，不能扩大 Candidate 通用文件范围

证据：`src/lalc/agent_policy.py:MODE_TOOLS / ENTRY_TOOLS / allowed_tools` 当前 Construct / Repair 共用工具集合，没有页面操作；`src/lalc/pi_probe.ts` 的 checkedPath / checkedEdit 将原生 read / edit 限制在 Candidate；`src/lalc/repair_tools.py:RepairTools.call` 独立检查允许集合并分发；`src/lalc/agent_repair.py:RepairConversation.run` 下发实际白名单并经 lalc.tool RPC 在线程中调用宿主。

影响：新增最小专用页面列举 / 读取、草稿创建 / 更新和预览工具，仅 GUI Construct 同时通过模型声明和宿主分发；普通 read / edit 保持原范围。正式页只读工具只返回源码 / 元数据，不导入执行代码。草稿写入工具不能直接写正式目录；不提供 Agent 可独立调用的安装工具。安装由预览窗口的人工作用触发。

相关测试：`tests/test_workbench.py:test_mode_entry_policy_and_host_reject_before_dispatch`、`tests/test_developer_session_agent.py:test_mode_white_list_hides_and_rejects_disallowed_native_tools` 已检查权限链；新增页面工具的模式 / 入口拒绝、实际声明及调用回路检查。历史工具结果不能赋予权限，格式纠正阶段继续禁用全部工具。

### 2. Session 已有持久目录和锁，草稿需独立于 Manifest

证据：`src/lalc/developer_session.py:DeveloperSession.__init__ / create / check / restore` 将 Candidate、固定基线和日志置于 Session；`src/lalc/developer.py:candidate_files / editable_files` 只处理 Candidate；`DeveloperHost.candidate_lock` 和 `RepairConversation.run` 已串行化当前 Session。

影响：在 Session 下按需建立 page-drafts，不改 Manifest schema 或已有日志格式。保存原文件名 / 新增身份的草稿元数据，拒绝路径越界、符号链接、非法及不被加载器发现的文件名；新建与更新分开，更新保持原目标，不借字段改动暗中转成另一文件覆盖。空白草稿直接提交完整单文件源代码，不新增通用文件工具。草稿保存失败保留旧版本，重开 Session 读取已保存内容；本轮新增文件只能通过专用页面接口访问。安装后保留草稿，不迁移或自动清理旧 Session。

工作台沿用既有文件夹入口的交互方式补充当前 Session 草稿目录入口，不建设额外草稿管理页面。新旧 Session、正式目录和手工 Candidate 的隔离需专项测试。

### 3. 正式页面加载器的契约可复用，配置保存不能直接复用

证据：`src/lalc/user_pages.py:discover_pages` 直接编译当前源码字节，用独立模块名加载；检查 PAGE_ID / PAGE_NAME / TASK_ID、保留 ID、重复 ID、create_page 返回值及 submit 方法；逐页隔离普通加载异常。`UserSettings.save` 通过 atomic_write_json 写正式设置，`PageContext.save` 直接委托 store.save，`PageContext.load` 返回深拷贝。

影响：抽取最小必要的单页加载 / 契约逻辑供正式发现和双预览共用，保留现有错误、导航图标、语言及重复注册处理；单页加载接受固定源码字节，不能重新读取变动后的草稿冒充已预览版本。预览使用两个独立内存存储，以当前正式设置复制初始化；两侧使用不同模块身份 / 页面实例，不加入正式导航。宿主 context.save 只更新各自内存，关闭丢弃，不生成正式或试验配置文件。

不自动调用 submit()；字段含义及 Plan 兼容性由 Agent 查阅源码总结。加载异常按旧侧 / 草稿侧分别返回，旧页失败仍可修复；草稿失败不能安装。`tests/test_user_pages.py` 的正常页面发现、重复注册、配置 / Dashboard / Plan 测试可作回归，不能替代内存零落盘、两侧不互相修改及失败侧处理的新检查。

### 4. 人工等待可沿用线程协议，不能把非模态反馈框改成页面安装确认

证据：`src/lalc/human_feedback.py:FeedbackRequest` 单次结算并作废迟到答复；`src/lalc/repair_tools.py:request_feedback` 可取消等待；`src/lalc/developer_gui.py:FeedbackDialog / RepairPage.show_feedback` 是非模态文字反馈，并核对日志身份 / 轮次 / 当前作业。`RepairPage.is_busy / update_actions` 禁止活动中切换 Session；`src/lalc/application.py:ApplicationService.activity` 在 Agent 轮次期间持有活动所有权。

影响：页面审查采用独立请求和窗口，保留单次结算、身份检查、取消收尾及日志关联模式。预览作为当前 Agent 活动中的子步骤，不能再次申请同名排他活动造成自锁。Qt 主线程创建页面及窗口，Agent 后台等待；应用级模态锁住其他 LALC 窗口，被锁窗口点击强调 / 聚焦现有预览并在现有窗口提示，不叠警告框。窗口内三种选择均有完成路径，关闭 / Esc 不安装，取消先取消本轮，迟到确认无效；结束 / 异常 / 退出解除等待与锁定。游戏和其他应用不被锁住。

`tests/test_human_feedback.py` 只证明非模态反馈、空确认、取消和迟到回调；新增页面预览测试需验证 ApplicationModal、双窗口阻挡、三种结算、旧请求拒绝和下一轮不受旧回调影响。

### 5. 安装需要固定字节提交，重载保持现有入口

证据：`src/lalc/user_pages.py:discover_pages` 只加载 data_root/pages 的顶层 .py 文件；`src/lalc/gui.py:GuiCoordinator.request_reload / restart_process` 已负责活动门控、保存两窗状态、生命周期清理后重启；UserWindow.submit_pages 会提交当前已加载的旧页面实例。`src/lalc/runtime.py:atomic_write_json` 提供已有“临时文件再 replace”提交模式，但只处理 JSON，不能直接用于页面源码。

影响：预览请求保留实际草稿源码和目标身份，窗口显示来源、目标及版本标识；人工安装只提交该快照，不重新读取后续草稿。提交前重新检查目标路径、页面 / Task ID 注册边界；正常替换自身身份不算重复。必要冲突检查不等于正式版本冲突检查，不做自动合并或文件版本一致性门控。新增不能误覆盖，替换使用目标目录内准备文件和原子提交，提交失败保留旧正式文件及 Session 草稿，错误留在窗口并反馈 Agent，不能误报已安装。

不保存试填值、不清空原配置、不改变 Default。安装后明确提示使用既有整应用重载，不能在仍等待工具结果的 Agent 轮次中自动重启。重载后的页面配置进入现有 task_inputs / Dashboard / Plan 路径；复用 `tests/test_user_pages.py` 的重载门控、真实子进程重扫和 Plan 输入检查，补充“实际安装后再重载”的闭环。

## 潜在风险与验证边界

- 同进程页面导入 / create_page 可能写盘、联网、退出或卡死，宿主内存配置并非安全沙箱；沿用已接受限制。重开只保证新模块身份和当前页面字节，不保证清理所有导入依赖；不能用普通异常测试证明进程故障隔离。
- 固定程序不能证明旧字段含义与 Plan 一致。Agent 的影响总结及破坏兼容授权需在 Prompt / 工具说明中明确，加载结果不能包装成兼容通过；实际模型是否正确执行该指导须独立验收。
- 已打开的旧正式页若 submit() 报错，现有 request_reload 会阻止重载（`tests/test_user_pages.py:test_validation_failure_does_not_start_or_schedule_restart` 覆盖该规则）。本票不偷偷跳过旧页提交或丢弃未保存输入；需要报告限制，可在正常退出后重新启动加载已安装修复页。旧代码完全卡死时同进程方案无法保证交互收尾。
- Windows 成品的应用级模态、被锁窗点击反馈、双栏布局 / 缩放、页面安装文件占用及重启须实机验证。macOS/offscreen 检查、HTTP 模型替身及真实游戏证据分别记录。
- 检查时工作区已有其他文档改动；本轮仅新增决定 / 审查文件，不覆盖这些改动。正式规格同步在获准实现后按最小段落合并。

## 后续工作顺序与验收

1. 开发者确认本报告后，同步 Stage 5 规格、实施拆分、Developer GUI 用法和 domain 入口的本轮细化；保留历史记录，不改 CONTEXT 术语或创建重复 ADR。
2. 实现 Session 单文件草稿存储和专用只读 / 写草稿工具，接通 Construct / GUI 双层权限、工具 schema、Prompt、持久日志；不扩大 Candidate 通用权限。
3. 复用页面契约实现双侧固定字节加载和内存配置，再接 Qt 主线程模态审查 / 可取消等待、窗口内人工安装及原子提交。
4. 运行聚焦普通测试：草稿持久化 / 隔离 / 越界、正式读取不执行、契约和冲突、两侧配置零落盘、失败侧策略、版本快照安装、安装失败保留旧页、取消和迟到回调、安装重载到 Dashboard / Plan。
5. 本票确实涉及 Agent 工具接入，显式选择相关 `pytest.mark.agent` 测试并加 `--run-agent-tests`，使用实际 pi 与本机 HTTP 替身验证工具声明 / 拒绝 / 同轮结果 / 中断恢复；不调用付费或真实模型。普通全量回归不加该参数，跳过不算通过。
6. 交付实施记录，区分本地测试、真实模型、Windows 成品和游戏验收；开发者确认完整成果后才按 completed 关闭 #339 / #340。
