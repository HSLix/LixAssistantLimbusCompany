---
name: workflow-conventions
description: LALC Workflow 的共用编写规范。创建、修改或审查 Plan、Task Workflow、Subworkflow、Step、Recovery Rule 时读取，涵盖调用边界、恢复职责、完成证据和日志。
---
# Workflow 编写规范

- 遵守 Python Plan → TaskWorkflow → Subworkflow → Step 的调用边界；通过 ctx.call 调用 Component、ctx.action 调用应用注册的 Trusted Action，Recovery Rule 保持 detect/recover 契约。
- Plan 使用 execute(ctx)，不再接收 task_repetitions、settings 参数；配置和必要业务进度通过 ctx.run_state.task_repetitions / settings 共享。业务代码自行决定状态含义、更新时间与重调入口后的行为，修改立即共享，失败不回滚；普通调用参数仍是独立快照，不随 RunState 自动重算。框架 recovery_count 只读，不可自行清零。
- Plan／Workflow／Step 各自调度或执行失败可在本层入口修复后重新调用；不能依赖失败帧的局部变量或任意行续跑。非必要不修改调用约定，避免破坏仍在等待的调用者；这是编写建议，不是旧新签名一致的强制校验。
- 动作 Step 是一次局部尝试：重新观察并复查输入条件，适用才执行一次动作或一组固定动作，然后用 `-> None` 返回。入口失配直接零输入返回；不要用返回 False 会触发恢复的 `condition()` 表达普通失配。真正异常继续传播。纯观察 Step 可返回有实际用途的识别数据。
- 动作 Step 不轮询或承诺业务完成；Workflow 用新画面验收并决定后续动作。购买等不可安全重复的输入，未确认之前不能因分支重复命中而重放。变更旧接口前检查所有调用方。
- Task Workflow 负责完整分派；Subworkflow 默认有限编排，需要时可用有界循环。联网循环每轮都先处理确认的错误弹窗和正常过渡，再选业务或未知分支。通用等待和未知也是分支；同一分支允许连续执行三次，第四次仍命中则在执行前抛 ExecutionFailure；总预算不重置。局内战斗可保留有界循环，注明回合及动画不依赖网络，进出战斗的加载仍由外层处理。详见 [分派与等待](references/dispatch-and-wait.md)。
- 点击返回或固定等待结束不证明业务完成。完成证据可以是特征出现、可靠消失、OCR 或其他可靠状态，不限定必须使用某种识别方式。
- 先读 action_contracts 和已有 Component 签名，按实际参数与返回契约复用能力，避免重复实现；Action 参数不能直接套给签名不同的 Step 包装。
- 匹配保留完整返回结果。多个命中不自动失败、不视为无目标，也不要求全部动作；业务 Step 决定选择和动作，有歧义时用 ctx.log 记录 warning 语义及依据，不随意丢字段或认定完成。
- Plan 调用 Task 后记录逻辑名、当前／总循环次数及 status；失败记录原始 failure_code、failure_message，成功记录有意义的 output，不统一降为 unknown。普通 Task 失败仍可继续调度；取消和不可恢复环境故障向外传播，不吞掉或改写为普通失败。
- ctx.log(message) 可记录语义日志并附已有截图，不重新截图。Python 模块和关键函数使用简洁中文 docstring。
- 已发布 Manifest／源码及 Trusted Actions 不可修改。新增源码走专用创建工具，不自动登记未引用文件；不生成绕过 ctx 的文件操作、网络、子进程、顶层副作用或后台调用。
- 允许的轮询必须有明确边界；总预算不能被“仍在已知页面”重置，外层上限也约束不了尚未返回的 Step。动作 Step 不在内部重试业务输入。
- Recovery Rule 只处理独特特征确认的外部异常，不在每个正常轮询中遍历错误弹窗；规则只推进当前异常，有界等待后可交回，不需内部循环到整条异常链结束。编写或排查规则时读取 [references/recovery-rules.md](references/recovery-rules.md)。
- 循环检测状态前及时调用 observe.capture_screen 刷新截图，尤其注意循环内动作、等待或子流程返回后的状态变化；继续判断前重新截图，或回到会重新截图的循环顶部，不在旧帧上反复空检测。match_asset／match_feature／ocr 读取当前内存帧，不自动刷新；observe.wait 也不刷新。换帧后重新获取匹配、OCR 及派生状态，不沿用旧变量。未发生动作或等待的同轮纯条件分流可复用一帧，不必每个 if 都截图；同帧先用足够的匹配证据，再按需局部／全屏 OCR，避免无条件全屏 OCR。
- edit 的 oldText／newText 可直接使用中文，不需要手写 Unicode 转义。oldText 从最新读取的文件复制，选短且唯一的代码锚点；匹配失败先重读并修正，不重复提交同一错误文本。
- 选状态特征时先查询现有 Asset，优先复用标题、特色按钮等少量易识别且较少误判的特征，不凭共有 Confirm／Enter 或导航标志推断页面。允许根据多次现场证据逐步改进，不要求首次找齐或堆砌检测；TODO 记录待采集的情景和特征，不等于已实现保护。素材及只读识别试验见 `../asset-management/SKILL.md`，验证和试运行统一见 `../validation-and-trial/SKILL.md`。

## Component 类型示例

以下规则适用于普通 execute 关键字参数和 Task Workflow 返回注解；它们按源码中的类型表达式校验，不支持用自定义别名替代：

- 基本类型：`str`、`int`、`float`、`bool`、`None`。
- 递归容器：`list[str]`、`list[list[int]]`、`dict[str, int]`、`dict[str, list[dict[str, float]]]`；dict 键必须是 str。
- 可空类型：`str | None`、`list[int] | None`；这是受限的可空联合，不支持 `str | int`、`Optional[str]` 或 `Union[str, None]` 写法。
- 字面量：从 typing 导入 `Literal` 后可写 `Literal["team", "path"]`；Literal 的值限字符串、整数、浮点数、布尔值或 None。
- 不接受 `object`、`Any`、`dict[str, object]`、裸 `dict`／`list`、`dict[int, str]`、`tuple[int, int]`、TypedDict 或自定义类型。Plan 返回注解另允许 Any，但实际结果仍须为 JSON 数据；不要把该例外套给 Task 返回值或普通输入。

例如 Task 可写 `def execute(ctx: RunContext, *, names: list[str], limit: int | None = None) -> dict[str, list[str]]:`，返回 `{"names": names}`。嵌套 JSON 不需要转成字符串。

运行值也须符合注解：bool 不当作 int，int 可用于 float，浮点数必须有限；容器递归检查且 dict 键必须为字符串。Subworkflow／Step 的返回注解不套用上述 Task 白名单，但返回值仍按实际注解规范化；不要据此假设任意 Python 对象都可返回。

可交回 Step 的 completed 布尔值和 reason 字符串保持原类型，不为迁就 `dict[str, str]` 而字符串化，也不把这种异构返回约定直接套入 Task 的注解白名单。
