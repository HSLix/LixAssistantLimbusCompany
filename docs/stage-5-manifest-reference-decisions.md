# Stage 5 — 已发布 Manifest 参考附件

#336 本轮决定删除 Developer GUI 人工运行选择，Agent 试运行保留；见[实施前决定](stage-5-336-decisions.md)。下文提到 Developer Selected Manifest 仅为此前的状态隔离要求，不代表继续实现该入口。

状态：2026-10-31 grill 各项已确认，包含开发者最后明确的 Runtime Repair 白名单授权；按原请求进入专项影响审查、同步本地文档，再更新 #336。不表示产品已实现。

## 已确认

- Developer GUI 的 Agent 附件可指定其他已发布 Manifest，要求参考全部内容或其中部分内容。
- 2026-10-31 最终修订：Manifest 附件仅是留在聊天上下文的参考提示，不是访问授权清单；可以提示参考整个版本或其中部分内容。只读工具可自行查看任意已发布 Manifest，不要求先附加。该规则替代本轮早先“只允许访问已附加 Manifest”的决定，不建设附件授权登记或逐 Manifest 权限管理。
- 参考信息作为消息内容随 Session 上下文保留并恢复，不另建按轮授权或撤销机制；附件不要求把整个版本源码一次性注入上下文。
- GUI Construct / Repair 及 CLI Repair 均提供任意已发布 Manifest 的只读工具，复用底层实现；参考附件选择界面仅 GUI 提供。Runtime Repair 已明确获准使用任意已发布 Manifest 内容只读工具，不受值守状态限制；实际接入留 Stage 6，不整体继承其他开发工具。
- GUI 附件可选择一个或多个已发布 Manifest，部分内容的参考重点直接写在聊天消息里，例如某版本的指定 Workflow 或 Recovery Rules。首版不提供逐 Component 的树形勾选界面，也不把自然语言参考重点解释成访问范围限制。
- 参考附件不授予执行权限；不得用参考选择改变当前 Session Candidate、固定基线、Developer Selected Manifest 或 Default。

## 收口与审查输入

附件为上下文提示、工具不以附件限权、GUI / CLI / Runtime 只读能力范围及简化附件交互已逐项确认。专项审查检查版本 / 来源定位、按需读取、失效反馈及恢复记录的影响。

只读查看应按已发布 Manifest 及其登记 Component 定位源码，不通过工具读取任意文件，不导入或执行参考源码；这属于只读要求的实现边界，审查时追踪实际加载路径，不能以现有执行加载器直接替代。

本地正式规格和 ADR 已同步；专项审查见[记录](stage-5-manifest-reference-impact-review.md)。工具名、参数及输出分页等可在保持上述边界下实施时细化，已更新 [#336](https://github.com/HSLix/LixAssistantLimbusCompany/issues/336)，新增七条验收要求，回读确认原标签及 #335 原生阻塞边保持。
