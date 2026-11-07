# wait 迁移为 observe：决定与影响审查

2026-11-07。开发者已确认 observe 的所有现有调用阶段均允许等待，并统一改名为 `observe.wait`，移除 `control.wait`，不保留兼容别名。开发者随后确认下述完整语义并授权实施；本文的源码检查与文末执行验证分别记录。

## 设计变化

- `control.wait` → `observe.wait`：等待不主动向游戏注入输入，但仍是应用登记的 Trusted Action，必须经 `ctx.action()` 调用。
- 沿用 observe 权限矩阵：Task Workflow、Subworkflow、Step execute/condition、Recovery Rule detect/recover 均可调用；Automation Plan 仍不得调用任何 Action。
- 保留 seconds 参数、返回 None、0–60 秒有限数值校验、输入会话检查、暂停、接管、取消及逐次 Trace。不新增条件等待或可配置权限。
- 沿用现有观察中断语义：Workflow 直接等待遭接管后，手动恢复时重做本次完整等待，保留 Python 调用栈且不重放已返回 Step；Step 内等待沿现有 Step 恢复边界处理，Rule 阶段不吞掉中断。普通协作暂停继续沿 Run Gate 处理，不统一改成重新计时。
- 旧 Manifest 不原地改写：旧名称将校验失败，须将源码导入 Candidate，改名后重新发布；旧 Trace 保留原名。

## 已确认的影响

下表保留实施前源码检查结果，所列差距已按文末记录修订。

| 位置 | 检查证据与所需修改 |
| --- | --- |
| `src/lalc/actions.py:wait/application_actions` | 当前登记为 control 且调用 `ctx.control_input("wait")`；需同步分类、名称和安全执行入口。 |
| `src/lalc/runtime.py:trusted_action/control_input`、`src/lalc/run_context.py:control_input` | 原生输入入口只接受 control。仅改登记会在执行期失败；应只为 observe 的 wait 操作开放既有会话转发，不能放开 observe 的 click/key/drag/restart。 |
| `src/lalc/manifest.py:_validate_action_calls`、`src/lalc/runtime.py:_ACTION_ACCESS` | 静态与执行期矩阵均按分类判断，可原样复用，不需按角色增加 wait 特例。Plan 没有 Action 权限。 |
| `src/lalc/control.py:InputSession.execute/_wait/_duration` | 已有等待分支与 0–60 秒校验，轮询输入和取消；继续复用，避免新增计时器或后端。 |
| `src/lalc/repair_tools.py:action_contracts`、`src/lalc/stubgen.py`、`src/lalc/run_context.pyi` | Agent 契约与类型提示由登记/源码派生；重新生成 stub，更新动作 docstring。无需新建 Agent 工具或修改 Core prompt。 |
| `example/workflow/`、`example/acceptance/wait.py`、`tests/fixtures/focused-control/` | 调用名称迁移；相应示例断言、Plan 拒绝测试、日志与类型测试一并更新。 |
| `docs/stage-2-workflow-and-execution-contract.md:18,85,245`、`docs/reconstruction-plan.md:84,88` | 明确将 wait 定义为 control，与本轮替代决定冲突；更新现行契约，并在 ADR 0023 追加本次分类修订入口。教程与当前状态同步说明用法和迁移。 |

## 潜在风险与验证

- observe 权限扩大后，恢复 detect/condition 可额外耗时；仍采用单次 60 秒上限，不新增总耗时预算。
- 旧已发布 Manifest 和外部源码可能使用旧名称；不建立自动迁移，也不声称已检查用户全部本地数据。
- 重点回归：所有允许阶段可校验并实际等待、Plan/旧名称拒绝、observe 无法注入控制输入、非法时长拒绝、接管恢复不重放前序 Step、取消结束等待、Trace 使用 observe 分类，以及示例/stub 同步。
- 本轮不需要真实模型调用；Windows 输入与真实游戏行为仍需对应环境验收。

## 实施顺序

确认完整语义 → 更新登记及受限后端入口 → 迁移调用与生成类型提示 → 更新契约/教程 → 串行执行相关默认测试并记录结果。该变更复用既有分类与恢复模型，不新增 ADR 或通用等待抽象。

## 实施与验证

2026-11-07 已完成：登记改为 `observe.wait`；执行器仅对 observe 的 `wait` 操作开放既有输入会话入口，其他控制操作仍被拒绝。没有改动分类权限矩阵、底层计时器或恢复流程。仓库示例、测试 fixture、类型声明、现行契约、教程和领域词汇同步更新；已发布资源和旧 Trace 未改写。

串行执行默认测试，未开启 Agent 接入测试：

```sh
QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest -q tests/test_observe_wait.py tests/test_input_control.py tests/test_manifest_transition.py tests/test_example_workflow.py tests/test_stubgen.py tests/test_python_plan.py tests/test_workflow_observability.py -k 'not test_exp_mirror_pages_feed_plan_and_shared_actions'
QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest -q tests/test_manifest.py tests/test_game_restart.py tests/test_windows_packaging.py
```

结果分别为 **137 passed, 2 deselected** 和 **50 passed**。新增测试经真实 Manifest 校验与应用会话替身执行，覆盖六个 observe 调用阶段、Trace 分类、observe 控制输入拒绝、非法时长、旧名称拒绝、Workflow 接管后完整重等且不重放前序 Step，以及等待取消。既有 Step 接管/取消、Plan Action 拒绝、类型生成与 Pyright 调用检查均通过。`git diff --check` 通过。

首轮包含全部七个相关文件的运行中，`test_exp_mirror_pages_feed_plan_and_shared_actions` 两个参数项失败：当前示例 Plan 只执行 mirror，而测试仍要求 exp 两次加 mirror 一次；失败分支还读取不存在的 `example/workflow/exp.py`。已核对 HEAD 中的示例 Manifest/Plan，以上差异在本轮改动前已存在；这两项未修改或计为通过，后续相关检查显式排除。新增测试首轮的测试对象/Trace 解析及取消结果断言问题已修正并重跑通过。

没有运行全量回归、真实模型、Windows 成品或真实游戏验收；本地打包测试不等于 Windows 成品验证。旧名称不兼容风险仍按已接受的迁移决定保留。
