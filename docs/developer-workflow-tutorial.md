# Developer Workflow

2026-11-11 Stage 6 已实施：正式 Plan 为 `execute(ctx)`，配置通过 `ctx.run_state` 共享，旧签名没有兼容层。旧已发布版本可只读复制到修复草稿，改签名后校验并重新发布；原不可变版本不重写。恢复、配置来源及验证见 [Stage 6 实施记录](stage-6-implementation.md)。

2026-10-30：本文 uv 命令针对源码项目；Windows 成品通过 `LALC-console.exe` 使用同一 CLI，Candidate 固定在用户数据目录，不随终端工作目录改变。构建输入、独立示例准备与验收见[Windows 说明](windows-packaging.md)。

2026-10-27：#331 已实现 Python Plan、双窗口及跨进程互斥，当前用法见下文和[实施记录](stage-4-331-implementation.md)。外置页面及共享 Agent 配置已在 #332 本地实现，#333 双语与语言重载也已完成本地实现、已获开发者人工验收确认并关闭 #333（[使用与证据](stage-4-333-implementation.md)）；#334 已由开发者决定关闭，未执行项不计通过；当前验收由 #340 推进，阶段状态见[集中入口](current-state.md)。

正式 Run 要求唯一可用的 Windows 游戏窗口。运行开始时先启动物理输入监听，再连接并立即聚焦，结束时清理；自动化测试提供平台替身。

游戏在前台时，物理键盘按下及客户区内鼠标点击、滚轮触发手动暂停；鼠标移动和操作其他应用不触发接管。`Ctrl+Alt+P` 是全局暂停热键。运行中单纯失焦或最小化时，等待其他应用连续空闲 10 秒后自动还原、聚焦；鼠标移动也会重新计时。游戏已回前台则立即继续。明确开始运行或点击“恢复”不等待十秒，恢复仍检查物理输入释放。等待开始、结束、耗时及原因进入 Info 日志。输入动作途中失焦先释放，再等待并重入当前 Step；输入前等待保留当前执行位置。详见[设计与影响审查](input-ownership-design-impact-review.md)。

取得聚焦资格后，原生置前请求最多尝试 10 次：首次立即请求，之后每隔 1 秒重试，每次等待期间持续核对实际前台窗口并响应暂停、接管和取消；游戏已在前台则直接返回。第 10 次请求后仍等待最多 1 秒，未成功则抛出窗口错误，包含目标窗口、实际前台窗口及最后一次 SetForegroundWindow 返回值。这个重试上限独立于前面的用户活动等待，不把等待用户空闲视为聚焦失败。

## Component 工作台与发布

```bash
uv run lalc init
# 编辑 candidate/manifest.json 和 Component Python 源码
uv run lalc validate
uv run lalc publish
uv run lalc set-default <publish输出的UUID>
uv run lalc run <logical-name> --inputs '{}'
uv run lalc run-plan
uv run lalc --developer
```

常规使用按 publish → set-default → run / run-plan 进行，后续省略 `--manifest`。每次发布并希望使用新代码版本时，再设置 Default；临时运行其他版本才用 `--manifest <id>`。

Manifest schema 2 只管理 `components` 和 `recovery_rules`，保存格式另有 UUID `manifest_id`。Asset 与 Trusted Action 都不是 Manifest 条目，不接受内嵌 `assets` / `trusted_actions`。Candidate 不需要素材映射文件；init 不复制素材，validate 不验证素材或写发布物，publish 不改 Default。手工已有非空 Candidate 仅在明确使用 `init --replace` 后重建；clear 需要确认。初始化同时保存独立的固定 Diff 基线。Agent 使用独立 Developer Session，换来源须新建 Session，不接管手工 Candidate；工作台用法见 [修复指南](agent-repair.md)。

初始化即生成并登记空调度 `plan.py`；Manifest 必须恰有一个 `@automation_plan`，其仅通过字面量 `ctx.call()` 调用 Task，不能直接调用动作。其入口为 `execute(ctx)`，通过 `ctx.run_state.task_repetitions` 和 `ctx.run_state.settings` 读写本 Run 配置。宿主复制初始数据，同一 Run 后续共享修改，失败不回滚，不回写页面配置；示例及启动选项见 [Stage 6](stage-6-implementation.md)。其余源码用 `@task_workflow`、`@sub_workflow`、`@step` 标记角色，Recovery Rule 使用 detect/recover。字面量 `ctx.call()` 调用正式 Component，`ctx.action()` 调用应用统一注册的动作；不直接调用原生截图或控制后端。

业务 Step 负责识别当前状态、执行动作、确认完成及抛出业务异常；已完成时直接返回，预期过渡继续观察，未知或停滞状态按证据失败。完成标识可用模板、OCR 或其他可靠状态，点击返回或固定等待结束不能证明业务完成。基础截图、等待 Step 只保证自身职责。Task／Subworkflow 负责排布、传参、分支、循环和汇总，也可通过 observe 动作先观测、确认状态再进入子步骤；控制动作仍由 Step 执行，上层检查不能替代 Step 恢复重调时自身的状态确认。

开发时优先从当前中间状态验证受影响的 Step／分支，各段稳定后再补一次完整路径；每次试运行前简要明确起点和期望变化、终点或输出，结束后核对是否符合。共有导航标志或已在终点时零动作返回不能证明完整路径已覆盖。正常流程等待通常十秒左右到十几秒，更长超时须有实际耗时依据；超时后交给 Recovery Rule 识别错误，不要求在正常轮询中反复检测错误弹窗。同一帧先用足够的模板证据，按需再做局部／全屏 OCR。准确类型示例见[共用编写规范](../src/lalc/skills/workflow-conventions/SKILL.md#component-类型示例)。

Plan 的 `ctx.call("tasks.xxx")` 返回 `status`，成功含 `output`，失败含 `failure_code`、`failure_message`。记录 Task 逻辑名、当前/总循环次数和这些字段，不把失败简化为 `unknown`；普通 Task 失败可继续，取消及不可恢复环境故障仍向外传播。完整 Trace 已由宿主记录，无需新建日志存储。

## Trusted Action 类型补全

`ctx.action("observe.wait", seconds=1.0)` 协作等待 0–60 秒，不注入游戏输入；所有允许 observe 的阶段都可使用，包括 Task Workflow、Subworkflow、Step condition 和 Recovery Rule detect。期间保留暂停、接管与取消检查；Workflow 遭接管后手动恢复会重新等待完整时长，不重放已完成 Step。Plan 不能调用 Action。旧 `control.wait` 已移除；已有源码需在 Candidate 中改名并重新发布，不改写已发布源码或旧 Trace。

`ctx.action("control.restart_game")` 可由 Step 或 Recovery Rule 的 recover 阶段调用，无参数。应用先验证已保存的 Steam 客户端路径及唯一安装，正常关闭原游戏，5 秒未退出则只强制终止原进程并再等待 5 秒，随后启动 `LimbusCompany.exe`，最多等待 60 秒完成新窗口绑定及置前。返回只证明窗口可用，不证明完成登录、更新或进入业务页面。等待、关闭、启动、绑定、失败及取消过程均记录 Info／Warning／Error 日志，在 User Logs 默认可见；暂停和物理接管后须手动恢复，继续原重启阶段，避免重复启动。

运行中确认绑定进程退出时，应用内置 `builtin.game_crash` 规则优先处理并重新调用当前 Step，保留 Task／Subworkflow 的调用栈和局部结果。每个 Run 最多自动重启一次，显式调用不占此额度；再次退出或重启失败会终止整个 Run／Plan。失焦、最小化走活动等待后自动聚焦；进程仍在但窗口消失，以及用户接管仍走人工恢复。初次运行前没有游戏窗口仍拒绝启动；Step 外不新增自动恢复边界。见[重启契约与验证](game-restart-design.md)。

开发者从根包导入 `RunContext`，给 execute、condition 或 detect/recover 的 ctx 参数添加注解。IDE 使用项目的 Python 环境，即可补全 Action 名称、对应关键字参数和返回类型；其他 Context 成员（例如 `ctx.call()` 和 `ctx.game_language`）也保留类型信息。

Agent 编写代码前读取 `action_contracts` 和已有 Component 签名。点击优先使用 `ctx.action("control.click", centerxy=target["centerxy"])`，复用匹配返回的中心点；也支持完整 `x/y`，两种形式不可混用。不要裁掉返回字段后重新计算中心。合并示例通过 `ctx.call("steps.actions", operation="click", x=x, y=y)` 调用，其参数以 Step 自身签名为准，不自动继承 Action 参数。以下独立动作样例展示直接坐标形式，不是完成业务检查的示例。

```python
from lalc import RunContext, step


@step
def execute(ctx: RunContext, *, x: int, y: int) -> None:
    ctx.action("observe.capture_screen")
    ctx.action("control.click", x=x, y=y)
```

新增或修改应用 Trusted Action 的注册、函数签名，或修改 RunContext 公开接口后，在源码 checkout 中运行：

```bash
uv run lalc generate-stubs
```

命令直接从 `application_actions()` 和真实函数签名生成完整的 `src/lalc/run_context.pyi`，保留默认值并移除执行器注入的 Context 参数；装饰器需通过 `functools.wraps` 或准确的 `__signature__` 保留签名。注解须能解析，Action 参数和返回值采用运行时支持的 JSON 类型；无法表达的签名、缺失注解或写入失败会报错并返回非零。生成成功后把声明与源码一起提交，不手工编辑声明。命令无需 Candidate、Manifest、游戏窗口或模型服务。

`tests/test_stubgen.py` 比较声明与当前注册、Context 接口是否一致，并使用 Pyright 验证典型合法与非法调用。静态声明对应应用正式注册，不随测试替身表或 Manifest 切换；角色/阶段权限仍由现有 Validator 和执行器检查，`ctx.call()` 仍保持现有动态参数与返回类型。

## 独立素材与标签

完整逻辑名对应完整目录，例如 `ui/claim` 对应数据目录的 `assets/ui/claim/`。每张图为 `<完整SHA256>.png`，目录下 `asset-tag.json` 保存 `哈希 → tag列表`。语言只是普通可选 tag，无特殊筛选规则。所有有效图片都参与候选；缺 tag 文件或缺哈希条目时按 `[]` 处理，不需要登记白名单。

```bash
uv run lalc crop-asset ui/claim --region '{"x":2,"y":1,"width":20,"height":20}' --tags zh event
uv run lalc tag-asset ui/claim --image <crop返回的image_path> --tags dark event
```

裁剪重新连接游戏并截图，保存图片、实际观察/区域来源和标签。tag-asset 仅给已有本地裁剪设置标签，核对逻辑名、来源、完整哈希及解码，不连接游戏、不接受外部 PNG、不复制图片。两个命令都无需 Candidate 或 Manifest 发布。

标签按本次输入整体覆盖：原为 `["zh", "event"]`，再传 `--tags dark event` 后为 `["dark", "event"]`。不追加、不合并、不去重，输入顺序与重复项原样保留。省略 `--tags` 或传空列表会写入 `[]`，清空已有标签。新图片和不同主题可并存；相同字节复用同一哈希图片，图片字节从不覆盖。重复裁剪相同图片时也按本次 tags 替换标签列表。标签更新无需确认，不改变其他哈希的标签。

## 匹配规则

截图默认使用 `auto_park_cursor=True`：仅在拥有控制权且无需等待用户返还控制时，将客户区内的鼠标移到游戏窗口右下角外 8 像素，并等待 0.1 秒供游戏刷新悬停状态。鼠标本来在外则不移动。移动前后及截图前后检查接管；Run 中接管后丢弃本次观察，手动恢复后重新检测位置和截图，不沿用中断前的位置。手动截图也监听接管，发生接管则报错，由用户重新发起。截图完成后再次确认鼠标未进入客户区，若进入则重新观察；连续三次截图均重新进入时记录 Warning 并采用最后一帧，避免无限循环。

可用 `ctx.action("observe.capture_screen", auto_park_cursor=False)` 关闭本次截图的自动归位。该参数也适用于底层 `FocusedAutomationSession.capture`、开发者截图接口和 Agent 的 `game_screenshot` 工具。归位最多尝试三次，每次等待 0.1 秒并检查控制权和窗口。若右下角外目标超出桌面范围、移动注入失败，或移动后鼠标仍在客户区，记录 Warning 后继续截图；日志包含每次移动前后客户区坐标、失败原因，以及可取得的目标屏幕坐标、窗口／虚拟桌面范围和 Windows 鼠标裁剪范围。接管、取消、焦点、窗口和截图错误仍按原边界处理。降级截图可能包含鼠标遮挡或悬停效果，影响匹配；可据日志调整远程控制、移动／缩小游戏窗口，或显式关闭归位。0.1 秒是固定重绘等待，不代表已验证每个游戏动画结束。

Step 先 `ctx.action("observe.capture_screen")`，再执行：

```python
ctx.action("observe.match_asset", asset="ui/claim", priority_tags=["zh", "event"])
```

priority_tags 默认 None，空列表也表示全部匹配。包含任一优先 tag 的模板组成优先组，组内全部匹配；有达标结果则只返回该批，不读取其余模板。优先组无结果时，剩余模板全部匹配，包括无标签图片。语言不会从 `--language` 自动转成优先 tag。

选定批次统一 NMS（默认启用、IoU 阈值 0.5），按分数降序、同分按稳定位置和哈希返回；关闭 NMS 保留所有达标结果。结果包含模板路径、完整哈希、tag、客户区坐标、分数、归一化区域和观察 ID。未知逻辑名是错误，存在但无命中的目录返回 `[]`；哈希、解码或标签文件格式错误保留原始异常，不伪装成未找到。

匹配 Step 保留全部返回结果及 `centerxy` 等字段。多匹配只代表多个候选，不自动失败、不视为没有目标，也不要求全部点击；业务 Step 根据界面含义决定如何使用，有歧义时用 `ctx.log(message, level="warning")` 记录歧义和依据。不能仅靠“没有匹配到关闭按钮／角标”认定已回到主界面，应确认可靠的完成标识。

User GUI 的 Logs 可按 Run 查看这些日志。Trusted Action 由执行器自动记录 Debug，匹配结果、OCR、点击和拖动可关联已有截图及预览标注，无需业务代码再写重复动作日志；不会额外触发截图。Debug 默认不显示但仍落盘，完整交互见[运行日志页](user-run-logs.md)。

每次匹配重新读取该逻辑名目录和标签，并固定本次候选/标签。新增图片或改标签从下一次匹配生效，包括同一 Run；不需要 publish 或 set-default，也不建立跨调用缓存。observe.crop_asset 同样可传 tags，始终重新截图，保存后立即可被后续匹配发现。

### SIFT 特征匹配

模板匹配不足以应对目标缩放或形变时，可显式使用应用提供的 SIFT 动作：

```python
ctx.action("observe.capture_screen")
matches = ctx.action("observe.match_feature", asset="mirror/node/regular_encounter")
```

该动作只读取当前已捕获的客户区帧，不隐式刷新或保存截图。按逻辑名尝试全部模板，不使用优先标签短路。
提供[识别调试页](template-match-lab.md#特征匹配sift)相同的全部 SIFT 参数，另有 `region`、`nms`、`nms_iou_threshold`；
最小内点比例 `min_inlier_ratio=0.4`、NMS 默认开启且 IoU 阈值 0.4。按内点数降序合并后统一 NMS，同分按 y、x、模板哈希排序。
`score` 是内点数，不能与模板相似度直接比较。结果保留原图框、`centerxy`、内点数／比例、模板及目标覆盖率、几何指标、
模板路径／哈希／标签、逻辑名、归一化框和 observation。多个命中由业务代码判断歧义，不自动点击。

动作属于 observe，沿用当前执行阶段的观察权限及统一 Trace；成功的非空匹配更新 Asset Usage Index，事件注明 SIFT 和实际参数。
不存在的逻辑名、坏素材和非法参数报错；存在但未命中返回 `[]`。需要图像证据时显式截图保存或 `ctx.log(..., screenshot=True)`。
SIFT 全图放大和整组匹配可能耗时；低纹理、重复图案、遮挡或透视退化仍可能误检或漏检。

## 证据和边界

`lalc data-dir` 查看数据根。图片在 assets/，裁剪来源在 asset-provenance/。Trace 的 asset_matched 记录优先条件、实际尝试模板、所选批次和最终检测结果；asset-usage.json 按逻辑名保存最近一次非空返回及来源，空结果不更新，不等待 Step 成功，也不影响搜索区域。普通截图不落盘，显式 `save=True` 才保存证据。

[三层教学样例](../example/workflow/README.md) 不附图片或素材映射文件，默认只截图和等待。Plan 从已发布 Manifest 加载不可变 Python 源码，按普通 Python 控制流调用 Task，共用 Run、会话和 Working Manifest；物理接管需明确 Resume，Stop 后释放持有输入并收尾。

[ADR 0027](adr/0027-resolve-assets-independently-with-optional-priority-tags.md) 取代旧专属库。旧 Asset 布局、Candidate 素材库及已发布专属库废弃，清理后重新准备，不做迁移或兼容；Component、Manifest、Default 和运行历史保留。相同 Manifest 的素材结果可随文件更新而变化。

Stage 2 已按 [ADR 0026](adr/0026-close-stage-2-without-a-real-game-workflow.md) 收尾；[#317 已由开发者取消](https://github.com/HSLix/LixAssistantLimbusCompany/issues/317#issuecomment-6652564769)，当前验收由 #340 推进，不保留独立邮箱门槛。开发 Agent 已按 ADR 0028–0031 提供专用裁剪新增与归档移除工具，仍不允许覆盖旧图像；Runtime 权限另按 Stage 6 决定。

## 外置业务页面与共享 Agent 设置

Developer GUI → Agent Repair 中，“打开 Agent 工作区”右侧的“打开扩展配置页面文件夹”会打开数据目录下的 `pages/`，目录不存在时先创建。添加、编辑或删除页面文件后，通过 General Settings 的整应用重载使其生效；此入口不授予内置 Agent 读取或编辑页面的权限。

#332 已接入数据目录 pages/ 中的可信 Python 页面、按任务 ID 配置的循环次数和纯设置页输入。最小页面/Plan 示例、安装及创建契约见[示例](../example/workflow/README.md)，双窗口即时保存、单一编辑入口和整应用重载见[实施记录](stage-4-332-implementation.md)。旧 Plan 未声明支持列表时会告警，不改写旧发布物。

注册循环任务必须同时在页面声明 `TASKS` 并给出任务 `id`、在 Plan 模块声明字面量字符串列表 `SUPPORTED_TASK_IDS` 包含该 ID。Dashboard 使用已加载页面与当前 Default Plan 的任务交集；配置按 `ctx.run_state.settings[PAGE_ID]`，次数按 `ctx.run_state.task_repetitions[任务id]` 读取。安装页面、发布 Workflow、用户选择 Default 相互独立；重载不会补上缺失声明，也不会自动切换到新发布版本，Agent 不设置 Default。底层对缺声明仍产生 warning；User GUI 按现行规则展示中性空状态。

Component 说明优先读取 execute 函数的 docstring，缺失时兼容回退到模块 docstring；两者至少提供一处。Recovery Rule 没有 execute 入口，仍必须提供模块 docstring。只写 # 注释不构成 docstring。

## 工作流版本说明与时间

候选 `manifest.json` 可填写字符串字段 `AdditionalMessage`，缺省为空；发布时保存说明并生成带时区的 `published_at`（ISO 8601，保留亚秒用于排序，界面显示到秒），已发布文件保持不可变。新候选从版本初始化时保留说明，重新发布生成新的发布时间。旧版本缺少这些字段仍可读取。

UserGUI 显示完整 UUID、本地时间（到秒）和说明；空白说明显示“无附加信息”。旧版本的时间回退文件修改时间；导入导出保留已记录的发布时间和说明。最新版本按该时间排序，范围包含所有本地留存版本。首页每两秒检查一次，只在最新版本与默认版本不同时显示提示卡片，点击才设置默认版本；历史版本仍可选择。默认版本切换只影响后续运行。

任务次数输入框按约六位数字限制宽度，不改变可输入次数范围；其余横向空间分配给任务名。


每个 TASKS 项必须声明布尔 show_task_count。False 隐藏该任务的次数控件，保留勾选与“设置”；匹配且启用传 1，未启用或不匹配传 0。True 使用保存的次数（1–2147483647）；隐藏期间保留旧次数。旧 TASK_ID 和页面级 SHOW_TASK_COUNT 不再支持。

页面多任务声明示例（任务 ID 全局唯一；names 为可选中英文名称）：

```python
TASKS = [
    {"id": "exp", "name": "经验本", "show_task_count": True,
     "names": {"zh_CN": "经验本", "en_US": "EXP"}},
    {"id": "reward", "name": "领取奖励", "show_task_count": False},
]
```

GUI Construct Agent 可使用 page_list 查询包括停用页面在内的列表及 enabled 状态，通过 page_set_enabled 请求专用人工确认。停用与启用均需确认，关闭/取消不修改；保留全部资源、配置及 ID 占用，不提供永久删除或专门管理入口。变更重启后生效，覆盖安装不改变状态，恢复后仍按 Plan 支持项执行。详情见设计与影响审查。
