# #331 — Python Plan 与双窗口执行闭环

2026-10-27：本轮关键决策、影响评审均获开发者确认，随后完成本地实现。开发者随后明确同意以自动化验证通过先行关闭 #331，真实使用测试以后再做；GitHub 已关闭为 completed。本记录不表示代码已提交或 Windows 成品已验收。#332 外置业务页面/共享 Agent 配置、#333 双语/信息面板、#334 Windows 打包现场验收仍独立待办。

2026-10-27 后续更新：#332 已接入外置页、循环配置、共享 Agent 设置与整应用重载，当前操作以[#332 实施记录](stage-4-332-implementation.md)为准。下文关于空次数/配置和尚未接入页面的描述保留为 #331 完成时的证据。

## 当前入口

- `uv run lalc`：User Dashboard；General Settings 提供 Developer 入口及用途提示。
- `uv run lalc --developer`：打开/激活 Developer，保留 Capture、Agent Settings、Agent Repair 三页。上方 Selected Manifest 和试运行按钮不改变 Default 或 Candidate 来源。
- 同一用户重复 GUI 入口经用户私有本地通道唤起已有应用；两个窗口共享服务与宿主。Run、Agent、Capture 的游戏占用也与独立 CLI 跨进程互斥，不按数据根另开执行环境。同一 Candidate 的编辑/校验/发布有独立排他；只读查询不因游戏占用一律拒绝。
- 执行窗口按所属窗口模态，暂停/继续/停止沿用正式服务；空闲窗口可独立关闭。关闭工作所属窗口需确认停止并等待清理，最后窗口关闭才退出服务。失焦、最小化及用户接管仍等待手动恢复。
- Dashboard 当前只提供 Manifest 选择、真实启动、控制与结果通知；业务次数/设置页面尚未接入，因此 GUI 当前传空次数与配置。CLI/API 可传完整快照。通知多条共存、手动关闭，不跨重启恢复。Developer 普通连接配置可编辑/保存，实际检查仍遵守活动互斥。

## 初始化、发布与运行

全新 `uv run lalc init` 创建 `candidate/manifest.json` 并登记空调度 `plan.py`，不执行 Task、不自动 Publish、不改变 Default。从合法保存版本初始化时物化已有 Plan；源码文件按逻辑名物化，可能名为 `plans.default.py`。

```python
"""调度示例；任务逻辑名必须已登记在同一 Manifest。"""
from typing import Any
from lalc import automation_plan

@automation_plan
def execute(ctx, *, task_repetitions: dict[str, int], settings: dict[str, Any]) -> None:
    for _ in range(task_repetitions.get("sample", 0)):
        ctx.call("tasks.example", save=True, seconds=0)
```

每个 Manifest 恰有一个 `@automation_plan`，以既有 components 分区、稳定逻辑名和精确源码哈希标识；不引入第二个 Plan 选择器或任意路径执行。Plan 仅调用 Task，不能直接调用 Step/Subworkflow/Recovery Rule、另一个 Plan 或 Trusted Action。其他正式角色的输入和调用契约保持。

```sh
uv run lalc validate
uv run lalc publish
uv run lalc set-default <发布返回的UUID>
uv run lalc run-plan
uv run lalc run-plan --manifest <UUID> --inputs '{"task_repetitions":{"sample":2},"settings":{"page":{"mixed":[1,true,null,{"mode":"demo"}]}}}'
```

Plan 输入为独立规范化快照；次数为非负整数，settings 按页面 ID 包含 JSON 对象，允许混合嵌套但拒绝非有限浮点、非字符串对象键及非 JSON 类型。业务页面校验由 #332 接入，本票不建立通用业务 schema。

Plan→Task 返回成功 status/output 或失败 status/原始 failure_code/failure_message，普通失败后仍可继续剩余重复。执行器独立保留实际 Task 结果、Ledger、Trace 和共享 Working Manifest。Plan 正常返回使用 `status=completed`，`all_tasks_succeeded` 单独表达 Task 是否全部成功，`output` 只保存业务返回。取消、无法继续的环境错误、输入释放/必要持久化失败、Plan 自身错误使用 interrupted，保留已有结果，不回放、不接入 Runtime Agent。CLI 正常完成且全部 Task 成功才返回 0；空 Plan 正常结束为 0，其余为 1。

Developer Agent 可以编辑已有 Candidate Plan；初始化提供 Plan，不增加 Agent 创建 Plan 的权限。修改后须 Validate/Publish，`trial_run(manifest_id, inputs=...)` 省略 logical_name 时执行该保存版本的唯一 Plan。显式 logical_name 仍支持直接 Component 试运行；不接受 plan_path，不执行可变 Candidate 文件，也不修改 Default。宿主、pi 工具、提示词与快照共同执行边界。

可运行教学样例为 `example/workflow/`，按其 README 将完整样例准备为 Candidate、发布并选择 Default 后运行；默认只观察和等待，但正式执行仍要求唯一可用 Windows 游戏窗口。不能把示例成功当作真实游戏业务验收。

## 旧数据

JSON Plan 执行、CLI 的路径参数及 Agent plan_path 已移除。不会扫描、转换、删除用户旧 plan.json，也不补写旧不可变 Manifest；缺少合法唯一 Plan 的版本明确不兼容。

已有旧 Candidate 请先保留草稿，人工增加带正式入口的 Python Plan，并在 components 中以稳定逻辑名登记 source_path，随后 Validate/Publish 成为新版本。不要用 init --replace 覆盖尚需保留的开发内容。若仅有旧发布物而无 Candidate，请人工准备新的完整 Candidate 或采用更新后的教学样例；不兼容旧 Manifest 无法直接通过 init --from 加载。仓库教学样例与测试夹具已随代码迁移，用户运行数据不参与该替换。

## 验证记录

- 普通回归：`QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest -q --tb=short`：**439 passed，50 skipped**，5.54 秒。默认跳过 Agent 测试；Windows DPAPI 与受限环境下的本地 IPC 测试也未计为通过。
- 真实跨进程 IPC：在允许本地通信的环境显式执行 `tests/test_user_gui.py::test_gui_request_is_forwarded_across_real_processes`：**1 passed**。普通环境对此项的 skip 不冒充通过；本次独立运行证明跨进程请求/确认通道。
- Agent 接入：显式使用 `--run-agent-tests`，仅选择 `tests/test_agent_repair_agent.py` 中多文件/Plan 编辑、发布后试运行、Python Plan 未发布修改隔离、停止/轮次取消清理：**5 passed，35 deselected**，6.43 秒。使用真实 pi 与测试启动的本地 HTTP 替身；未调用真实模型，不作为 Windows/游戏验收。
- 普通回归中的 `test_process_lock.py` 使用真实子进程验证 GUI/CLI 游戏占用、不同数据目录拒绝绕过及进程异常退出后释放；`test_user_gui.py` 的 offscreen 检查覆盖双窗口共享、模态范围、配置可编辑、独立关闭、所属窗口停止清理和通知。
- `git diff --check` 通过。User Dashboard 和 Developer 三页壳已做 offscreen 渲染检查；预览位于源码 checkout 的 `.generated/stage-4-331/`，仅为开发证据。

Windows DPAPI、实际窗口焦点/接管、Windows 打包现场验证和真实模型未在本轮执行。#331 的本地代码/自动化完成不等于 #334 Windows 成品验收完成。
