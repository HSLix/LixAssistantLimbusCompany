# Stage 5 — Tickets 实施拆分

2026-10-31，开发者确认将原第 2 / 3 票合并，其余通过，共六票。依据已确认规格及设计影响审查；按此拆分发布 GitHub Issues。已发布为 #335–#340，六票正文、ready-for-agent 标签及五条原生阻塞关系均已回读核验。下列序号保留为实施顺序。

依赖：1 → 2；2 → 3、4、5；5 → 6。3 / 4 不阻塞页面预览或安装；业务由开发者推进，不作为工具发布前置。

## 1. [#335](https://github.com/HSLix/LixAssistantLimbusCompany/issues/335) CLI Repair 使用独立且可恢复的 Developer Session

**Blocked by:** 无，可立即开始

**交付：** 开发者可从指定已发布 Manifest 创建 Repair Session，在 CLI 对话、修改草稿、校验、Publish 和明确版本试运行；退出后按 Session ID 继续，手工 Candidate 始终不变。

- [ ] 创建必须明确已发布来源；每 Session 独立 Candidate / 固定基线 / 聊天 / 模式，创建失败不破坏已有数据。
- [ ] 恢复保存的消息、附件和工具结果关联、轮次及日志，模式为 Repair；CLI 不执行 Construct 或 GUI 工具。
- [ ] 同一 Session 跨进程互斥，保留既有游戏活动互斥；再次执行前在锁内读取最新状态。
- [ ] 意外退出标记中断，不自动重放模型请求、工具、试运行或确认，不补造成功结果；悬空工具调用处理有针对性验证。
- [ ] 手工初始化 / 校验 / 发布 / 清理仍使用开发者 Candidate；不迁移旧草稿或旧日志，不删除或自动清理 Session。
- [ ] 保留原修复及发布后试运行能力，针对两 Session 隔离、恢复、失败和锁竞争验证；真实 pi / 工具循环测试按 agent 规则显式选择。

## 2. [#336](https://github.com/HSLix/LixAssistantLimbusCompany/issues/336) Agent 工作台统一页面、Session 导航与 Construct / Repair 模式

**Blocked by:** [#335](https://github.com/HSLix/LixAssistantLimbusCompany/issues/335)

**交付：** Developer GUI 在统一工作台中创建及恢复 Construct / Repair Session，完成历史续聊、空白或指定来源开发、校验、发布和明确版本试运行；页面布局、模式权限及会话导航作为一个完整增量验收。

- [ ] 工作台包含历史 Session 侧栏、聊天主体、底部输入区和紧凑新建按钮；新建选择模式，开始对话后固定，历史显示真实模式，不提供 Session 重建或删除。
- [ ] Construct 可从空白最小 Python Plan 或已发布 Manifest 开始，Repair 必须选已发布来源；空白不隐式使用 Default，新建不影响其他 Session 或手工 Candidate。
- [ ] 恢复 GUI / CLI Repair Session，Diff / Validate / Publish / 事件 / 诊断 / 脱敏及请求计数准确归属；重启可继续，旧日志不自动变成 Session。
- [ ] Construct / Repair 各有初始 Prompt 和工具白名单，实际能力取模式与入口交集；模型声明和分发均拒绝越权，覆盖 read / edit、validate 和宿主工具。
- [ ] 两种模式复用 Agent 核心，保留自身 Candidate 编辑及专用新增、完整校验、Asset / Trusted Action 边界、不可变 Publish 后显式试运行；CLI 拒绝 Construct，不因历史记录扩权。
- [ ] Agent 执行、人工等待或试运行期间禁切换 / 新建 Session，取消实际收尾后恢复；不提供后台多 Session 执行。
- [ ] 移除各页顶部 Manifest 区域，仅工作台右上折叠区选择全局 Developer Selected Manifest 并试运行所选 Plan；不新增 Runner 页面。
- [ ] 选择列表展开前自动刷新并保留有效选择，失败或缺失报错，不静默替换；Session 切换 / Publish 不自动改选，不修改 Default 或 Candidate 来源。
- [ ] Capture / Agent Settings 原职责保持，双语一致；完成两种来源到发布 / 试运行以及 CLI-GUI 续聊、权限拒绝的针对性验证，Windows 成品操作另记。
- [ ] 后续知识库、人工反馈、页面构建工具分别按对应票接入白名单，尚未实现时不可调用；本票不把替身证据计为真实模型或游戏验收。

## 3. [#337](https://github.com/HSLix/LixAssistantLimbusCompany/issues/337) GUI 两种模式读取知识库并检查受控 Git 更新

**Blocked by:** [#336](https://github.com/HSLix/LixAssistantLimbusCompany/issues/336)

**交付：** 开发者打开数据目录中的知识库文件夹准备资料，两种 GUI 模式可检索、查看文件或提交内容，获得准确的远端更新反馈。

- [ ] 仅授权数据目录知识库只读资料访问，包含文档和图片；不编辑参考资料、clone、执行项目或把新增 read 根目录变成 edit 权限。
- [ ] 每轮首次访问每仓库自动尝试 fetch 一次，可显式 fetch，不自动重试；每次后 status，失败本地仍可读取。
- [ ] 以当前分支 upstream 的 before / after 反馈区间差异；缺失 upstream / detached HEAD 报不确定，不猜分支或宣称最新。
- [ ] 区分 HEAD、参考提交和未提交工作区；无更新仍可 show / log / diff，不自动更新工作区或 push。
- [ ] Git 操作及真实路径 / 符号链接 / 引用 / 参数受控，无命令或写出路径绕过，失败 / 取消不遗留等待。
- [ ] 检索和 diff 输出可定位来源 / 版本，截断明确且能继续查看；不自动授予 CLI / Runtime，也不前置复杂索引或指定外部业务。

## 4. [#338](https://github.com/HSLix/LixAssistantLimbusCompany/issues/338) GUI Construct 与 Repair 同轮请求人工反馈

**Blocked by:** [#336](https://github.com/HSLix/LixAssistantLimbusCompany/issues/336)

**交付：** 两种 GUI 模式可在当前开发轮次提问或请求人工操作，等待反馈后继续；人可跳过、关闭或取消，游戏仍可操作。

- [ ] 显示请求、输入及 Confirm / Skip，实际答复返回同 Session 上下文并按现有规则脱敏记录，不重置本轮请求额度。
- [ ] Confirm 仅代表答复 / 操作反馈，不证明游戏目标达成、不隐式恢复人工暂停、不替代安装或其他明确授权。
- [ ] Skip / 关闭 / Esc 明确跳过，不推断操作完成或取得授权；空答复具有明确结果。
- [ ] 等待不并行自动输入或试运行，不妨碍切换游戏；GUI 响应且有可用取消出口。
- [ ] 取消 / 窗口退出解除等待并按既有流程清理，重复 / 迟到回调不能写入其他请求或 Session。
- [ ] CLI / Runtime 不暴露该 GUI 工具；Stage 6 值守权限只作契约，不在本票实现 Runtime 接入。

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
