---
name: workflow-conventions
description: LALC Workflow 的共用编写规范。创建、修改或审查 Plan、Task Workflow、Subworkflow、Step、Recovery Rule 时读取，涵盖调用边界、恢复职责、完成证据和日志。
---
# Workflow 编写规范

- 遵守 Python Plan → TaskWorkflow → Subworkflow → Step 的调用边界；通过 ctx.call 调用 Component、ctx.action 调用应用注册的 Trusted Action，Recovery Rule 保持 detect/recover 契约。
- Plan 使用 execute(ctx)，不再接收 task_repetitions、settings 参数；配置和必要业务进度通过 ctx.run_state.task_repetitions / settings 共享。业务代码自行决定状态含义、更新时间与重调入口后的行为，修改立即共享，失败不回滚；普通调用参数仍是独立快照，不随 RunState 自动重算。框架 recovery_count 只读，不可自行清零。
- Plan／Workflow／Step 各自调度或执行失败可在本层入口修复后重新调用；不能依赖失败帧的局部变量或任意行续跑。非必要不修改调用约定，避免破坏仍在等待的调用者；这是编写建议，不是旧新签名一致的强制校验。
- Step 按一个可独立恢复的局部业务目标划分，文件名及逻辑名反映职责；允许处理同一目标的动作前、过渡中和完成后状态，不按画面数量拆分。多个独立业务阶段由 Task Workflow／Subworkflow 编排。每次进入重新观察，先检测已知退出／完成信号，确认已完成则不重放动作，再检查是否仍适用输入；上层观察不能替代局部适用性检查。退出信号需先试跑才能获知时，按验证指导分阶段补齐，不编造信号。
- 通用基本动作 Step 参考一次短尝试：检查适用性→动作→短暂等待→重新检测退出／完成信号。动作后建议至少等待 1 秒，也可等 2 秒再检测；这是参考，不强制专门业务 Step 同形。首次生成不预加补点，后续有原动作可能无效的证据时再考虑安全补点；不能因暂未看到结果就认定输入未生效。
- 新建或本次改造的可交回动作 Step 返回 `{"completed": true/false, "reason": "说明"}`，completed 表示局部目标已确认达成，确有业务数据才加字段。入口不适用、未知或局部等待后仍未达成都显式交回；参数、工具等真正异常继续传播，不用宽泛捕获转换成未达成。观察／专用等待 Step 保留职责型返回，旧接口按需迁移并检查所有调用方，不把 None 自动当作未达成。购买等不可安全重复的输入，重入先确认已有操作结果，不因分派重试而重复消费。
- Task Workflow／Subworkflow 默认直接观察、判断和分派，使用多个条件分支；多个 Workflow 确实复用同一套场景分类，或需要独立验证该识别能力时，再考虑提取识别 Step，不预设每个 Workflow 都需单独的场景分类 Step。统一采用有界循环分流：每轮重新观察，处理一个分支后重新完整分派；记录 Step 情况，统一按目标是否达成维护连续无效计数，不为每种 reason 编写分支。无效初始上限 3 次，未耗尽时等待 1 秒再观察；确认局部目标达成才清零，已知页面本身不能清零。另设不随局部成功重置的总上限，任一预算耗尽抛 ExecutionFailure。需大量循环的单次 Task 用足够覆盖正常执行的稍大固定上限兜底，实际不足再增加；Subworkflow 按职责设定，不新增共享预算或配置。完整分派及过渡等待规则见 [references/dispatch-and-wait.md](references/dispatch-and-wait.md)，编写或修改这类流程时读取。
- Connecting／Combat Tips／Now Loading 等已确认的正常过渡在 Workflow 统一识别，交共用等待 Step 有界观察，不要求每个动作 Step 重复识别，也不依赖 Recovery Rule 处理正常加载。过渡不计无效、不清零；消失不证明业务完成。错误弹窗仍由恢复规则处理，黑屏、无 OCR 结果或未知页面不能当作加载；共用等待预算及超限后的重新观察见上述参考。控制动作仍由 Step 执行，基础观察／等待不冒充业务完成。
- 退出信号既可取状态转移后出现的新特征，也可取原状态可靠特征的消失，例如关闭弹窗后其独特标题不再出现。若局部目标就是离开该状态，可靠消失可确认完成；若目标要求到达特定页面或获取业务结果，仅消失可作为停止原动作、交回分派的依据，不能据此宣称该目标达成。限定适用范围并使用有效新截图，不把 OCR／截图错误、短暂遮挡或任意陌生页面中的未命中当作可靠消失，不强制堆叠多重检测。
- 点击返回或固定等待结束不证明业务完成。完成证据可以是特征出现、可靠消失、OCR 或其他可靠状态，不限定必须使用某种识别方式。
- 先读 action_contracts 和已有 Component 签名，按实际参数与返回契约复用能力，避免重复实现；Action 参数不能直接套给签名不同的 Step 包装。
- 匹配保留完整返回结果。多个命中不自动失败、不视为无目标，也不要求全部动作；业务 Step 决定选择和动作，有歧义时用 ctx.log 记录 warning 语义及依据，不随意丢字段或认定完成。
- Plan 调用 Task 后记录逻辑名、当前／总循环次数及 status；失败记录原始 failure_code、failure_message，成功记录有意义的 output，不统一降为 unknown。普通 Task 失败仍可继续调度；取消和不可恢复环境故障向外传播，不吞掉或改写为普通失败。
- ctx.log(message) 可记录语义日志并附已有截图，不重新截图。Python 模块和关键函数使用简洁中文 docstring。
- 已发布 Manifest／源码及 Trusted Actions 不可修改。新增源码走专用创建工具，不自动登记未引用文件；不生成绕过 ctx 的文件操作、网络、子进程、顶层副作用或后台调用。
- 重试／轮询使用 `for ... in range(...)` 等明确有界循环，不使用 while True；观察轮数、输入次数与总推进轮数含义不同，不统一套重试默认值。总预算不能被“仍在已知页面”重置，外层上限也约束不了尚未返回的 Step；专用业务 Step 内的循环同样有界，按真实职责说明交回与失败出口。
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
