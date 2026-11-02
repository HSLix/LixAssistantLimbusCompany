# 页面审批三 Tab 与失败自动退回 — 影响审查

2026-11-02。输入为试用截图、本轮[已确认的修订决定](stage-5-339-340-decisions.md#2026-11-02-试用反馈后的修订讨论)、Stage 5 规格和 ADR 0034。本轮仅阅读源码 / 测试并记录设计，尚未修改实现或运行测试。原 #339 / #340 的本地通过记录不证明本次新交互已经实现。

审查完成后按开发者已授权的实施顺序交付修订，见[实施与验证](page-review-tabs-implementation.md)。下文保留审查时的代码差距。

## 设计变化

| 原行为 | 已确认的新行为 |
| --- | --- |
| 先显示模态审批窗，再加载拟安装页；失败后禁用安装，等人关闭才返回错误 | 拟安装页加载、接口或 ID 注册检查失败，不进入人工审批，直接把具体错误返回同轮 Agent |
| 左右双栏同时显示正式页与拟安装页，总结和哈希常驻窗口 | Current / Proposed / Review 三 Tab，每次默认 Proposed；Review 集中显示 Agent 总结、文件名、页面 ID 和版本详情 |
| 两侧独立实例及内存配置 | 保持两套实例和配置，切换 Tab 不重新创建 / 加载、不丢试填值 |

保持：旧正式页缺失 / 加载失败不阻止审批有效修复页；安装 / 关闭不安装 / 取消本轮三按钮始终可用，不强制浏览各 Tab；版本绑定、原子安装、失败保留原页、无自动重载、模式权限和取消收尾不变。安装时仍需重查目标及注册边界，安装写入失败继续沿现有窗口显示错误 / 允许关闭或取消，不把本次加载失败退回规则扩大为新的安装重试策略。无固定配置兼容检验，不调用 submit()。

附件中仅有关闭 / 安装的示例不替代已明确确认的三按钮；示例中的 Failed Review 展示不替代已明确确认的“拟安装页失败自动退回”。purpose 按样例术语 Proposed（拟安装页）处理。复用应用已有 Fluent 组件，不新增 UI 依赖或复制图片中的网页样式实现。

## 已确认的代码差距及影响

### 1. 失败只成为窗口内容，未自动结束工具等待

证据：`src/lalc/developer_gui.py:RepairPage.show_page_preview` 校验身份后构造并 show；`src/lalc/page_preview.py:PagePreviewDialog.__init__` 用 QTimer.singleShot 延后 load_pages。`load_pages` 捕获异常交给 show_error，并不结算 PreviewRequest。`src/lalc/repair_tools.py:RepairTools.page_preview` 一直等待 request.done，直到人关闭 / 安装 / 取消；因此缺 PAGE_ID 仍进入窗口，与截图一致。`tests/test_page_drafts.py:test_preview_failure_sides_and_no_install_on_close` 当前要求新侧失败也显示窗口，必须按新决定改写。

实施：保留 GUI 请求身份 / 轮次 / 取消校验，随后在 Qt 主线程先用共享加载器准备拟安装实例并检查注册；失败直接结算失败请求，后台工具返回 isError 与具体失败详情，记录同一轮 / 同一工具调用，不发新用户消息、不重置额度、不依赖人工关闭或另弹错误窗。成功后才准备旧侧并显示审批窗。正式配置读取失败同样无法建立有效预览，应返回明确错误而不打开空审批。

不能在后台工具线程创建 QWidget，不能只做缺 PAGE_ID 的静态字符串检查，也不能强制页面 ID 必须是字面量。复用 `src/lalc/user_pages.py:load_page_module / create_business_page` 的实际契约：缺声明、create_page 异常、返回对象 / submit 方法不符合要求、页面 ID / Task ID 冲突均返回真实错误；不调用 submit 检验配置。

### 2. 加载和窗口构建需要分开，成功实例只能准备一次

证据：`PagePreviewDialog.load_pages` 目前负责读取配置、加载两页、注册检查及拼装列内容；`src/lalc/page_drafts.py:MemorySettings` 提供独立内存配置，`PageDrafts.snapshot` 固定实际字节。若在新检查后仍沿用原 load_pages，会再次执行模块 / create_page，增加副作用并重置初始状态。

实施：把最小的准备步骤与呈现分开，将已加载的拟安装模块 / 页面实例及固定快照直接交给审批窗。拟安装页失败时无需加载旧页；成功时旧侧仍独立加载、独立内存，失败记录在 Current。切换 Tab 仅切换容器，保留两页实例。失败或取消时清理已准备而未展示的控件，取消后不闪出窗口，也不遗留未完成等待。

### 3. 审批布局替换，版本与权限边界保留

证据：`PagePreviewDialog.column` 和构造函数创建 QHBoxLayout 双列，Agent summary 为顶部 PlainTextEdit；当前各列显示哈希，未集中展示 PAGE_ID。`PagePreviewDialog.install / finish_closed / cancel_round / eventFilter` 已实现快照安装、单次结算、模态与关闭语义。`src/lalc/developer_gui.py:RepairPage` 已使用 Fluent SegmentedWidget，可复用同类 Tab 组件配合 Qt 页面容器。

实施：Current 展示旧页、缺失说明或错误；Proposed 展示已加载草稿；Review 展示只读 Agent 总结和版本详情（文件名、Session、PAGE_ID / 可选 TASK_ID、SHA-256；旧侧信息可得时一并区分）。默认 Proposed，在 Tab 外保留简洁目标标题与三按钮，不强制先访问 Review。Review 是 Agent 提交的审查说明，不是宿主证明配置 / Plan 兼容或业务通过的结论。保持正式路径只读工具、Construct 白名单、人工安装批准及快照绑定，不新增 Agent 安装工具或自动批准。

### 4. 工具返回、Prompt、测试及文档需要一同更新

证据：`RepairTools.call` 统一日志 / isError 传输；目前 page_preview 只把 request.result 包装为普通 text。`src/lalc/pi_probe.ts` 的 page_preview 描述仍说明双栏及“失败禁用安装”；`src/lalc/agent_prompts.py:MODE_PROMPTS` 仍按现有预览规则指导。`tests/test_developer_session_agent.py:test_actual_gui_page_install_returns_to_agent` 已检查真实 pi / GUI 安装链，但没有失败自动退回后修复重试的闭环。

实施：沿用现有工具名称、参数和传输结构，只补充可区分的预览失败结果与 isError；Agent 读错误、修正自己的草稿、重新请求预览，受本轮既有请求上限约束，宿主不自动修改代码或另造无界重试循环。更新工具说明 / Prompt，明确人工审批只接收已通过加载检查的页面，加载通过不等于业务兼容。

同步 Stage 5 规格中的左右对比、修订决定、当前实施记录、开发者用法及中英文 TS / QM。`docs/stage-5-339-340-design-impact-review.md` 保留原审查历史，并链接本次替代规则。ADR 0034 规定同进程比较、模态和人审版本，并未要求必须左右同时显示；其核心取舍不变，无需新 ADR。CONTEXT.md 的 Page Preview 是人工比较的概念，无需新增术语或写入 Tab 实现细节。

## 潜在风险与验证

- 提前加载仍是同进程可信 Python，卡死 / 崩溃不能保证返回；Qt 主线程加载期间也不能保证即时处理取消。沿用原风险，不宣称故障隔离，不扩大到子进程改造。
- 页面 create_page 自身的任意副作用不能靠隐藏宿主窗口阻止；只保证宿主不展示失败审批、不写正式配置。避免先试加载再重建造成双重副作用。
- 预览通过后正式目录可能变化；安装时必要路径 / ID 校验继续保留，不增加版本冲突阻断。Tab 默认和显示位置不能改变人工批准实际快照的范围。
- 拟安装页正确加载不代表 Agent 审查正确。自动退回只处理明确加载 / 契约 / 注册错误，不恢复此前已放弃的字段兼容检验。

实施后聚焦检查：缺 PAGE_ID、create_page 异常、非法返回值 / 缺 submit、ID 冲突均无审批窗 / 无人工点击而返回脱敏错误；旧页失败仍可安装修复页；成功后只执行一次拟安装模块及 create_page；默认 Proposed、三 Tab 切换不重置配置、Review 中身份 / 版本正确；取消及迟到回调不授权；快照安装及安装失败保留原页不回退。

Agent 测试显式标记并选择 `--run-agent-tests`，经实际 GUI → pi → 失败返回 → page_update 修正 → 再预览 / 安装 → 同轮继续验证；只用本机 HTTP 替身，与普通回归串行执行，避免共用游戏活动锁冲突。离屏布局检查和 Windows 成品模态 / 缩放 / 加载证据分别记录，跳过不计通过。

## 后续顺序

1. 按已确认的修订范围，先改准备 / 失败结算路径，再替换三 Tab 呈现，保留已有安装和取消核心。
2. 更新工具说明、Prompt、回归及 Agent 闭环测试，中英文资源和现行文档；不新增依赖、配置迁移或持久日志格式。
3. 交付修订验证记录，继续等待开发者验收；不因修订本地检查通过而关闭 #339 / #340。
