# #317 邮箱 Workflow 验收与 Stage 2 收尾指导

检查日期：2026-10-22。本文是实施与验收指导，不是已经通过的验收报告。

## 1. 检查结论与适用基线

**可以在当前基础上实现并验证 #317。基础能力已有实现；邮箱业务本身尚未实现，Stage 2 实现尚不能宣布结束。**

本次检查对象是 HEAD `9c740e6ab15deafd02e114e9b2feec9bf16b1dc6` 加当前未提交工作区，特别是 #321 的 schema 2、应用动作注册、专属 Asset Library、Run 会话生命周期和测试夹具迁移。单独检出此 HEAD 不能复现本文所述完整基线。正式验收必须重新记录最终提交、剩余工作区差异和环境。

本轮实际执行 `QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest -q`：**173 passed in 2.35s**。这证明当前自动化回归通过，不证明邮箱业务或 Windows 实机通过。原先 `uv run --frozen --all-extras pytest -q` 因本机默认缓存目录访问受限未启动，故本轮采用现有虚拟环境直接运行。

新增目录按本次要求使用单数 `example/`，仅保存本指导；不恢复 #321 已删除的旧 `examples/`、Action 转发文件或兼容运行时。

## 2. 要求来源、关联 issue 与结束边界

| 来源 | 2026-10-22 实时状态 | 本次验收的责任 |
| --- | --- | --- |
| [#307 Stage 2 父 Spec](https://github.com/HSLix/LixAssistantLimbusCompany/issues/307) | OPEN | 从完整 Manifest 到真实、model-free 邮箱任务，汇总子 issue 与最终证据 |
| [#308](https://github.com/HSLix/LixAssistantLimbusCompany/issues/308)、[#309](https://github.com/HSLix/LixAssistantLimbusCompany/issues/309) | CLOSED | Manifest 加载校验、开发闭环和 fake Workflow 基础 |
| [#310 Step Recovery](https://github.com/HSLix/LixAssistantLimbusCompany/issues/310) | OPEN | 当前已有相关实现和测试，但需按现行契约重新逐项验收；历史评论有实现后撤回记录，不能据早期通过评论认定关闭 |
| [#311 Working Manifest](https://github.com/HSLix/LixAssistantLimbusCompany/issues/311) | OPEN | 完整切换、兼容性、持久历史和不自动回滚，需独立核对验收 |
| [#313 Plan / Ledger](https://github.com/HSLix/LixAssistantLimbusCompany/issues/313) | OPEN | 全量预检、逐项执行、取消、统计与持久化，需独立核对验收 |
| [#314](https://github.com/HSLix/LixAssistantLimbusCompany/issues/314) | CLOSED | Windows connect 已有真实截图及身份检查证据；该证据不代表正式邮箱 Workflow 已通过 |
| [#315 控制与接管](https://github.com/HSLix/LixAssistantLimbusCompany/issues/315) | CLOSED | 已有动作和人工恢复基础；当前邮箱集成仍须验证接管、释放、Resume、Stop |
| [#316 Asset 匹配](https://github.com/HSLix/LixAssistantLimbusCompany/issues/316) | CLOSED | 原格式的 Windows 裁剪→发布→检测实验已通过；不能代替 #321 新格式的集成验收 |
| [#321 注册与库迁移](https://github.com/HSLix/LixAssistantLimbusCompany/issues/321) | CLOSED | **额外关联前置**。本地实现及 173 项回归、macOS 替身打包探针获确认；Windows 游戏裁剪／确认／publish／检测、接管释放及 Windows onedir 验收移交 #317 |
| [#317 邮箱 Task Workflow](https://github.com/HSLix/LixAssistantLimbusCompany/issues/317) | OPEN | 邮箱记录/fake 覆盖、开发环境实机闭环，以及 #321 移交的 Windows 包内验收 |
| [#312](https://github.com/HSLix/LixAssistantLimbusCompany/issues/312) | OPEN，现已改为 Stage 3 独立 Component 修复 | 不作为 Stage 2 结束前置；不在 #317 接入模型 |

现行本地依据：

- [领域语言](../CONTEXT.md)、[Stage 2 执行契约](../docs/stage-2-workflow-and-execution-contract.md)、[实施切片，尤其 Slice 8 和完成规则](../docs/stage-2-implementation-slices.md)。
- [ADR 0019](../docs/adr/0019-resume-user-interrupted-steps-manually.md)：接管只走显式人工 Resume。
- [ADR 0021](../docs/adr/0021-retain-created-files-and-defer-resource-maintenance.md)：保留文件，审批或拒绝均不触发资源清理。
- [ADR 0023](../docs/adr/0023-register-trusted-actions-in-the-application.md)、[ADR 0024](../docs/adr/0024-use-a-dedicated-asset-library-for-each-manifest.md)：应用动作注册、每 Manifest 专属库、新格式与生命周期。
- [ADR 0025](../docs/adr/0025-validate-component-repair-before-runtime-agent-recovery.md)：Stage 3 为独立 Component 修复，原运行时 Agent 工作移交 Stage 3.5。

### 阅读旧要求时须处理的差异

1. #307 仍有独立 verifier、terminal verifier、timeout 等旧表述；#310/#311 也残留旧异常名或 `verify` 表述。按现行 Stage 2 契约和 #317 明确修订执行：业务检查是普通 Step，Task 合法正常返回即成功；非用户失败使用 `ExecutionFailure`，用户信号独立处理。没有独立 verifier 回调、框架自动超时或通用重试策略。
2. 可观察的停滞由具体 Step 基于状态及进度证据判断。预期转换中的一次模板未命中既不等于完成，也不自动等于超时失败；具体转换与停滞判据必须由实机状态支持。
3. 当前控制范围是 click、Esc/P/Enter、drag、协作 wait。drag 已提供长动作验收路径，不需为了旧词汇另加 long_press。截图时机归 Step；重要业务动作后的新观察由邮箱代码负责。
4. 失焦时当前实现暂停，不自动抢回焦点。单独验证“无物理输入的失焦→旧图失效→人工 Resume→聚焦、新图、重新判断”，不要求新增自动聚焦恢复。
5. #317 早期写“打包交后续”，但其 **Accepted current contracts and #321 handoff** 明确增加 Windows onedir 验收。当前完成范围包含这一移交项。
6. 总规划中 Stage 2 “accepted and complete”描述的是契约收敛；实施切片明确只有 Slice 8 自动化和监督式 Windows 验收通过后，实现才算完成。收尾时需消除会误导读者的阶段状态措辞。

## 3. 当前实现能支撑什么，还缺什么

| 要求 | 已检查的实现入口 | 已执行的验证及边界 |
| --- | --- | --- |
| schema 2 校验、发布、加载及专属库 | `src/lalc/manifest.py`、`assets.py` | `tests/test_manifest.py`、`test_manifest_transition.py` 已随全套通过 |
| 应用统一 observe/control 动作与调用权限 | `src/lalc/actions.py`、`runtime.py::trusted_action` | Workflow、Manifest、Asset、控制回归通过；不是邮箱业务覆盖 |
| 异步 Run、窗口会话、监听和清理 | `application.py::start/_start_session/_worker` | `test_manifest_transition.py` 覆盖纯计算 Run/Plan 也先连接监听；平台为替身 |
| 当前 Step 恢复与完整 Working Manifest | `runtime.py::_recover_step/_try_manifest_choices`、`application.py::_select_working_manifest` | `test_recovery.py` 通过；#310/#311 仍需逐项验收和 issue 收尾 |
| Plan 和 Ledger | `application.py::_run_plan`、`ledger.py` | `test_plan.py` 通过；#313 仍开放 |
| 物理接管、释放、人工 Resume、Stop | `control.py::InputSession`、`runtime.py::_wait_manual_resume/_resume_step` | `test_input_control.py` 通过；当前邮箱实机未跑 |
| 裁剪→Candidate 库→发布→匹配及 Usage Index | `application.py::crop_candidate_asset/_match_asset`、`assets.py`、`__main__.py` | Asset 和迁移回归通过；新格式 Windows 集成待执行 |
| 邮箱业务状态、正式 Component、实际模板 | `src/`、`tests/` 搜索未发现完整邮箱实现；GUI 仅有 `tasks.claim_mail` 占位提示 | **缺失**；现有测试不证明正常领取或最终业务检查 |
| Windows 包内真实邮箱执行 | `LALC.spec`、`packaging_entry.py` 提供构建入口 | **本轮未执行**；macOS 替身探针不证明 Windows 输入或真实游戏效果 |

可实现性的判断依据是上述生产入口已连通，剩余工作可由正式 Component、实际模板和测试完成，不需先接 Agent、OCR、旧 Pipeline 或另建执行器。模板阈值、实际画面及业务判据还需 Windows 观察；没有真实画面时不能宣称已经校准。

## 4. 实施前先确定可检查的邮箱目标

先在 Windows 记录游戏语言、客户区尺寸、DPI/缩放、实际邮箱画面和关键模板，再把支持范围写入邮箱 Task/Step 的中文说明与测试。下列为建议的最小目标，需用实际画面固定下来：

- 入口：已登录且主界面可操作，或已在邮箱/本次领取的可识别中间状态；不包含自动登录、更新、战斗中退出等扩展路径。
- 目标：领取当前可领取邮件，处理实际出现的奖励确认，重复观察直到邮箱中已无可领取项。
- 结束：退出邮箱后回到可明确识别的主界面；“点击了返回”不是结束证据。
- 已完成：明确识别邮箱无可领取项后同样退出，并正常返回。不能把“没有匹配到领取按钮”单独作为无可领取项的证明。
- 若实际存在暂不可领取邮件，不把“邮箱清空”当目标；检查的是可领取项已处理。不要推断未观察过的奖励数量或领取成功数。

建议入口逻辑名为 `tasks.claim_mail`。Task 通过字面量 `ctx.call()` 组织准备、领取、退出和最终检查 Steps；有复用需要时再用 Subworkflow。每个 Step 从新观察识别自己负责的部分完成/已完成状态，不依赖上次中断前的局部变量，不直接调用原生窗口或输入接口。

结果须满足实际声明的 JSON-compatible 返回注解，例如 `dict[str, bool | str]`，可返回 `{"mailbox_complete": true, "end_state": "main_menu"}`。这是建议业务结果，不是增加运行时状态枚举。运行时外层仍为 `status: success|failure`；最终检查 Step 在证据不成立时抛 `ExecutionFailure`，不能正常返回一个失败标志让 Task 被记成成功。

## 5. 第一轮：可重复的记录 / fake 验收

测试自有 Component、图像记录、动作替身放在 `tests/`，正式邮箱源码须有可维护的交付位置及 Candidate 构建说明，不能只存在于 Git 忽略的个人 `candidate/`。测试使用正式邮箱源码，替换环境和动作；不要另写一个必然通过的假邮箱 Workflow。

通过 `ManifestManager` 校验发布，再从 `ApplicationService.start()` 进入，使用 `wait_for()`、公开 `state`、Trace 和 Ledger 断言。通过应用层注册 fake 动作或注入窗口/输入替身，不向 Manifest 填 `trusted_actions`，不直接调用私有 Executor。可参考 `test_workflow.py`、`test_assets.py`、`test_input_control.py` 和 `test_manifest_transition.py`。

| 场景 | 提供的观察序列 | 必须证明 |
| --- | --- | --- |
| 正常领取，含重复领取 | 主界面→邮箱有奖励→确认/新奖励→无可领取项→主界面 | 重要控制后观察标识更新，效果与顺序正确，最终检查执行；Run/Ledger 成功，Agent 调用为零 |
| 已经完成 | 主界面或邮箱→明确的无可领取项→主界面 | 不发送领取动作；合法退出并检查后成功 |
| 预期转换 | 已确认的加载/动画状态→可操作状态 | 转换期间只做必要观察/协作等待，不反复点击、不因单次空匹配宣告完成 |
| 可观察停滞 | 相同可操作状态持续存在且前一动作未产生预期效果 | 按 Step 明确的进度判据失败；走确定性恢复，仍失败则异常和安全终止；无无限盲点 |
| 未知状态 | 既不满足完成、可操作，也不满足已支持转换的画面 | 不猜坐标、不发送新控制；保留失败观察及诊断 |
| 最终业务检查失败 | 领取/退出动作已返回，但完成或主界面证据不成立 | 普通检查 Step 失败，不能因前面点击成功而返回 Task success |
| 部分动作已生效后 Resume | 领取已生效但确认/返回未完成，再进入同一 Step | 从新观察继续剩余职责，不重放已完成的领取，保持 Workflow 调用链 |
| 接管 / Stop | 第一次观察、两个 Step 间、控制动作中分别触发 | 接管停止后续控制；显式 Resume 前无控制；Stop 后无新动作并完成已持有输入的释放 |

以上“无真实输入”须由 fake 后端或动作记录证明。至少一个记录图像用例应经过生产匹配动作，证明真实像素→模板→客户区坐标→业务判断这条链；纯符号状态替身不能代替这部分。

未知/停滞首先走 Stage 2 的确定性恢复：零匹配仍允许当前 Step 一次新的检查/调用；规则检测异常、多匹配或恢复异常直接进入 Execution Anomaly。最终无合法继续路径时任务失败。测试不能错误断言所有失败都只调用 Step 一次，也不能把用户接管当公共异常自动恢复。

建议新增 `tests/test_mailbox_workflow.py`，文件头写中文覆盖范围与根目录完整运行命令。该文件尚不存在，以下第一条应在实现后执行：

```bash
QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest -q tests/test_mailbox_workflow.py
QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest -q
git diff --check
```

## 6. 第二轮：Windows 开发环境监督式验收

每轮先记录最终源码版本/差异、Windows 与游戏版本、游戏语言、Python/依赖版本、客户区尺寸及缩放。游戏须为唯一可选 Target Window，实际前台可操作。CLI 从项目根目录运行；已有非空 Candidate 时先人工检查，不为验收盲目清空它。

1. `uv run lalc data-dir` 确认实际数据根；`uv run lalc connect` 检查客户区截图及身份。connect 只是诊断，不创建 Run，也不把窗口句柄跨进程传给后续 Run。
2. 使用 `uv run lalc init` 建立 Candidate；已有保留 Manifest 可用 `init --from <id>`。按交付说明放入正式邮箱源码、完整 schema 2 映射与 `candidate/assets.json`。
3. 在实际游戏画面上用 `uv run lalc crop-asset <语义名> --language <语言> --region <客户区矩形JSON>` 获取模板。区域须从当前实际客户区测量，不能照抄测试坐标。检查返回的 PNG 与来源信息。
4. `uv run lalc validate` 应通过且不发布任何文件、不修改 Default。`uv run lalc publish` 得到 Manifest A；保留该 UUID、对应库及图片 SHA-256。
5. 将本次实际输入写入 UTF-8 JSON 对象文件 `mailbox-inputs.json`，无参数时内容为 `{}`。执行 `uv run lalc run tasks.claim_mail --manifest <A的UUID> --language <语言> --inputs-file mailbox-inputs.json`。`--language` 必须与实际游戏一致，不沿用默认 en。
6. 完成一轮有奖励领取，保存“邮箱已无可领取项”和“退出后主界面”的新截图。再跑已完成场景，检查没有额外领取。没有可用奖励时，记录该场景未执行，不能用已完成场景代替正常领取。
7. 在明确安全的业务边界制造物理鼠标/键盘接管。暂停期间人工改变为已支持的部分完成状态，确认不自动动作；CLI 按提示输入 `r`，或 GUI 点击恢复。Trace 应显示安静边界、聚焦、新观察、适用的 condition 检查及当前 Step 新调用。已经返回的 Step 不得重跑。
8. 保留安全区域中的长 drag 验收入口，接管正在持有的触点，证明该次触点释放恰好一次、动作结果 unknown、暂停且不自动重试。邮箱业务无需 drag 时，用同一 ApplicationService/注册动作/会话的独立验收 Step；不能拿旧实验脚本代替集成路径。
9. 在 Run 启动后的首次观察边界、暂停中和长动作中分别验证 Stop（CLI 为 Ctrl-C，GUI 为停止）。Stop 后不得开始新的业务动作；允许完成已持有输入的必要释放及证据/结果写入。不能把必要释放误判为 Stop 失效。
10. 单独造成无物理输入的失焦，检查旧图失效、暂停和人工 Resume 后的新观察；不得立即发送失焦前决定的控制。窗口消失、Resume condition 不成立等故障至少保留自动化覆盖，实机未执行的明确标注。

### #321 移交的 Asset 集成项

- 在同一语义名＋语言下，选择实际内容不同的新裁剪，先拒绝替换：Candidate 库、旧图、已发布 A 的 Manifest/library 均保持原字节；不同内容是触发确认的前提。
- 再明确确认替换：仅 Candidate 映射改指向新 PNG，路径含完整 SHA-256；旧 PNG 不变。相同内容应复用，无需重复确认。EOF/取消的无写入边界由回归覆盖，实机有跑则记录。
- 重新 publish 得到 B，Component 源码不变也应产生新 Manifest/library。用 B 匹配当前目标，检查 Trace 的语义名、实际语言、图片路径/完整哈希及命中坐标指向新库。
- A 的 Manifest/library 和旧图逐字节保持不变。用 A 重新加载仍解析旧映射；旧模板可能不再匹配当前新画面，不能要求它也命中。B 的使用不能依赖运行时重读或回退到别的库。

## 7. 第三轮：Windows onedir 包内验收

在 Windows x64 按 [README 构建流程](../README.md) 执行；以下为 PowerShell 示例。构建会同步依赖，完成后若还需开发测试，重新同步测试组。

```powershell
$env:UV_CACHE_DIR = ".generated/uv-cache"
$env:UV_PYTHON_INSTALL_DIR = ".generated/python312"
uv sync --locked --no-editable --no-default-groups --group build --all-extras
uv run --no-sync pyinstaller --clean --noconfirm LALC.spec
```

复制整个 `dist/LALC/` 到无系统 Python、无开发环境依赖的 Windows 验收环境。不要只复制 exe。正式源码通过包内 CLI 的既有 Candidate→validate→publish 路径加载到可写数据目录；不要假设 PyInstaller 自动打包了 Candidate、模板或已发布 Manifest。

用 `dist/LALC/LALC.exe` 替换上一节的 `uv run lalc`，在固定工作目录完成新格式裁剪、拒绝/确认、发布和检测，并运行相同邮箱 Workflow、接管/Resume/Stop。无参数启动 GUI 时先用包内 `set-default <UUID>` 选择正确版本，再填入口和 JSON；当前 GUI 没有语言选择，非默认语言应走带 `--language` 的 CLI，不把语言配置差异误判为匹配错误。

当前 spec 为 `console=False`：Windows 包内 CLI 交互输入/输出能否使用也须实际检查。若 crop 确认或暂停后的 `r` 提示不可操作，作为本票包内验收阻塞处理；修复后重测。`--packaging-probe` 是内部诊断入口，不能用替身探针成功替代正式包内用户路径。

必须证明包内 NumPy/OpenCV 能完成实际截图解码、匹配和裁剪，应用统一动作注册可用；执行期间不依赖源码 checkout、系统 Python 或旧 runtime。只成功启动 GUI、只构建成功、或只跑 macOS 包都不足以通过。

## 8. 每个场景的证据与判定

通过 `lalc data-dir` 获取根目录（Windows 默认 `%LOCALAPPDATA%/LALC`）。当前实际产物：

| 证据 | 位置 / 核对重点 |
| --- | --- |
| Run Result | CLI JSON 或公开 `service.state['result']`；Trace 最终 `run_finished.result`。成功含规范化 output；失败含原始含义的 failure_code/message |
| Trace | `traces/<run_id>.jsonl`；Component/动作顺序、身份、参数、观察、匹配、恢复、暂停、释放、结束 |
| Ledger | `ledger/<run_id>.json`；Task/Subworkflow 结果、时长、恢复与 Agent 计数，不能以 success 掩盖业务检查失败 |
| Manifest 选择历史 | `runs/<run_id>.json`；Base、Working、attempted IDs，关联 `manifests/` 和 `asset-libraries/` |
| 显式保存的现场图像 | `evidence/<run_id>/<observation>.png`；由 `observe.capture_screen(save=True)` 保存，Trace 的 screenshot_saved 关联同次观察 |
| Asset 与来源 | `assets/`、`asset-provenance/`；PNG 完整哈希、实际裁剪观察和区域 |
| Usage Index | `asset-usage.json`；非空匹配记录全部最终命中及 Run/Trace/观察，空匹配不更新 |
| 应用错误 | `logs/lalc.log` 及失败结果/Trace；保留原始 traceback 和异常链 |

普通观察默认只有内存图像；Trace/Usage Index 有观察引用不代表 PNG 已保存。邮箱实现应在关键完成状态、未知/停滞和业务检查失败时显式留图，并让判断使用对应的新观察。不要事后另截一张图冒充失败当时的画面。

按实际时间顺序核对：重要控制→新观察→效果判断；接管中止→持有输入释放→暂停→明确 Resume→聚焦/新图→condition（如有）→Step 新调用。Stop 后只允许释放和收尾。每个曾按下的输入核对其对应释放，不把整个 Run 的释放次数固定为一。

每场景填写：环境与版本、运行入口/输入、Manifest ID、Run ID、初始及最终画面、预期、实际结果、Trace/Ledger/图像路径、结论 `通过/失败/未执行`。实机观察到的现象、自动故障注入和未跑项分开记录；不把历史 12 ms 当 SLA。

## 9. #317 与 Stage 2 的完成清单

### #317 可宣布完成的条件

- [ ] 正式邮箱源码与交付步骤进入版本管理；不依赖旧 runtime 或仅存在本机的 Candidate。
- [ ] 第 5 节记录/fake 场景全部通过，包含真实像素匹配覆盖；无真实输入、无模型调用。
- [ ] Windows 开发环境完成正常领取、已完成、最终业务检查及接受的结束状态。
- [ ] 当前邮箱集成验证从 Run 启动开始的监听、接管、无重放、显式 Resume、新观察、Stop 和释放。
- [ ] #321 移交的 Windows 裁剪/拒绝/确认/publish/检测与旧文件保留完成。
- [ ] Windows onedir 在无系统 Python 的环境通过正式用户路径，图像依赖与动作注册可用。
- [ ] 最终版本回归与 `git diff --check` 通过；所有要求关联到可检查证据，失败/未执行项未冒充通过。

### Stage 2 实现可宣布结束的条件

- [ ] 逐项核对 #310、#311、#313 的现行要求及当前实现/测试，补足缺口并完成各票验收记录；不能仅因邻近回归通过而自动关闭。
- [ ] #308/#309/#314/#315/#316/#321 的前置结果与保留证据可追溯，#317 通过。
- [ ] 对照实施切片 Slice 1–8 汇总最终版本、自动化、Windows 开发运行和 Windows 包内证据。
- [ ] 在获得关闭授权后，将上述结果回填对应 issue，并以 #307 汇总收尾；同步规划/README 中容易混淆设计完成与实现完成的状态文字。
- [ ] #312 当前 Stage 3 独立修复、Stage 3.5 Runtime Agent、发布后子进程隔离 TODO 保持各自范围，不塞入 Stage 2 完成门槛。

本指导不执行真实游戏、构建 Windows 包或关闭 issue。完成当前审查和文档只表示验收路线已明确。
