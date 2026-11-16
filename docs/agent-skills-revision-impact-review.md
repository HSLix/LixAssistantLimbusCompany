# Agent Skills 修订影响审查

2026-11-16，实施前只读审查。输入为[已确认讨论](agent-skills-revision-discussion.md)及用户随后补充的 Asset 复用、只读识别试验和临时 Step 清理要求。本文的实施前结论不等于游戏 Manifest 已迁移。

## 设计变化

- 按画面拆 Step、普通超时直接失败 → 按局部目标划分；通用动作参考一次短尝试，以 completed／reason 交回业务未达成，真实异常继续传播；专用业务 Step 可采用其他形态。
- Workflow 写法及重试预算不统一 → 统一有界循环分派；连续无效初始 3 次、无效等待 1 秒；Task 源码内固定足够覆盖正常执行的较大总循环兜底，Skill 不规定具体数字，短子流程按职责定总上限。两类预算与框架 recovery_count 无关。
- 正常加载主要靠业务 Step 或 Recovery Rule 等待 → Workflow 集中识别可靠的 Connecting／Combat Tips／Now Loading，调用共用等待 Step，初始 60 轮、轮间 1 秒；超限由上层重新观察一次，仍在才抛失败。
- 各段稳定后强制完整实跑 → 按改动范围验证；珍惜可能只有一次低成本验证机会的现场，禁止为重复验证擅自复位或消耗资源。少量可靠特征按证据逐步改进。
- 先造识别资源 → 先查询现有 Asset，以语义命名支持检索；必要时通过仅观察的临时 Step 验证当前页面命中与误识别，按工具权限和专用确认清理 Candidate 文件。

## 已确认的影响

| 位置（实施前） | 证据与影响 | 后续动作 |
| --- | --- | --- |
| `src/lalc/skills/workflow-conventions/SKILL.md:10–21` | 多状态绝对拆分、超时直接失败及重试初始 3，与本次已确认指导冲突。 | 替换职责、交回与预算规则，详细分派／等待过程放按需参考。 |
| `src/lalc/skills/workflow-development/SKILL.md:7–17`、`workflow-repair/SKILL.md`、`asset-management/SKILL.md` | 重复校验发布流程；开发第 7 项无条件完整实跑，第 8 项对缺页面普遍询问。 | 验证集中到 validation-and-trial；页面询问收窄到需 Dashboard 接线的用户任务。 |
| `src/lalc/skills/page-development/SKILL.md` 的 description／启停指导；`src/lalc/remote_mcp.py:MCP_TOOLS` | 文字写仅 GUI Construct，但远程入口登记 page_* 与专用审批工具。 | 按实际启用工具和专用审批描述，不新增权限。 |
| `src/lalc/run_context.py:RunState.__init__` | settings 启动输入必须为字符串键到对象的映射；顶层整数预算无法作为独立试运行初值传入。 | 用户最终选择源码本地常量，不新增共享预算或字段；现有启动契约不改。 |
| `src/lalc/runtime.py:_invoke_entry`、`_recover_call`、`_recover_rules` | 正常返回不会触发恢复；包括 completed=false 的正常 Step 返回也会清零框架恢复计数。首次失败零规则匹配不会自动重试，而转 Agent／结束。 | 指导明确 completed 是业务目标结果，业务无效计数由 Workflow 自行维护；不改执行器，不承诺消除超时后的所有时序窗口。 |
| `src/lalc/runtime.py:_normalize_value`、`src/lalc/manifest.py:_validate_execute` | Step 返回按自身注解规范化，Task 输入／输出注解另有更窄白名单。 | 不将异构 completed／reason 字典示例误推广成 Task 返回注解；按需同步真实调用方，不新加全局强制校验。 |
| `src/lalc/repair_tools.py:delete_component`、`agent_prompts.py:CORE_PROMPT`、`agent_policy.py`、`remote_mcp.py` | 只删经确认的一个 Candidate Python 文件，不清登记／引用、不删历史；CLI／Runtime 不提供该工具。 | 临时不构成自动删除授权。使用时检查请求、登记和调用方，遵守专用确认；移除登记／引用后完整校验发布。 |
| `src/lalc/agent_skills.py:initialize_skills`、`prepare_skills`；`pyproject.toml`、`scripts/build_windows.py` | 默认 Skills 与附属资料递归分发；已存在用户目录不覆盖。 | 保留必需入口和打包接口，不限制额外 Skill 数量；新增参考必须能随初始化／快照复制；提供手工合并说明，保留用户游戏知识及图片。 |
| `CONTEXT.md:Step`；`docs/developer-workflow-tutorial.md` 的 Workflow 指导；`docs/current-state.md` | 现行解释仍有“未知／停滞必须在 Step 抛失败”等旧表达；当前状态中的历史条目记载旧指导。 | 同步受影响术语与现行教程，新状态入口明确替代范围；历史实施记录保留原时点。 |

## 潜在风险与验证边界

- 新指导不能自动迁移 Windows 用户 Skills 或已发布 Manifest。当前既有普通 Step 可能仍返回 None 或依靠局部循环；迁移前必须读取调用契约，不能批量视为新 completed 格式。
- 本地总循环上限是每次组件调用的兜底，不是共享剩余次数、绝对时限或持久断点；嵌套流程及识别耗时使总耗时无法据此直接推算。用户已撤回共享预算与数据分离方案。
- 等待提示消失不证明目标完成；超限后重新观察仍无法消除所有“随后自行恢复”的时序窗口。错误弹窗、黑屏及识别错误不得伪装成正常过渡。
- 当前页面的正例／负例识别试验只能支持当前现场，不能声称跨页面或跨截图稳定。只读观察 Step 仍须发布后用明确版本运行；截图可能置前窗口，但不应包含游戏控制输入。
- 本轮不启动真实 pi、模型或游戏，不修改 Runtime、Validator、工具权限、游戏 Manifest、资源或用户安装目录。Skill 结构检查及普通初始化／快照回归不能证明模型会遵守新指导。

## 实施顺序

1. 已通过本地固定上限避开共享预算与 RunState 启动输入的结构冲突，补记最终确认与新增要求。
2. 更新共用规范及按需参考，再改开发／修复／素材／验证入口与页面过时说明；同步现行术语、教程及维护指南。
3. 检查引用、Skill 元数据、旧规则冲突、默认资源复制和只读快照；无需为了文字修订启动 Agent 接入测试或新增措辞匹配测试。
4. 记录实际验证结果，明确手工合并路径和后续 Manifest 按需迁移范围。

## 实施与验证结果

已完成六个默认过程 Skill 的指导修订；新增 workflow-conventions 下的分派／等待及恢复规则参考，按任务读取。同步 Step／Subworkflow 术语、现行开发教程、Skills 维护与当前状态入口。human-feedback、游戏知识、图片、Runtime、RunState、Validator 和工具权限未修改。

本次不创建共用等待业务 Component，也不批量改造既有游戏 Manifest。指导描述如何按需实现与迁移，不宣称既有游戏流程已采用新设计。Skill 中没有规定固定 Task 总循环数，不新增共享预算。

验证记录：

- 六份修改后的 SKILL.md 通过 skill-creator 的 quick_validate（元数据与未完成占位检查）。参考路径及本地文档链接检查通过。
- 以仓库普通工作目录模拟初始化及固定副本，当前完整资源树逐文件字节一致，新参考随目录复制，快照退出后清理，已有定制内容不被重新初始化覆盖；不接触真实用户安装目录。
- 首次定向回归发现旧测试将必需清单与实际全部 Skill 集合判为相等，拒绝已有额外游戏知识 Skill；HEAD 已有同一清单、断言与额外资源。按用户本轮明确要求，改为必需入口子集检查、当前完整资源树复制检查，并验证人工新增 Skill 保留；递归清理适配参考子目录，不限定 Skill 总数。
- 最终普通定向回归：`QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest -q tests/test_agent_skills.py tests/test_agent_prompts.py tests/test_windows_packaging.py`，**22 passed**，无排除项。覆盖初始化／快照、额外内容、Prompt 错误边界和打包组装逻辑；打包回归使用夹具，不是 Windows 成品构建。
- `git diff --check` 通过。未运行全量、真实 pi／Agent／模型、Windows 成品或游戏验证；没有将未运行项目报告为通过。

已有用户 Skills 仍须按 [合并说明](agent-skills.md#合并本次指导到已有安装)人工对照更新，包括两个新增参考文件；保留自建游戏知识、图片和其他 Skill。真实模型是否遵循新指导，需后续按需使用实际任务验证。仓库原有 `.gitignore` 修改未触碰。

## 后续补充：人工商讨特征与分阶段退出验证

用户提出两点补充，经核对均合理：特征难选时向人工商讨，原来只有 human-feedback 的通用信息请求与 development 的转介，未明确这一情景；退出信号须先试跑才能获知，原来虽允许渐进开发并要求完成态不重放，但缺少分阶段获取退出证据的过程。

已在 workflow-development 链接该情景，在 human-feedback 补充具体商讨信息；在 workflow-conventions 明确退出检查先于入口／输入，在 validation-and-trial 补充分阶段验证：入口与单次动作→发布后独立试一次并保留落点→依据实际画面补退出信号→发布新版本后在目标画面验证零输入退出。没有退出依据时显式未达成，不接入自动循环反复尝试；画面变化不自动算目标完成。两次证据分开报告，不声称验证完整路径。本段之后 human-feedback 也属于需合并的更新，前节“未修改”仅描述首轮实施。

本次补充的四份 Skill 均通过 quick_validate；同一普通定向回归重新执行为 **22 passed**，git diff --check 通过。未进行真实 Agent、Windows 或游戏验证，已有用户 Skills 未覆盖。
