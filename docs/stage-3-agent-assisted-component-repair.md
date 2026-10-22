# Stage 3 — Agent-assisted Component Repair

Status: accepted scope under [ADR 0025](adr/0025-validate-component-repair-before-runtime-agent-recovery.md); implementation and model-backed acceptance remain to be completed.

Tracking: [GitHub Issue #312](https://github.com/HSLix/LixAssistantLimbusCompany/issues/312).
本阶段以尽快验证 Agent 自主修复已有 Component 的可行性为核心。通过独立 CLI 手动启动一次修复，提供已有 Component、游戏截图、异常信息与必要上下文；Agent 使用 Deep Agents 或类似 SDK 阅读源码、分析问题、执行局部修改，并调用现有 Validator，根据反馈继续调整。无需先实现 Runtime Agent Session、自动异常接管或运行时恢复。

## Input and repair boundary

- 明确选择已有 Component 的逻辑名及其来源 Manifest / 源码版本，保留原始字节和缺陷种子，使每次评估可以从相同版本开始。
- 输入包括人工提供的游戏截图、异常信息（可含 traceback / Trace）及复现步骤、预期行为等必要上下文。截图是诊断材料，CLI 不要求连接游戏或重建暂停的 Python 调用栈。
- 首版只修改一个已有 Task Workflow、Subworkflow 或 Step 的完整源文件；可只读查看相关源码、现有 Asset、应用注册的 Trusted Actions 及签名/docstring。Trusted Action、Recovery Rule 的修改、新 Component、新增或修改 Asset、多组件编辑均不在本阶段范围。
- 使用隔离的修复工作区保留候选修改，不覆盖正式 Component、已有 Manifest、Asset Library 或 Asset 文件，也不覆盖用户现有 Developer Candidate 的未发布修改。完整候选 Manifest 的其余映射和 Asset Library 保持基线内容，用于现有校验路径。
- SDK 负责一次 CLI 调用中的源码阅读、局部编辑及工具循环；不套用 Runtime Agent Session 的三种 Turn 结果、暂停 Step 续接和 `max_turns` 协议。SDK 选型、具体命令参数与日志格式由最小实现实验确定。

## Validation and outputs

- 每次候选修改复用 `ManifestManager.validate()` / 现有 Validator 检查完整候选 Manifest，并把实际校验反馈交回 Agent；校验失败不冒充修复成功，可以继续修改。
- 校验不发布、不分配 Manifest ID、不切换 Working Manifest 或 Default Manifest。当前校验会导入候选 Python，不能把它描述为纯静态分析或安全沙箱；校验本身不构成游戏行为验证。
- 最终输出完整候选 Component 源码、相对原始版本的 Diff，以及实际验证结果。未通过校验、模型失败或中断时保留已有诊断与候选内容，明确说明未完成。
- 后续人工审阅并通过既有 Developer Candidate / `ManifestManager.publish()` 路径发布完整 Manifest；Agent CLI 不自动 Publish，也不修改 Default Manifest。设置 Default 仍是另一次显式开发者操作。

## One-call logging

一次 CLI 调用必须保留可关联的模型输入、工具操作和最终输出日志：

- 实际发送的系统提示、上下文、截图内容或可持久访问的截图引用，以及每次模型请求/响应；多轮修订属于同一次 CLI 调用。
- 工具名称、参数、返回结果或异常，源码读取/修改、Diff 和每次 Validator 的反馈，按发生顺序记录。
- 最终候选源码、Diff、验证结果与完成/失败/中断状态，并保留模型/SDK 标识和必要配置以解释本次结果；不记录认证密钥。

该日志复用 Agent Interaction Log 的诊断目的，但不要求建立 Workflow Run、Execution Trace 或 Runtime Agent Session。

## Acceptance

1. 保留至少一个可重复失败的已有 Component 原始版本、截图/异常、输入、复现步骤及预期行为；重复评估不覆盖缺陷种子。
2. 通过一次独立 CLI 调用，让真实模型读取源码、执行单文件修复并调用现有 Validator，产出完整源码、Diff、验证结果和完整调用日志；替身测试不能替代这一证据。
3. 人工审阅候选，复用现有发布和运行方式，在可复现条件下验证修复后的 Component 解决原问题，保存修复前失败与修复后成功的对照证据。涉及游戏交互时由人工另行发起实机验收；Agent CLI 不自动实机试运行。
4. 检查正式源码、已有 Manifest、Asset Library、Asset 和 Default 选择未被修复调用改变，候选仅包含指定 Component 的源码差异。

## Deferred to Stage 3.5

完整 Runtime Agent Recovery、自动异常接管、Runtime Agent Session / Adapter / Context Builder 协调、监督运行与运行时审批、完整 Working Manifest 试运行和暂停 Step 续接、Agent Asset 创建与图像检查交互、多组件编辑及相关能力演进，见 [Stage 3.5](stage-3.5-agent-runtime-step-recovery-and-maintenance.md)。完整依赖/反向查询分析和 Stagehand 研究也保留在该阶段，不作为首个修复案例的前置条件。新增目标的 Workflow Drafting、自主 Capability Expansion 与 Unattended Operation 仍无本次交付承诺。
