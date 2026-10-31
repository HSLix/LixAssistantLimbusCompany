---
status: accepted
supersedes: 0029 (Agent shared Candidate and conversation reset lifecycle), 0032 (Developer GUI Agent entry and page construction prohibition)
---

# 统一 Agent 工作台、独立开发 Session 与人工页面安装

2026-10-31 经逐项 grill 确认，开发者授权开始设计影响审查。本文按最终决定重写，替代 2026-10-30 双页面与独立进程预览、以及本日早先双入口共享 Candidate 的方案；其余旧 ADR 仅在本声明涉及范围内被替代，历史实现证据不改写。

## 决定与取舍

Developer GUI 使用一个 Agent 工作台，保留 Construct / Repair 模式。Session 创建时选定，开始对话后固定；分别提供初始 Prompt 和工具白名单，模型工具声明与宿主实际调用同时强制执行。复用 Agent Loop / 工具 / 日志核心，避免复制实现；单一界面不代表统一权限。GUI 两种模式均可请求人工答复 / 操作反馈，仅 Construct 可构建页面草稿并进入预览安装流程。

每个 Developer Session 拥有独立 Candidate、固定 Diff 基线、连续聊天及页面草稿，持久保存并可恢复。Construct 可从空白最小 Plan 或已发布 Manifest 开始，Repair 必须从已发布 Manifest 开始。取消 Session 内重建，换基线就新建；首版不删除或自动清理。相较共享草稿，代价是磁盘占用增加，收益是历史会话与其草稿来源保持一致。

CLI Repair 使用同一 Session 存储，支持按 Session ID 继续且可由 GUI 打开；同一 Session 执行互斥，入口权限与模式权限取交集，CLI 不运行 Construct 或 GUI 弹窗工具。手工 Candidate 留给开发者命令，Agent 不再接管；现有草稿与旧日志不自动迁移。意外退出保留已保存内容、标记中断，不自动重放操作或恢复未完成人工确认。

Asset Library、正式页面 / 配置、已发布版本和外部知识库仍全局共享，切换 Session 不回滚。Developer Selected Manifest 保持全局选择，只在工作台折叠区显示，选择前刷新，切会话和 Publish 均不自动改变，不修改 Default 或 Session 来源；Agent 试运行仍须明确的已发布 Manifest ID。

页面草稿不进入 Manifest。采用同进程应用级模态对比窗口，分别运行当前正式页与拟安装页，配置各自为内存副本，锁住其他 LALC 窗口，关闭后解除。人工对照并确认实际预览版本，安装失败保留原页，正式接入由人主动整应用重载。取消独立进程的启动 / 通信 / 清理成本，接受页面卡死或崩溃可能影响主应用，以及无法完全卸载导入模块的限制；内存配置不是安全沙箱。

不做自动页面版本冲突检测或智能合并，由人检查覆盖是否符合预期。需要适配时 Agent 受控只读查阅最新正式页并在本 Session 草稿继续修改。保留安装目标、契约及预览版本校验，安装批准不因普通答复或旧确认而成立。该取舍减少自动合并机制，接受人确认覆盖其他 Session 改动的风险。

外部知识库供 GUI 两种模式只读查阅，Git 为限定同步例外：每轮首次访问仓库自动尝试 fetch 一次，可显式 fetch，每次尝试后 status；以当前分支 upstream 的前后提交比较更新，无 upstream / detached HEAD 则报告不确定，不猜分支或宣称最新。只开放受控 diff / show / fetch / log，不改工作区，版本来源明确；无通用终端、任意文件操作或设置 Default 权限。

Runtime Repair 保留 Stage 6 范围，不继承开发工具集，无删除工具和权限；人工交互仅有人监督 / 值守时开放，无人值守时不开放。值守状态及运行时接入细节留 Stage 6，不在本阶段修改 Working Manifest / Recheck 或运行时替换检查。

## 后果与验证

工具与开发者业务使用分批迭代，业务选择和验收由开发者承担。必须验证模式 / 入口权限、Session 持久化 / 中断 / 互斥、手工草稿保护、全局资源边界、双页模态 / 内存配置 / 版本确认安装；Windows 成品与实际模型 / 游戏另行记录。设计接受不等于实现完成。

完整契约见 [Stage 5 规格](../stage-5-agent-workbench.md)，源码差距见[影响审查](../stage-5-design-impact-review.md)，讨论决定见[记录](../stage-5-2026-10-31-decisions.md)。
