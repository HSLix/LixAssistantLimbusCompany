## Problem Statement

开发者需要验证真实模型能否理解 LALC 的游戏截图、异常和 Component 源码，并在受限工具内产出可审阅、可发布的修复。目前没有真实模型驱动的独立修复闭环；仅有 Validator 通过不能证明游戏行为修复，平台替身也不能替代 Windows 实机证据。

目标是在 2026-10-29 前向 TA 交付 demo：开发者准备一个可复现的真实单 Component 缺陷，Agent 自主读取、修改和校验，人工审阅发布后在真实游戏中展示修复前失败、修复后成功。

## Solution

提供人工启动的独立 LALC 修复 CLI。LALC 从 Default Manifest 重建 Developer Candidate，优先通过 pi 子进程运行真实模型和受限工具循环。Agent 只修改指定 Component，可查看候选代码、Asset 和 Trusted Action 说明，通过专用工具查看当前游戏、从新截图裁剪新增 Asset，并复用现有 Validator 迭代。

所有输入、模型与工具交换及产物按一次调用留存。Agent 不点击或按键、不运行候选、不自动 Publish、不修改 Default；修复是否解决真实游戏问题由开发者人工验收。先在 Mac 验证模型与工具集成，再在 Windows 验证实时游戏工具、DPAPI 和最终 demo。

## User Stories

1. As a 开发者, I want 手工指定一个已有 Component 和问题描述, so that 修复目标清楚且不会扩展到多个 Component。
2. As a 开发者, I want 从 Default Manifest 固定本次源码基线, so that Agent 修改有可复现的来源。
3. As a 开发者, I want 在没有可用 Default 或目标不存在时收到明确错误且保留原草稿, so that 无效启动不会损坏工作。
4. As a 开发者, I want 有效启动时清空并重建 Developer Candidate, so that Agent 只看到本次基线的完整代码。
5. As a Agent, I want 按需读取全部候选文件, so that 我能理解调用方、被调用方和只读 Recovery Rules。
6. As a 开发者, I want Agent 只能改指定候选 Component, so that 其他源码、候选 Manifest 和正式发布物保持不变。
7. As a Agent, I want 获得问题描述、异常、预期行为、截图和 LALC 编写约束, so that 我能根据现有执行契约分析问题。
8. As a Agent, I want 查看全部 Asset 逻辑名的文字树, so that 我能发现可能需要的素材。
9. As a Agent, I want 查看一个完整逻辑名下的所有文件名和标签映射, so that 我能选择实际存在的模板。
10. As a Agent, I want 用逻辑名与完整哈希查看一张或多张实际图片, so that 我能比较素材而不是猜测文件内容。
11. As a Agent, I want 查看全部注册 Trusted Actions 的分类、签名与说明, so that 我能使用既有接口而不直接调用底层实现。
12. As a Agent, I want 获取当前游戏客户区的新截图, so that 我能补充启动时材料之外的实时观察。
13. As a Agent, I want 从一次新截图裁剪并保存 Asset, so that 缺少模板时能够补充修复所需素材。
14. As a 开发者, I want 重复裁剪复用同名同哈希的原图和原标签, so that Agent 不会覆盖已有素材配置。
15. As a 开发者, I want 新增 Asset 无需 Publish 即可被读取和匹配, so that 修复沿用共享 Asset Library 的现行规则。
16. As a Agent, I want 调用现有 Validator 并读取原始反馈, so that 我能继续修订不符合契约的源码。
17. As a 开发者, I want 最终源码再次校验并输出完整候选与 Diff, so that 人工可以审阅真正提交的版本。
18. As a 开发者, I want 设置服务地址、模型和 API key, so that 我能连接另一台设备上的 llama.cpp 服务。
19. As a 开发者, I want 启动前确认指定模型可以实际接收图片, so that 截图不会被静默丢弃。
20. As a 开发者, I want 一次修复保持指定服务和模型且不自动回退, so that 调用结果和成本来源可以解释。
21. As a 开发者, I want 默认 20 次的模型请求上限可持久设置或单次覆盖, so that 重复修复有一致且可控的边界。
22. As a Windows 用户, I want 以 DPAPI 保存命名密钥并与普通设置分离, so that 模型 API key 和未来其他密钥共用同一安全存储边界。
23. As a Mac 开发者, I want 临时输入密钥而不持久化, so that 我能先验证本地接入而不依赖 Windows。
24. As a 开发者, I want 取消、超限和模型错误后停止并保留已有产物, so that 我能检查部分工作而不会自动重启修复。
25. As a 开发者, I want 信息不足时 Agent 给出缺少内容的最终回答后结束, so that 我能补齐材料而不依赖交互追问或会话续接。
26. As a 开发者, I want 在数据目录按日期和 UUID4 查看完整交互记录, so that 下次重建候选时仍能复盘前次修复。
27. As a 开发者, I want 日志包含真实模型输入、图片、回复、工具结果、最终产物、有效配置和请求次数而不含密钥, so that 诊断与验收有可信证据。
28. As a TA, I want 看到真实模型修复记录及人工游戏前后对照, so that 我能区分工具可运行、契约校验通过和行为真正修复。

## Implementation Decisions

- 范围遵循 ADR 0025，并按 ADR 0028 修订源码工作区、实时截图和 Agent Asset 新增权限；Runtime Agent Recovery 与 Working Manifest 衔接仍属 Stage 3.5。
- 首选 pi，由 LALC Python CLI 通过 RPC 启动子进程，以专用扩展提供工具，不重写模型与工具循环。最小接入实验先验证本机 pi 的图片、工具、事件、认证传递和中止能力，再固定同一版本用于 Mac 和 Windows；本机版本能够启动不等于这些能力已经通过。
- 一次修复只处理一个已有 Task Workflow、Subworkflow 或 Step。固定启动时的 Default Manifest 与原始字节；先确认来源和目标可用，再清空或新建 Developer Candidate。没有 Default、不合法或无法加载、目标缺失时明确报错，不清空草稿，不改选其他历史版本。有效启动会替换未发布草稿，这是已确认的取舍。
- 代码读取仅限本次 Developer Candidate，允许查看全部候选文件；写入只限指定 Component。候选 Manifest、其他源码和正式发布物不可改。框架自带终端、通用文件写入和未授权工具不暴露给模型，读取和写入边界由工具实现检查，不仅依赖提示词。预置模型上下文应提供 LALC 编写与权限约束。
- 三个 Asset 只读工具分别返回全局逻辑名文字树、指定完整逻辑名的全部文件名与标签文件内容、按完整逻辑名和完整哈希选取的一张或多张实际图片。缺失标签如实报告并沿用空标签语义。复用现有逻辑名、库内路径和哈希校验，不提供任意文件读取能力。
- 一个 Trusted Action 只读工具返回应用实际注册的全部动作及 observe/control 分类、参数/返回类型和 docstring。内容由注册表与源码签名派生，不维护第二份手写接口说明，不暴露动作实现或通用执行能力。
- 两个专用游戏工具分别取得当前客户区新截图、从重新取得的截图现场裁剪新增 Asset。复用现有唯一窗口、焦点、像素坐标、区域和图片检查。返回实际图片、尺寸或哈希与标签，并保留真实来源；不从保存截图裁剪，不以旧图充当当前画面。Mac 不具备该真实能力时明确报告不可用。
- Agent 裁剪同逻辑名同哈希时直接复用原图和原标签，明确报告已存在；请求中的不同标签不能覆盖旧标签。新哈希可新增标签条目，未提供标签明确存空列表，并保留其他条目。开发者裁剪和标签工具仍按 ADR 0027 整体替换标签。新图片无需 Manifest 映射或 Publish，调用失败、取消或人工拒绝均不触发删除。
- 模型连接由 LALC 管理完整服务地址、模型标识和所需密钥，首个目标为远程 llama.cpp。普通本地配置持久化地址、模型和请求上限，默认上限 20；单次覆盖不修改已保存值，每次调用固定并记录实际配置。图片能力既检查服务信息，也通过实际图片请求验证；不能只相信配置中的能力标记。区分不可达、认证失败、模型未加载和图片不支持，不自动换模型或供应商。
- 命名密钥存储与普通设置分离。Windows 使用 DPAPI；Mac 首版只接受运行时临时输入、不持久化。认证只供模型客户端使用，不进入提示、Agent 可读文件、交互日志、命令行明文参数或 pi 的明文持久配置；具体向子进程传递的方法由最小接入实验验证。未来其他密钥复用该边界，不预建未来业务功能。
- 模型主动结束后，LALC 对最终版本再执行现有 Validator。通过只表示候选符合执行契约，不代表修复成功。信息不足时 Agent 最终回答说明缺少内容，然后结束并标记未完成；不提供交互追问。超限、取消或模型错误停止，不自动重启；保留已有候选、日志和结束原因。
- 每次调用对应一个 UUID4 的 Agent Interaction Log，存入本地数据目录、按日期分组，单独记录精确时间。记录真实提示/上下文/截图、逐次模型请求和回复、工具参数与结果或异常、最终候选和 Diff、全部校验反馈、模型及 SDK 标识、有效非密钥配置、实际请求次数和结束原因。原始源码、图片和最终产物独立保留，不依赖下一次会被清空的 Developer Candidate；不为日志创建 Workflow Run。
- Validator 仍会导入候选 Python。这是现有可信代码验证路径，不是纯静态分析或操作系统沙箱；本阶段不承诺阻止任意 Python 副作用。正式候选试跑、Publish 和真实游戏行为确认均由人工另行发起。

## Testing Decisions

- 统一以独立修复 CLI 的公开行为为最高验收入口，复用实际 ManifestManager、Validator 和现有窗口/Asset 服务；只替换模型传输或平台交互等外部边界，不增加测试专用执行器。
- 自动化检查观察输入输出、工具结果和持久产物：无 Default 时不清空草稿；有效启动正确物化；只能改指定源码；越界路径和工具访问被拒绝；原 Manifest、正式源码、原图、旧哈希标签和 Default 不变。
- 覆盖正常候选、真实校验失败后再修订、最终校验失败、持久设置与单次覆盖、请求上限、信息不足、模型失败和取消；核对保留的最终内容、请求次数及结束原因，不只检查模型自述。
- Asset 工具验证真实返回多图、标签缺失、逻辑名/哈希错误、首次新增、重复裁剪复用且原标签不变、新条目不改旧条目。窗口替身只证明工具契约与边界，不证明真实游戏行为。
- 日志测试使用可识别的测试密钥，检查配置、候选、模型上下文、日志及异常输出无泄露；检查后续重建候选不丢前次日志与图片。Windows 需要真实 DPAPI 存储/解密的独立实测，Mac 替身不能代替。
- 参考现有 CLI、Manifest、开发者 Asset、窗口观察和取消测试的公开行为写法，不复刻工具内部实现，不实现游戏状态模拟。
- Mac 真模型验收必须经 pi 完成图片输入、工具调用、单文件修订和 Validator 反馈并留存完整交互；替身测试不替代真实模型证据。
- Windows 验收真实截图、现场裁剪、重复图片与旧标签保护、DPAPI 及同一固定 pi 版本。开发者准备真实缺陷并完成前后游戏对照；只修语法、Validator 通过或替身成功均不算最终 demo 完成。

## Out of Scope

- 运行中 Working Manifest 发现与接入、Runtime Agent Session、自动异常接管、暂停 Step 续接、自动候选试跑、游戏点击/按键及多 Component 修改。
- Agent 修改已有图片/旧标签、任意素材导入、修改 Trusted Actions 或 Recovery Rules、创建新 Component、自动 Publish 或设置 Default。
- 交互追问、跨调用恢复、供应商/模型自动回退、操作系统安全沙箱、游戏状态模拟。
- 密钥跨机迁移、Mac 持久密钥后端、未来密钥业务接入、数据库、日志搜索/管理界面、资源自动清理。
- GUI、完整应用打包、邮箱 Workflow 和延期 Windows 集成清单的整体完成。

## Further Notes

关联既有 Stage 3 跟踪 #312。当前 Spec 记录此次已确认范围，不关闭或修改该阶段跟踪；后续实施按经确认的垂直步骤发布。

截止目标是 2026-10-29 前交付 TA；建议 10 月 28 日完成证据与演示材料，预留一天处理交付。具体缺陷由开发者选择，尽早准备但不阻塞工具边界与接入实验。

尚未完成：真实模型、pi RPC/扩展、图片通道、受限工具、模型请求统计与取消、密钥运行时传递、Windows DPAPI 及真实游戏验收。已有主机版本检查和文档检查不冒充这些验收。
