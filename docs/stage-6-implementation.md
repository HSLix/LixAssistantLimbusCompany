# Stage 6 本地实施与验证

2026-11-11。依据[接受设计](stage-3.5-agent-runtime-step-recovery-and-maintenance.md#2026-11-11-设计讨论已确认边界)、[影响审查](stage-6-design-impact-review.md)及 [ADR 0040](adr/0040-share-run-state-and-reuse-agent-sessions-for-runtime-repair.md)。开发者已授权实施，并逐项回答实施中发现的边界。本文记录本地结果，不代替 Windows、真实模型或游戏验收；未创建 tickets、未提交 Git commit。

## 配置与启动

正式 Plan 改为 `execute(ctx)`，不接受旧配置参数。所有入口持有独立的 RunState，同一 Run 的 Plan、Task、Subworkflow、Step 和 Recovery Rule 共享：

```python
from lalc import automation_plan

@automation_plan
def execute(ctx) -> None:
    state = ctx.run_state
    while state.task_repetitions.get("daily", 0) > 0:
        task = ctx.call("tasks.daily", team=state.settings.get("daily", {}).get("team", "A"))
        if task["status"] == "failure":
            break
        state.task_repetitions["daily"] -= 1
```

业务数据可直接修改，失败不回滚；普通 `ctx.call()` 参数仍复制为本次调用的快照，恢复时不会根据 RunState 自动重算。框架维护 `recovery_count` 只读属性。RunState 不保存为可恢复检查点、不回写页面配置；Trace 可保留初始化等诊断快照。

`ApplicationService.start()`／`start_plan()`、CLI 和 Developer `trial_run` 均增加 `use_saved_config`，默认 True：采用保存的页面配置，以及启用任务的次数（未启用为 0）。False 使用显式 `task_repetitions`／`settings`，未提供为空。Dashboard 自行完成单次运行等设置快照后，显式用 False 传入，保留既有界面语义。

```sh
# 默认采用保存的配置
uv run lalc run-plan
# 独立空配置
uv run lalc run-plan --no-use-saved-config
# 显式配置；不再作为 Plan execute 参数
uv run lalc run-plan --no-use-saved-config --inputs '{"task_repetitions":{"daily":1},"settings":{}}'
# Component 的业务输入与初始状态分开
uv run lalc run steps.example --inputs '{}' --no-use-saved-config --run-state '{"settings":{},"task_repetitions":{}}'
```

Developer Agent 的 `trial_run(manifest_id, logical_name=..., inputs=..., use_saved_config=True, run_state=...)` 具有相同配置来源规则；Plan 省略 logical_name、inputs 为空。独立试运行不启动 Runtime Agent，失败交回发起它的 Developer Agent。

## 恢复与版本

`WorkflowExecutor._invoke_entry()` 在 Plan／Workflow／Step 各自入口处理自身错误。保留等待者，重新调用失败入口，实际结果只返回一次；下层恢复终止不升级为外层自身错误。Task 重试在 Ledger 同一逻辑记录中追加 attempts；Plan 重入保留之前实际产生的 Task 记录。

规则先完整检测一轮；唯一匹配执行 recover，成功后重调。零匹配、歧义及规则错误交 Agent；Agent Recheck 后零匹配直接调用修复入口。正常 Step 返回或实际 Agent 介入清零连续规则恢复次数，默认上限 10；内置游戏重启纳入统一计数，不再单独限制每 Run 一次。重启耗尽且 Agent 无法介入时终止整个 Run；重启本身失败仍按不可继续环境故障终止。普通业务恢复耗尽只让当前 Task 返回 failure；Plan 自身耗尽结束 Run。

Runtime 使用现有 DeveloperSession、Candidate、固定基线和聊天日志。同一恢复会话的多轮反馈共享请求余额，默认 50，不因 Recheck、发布或选版本重置。工具白名单开放只读 `read_run_state`、历史／知识库／Skills 及修复工具，禁止独立 trial_run、删除、知识库 Git、页面编辑和直接写 RunState。Runtime 发布须 `publish(summary="简述修复的问题")`，说明进入 Manifest AdditionalMessage；再 `recheck(manifest_id)`，立即结束本轮模型交互，将执行权交给 Runtime。完整 Validator、正常输入输出与角色检查保留，不强制新旧调用约定一致。

Run 后同一 Session 可在 Developer GUI 继续，恢复点和 RunState 不重新启用。停止 Run 会取消正在等待的 Runtime Agent，并等待工具／日志收尾后清理活动权及状态访问。

User GUI 提供连续恢复上限、默认关闭的 Runtime 人工反馈，以及默认开启的“运行成功后自动使用修复版本”。Developer GUI 提供默认开启的全模式历史检索开关。前两类运行选项在 Run 开始固定；历史检索／人工反馈在下一轮 Agent 开始固定，不在工具调用时重新读取设置。已发出的人工请求保留答复／跳过和取消。

自动使用修复版本以 Plan `status=completed` 为条件，不检查 all_tasks_succeeded；直接 Component 要求 success，且必要收尾成功。采用最终实际 Working Manifest，完成 Default 写入后才提示成功；写入失败保留执行结果及旧 Default，另行提示失败。没有切换时不提示。Publish 本身不设置 Default。

## 迁移

旧 Plan 签名不再执行或发布，不提供兼容分支。Repair 初始化允许读取旧已发布 Manifest，校验身份、路径及源码 SHA-256 后复制为草稿；此过程不导入代码。修改签名和配置访问后再完整校验、发布，原不可变源码不重写。公开 RunContext 声明、仓库测试夹具、随包 Skills 和中英文设置说明已同步。

已有应用数据目录的 skills/ 仍按原机制不覆盖、不补齐；需要手动合并新随包指导。程序组织的 Runtime 提示包含新接口和执行边界，不依赖旧用户 Skill 自动更新。未增加被取消的调用关系／素材反向查询工具或分析文件。

## 本地验证与限制

- 普通全仓检查按 72 个测试模块串行分进程运行：首次 71 个正常退出，合计 1146 passed、104 skipped；User GUI P0 模块遇到旧禁用状态断言并发生 Qt 崩溃。已修正与既有 User Agent 开关语义冲突的断言，后续相关 8 文件复测 **165 passed、1 skipped**，包含该模块、翻译、声明、配置、Plan、恢复及重启检查。未把首次崩溃报告为通过。
- Manifest／迁移／Session／Runtime／User GUI P0 定向检查 **89 passed**；随后补充 Plan／Task／Subworkflow 自身失败、等待者与 Ledger 次数检查，Runtime 专项最终包含 14 项；连同 RunState、Manifest 及迁移检查最终 **57 passed**，包括 Developer Trial 不启动 Runtime Agent。这些定向结果存在重叠，不相加为全仓通过数。
- 显式真实 pi + 本机 HTTP 模型替身检查：Runtime 工具交接与既有 Agent 接入 **43 passed、4 skipped**；Runtime 交接及停止清理专项最终 **2 passed**。未连接真实模型服务。
- 生成 run_context.pyi、Python 编译检查及 git diff 空白检查通过。随包中文翻译重新编译。

单进程全套曾在 Qt 测试中发生段错误，分进程结果不能证明该累积崩溃已修复。Windows 原生界面／打包运行、真实模型、真实游戏和现场暂停／重启恢复均未验收；显式 Agent 测试中的跳过项不计通过。
