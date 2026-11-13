---

2026-11-05 补充：[ADR 0038](0038-use-versioned-reference-search-and-reusable-agent-processes.md) 替代本 ADR 的 Git fetch 不更新工作区约定，采用文件／索引一致的 A/B 更新；本 ADR 其他权限边界保持。
status: accepted
supersedes: 0029 (Agent shared Candidate and conversation reset lifecycle), 0032 (Developer GUI Agent entry and page construction prohibition)
---

# 统一 Agent 工作台、独立开发 Session 与人工页面安装

2026-11-11 局部替代：Runtime 使用现有 Repair Session 并可在 Run 后通过 Developer GUI 接续，按入口配权限；Runtime 只读知识库／Skills、全模式历史开关及人工反馈开关按新规格接入。开发页面安装审批和 Runtime 无删除权限保留。 见 [ADR 0040](0040-share-run-state-and-reuse-agent-sessions-for-runtime-repair.md)。下文保留原决定，不代表新设计已实现。

2026-10-31 经逐项 grill 确认，开发者授权开始设计影响审查。本文按最终决定重写，替代 2026-10-30 双页面与独立进程预览、以及本日早先双入口共享 Candidate 的方案；其余旧 ADR 仅在本声明涉及范围内被替代，历史实现证据不改写。

## 决定与取舍

Developer GUI 使用一个 Agent 工作台，保留 Construct / Repair 模式。新建并选择模式与来源后，首条用户消息提交前仍可调整两者，首次提交时才固定模式和来源；分别提供初始 Prompt 和工具白名单，模型工具声明与宿主实际调用同时强制执行。复用 Agent Loop / 工具 / 日志核心，避免复制实现；单一界面不代表统一权限。GUI 两种模式均可请求人工答复 / 操作反馈，仅 Construct 可构建页面草稿并进入预览安装流程。

每个 Developer Session 拥有独立 Candidate、固定 Diff 基线、连续聊天及页面草稿，持久保存并可恢复。Construct 可从空白最小 Plan 或已发布 Manifest 开始，Repair 必须从已发布 Manifest 开始。开始对话后取消 Session 内重建，换基线就新建；首版不删除或自动清理。相较共享草稿，代价是磁盘占用增加，收益是历史会话与其草稿来源保持一致。

CLI Repair 使用同一 Session 存储，支持按 Session ID 继续且可由 GUI 打开；同一 Session 执行互斥，入口权限与模式权限取交集，CLI 不运行 Construct 或 GUI 弹窗工具。手工 Candidate 留给开发者命令，Agent 不再接管；现有草稿与旧日志不自动迁移。意外退出保留已保存内容、标记中断，不自动重放操作或恢复未完成人工确认。

Asset Library、正式页面 / 配置、已发布版本和外部知识库仍全局共享，切换 Session 不回滚。#336 实施前进一步确认删除 Developer GUI 的 Manifest 选择及人工运行入口，不移入工作台，也不新增“应用到 User GUI”快捷设置；普通启动使用 User GUI。Agent 仍保留完整 Validate / Publish / 显式已发布版本 trial_run / Run 日志能力，以及原有互斥、取消与试运行日志窗口。旧 Developer Selected Manifest 设置停止读写，不迁移或删除旧文件；Session 来源及参考附件的选择职责保留。相较新增手动运行配置界面，此取舍减少重复入口，接受 Developer GUI 不再直接人工启动任意版本的限制。

页面草稿不进入 Manifest。采用同进程应用级模态对比窗口，分别运行当前正式页与拟安装页，配置各自为内存副本，锁住其他 LALC 窗口，关闭后解除。人工对照并确认实际预览版本，安装失败保留原页，正式接入由人主动整应用重载。取消独立进程的启动 / 通信 / 清理成本，接受页面卡死或崩溃可能影响主应用，以及无法完全卸载导入模块的限制；内存配置不是安全沙箱。

不做自动页面版本冲突检测或智能合并，由人检查覆盖是否符合预期。需要适配时 Agent 受控只读查阅最新正式页并在本 Session 草稿继续修改。保留安装目标、契约及预览版本校验，安装批准不因普通答复或旧确认而成立。该取舍减少自动合并机制，接受人确认覆盖其他 Session 改动的风险。

外部知识库供 GUI 两种模式只读查阅，Git 为限定同步例外：每轮首次访问仓库自动尝试 fetch 一次，可显式 fetch，每次尝试后 status；以当前分支 upstream 的前后提交比较更新，无 upstream / detached HEAD 则报告不确定，不猜分支或宣称最新。只开放受控 diff / show / fetch / log，不改工作区，版本来源明确；无通用终端、任意文件操作或设置 Default 权限。

Runtime Repair 保留 Stage 6 范围，不继承开发工具集，无删除工具和权限；人工交互仅有人监督 / 值守时开放，无人值守时不开放。值守状态及运行时接入细节留 Stage 6，不在本阶段修改 Working Manifest / Recheck 或运行时替换检查。

2026-10-31 Manifest 参考补充：GUI 附件可多选已发布 Manifest，参考部分直接在消息说明，不做 Component 树形选择。附件作为上下文信息保存 / 恢复，不充当访问白名单；GUI 两种模式和 CLI Repair 可按需只读查看任意已发布 Manifest 的结构及登记源码。选择本地已发布版本集合作为只读能力范围，避免维护逐附件授权状态；仍校验成员、哈希及路径，查看不导入 / 执行源码，不扩大 edit 或切换 Candidate / Default。Runtime Repair 也已明确获准使用该只读能力，不受值守状态限制，实际接入留 Stage 6；不因此继承其他开发能力。详见[专项审查](../stage-5-manifest-reference-impact-review.md)。

## 后果与验证

工具与开发者业务使用分批迭代，业务选择和验收由开发者承担。必须验证模式 / 入口权限、Session 持久化 / 中断 / 互斥、手工草稿保护、全局资源边界、双页模态 / 内存配置 / 版本确认安装；Windows 成品与实际模型 / 游戏另行记录。设计接受不等于实现完成。

完整契约见 [Stage 5 规格](../stage-5-agent-workbench.md)，源码差距见[影响审查](../stage-5-design-impact-review.md)，讨论决定见[记录](../stage-5-2026-10-31-decisions.md)。

2026-11-06 试用修订：页面草稿不再区分新增／替换，也不依赖独立目标元数据；同一草稿可反复编辑、预览并由人工批准覆盖同名正式页，旧元数据忽略。仍校验路径、注册冲突及固定整包快照。本轮 Agent 后台作业结束并清理完成后，仅当本轮有实际页面安装时统一显示一次独立完成弹窗；安装后本轮失败或取消仍提示，无安装或仅恢复历史不提示。可取消提示继续工作，或主动选择现在重启，沿用既有整应用重载，不绕过活动门控。


2026-11-13：Developer GUI → Agent Settings 新增“允许查询已发布 Manifest”（`manifest_reference_enabled`），默认开启，保存后下一轮生效；统一控制 GUI Construct／Repair、CLI Repair 和 Runtime Repair 的 `list_manifests`、`read_manifest`、`read_manifest_source`。关闭后不向模型提供这三个工具，宿主同时拒绝调用；不影响历史检索、外部知识、Candidate 编辑、发布或试运行。仍允许附加 Manifest 引用并验证 ID，附件不重新授予工具权限；已进入上下文的历史内容不清除。旧配置缺字段时默认开启，无须手工迁移。
