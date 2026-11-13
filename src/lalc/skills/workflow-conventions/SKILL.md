---
name: workflow-conventions
description: LALC Workflow 的共用编写规范。创建、修改或审查 Plan、Task Workflow、Subworkflow、Step、Recovery Rule 时读取，涵盖调用边界、恢复职责、完成证据和日志。
---
# Workflow 编写规范

- 遵守 Python Plan → TaskWorkflow → Subworkflow → Step 的调用边界；通过 ctx.call 调用 Component、ctx.action 调用应用注册的 Trusted Action，Recovery Rule 保持 detect/recover 契约。
- Plan 使用 execute(ctx)，不再接收 task_repetitions、settings 参数；配置和必要业务进度通过 ctx.run_state.task_repetitions / settings 共享。业务代码自行决定状态含义、更新时间与重调入口后的行为，修改立即共享，失败不回滚；普通调用参数仍是独立快照，不随 RunState 自动重算。框架 recovery_count 只读，不可自行清零。
- Plan／Workflow／Step 各自调度或执行失败可在本层入口修复后重新调用；不能依赖失败帧的局部变量或任意行续跑。非必要不修改调用约定，避免破坏仍在等待的调用者；这是编写建议，不是旧新签名一致的强制校验。
- Step 承担自身职责的状态识别、动作、完成确认及业务异常；恢复时重新观察，已完成则直接返回，不重放已完成动作。预期过渡继续观察，未知或停滞按证据抛出 ExecutionFailure。
- Step 的文件名、逻辑名应该与内容相符。对于一个 Step 承担了多个状态的场景，应该把 Step 切分出多个 Step。
- Task Workflow／Subworkflow 负责排布、参数传递、分支、循环和汇总，也可通过 observe 动作观测、确认当前状态，再决定是否进入子步骤。控制动作仍由 Step 执行；上层检查不能替代 Step 在恢复重调时重新观察和确认自身职责。观察、等待等基础 Step 只确认自身职责，不冒充业务完成。
- 点击返回或固定等待结束不证明业务完成。完成证据可以是模板、OCR 或其他可靠状态，不限定必须使用某种识别方式。
- 先读 action_contracts 和已有 Component 签名，按实际参数与返回契约复用能力，避免重复实现；Action 参数不能直接套给签名不同的 Step 包装。
- 匹配保留完整返回结果。多个命中不自动失败、不视为无目标，也不要求全部动作；业务 Step 决定选择和动作，有歧义时用 ctx.log 记录 warning 语义及依据，不随意丢字段或认定完成。
- Plan 调用 Task 后记录逻辑名、当前／总循环次数及 status；失败记录原始 failure_code、failure_message，成功记录有意义的 output，不统一降为 unknown。普通 Task 失败仍可继续调度；取消和不可恢复环境故障向外传播，不吞掉或改写为普通失败。
- ctx.log(message) 可记录语义日志并附已有截图，不重新截图。Python 模块和关键函数使用简洁中文 docstring。
- 已发布 Manifest／源码及 Trusted Actions 不可修改。新增源码走专用创建工具，不自动登记未引用文件；不生成绕过 ctx 的文件操作、网络、子进程、顶层副作用或后台调用。
- 对于 Step 内的操作，等待状态变化必须有明确超时或重试次数限制；通常十秒左右到十几秒即可，更长等待应有实际加载或网络耗时依据。流程专注正常状态推进，超时后抛出 ExecutionFailure，由 Recovery Rule 识别和处理错误；不要求每次轮询都检测错误弹窗。
- Workflow 和 Recovery Rule 的重试、轮询禁止使用 while True，即使内部有超时或 break 也不例外；统一使用 for ... in range(MAX_RETRIES) 这样的有界循环。MAX_RETRIES 初始设为 10，只有实际运行发现次数不足时再按证据增加；耗尽后明确报告失败，不以循环结束冒充成功。
- 同一截图优先使用足以判定状态的模板匹配，需要文字时再按需做局部或全屏 OCR，避免每轮无条件全屏 OCR；点击后重新截图，不复用旧帧识别结果。
- edit 的 oldText／newText 可直接使用中文，不需要手写 Unicode 转义。oldText 从最新读取的文件复制，选短且唯一的代码锚点；匹配失败先重读并修正，不重复提交同一错误文本。

## Component 类型示例

以下规则适用于普通 execute 关键字参数和 Task Workflow 返回注解；它们按源码中的类型表达式校验，不支持用自定义别名替代：

- 基本类型：`str`、`int`、`float`、`bool`、`None`。
- 递归容器：`list[str]`、`list[list[int]]`、`dict[str, int]`、`dict[str, list[dict[str, float]]]`；dict 键必须是 str。
- 可空类型：`str | None`、`list[int] | None`；这是受限的可空联合，不支持 `str | int`、`Optional[str]` 或 `Union[str, None]` 写法。
- 字面量：从 typing 导入 `Literal` 后可写 `Literal["team", "path"]`；Literal 的值限字符串、整数、浮点数、布尔值或 None。
- 不接受 `object`、`Any`、`dict[str, object]`、裸 `dict`／`list`、`dict[int, str]`、`tuple[int, int]`、TypedDict 或自定义类型。Plan 返回注解另允许 Any，但实际结果仍须为 JSON 数据；不要把该例外套给 Task 返回值或普通输入。

例如 Task 可写 `def execute(ctx: RunContext, *, names: list[str], limit: int | None = None) -> dict[str, list[str]]:`，返回 `{"names": names}`。嵌套 JSON 不需要转成字符串。

运行值也须符合注解：bool 不当作 int，int 可用于 float，浮点数必须有限；容器递归检查且 dict 键必须为字符串。Subworkflow／Step 的返回注解不套用上述 Task 白名单，但返回值仍按实际注解规范化；不要据此假设任意 Python 对象都可返回。
