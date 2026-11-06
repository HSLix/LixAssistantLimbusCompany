---
name: workflow-conventions
description: LALC Workflow 的共用编写规范。创建、修改或审查 Plan、Task Workflow、Subworkflow、Step、Recovery Rule 时读取，涵盖调用边界、恢复职责、完成证据和日志。
---
# Workflow 编写规范

- 遵守 Python Plan → TaskWorkflow → Subworkflow → Step 的调用边界；通过 ctx.call 调用 Component、ctx.action 调用应用注册的 Trusted Action，Recovery Rule 保持 detect/recover 契约。
- Step 承担自身职责的状态识别、动作、完成确认及业务异常；恢复时重新观察，已完成则直接返回，不重放已完成动作。预期过渡继续观察，未知或停滞按证据抛出 ExecutionFailure。
- Task Workflow／Subworkflow 只负责排布、参数传递及根据 Step 结果分支、循环、汇总；游戏状态识别和业务成功判断放在 Step 中，以便恢复时重新判断。观察、等待等基础 Step 只确认自身职责，不冒充业务完成。
- 点击返回或固定等待结束不证明业务完成。完成证据可以是模板、OCR 或其他可靠状态，不限定必须使用某种识别方式。
- 先读 action_contracts 和已有 Component 签名，按实际参数与返回契约复用能力，避免重复实现；Action 参数不能直接套给签名不同的 Step 包装。
- 匹配保留完整返回结果。多个命中不自动失败、不视为无目标，也不要求全部动作；业务 Step 决定选择和动作，有歧义时用 ctx.log 记录 warning 语义及依据，不随意丢字段或认定完成。
- Plan 调用 Task 后记录逻辑名、当前／总循环次数及 status；失败记录原始 failure_code、failure_message，成功记录有意义的 output，不统一降为 unknown。普通 Task 失败仍可继续调度；取消和不可恢复环境故障向外传播，不吞掉或改写为普通失败。
- ctx.log(message, screenshot=False) 可记录语义日志并附已有截图，不重新截图。Python 模块和关键函数使用简洁中文 docstring。
- 已发布 Manifest／源码及 Trusted Actions 不可修改。新增源码走专用创建工具，不自动登记未引用文件；不生成绕过 ctx 的文件操作、网络、子进程、顶层副作用或后台调用。
