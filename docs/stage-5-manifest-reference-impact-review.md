# Stage 5 — 已发布 Manifest 参考的专项影响审查

#336 本轮补充见[专项审查](stage-5-336-design-impact-review.md)：删除 Developer GUI 人工运行选择，保留 Agent 试运行；下文提到 Selected 的不变性检查不再要求保留该界面状态，其余只读边界保持。

2026-10-31，依据[已确认讨论](stage-5-manifest-reference-decisions.md)和[完整规格](stage-5-agent-workbench.md#已发布-manifest-参考附件与只读查看)。本次审查读取实际 GUI 附件 → Agent 消息 / 日志 → Session 恢复、Python / TypeScript 工具及 Manifest 源码加载路径与相关测试，随后按用户授权同步本地文档，再更新 #336。只修改文档和 issue，不修改产品源码或测试，不执行产品回归、真实 pi / 模型、Windows 或游戏。

## 设计变化

| 旧范围 / 讨论 | 已确认的新增或替代 |
| --- | --- |
| 附件仅图片；其他 Manifest 主要用于初始化 / 试运行 | GUI 附件可多选已发布 Manifest；全部 / 部分参考重点写在聊天消息，不做 Component 树形勾选 |
| 曾讨论仅附加版本可查看 | 明确放弃附件授权清单：GUI Construct / Repair、CLI Repair 均可只读查看任意已发布 Manifest，无须先附加 |
| 参考授权按轮 / Session 登记 | 附件只是消息上下文，随聊天保存 / 恢复，不另建授权登记或撤销机制，不自动注入全部源码 |
| Runtime 是否使用尚未确认 | 已明确纳入 Runtime Repair 白名单，不受值守状态限制；Stage 6 实际接入，不由 Stage 5 提前实现 Runtime 恢复 |

不新增执行、任意文件访问、自动复制落盘、编辑或删除参考源码的工具权限。查看不切换 Candidate / 固定基线、Selected、Default 或 Working Manifest；已有 publish / trial_run 仍是独立能力。外部知识库及 Git 不在本增量内，#337 的范围和依赖不变。

## 已确认的代码差距

### 1. 图片附件路径不能承载 Manifest 提示

证据：`src/lalc/developer_gui.py:RepairPage.attach_image / clear_image / send` 维护图片路径列表；`src/lalc/agent_repair.py:image_attachments` 读取文件并解码为图片，`RepairConversation.run` 把这些内容放进 images 和附件留存。`tests/test_image_attachments.py:test_non_image_and_corrupt_image_are_errors` 明确要求非图片报错。

影响：Manifest 应作为版本引用信息进入当前用户消息 / 日志，而不是伪装成图片路径或把整个源码包塞进图片附件。GUI 可共享附件入口，但保留图片原样、多图片及文本独立可发送的能力；发送前选取不改 Candidate 来源。Manifest ID、自然语言重点及图片应在同一用户请求中清楚呈现。

### 2. Agent 没有跨已发布版本内容查看工具

证据：`src/lalc/repair_tools.py:REPAIR_TOOLS / RepairTools.call` 提供资产、动作契约、发布、试运行和 Run 日志；`src/lalc/pi_probe.ts:checkedPath / read / checkedEdit / repairTools` 把原生文件读取限定在当前根目录，注册清单无已发布 Manifest 索引 / 登记源码查看。`SYSTEM_PROMPT` 也仍说明只读取 Candidate 已有文件。`trial_run` 读取版本用于执行，不能当作内容查看。

影响：需要专用共享只读能力，模式 / 入口声明和实际分发一并接入 GUI 两种模式及 CLI Repair。不能把普通 read 根目录直接扩大到整个数据目录，不能把“任意已发布 Manifest”扩大为“任意数据文件”或提供全局 edit。不存在按附件过滤读权限的要求，不应新增 Session ACL 或授权缓存。

### 3. 现有 Manifest 执行加载会运行 Python

证据：`src/lalc/manifest.py:ManifestManager.load` 调用 `_prepare` 后调用 `_load`；`_load` 逐个 `_load_module`，最终执行 `exec(compile(source.content, ...))`。因此即使不调用 execute，直接 load 也不符合“查看不执行源码”。`list_manifests` 只读索引且不导入，可复用其列举用途；`_stored_source` 已有 Component ID 格式与内容哈希验证，可复用相同校验规则，不能为了只读查看调用整个执行加载器。

影响：按明确的 Manifest ID 读取结构，再按分区 / 逻辑名定位其中登记的 Component ID、核验源码字节身份与路径。返回源码及可定位来源，不导入模块。不能只因索引列出某版本就宣称它全部有效；未知版本、缺失成员、损坏源码等返回实际错误，不替换为 Default 或最新版本。共享同一 Component ID 的情况不要求复制源码，定位仍保留所查询 Manifest 的成员关系。

### 4. Session 已能保存消息，但未覆盖参考引用

证据：当前 `src/lalc/developer_session.py:restored_history / restore` 按 session_message 和实际工具事件恢复上下文；`RepairConversation.append_user / run` 保存当前消息，CLI 入口通过 DeveloperSession 继续 Repair。`tests/test_developer_session.py` 覆盖草稿隔离、中断和协议恢复，`tests/test_image_attachments.py` 覆盖图片附件，尚不等于 Manifest 引用与该新工具已实现。

影响：复用消息和工具结果留存，不需要另建参考授权表；确保消息中的 Manifest ID 和参考重点在 GUI / CLI 续聊、重启恢复后仍存在。已查看源码及工具输出沿用自包含 Agent Interaction Log 和脱敏，不让恢复时静默读取另一个版本替换原证据。后续源数据不可用时保留历史引用并在新工具调用中如实报错，不将旧消息改写为成功。

## 潜在风险及验证方式

- **路径与成员身份绕过**：若工具接受裸路径或裸 Component ID 并跳过所属 Manifest 检查，可能越过已发布版本边界。用未知 ID、路径穿越、符号链接、未登记成员、哈希不符及同名不同版本用例核验；输出明确来源。
- **隐藏导入副作用**：辅助校验可能间接调用 load / validate 并导入源码。用禁止模块加载的检查确认纯读路径仍能返回内容；核对调用链，不能仅断言“未调用 execute”。
- **提示与执行目标混淆**：附件选择、创建来源、全局 Selected 可能复用相似选择控件。对附加、查看前后的 Candidate 字节、基线与选择状态做不变性检查，工具不得创建 Run 或切换 Working Manifest。
- **超大输出**：任意已发布版本数量 / 源码可能很大。按需读取、明确截断及可继续定位即可，不为此建设复杂检索、源码复制或新索引。
- **Runtime 权限混用**：该只读能力已明确授权，不受值守状态限制；人工请求仍仅有人值守开放，删除仍禁止。Stage 6 接入时分别测工具可见性及实际拒绝边界，不把一个只读授权扩为开发工具全集。

## 文档同步与落票

已同步：完整 Stage 5 规格的参考章节及权限矩阵、ADR 0034 的取舍、CONTEXT 的 Manifest Reference Attachment 术语、讨论收口、Stage 6 明确白名单、Developer GUI / Repair 指南、领域导航、路线图及 #336 本地实施拆分。旧 ADR 0033 日志存储协议不改，#335 已有本地实现不因此被重写为包含此工具。

#336 增加完整路径：GUI 多 Manifest 参考附件 → 消息 / Session 恢复 → GUI / CLI 共享已发布内容只读工具 → 版本 / 成员 / 哈希 / 路径与不执行 / 不改变选择的验收。Stage 6 只记录 Runtime 接入承诺，不把运行时实现加入 #336，也不增票或改依赖。

本地文档检查通过后再更新 GitHub 正文，保留原 #336 验收条目、标签和 #335 原生阻塞边，回读核验最终正文。实际测试留实现时执行：普通元数据 / 路径 / 内容 / 无导入和恢复检查不启动 Agent；真实 pi / 工具循环测试标记 agent 并按相关文件显式选择，不把默认跳过计为通过。

## 同步与远端核验结果

本地同步先于 issue 更新完成；13 份相关文档的 119 个本地链接及锚点、差异空白检查通过。随后更新 [#336](https://github.com/HSLix/LixAssistantLimbusCompany/issues/336) 正文，增加七条验收要求；回读确认正文完全匹配，原标题、状态、标签及 #335 原生阻塞边保持不变。未更新其他 issue，未运行产品测试；代码差距仍待 #336 实现。
