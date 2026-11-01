# Stage 5 — Tickets 实施拆分

2026-10-31，开发者确认将原第 2 / 3 票合并，其余通过，共六票。依据已确认规格及设计影响审查；按此拆分发布 GitHub Issues。已发布为 #335–#340，六票正文、ready-for-agent 标签及五条原生阻塞关系均已回读核验。下列序号保留为实施顺序。

依赖：1 → 2；2 → 3、4、5；5 → 6。3 / 4 不阻塞页面预览或安装；业务由开发者推进，不作为工具发布前置。

## 1. [#335](https://github.com/HSLix/LixAssistantLimbusCompany/issues/335) CLI Repair 使用独立且可恢复的 Developer Session

2026-10-31：已本地实现并经开发者明确确认关闭为 completed；证据及限制见[实施记录](stage-5-335-implementation.md)。下列验收清单保留为原票范围，不将本地检查等同于真实模型 / Windows / 游戏验收。

**Blocked by:** 无，可立即开始

**交付：** 开发者可从指定已发布 Manifest 创建 Repair Session，在 CLI 对话、修改草稿、校验、Publish 和明确版本试运行；退出后按 Session ID 继续，手工 Candidate 始终不变。

- [ ] 创建必须明确已发布来源；每 Session 独立 Candidate / 固定基线 / 聊天 / 模式，创建失败不破坏已有数据。
- [ ] 恢复保存的消息、附件和工具结果关联、轮次及日志，模式为 Repair；CLI 不执行 Construct 或 GUI 工具。
- [ ] 同一 Session 跨进程互斥，保留既有游戏活动互斥；再次执行前在锁内读取最新状态。
- [ ] 意外退出标记中断，不自动重放模型请求、工具、试运行或确认，不补造成功结果；悬空工具调用处理有针对性验证。
- [ ] 手工初始化 / 校验 / 发布 / 清理仍使用开发者 Candidate；不迁移旧草稿或旧日志，不删除或自动清理 Session。
- [ ] 保留原修复及发布后试运行能力，针对两 Session 隔离、恢复、失败和锁竞争验证；真实 pi / 工具循环测试按 agent 规则显式选择。

## 2. [#336](https://github.com/HSLix/LixAssistantLimbusCompany/issues/336) Agent 工作台统一页面、Session 导航与 Construct / Repair 模式

2026-10-31：已本地实施并进入验证，等待开发者验收后关闭；见[实施记录](stage-5-336-implementation.md)。下列清单保留交付范围，不代表开发者或 Windows / 真实模型 / 游戏验收已通过。

**Blocked by:** [#335](https://github.com/HSLix/LixAssistantLimbusCompany/issues/335)

**交付：** Developer GUI 在统一工作台中创建及恢复 Construct / Repair Session，完成历史续聊、空白或指定来源开发、校验、发布和明确版本试运行；页面布局、模式权限及会话导航作为一个完整增量验收；支持 Manifest 参考附件，以及 GUI / CLI 按需只读查看任意已发布 Manifest。

- [ ] 工作台包含历史 Session 侧栏、聊天主体、底部输入区和紧凑新建按钮；新建后至首条用户消息提交前可调整模式和来源，首次提交时两者固定，历史显示真实模式，不提供 Session 重建或删除。
- [ ] Construct 可从空白最小 Python Plan 或已发布 Manifest 开始，Repair 必须选已发布来源；空白不隐式使用 Default，新建不影响其他 Session 或手工 Candidate。
- [ ] 恢复 GUI / CLI Repair Session，Diff / Validate / Publish / 事件 / 诊断 / 脱敏及请求计数准确归属；重启可继续，旧日志不自动变成 Session。
- [ ] Construct / Repair 各有初始 Prompt 和工具白名单，实际能力取模式与入口交集；模型声明和分发均拒绝越权，覆盖 read / edit、validate 和宿主工具。
- [ ] 两种模式复用 Agent 核心，保留自身 Candidate 编辑及专用新增、完整校验、Asset / Trusted Action 边界、不可变 Publish 后显式试运行；CLI 拒绝 Construct，不因历史记录扩权。
- [ ] Agent 执行、人工等待或试运行期间禁切换 / 新建 Session，取消实际收尾后恢复；不提供后台多 Session 执行。
- [ ] 删除 Developer GUI 各页顶部 Manifest 选择、刷新及人工运行入口，不移入工作台、不新增 Runner 页或“应用到 User GUI”；User GUI 普通启动保持。
- [ ] Agent 保留完整校验、Publish、显式已发布版本 trial_run、Run 日志及互斥 / 取消 / 试运行日志窗口；旧 Developer Selected Manifest 停止读写，不迁移或删除旧文件，不修改 Default 或 Candidate 来源。
- [ ] Capture / Agent Settings 原职责保持，双语一致；完成两种来源到发布 / 试运行以及 CLI-GUI 续聊、权限拒绝的针对性验证，Windows 成品操作另记。
- [ ] 后续知识库、人工反馈、页面构建工具分别按对应票接入白名单，尚未实现时不可调用；本票不把替身证据计为真实模型或游戏验收。

2026-10-31 参考附件增量（已 grill、专项审查及本地文档同步，纳入本票）：

- [ ] GUI 附件可选择一个或多个已发布 Manifest，参考全部 / 部分内容由聊天消息说明，不做逐 Component 树形选择；Manifest ID 和提示作为消息信息持久保存及恢复，不自动注入全部源码。
- [ ] GUI Construct / Repair 与 CLI Repair 均提供任意已发布 Manifest 的只读查看，无须先附加；附件不构成访问白名单，不增加逐附件授权或撤销机制。
- [ ] 工具可按需列出已发布版本、查看结构及其登记源码，返回 Manifest ID、分区 / 逻辑名、Component ID 和所读位置；截断明确且可继续读取，缺失 / 损坏 / 身份校验失败不静默替换版本。
- [ ] 查看不导入 / 执行参考 Python，验证成员关系、内容哈希、真实路径及符号链接边界；不得提供任意文件读取、编辑 / 删除 / 写出或执行能力，不扩大 Candidate edit 范围。
- [ ] 附加和查看不改变 Candidate、来源 / 固定基线、Default 或 Working Manifest，不启动试运行或切换执行版本；参考后修改仍走当前模式既有草稿工具。
- [ ] 新增验收覆盖多 Manifest 提示与会话恢复、未附加版本可查看、同名 Component 不同版本定位、越界 / 哈希异常及纯读取不执行源码 / 不改选择状态；保留图片附件行为。
- [ ] Runtime Repair 工具白名单已确定包含同一只读能力，不受值守状态限制；本票交付可复用核心及 GUI / CLI 接入，Stage 6 再接运行时，不提前实现恢复流程或其他权限。

## 3. [#337](https://github.com/HSLix/LixAssistantLimbusCompany/issues/337) GUI 两种模式读取知识库并检查受控 Git 更新

2026-11-01 本地实施已接入，见[实施记录](stage-5-337-implementation.md)；开发者人工验收总体通过，#337 已按 completed 关闭；以下勾选表示本地交付完成，不补造 Windows、真实远端或真实模型专项通过证据。目录缺失时创建空目录、文本 / 图片格式、非交互认证、系统 Git 降级及辅助程序边界见[补充决定](stage-5-337-decisions.md)。

**Blocked by:** [#336](https://github.com/HSLix/LixAssistantLimbusCompany/issues/336)

**交付：** 开发者打开数据目录中的知识库文件夹准备资料，两种 GUI 模式可检索、查看文件或提交内容，获得准确的远端更新反馈。

- [x] 仅授权数据目录知识库只读资料访问，包含文档和图片；不编辑参考资料、clone、执行项目或把新增 read 根目录变成 edit 权限。
- [x] 每轮首次访问每仓库自动尝试 fetch 一次，可显式 fetch，不自动重试；每次后 status，失败本地仍可读取。
- [x] 以当前分支 upstream 的 before / after 反馈区间差异；缺失 upstream / detached HEAD 报不确定，不猜分支或宣称最新。
- [x] 区分 HEAD、参考提交和未提交工作区；无更新仍可 show / log / diff，不自动更新工作区或 push。
- [x] Git 操作及真实路径 / 符号链接 / 引用 / 参数受控，无命令或写出路径绕过，失败 / 取消不遗留等待。
- [x] 检索和 diff 输出可定位来源 / 版本，截断明确且能继续查看；不自动授予 CLI / Runtime，也不前置复杂索引或指定外部业务。

## 4. [#338](https://github.com/HSLix/LixAssistantLimbusCompany/issues/338) GUI Construct 与 Repair 同轮请求人工反馈

2026-11-01 已本地实施，见[决定](stage-5-338-decisions.md)和[实施记录](stage-5-338-implementation.md)。以下勾选表示本地交付及自动检查范围，#338 尚待开发者人工验收，不代表 Windows、真实模型或游戏通过。

**Blocked by:** [#336](https://github.com/HSLix/LixAssistantLimbusCompany/issues/336)

**交付：** 两种 GUI 模式可在当前开发轮次提问或请求人工操作，等待反馈后继续；人可跳过、关闭或取消，游戏仍可操作。

- [x] 显示统一内容 / 意图与文字输入及 Confirm / Skip，实际答复返回同 Session 上下文并按现有规则脱敏记录，不重置本轮请求额度。
- [x] Confirm 仅代表答复 / 操作反馈，不证明游戏目标达成、不隐式恢复人工暂停、不替代安装或其他明确授权。
- [x] Skip / 关闭 / Esc 明确跳过，不推断操作完成或取得授权；空答复明确返回 confirmed 与空文字。
- [x] 不设自动超时；等待不并行自动输入或试运行，不妨碍切换游戏；普通非模态 GUI 响应且有可用取消出口。
- [x] 取消 / 窗口退出解除等待并按既有流程清理，重复 / 迟到回调不能写入其他请求或 Session。
- [x] CLI / Runtime 不暴露该 GUI 工具；Stage 6 值守权限只作契约，不在本票实现 Runtime 接入。

## 5. [#339](https://github.com/HSLix/LixAssistantLimbusCompany/issues/339) Construct 创建页面草稿并模态对比预览

**Blocked by:** [#336](https://github.com/HSLix/LixAssistantLimbusCompany/issues/336)

**交付：** Construct 可从空白或当前正式页面创建本 Session 草稿，修改后在一个模态窗口左右操作当前正式页和拟安装页，试填不影响正式配置。

- [ ] 页面草稿按 Session 保留，当前正式页通过受控只读入口访问；Repair / CLI 无构建与预览工具权限。
- [ ] 页面接口 / ID / 旧配置 / Plan 参数兼容检查结果反馈 Agent，破坏兼容先获授权，不自动丢弃旧配置。
- [ ] 同进程窗口左右各加载一个独立实例及内存配置；同名页不存在标明新增，修改后重开加载当前草稿字节。
- [ ] 应用级模态锁住 User / Developer 其他窗口，点击时提示并强调预览；两页可操作，游戏和其他应用不被锁住。
- [ ] 预览期间不能切换 / 新建 Session 或启动新 Agent 修改；关闭 / 失败 / 取消能解除锁定与等待，不依赖被锁主窗按钮。
- [ ] 宿主配置保存零正式落盘、两侧试填互不影响、关闭丢弃；记录同进程故障和模块卸载限制，Windows 成品模态与布局单独验证。

## 6. [#340](https://github.com/HSLix/LixAssistantLimbusCompany/issues/340) 人工确认对比版本后安装并重载业务页面

**Blocked by:** [#339](https://github.com/HSLix/LixAssistantLimbusCompany/issues/339)

**交付：** 开发者在双页对比中确认拟安装版本，安全新增或替换正式页面，再主动整应用重载，从 User GUI 配置并对接既有 Dashboard / Plan。

- [ ] 仅人工明确批准实际预览草稿版本才安装；普通答复、旧确认或后续修改不得复用授权。
- [ ] 对比当前正式页与拟安装页，由人决定覆盖；不加入自动版本冲突阻断或智能合并。需要适配可回到当前 Session 重读正式页修改草稿。
- [ ] 保留安装目标路径、页面契约及页面 / Task ID 验证；失败保留原正式页和草稿，不误报成功。
- [ ] 安装不导入试填配置、不清空已有配置、不进入 Manifest、不改变 Default、不自动重启；活动期间仍禁止重载。
- [ ] 安装与重载后真实页面配置按稳定 ID 进入 Dashboard / Plan 输入，页面 / 任务支持检查有效；不冒充实际游戏业务成功。
- [ ] 覆盖已接受的人工覆盖风险、版本绑定失效、新增 / 替换失败恢复及 Windows 成品加载与操作，证据与未验证项分别记录。
