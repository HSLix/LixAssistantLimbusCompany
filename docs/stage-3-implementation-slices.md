# Stage 3 — Implementation Slices

状态：拆分与依赖已由开发者确认，六项均已发布并标记 ready-for-agent；步骤 1–3 已实现并有自动化及 Mac 真模型证据，步骤 3 的 Windows 工具实测按确认移至步骤 6；步骤 4 已通过自动化与开发者 Windows 原生 DPAPI 测试，开发者确认关闭 #327，新启动流程的真模型和实际认证延期至开发者 GUI 完成后验收，不计为已通过。步骤 5/6 尚待完成。新增 #330 Developer GUI 与共享多文件修复升级，四页全部在 2026-10-29 前交付并作为 #329 前置；详见 [设计](developer-gui-design.md) 和 [ADR 0029](adr/0029-use-explicit-candidate-edit-selection-and-continuous-developer-chat.md)。步骤 1–4 的勾选记录原有 CLI 基线，不表示 #330 新契约已经实现。Spec：[GitHub #323](https://github.com/HSLix/LixAssistantLimbusCompany/issues/323)，关联阶段跟踪 #312。

## 1 — [Mac 贯通 pi、图片与受限工具的最小调用](https://github.com/HSLix/LixAssistantLimbusCompany/issues/324)

**Blocked by:** None — can start immediately.

**What it delivers:** 在 Mac 上从 LALC 的 Python 调用入口启动 pi，使用临时连接参数和内存密钥，真实模型收到图片并调用一个受限的源码读取工具，返回最终回答。CLI 展示实际请求、图片标识、工具交换和结束结果，不持久化交互日志或 pi 会话；固定此次验证通过的 pi 版本供跨平台复测。此步骤只证明接入可行，不宣称已完成修复。2026-10-23 开发者明确缩小本步骤日志范围；正式日志仍属步骤 2。用法见 [pi 最小接入验证](pi-probe.md)。

- [x] 验证 RPC、扩展加载、实际图片输入、受限工具回调、终端事件展示和密钥传递，不仅检查版本或帮助。
- [x] 验证可以关闭框架默认终端、通用文件写入、未授权扩展/配置引入的工具与上下文；不把个人 pi 配置作为接入前提。
- [x] 验证模型请求计数、终止与取消所需事件/接口；检查是否存在框架内部请求和重试，不静默绕过后续请求上限或失败即停止的约定。
- [x] 仅在 CLI 展示完整过程，不持久化交互日志或 pi 会话；不展示密钥，不在持久配置中保存明文凭据。
- [x] 以真实模型调用和可检查的终端输出为结果；若 pi 不能满足必要边界，报告具体阻碍并回到选型讨论，不自行更换框架或供应商。

## 2 — [从 Default Manifest 完成受限单 Component 修复](https://github.com/HSLix/LixAssistantLimbusCompany/issues/325)

**Blocked by:** [#324](https://github.com/HSLix/LixAssistantLimbusCompany/issues/324).

**What it delivers:** 开发者通过独立修复 CLI 指定一个现有 Component，提供问题、异常和截图；LALC 从 Default 重建 Developer Candidate，真实模型只修改目标源码，调用现有 Validator 迭代，最终输出源码、Diff、校验结果与完整日志。

- [x] 来源和目标检查先于候选清空；没有有效 Default、加载失败、目标缺失不启动 Agent、不破坏旧草稿、不改选历史 Manifest。
- [x] 有效启动替换已有 Developer Candidate，可读全部候选文件但只写指定 Component；拒绝任意路径、其他源码及候选 Manifest 写入，不自动 Publish 或改变 Default。
- [x] 源码读取与修改复用 pi 的 read/edit，通过扩展或文件操作接口实施权限检查，不重写文本替换或编辑引擎；不把工作目录当作隔离，不开放通用 write 或终端工具。
- [x] 接收初始截图/异常/问题描述和 LALC 编写约束；不引入游戏模拟或候选自动运行。
- [x] Validator 反馈实际回到模型；结束时重新校验最终源码，输出实际 Diff，不把校验通过称为行为修复成功。
- [x] 默认 20 次请求并支持本次设置；超限、模型错误和取消停止并保留产物，信息不足时最终回答说明缺少什么并结束。
- [x] 完整日志和原始/最终产物在数据目录留存，后续重建候选不会抹掉前次记录；错误、取消与校验失败也有明确结束原因。

2026-10-23 实现证据：入口为 `lalc repair`，用法与可重复检查见 [单 Component 修复](agent-repair.md)。真实 pi + HTTP 替身验证受限编辑、实际 Validator 反馈、最终 JSON 分组、取消、错误、上限和日志保留；Mac Gemma4 用 4 次请求、1 组交互将固定纯计算缺陷修为 `sum(values)`，通过四组独立输入输出断言。此结果不代表 Windows 或游戏行为验收完成，未替代步骤 5/6。

## 3 — [Agent 使用完整的 Asset、Trusted Action 与游戏观察工具集](https://github.com/HSLix/LixAssistantLimbusCompany/issues/326)

**Blocked by:** [#325](https://github.com/HSLix/LixAssistantLimbusCompany/issues/325).

**What it delivers:** 在实际修复调用中，Agent 发现 Asset 逻辑名、查看目录标签及一张或多张图片，查询应用动作契约，取得当前游戏截图并现场裁剪新增 Asset，再据此修改指定 Component 和调用 Validator。Windows 验证实时画面与裁剪，Mac 验证只读工具；除受限新增外不修改已有素材，不执行游戏控制。

- [x] 分别提供全局逻辑名文字树、指定逻辑名下全部文件名及标签内容、完整逻辑名/完整哈希选图三个只读工具。
- [x] 图片工具一次支持一张或多张，模型实际收到图片并能对应逻辑名与哈希；日志保留图片和实际返回。
- [x] 标签缺失如实返回，不修复元数据；非法逻辑名、越界路径、哈希前缀与内容不符被拒绝。
- [x] 一个动作查看工具从实际注册表和现有签名/docstring 派生全部动作的分类、参数和返回说明，不暴露实现源码、不执行动作。
- [x] 自动化检查和真实模型调用均确认只读结果与写入权限，原图、旧标签及动作注册保持不变。

- [x] 实时截图复用唯一 Target Window 与焦点检查，返回实际新图及尺寸，不伪装旧图为当前状态。
- [x] 裁剪接收逻辑名、客户区像素区域和可选标签，每次重新截图后裁剪，不从保存截图裁剪、不开放文件导入或任意输出路径。
- [x] 新哈希保存新图、标签与来源，缺省标签明确为空；同名同哈希直接复用原图和旧标签，明确返回已存在，不覆盖其他映射。
- [x] 新 Asset 无需 Publish 即可被共享库读取，失败或取消保留新增产物；开发者裁剪/tag 工具的标签替换语义不变。
- [x] 不增加点击、按键、候选执行或运行中 Working Manifest 接入；不支持的平台如实报告工具不可用。
- Windows 真模型截图、裁剪及重复裁剪的旧标签保护移至步骤 6（#329），结合步骤 5（#328）的真实样例综合验收，不再作为 #326 关闭前置。

2026-10-23：六个工具已接入公开修复 CLI，权限、图片回传及现场工具通过自动化契约检查；Mac Gemma4 以 6 次请求实际读取多图、动作契约并收到越界拒绝，基线与素材不变。每次截图/裁剪均可恢复并置前唯一窗口，多图任一项失败则整次失败。开发者确认按已通过的实现与测试关闭 #326；Windows 实机综合验证结合 #328 的真实样例在 #329 中完成，不计为本步骤已通过的实测；复现入口见 [工具验收](agent-repair.md#326-工具验收)。

## 4 — [持久模型设置与 Windows DPAPI 命名密钥用于修复](https://github.com/HSLix/LixAssistantLimbusCompany/issues/327)

**Blocked by:** [#325](https://github.com/HSLix/LixAssistantLimbusCompany/issues/325).

**What it delivers:** 开发者保存远程服务地址、模型和请求上限后，后续修复直接沿用；Windows 的命名 API key 由 DPAPI 存储并用于实际认证，Mac 开发仍使用临时内存密钥。

- [x] 普通配置与密钥分离；未设置请求上限时为 20，保存修改供以后沿用，单次覆盖不修改已保存值；本次有效配置固定并记入日志。
- [x] 连接开发者指定的 llama.cpp 地址/模型，检查服务状态和图片能力并验证实际图片输入；不把未加载与不支持图片混报，不自动换供应商或模型。实际传输经 pi/HTTP 替身检查，新的真模型启动流程待复测。
- [x] Windows 实现 DPAPI 命名密钥保存与读取，不限定模型 API key 类型，不预建其他密钥业务；实际认证不要求把明文写入 pi 持久配置。
- [x] Mac 首版不保存密钥，运行时临时输入；日志、模型上下文、候选文件、明文命令参数和普通配置均不泄露密钥。
- [x] Windows 原生 DPAPI 存取和损坏密文检查：开发者回报 `test_windows_native_dpapi_roundtrip_and_corruption` 为 `1 passed in 2.43s`。
- [ ] Windows 实际模型认证及新启动流程的真模型检查：开发者确认延期至开发者 GUI 完成后验收，不作为 #327 关闭前置，未计为通过。

2026-10-23 #327 确认并实现：现有用户数据目录一套当前设置，CLI 单次覆盖优先；没有显式模型禁止启动。完整 API 基础路径不追加 `/v1`。加载状态检查及一次无工具图片请求先于候选重建；该请求计入同一次 repair 上限，最低上限为 2。入口为 `agent-config`、`secret-set` 和既有 `repair`，用法及 Windows 验收见 [配置与认证验收](agent-repair.md#327-配置与认证验收)。本次非 Agent 回归 229 passed、35 skipped；相关配置与真实 pi/HTTP 替身测试合计 62 passed、5 skipped（当时未运行的 Windows 与真模型检查不计为通过），报告在 `.generated/issue-327-tests.xml`。随后开发者补充 Windows 原生 DPAPI `1 passed in 2.43s`，确认按已完成实现与检查关闭 #327；新启动流程的真模型及 Windows 实际认证留待开发者 GUI 完成后验收，不以替身结果代替。

## 5 — [开发者准备真实单 Component 缺陷与复现材料](https://github.com/HSLix/LixAssistantLimbusCompany/issues/328)

**Blocked by:** None — can start immediately.

**What it delivers:** 准备一个真实游戏中的可重复失败案例，确定只需修改一个现有 Component，保存原始版本、初始截图、异常、输入、复现步骤和预期行为，为最终前后对照提供固定基线。

- [ ] 不是单纯语法错误；原始 Component 在既定前置状态下能够重复表现行为缺陷。
- [ ] 缺陷种子、所需资源和人工准备游戏状态的方法被保存，不依赖已清空的 Developer Candidate。
- [ ] 确定人工如何观察修复成功，以及如何安全重建前置状态；不实现游戏状态模拟或离线行为判定工具。
- [ ] 由开发者选择并提供案例，作为最终 demo 的外部输入；不阻塞前四项的工具开发与接入验证。

## 6 — [Windows 集成验收并交付 TA demo](https://github.com/HSLix/LixAssistantLimbusCompany/issues/329)

**Blocked by:** [#326](https://github.com/HSLix/LixAssistantLimbusCompany/issues/326), [#327](https://github.com/HSLix/LixAssistantLimbusCompany/issues/327), [#328](https://github.com/HSLix/LixAssistantLimbusCompany/issues/328), [#330](https://github.com/HSLix/LixAssistantLimbusCompany/issues/330).

**What it delivers:** 在固定版本 pi 和指定真实模型下，对开发者案例完成一次完整修复。人工审阅发布后，在 Windows 游戏中展示原问题消失，并将可复现说明、交互日志、候选/Diff/校验和游戏前后对照交付 TA。

- [ ] 通过 Developer GUI 明确选择基础 Manifest 并初始化 Candidate，真实模型读取上下文与图片、使用受限工具并修改授权文件，完成最终 Validator 校验；案例仍可只需修改一个 Component。
- [ ] Windows 确认实时截图、现场裁剪、重复图片原标签保护及 DPAPI；需要时引用同固定版本/同实现的已留存实测，不要求把不相关操作硬塞进缺陷案例。
- [ ] 人工审阅并沿用既有 Publish/运行流程，保存修复前失败和修复后游戏行为成功的对照；只通过 Validator 不算完成。
- [ ] 核对正式源码、已有 Manifest、原图、旧标签和 Default 的 Agent 写入边界；仅授权的已有候选文件变化与允许的 Asset 新增，plan.json 只读且不能新建/删除候选文件。
- [ ] 提供启动、配置、工具范围、上限、信息不足/取消/错误、日志定位与人工验收说明，并说明 Candidate 仅在明确确认后重建，New Conversation 和后续修复保留草稿。
- [ ] 在 2026-10-29 前完成 TA 交付；目标 10 月 28 日完成演示与证据，保留交付余量。未完成的真模型/实机验收明确列出，不以替身填补。

## 7 — [Developer GUI 与共享多文件连续修复](https://github.com/HSLix/LixAssistantLimbusCompany/issues/330)

**What it delivers:** 现有 PySide6 上的 Capture、Runner、Agent Settings、Agent Repair，及共享 GUI/CLI 的 Candidate 生命周期、多文件授权、可选图片、连续对话、累计 Diff 和逐轮日志；2026-10-29 前完成，作为 #329 的直接前置。完整边界与检查项见 [设计](developer-gui-design.md)。

2026-10-23 实施：四页和共享宿主已实现；普通回归 235 passed、21 skipped，显式真实 pi/HTTP 替身检查 16 passed、4 skipped，四页已做 offscreen 渲染检查。下列作为整体验收清单保留；真模型连续修复、Windows DPI/焦点/坐标/裁剪及 GUI DPAPI 实际认证尚未验收，不能关闭 #330 或以旧证据代替，详见设计文档实施状态。

- [ ] Capture 坐标复用 Runtime，失效后手动刷新；冻结截图、框选、预览和确认后保存同一裁剪及逻辑名/标签，支持打开 Asset 目录。
- [ ] Runner 持久保存独立选择，四类入口/JSON/暂停恢复取消复用既有服务，实际 Base Manifest 可见，不改变 Default 或 Candidate。
- [ ] Settings 复用配置与 DPAPI，密钥不回显，空输入不覆盖；请求上限默认 20、最小 2，按用户轮次计。
- [ ] Repair 显式候选初始化/替换确认，多选/全选已有文件、无目标分析和素材工具；plan.json 只读，禁止文件新建/删除。
- [ ] 连续对话、可选图片、真实 Host 状态、每对话逐轮日志、累计 Diff、人工 Validate/Publish/独立 Default，保留取消和失败产物。
- [ ] 共享 Host 强制 Runner/Agent/Capture 互斥，关闭时安全取消，页面切换不取消。完成相关自动化、真模型与 Windows 验收，不以旧 CLI 证据代替新能力。

## 依赖与时序建议

- 原六步依赖保持；1–4 的已完成记录保留，5 的真实缺陷由开发者准备。
- 当前推进 #328 案例和 #330 GUI；#329 等待两者及原有工具/配置前置，完成延期的新启动流程、Windows 认证/截图/裁剪和真实游戏验证。
- #330 内按可验证增量落实：共享 Candidate/授权 → Runner 与 Host 互斥 → Capture → Settings → 连续 Repair/日志/Diff 与人工发布 → 真模型/Windows 联调。每个增量连接实际服务，不以假状态或假按钮冒充实现。
- 目标 10 月 28 日完成 GUI 联调与演示证据，2026-10-29 前交付；这是排期目标，不是已完成证据。分发打包不作为本期门槛。
- 原六项已建单，原生依赖保留；新增 #330 阻塞 #329。父 Spec #323 和原阶段跟踪 #312 不改写，不以本次扩展重开已验收票据。
