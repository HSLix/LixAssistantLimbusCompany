# 页面多任务、启停与 Session 来源显示

2026-11-08。来源：本轮开发者逐项确认。状态：开发者已整体确认，已完成本地实施；验证证据见文末，Windows 与真实游戏尚未验收。

## 已接受的设计变化

- Business Settings Page 从最多注册一个 Loop Task 改为注册零到多个任务；每个任务独立声明稳定 ID、显示名称、是否显示任务次数。
- 不兼容旧 `TASK_ID` 和页面级 `SHOW_TASK_COUNT` 声明；开发者确认没有需迁移的现存页面资源。示例、测试、文档及内置 page-development Skill 必须一并改为新接口。
- 任务关闭次数显示时，匹配且勾选传入 1，未勾选或不匹配传入 0；任务配置按任务 ID 保存，页面业务配置仍按 Page ID 保存。
- 删除需求替换为停用页面，不提供永久删除能力。保留源码、资源、页面业务配置和各任务设置；停用后侧栏和 Dashboard 隐藏相关项，关联任务次数为 0。
- Agent 可以列出全部已安装页面及启用状态，停用页面也可被列出、读取和恢复。不增加专门页面管理入口。
- 启用和停用均须专用弹窗等待人工确认；关闭或取消不更改状态。工具仅开放给 GUI Construct，不开放给 Repair、CLI 或 Runtime Agent。
- 启停状态保存后重启应用生效，不改当前运行中的任务；本轮 Agent 结束并完成清理后统一提示重启，沿用页面安装流程。
- 停用页面仍占用 Page ID 和全部任务 ID，不能由其他页面复用；正常更新同一页面仍允许。
- Agent 更新或 Sharing 覆盖安装保留既有启停状态，不能借更新隐式启用页面。
- Developer GUI Session 右上角齿轮左侧显示“基于 Manifest：<ID>”，无来源时显示“无”。新对话跟随选择；已有对话读取固定 source_manifest_id，切换 Session 时更新，不跟随 Default 或后续发布结果。

## 实施接口

采用模块级 `TASKS` 列表；每项包含 `id`、`name`、`show_task_count`。纯设置页使用空列表。任务名称沿用项目的中英文展示能力，保持 Page ID、任务 ID 与 Component 名不同的边界。

工具为 `page_set_enabled(filename, enabled, summary)`，启用/停用共用专用确认和取消路径，不新增通用写配置权限。本机状态单独保存在 `page-availability.json` 的停用文件名列表，初次安装默认启用，后续覆盖保留状态。

## 实施前源码检查确认的影响

| 范围 | 已检查位置 | 当前差距与实施要求 |
| --- | --- | --- |
| 页面与任务契约 | src/lalc/user_pages.py：BusinessPage、load_page_module、discover_pages、check_page_registration、task_inputs | 单个 task_id 和页面级次数开关；须改为任务集合，校验页内及跨页重复，保留停用页注册占用后再过滤可用页面。避免 Plan 支持但页面停用时读出旧非零次数。 |
| Dashboard | src/lalc/gui.py：任务行构建、页面加载 | 当前每页一行；须逐任务展示名称和次数开关，各行设置按钮跳回同一页面；重启前继续使用当前加载状态。 |
| 配置 | src/lalc/user_pages.py：UserSettings | 当前顶层结构严格限定 pages/tasks；启停状态须单独建模，不能混入页面业务配置，也不能让独立写入者互相覆盖。 |
| 审批与恢复 | src/lalc/page_drafts.py、page_preview.py、repair_tools.py：page_preview | 列表目前只有文件名、哈希、文件数量，预览只展示一个任务。扩展任务列表、状态查询和专用启停审批；不能把普通反馈当作批准。 |
| Agent 路由 | src/lalc/agent_policy.py、pi_probe.ts、agent_repair.py、developer_gui.py | PAGE_TOOLS 仅 GUI Construct 可用；新工具须覆盖声明、宿主路由、GUI 请求、取消清理和轮末重启提示。 |
| Sharing | src/lalc/sharing.py：page_entries 使用点、页面安装；sharing_gui.py | 导出发现与安装须保留停用包，不能把本地启停状态随包覆盖；停用页仍参与注册冲突检查。 |
| Session 来源 | src/lalc/developer_gui.py：context_button、new、activate_session；developer_session.py：source_manifest_id | 来源已持久化，当前顶栏缺显示；直接使用现有来源，无须修改 Session 数据格式。 |

## 文档与测试工作

- 同步 CONTEXT.md 的页面/任务关系、Stage 4/5 现行规格、页面示例 README 和源码、Agent 工具说明、Sharing 说明，以及当前状态入口。历史记录保留其时点，不将旧验收改写为新功能验收。
- 更新 src/lalc/skills/page-development/SKILL.md，覆盖新任务声明、各任务次数行为、Plan 接线、page_list 启用状态、启停专用确认、重启生效和覆盖安装保留状态；检查应用数据目录既有 Skill 的初始化策略，明确新指导的实际交付边界。
- 聚焦 tests/test_user_pages.py、test_page_drafts.py、test_page_package_tools.py、test_sharing_gui.py、test_gui_language.py 及相关 Session/权限测试：多任务与纯设置页、旧声明拒绝、非法字段和重复 ID、逐任务次数、停用归零且保留配置、恢复、覆盖安装保留状态、批准/取消/轮次取消、重启提示合并、来源显示与历史 Session 切换。
- Agent 工具接线属于本次范围；普通测试与确有必要的显式 Agent 接入测试串行运行，跳过项不得计为通过。

## 潜在风险与验证边界

- 停用状态与页面配置分离但由多个 GUI 对象读取，存在旧内存覆盖新状态的潜在风险；用交错保存及重启后的结果验证。
- 仅隐藏 UI 不足以停用，须验证 Plan 任务输入归零，停用页不创建页面控件，同时仍加载可信模块检查注册冲突；停用不构成 Python 源码执行隔离。
- 已安装 Skill 目录采用首次初始化策略；仅修改仓库内置版本可能不更新当前本地 Agent 指导，实施时需检查实际分发路径，不能直接宣称已生效。
- 实现前仅检查源码；本地测试证据如下。真实模型、Windows 或游戏验收未执行。


## 本地实施与验证结果

- 已实现 `TASKS`、各任务名称（含可选中英文 names）、次数开关、全局注册冲突检查、Dashboard 多行及共享页面跳转；旧单任务声明明确拒绝。
- 已实现独立本机启停名单、包含 enabled 的页面列表、`page_set_enabled` 宿主与 pi 声明、专用应用模态确认、版本变化拒绝、取消失效及轮末重启提示。Sharing 覆盖不重置状态，停用页仍参加冲突检查。
- Session 顶栏已显示来源或“无”，已有会话读取固定 source_manifest_id；示例、内置页面开发指导、中英文文案与现行规格同步。
- 普通相关回归：`QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest -q tests/test_user_pages.py tests/test_page_drafts.py tests/test_page_package_tools.py tests/test_sharing_gui.py tests/test_gui_language.py tests/test_developer_policy.py tests/test_developer_session.py tests/test_agent_prompts.py tests/test_agent_skills.py`：161 passed，1 skipped。跳过项未计通过。
- `tests/test_page_availability.py`：13 passed，覆盖多任务次数、旧声明拒绝、停用归零/恢复/占用、覆盖保留、专用弹窗确认/关闭/取消/版本变化、工具等待取消、GUI 路由与轮末重启、已有 Session 来源显示。
- `tests/test_sharing.py tests/test_developer_gui.py`：81 passed；后新增的 Sharing 启停保留与停用页第二任务冲突用例单独执行通过（1 passed）。以上分组覆盖 256 个通过用例。
- 普通测试退出后，显式执行 `QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest --run-agent-tests -q tests/test_developer_session_agent.py -k 'page_tool_declarations or page_availability_tool_roundtrip'`：4 passed，40 deselected。使用真实 pi 与本机 HTTP 模型替身，覆盖工具声明及启停调用往返，不等于真实模型验收。
- 初次将新增 GUI 用例与既有页面导航用例合并执行时，Qt 在导航测试中退出 139；后续上述分组分别通过。未证明该组合进程崩溃的根因已消除，不声称全量回归通过。
- `git diff --check` 通过；未进行 Windows、真实模型或真实游戏验收。已有数据目录的自定义 Skill 不自动覆盖，需按 docs/agent-skills.md 对照内置版本同步；本轮未改用户数据目录。
