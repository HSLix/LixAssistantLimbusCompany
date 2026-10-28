# Stage 4 — Vertical Implementation Slices

状态（2026-10-27）：设计与以下四阶段拆分已由开发者确认（原 1/2 合并、原 3/4 合并）；四票已发布 GitHub；#331 已在本地实现并经开发者确认关闭，真实使用测试留待后续，验证和未验收边界见[实施记录](stage-4-331-implementation.md)；#332 已完成本地实现及定向验证，见[实施证据](stage-4-332-implementation.md)；#333 已完成本地双语及语言重载实现，已获开发者人工验收确认并关闭 #333（[证据](stage-4-333-implementation.md)）；#334 尚未完成。每阶段独立可演示、验证，不按 schema/API/UI/测试横向拆分。依据 [Stage 4 规格](stage-4-extensible-user-gui.md)、[ADR 0032](adr/0032-use-python-plans-and-coexisting-user-developer-guis.md) 及[影响审查](stage-4-design-impact-review.md)。

直接依赖：1 → 2 → 3 → 4。已使用 ready-for-agent 和 GitHub 原生 blocked-by；不修改或关闭既有父议题。

## 1 — Python Plan 与双窗口执行闭环

**GitHub：** [#331](https://github.com/HSLix/LixAssistantLimbusCompany/issues/331)

**直接阻塞：** 无，可立即开始

**交付行为：** 用户从 Dashboard 选择 Default Manifest 并运行唯一 Python Plan；开发者可并存打开工具窗口，编辑 Candidate Plan、发布并试运行，所有执行/Agent/Capture/Candidate 冲突操作共用互斥。

- [x] 每个可运行 Manifest 各有且只有一个正式 Python Plan；唯一性、源码角色、稳定逻辑名、内容哈希、完整引用及调用权限贯穿初始化、校验、发布、加载和执行。旧不可变发布物不补写，缺失合法 Plan 明确报告不兼容；相关样例与调用方同步迁移。
- [x] Plan 接收次数和按页面 ID 组织的配置快照，支持 JSON 兼容的混合嵌套配置并复制输入；不全面放宽其他 Component 的输入契约。Plan 调用 Task，不能绕过 Task 直接操作游戏；既有 Task/Subworkflow/Step 调用规则和字面量目标约束保持。
- [x] Plan→Task 成功返回业务 output，普通失败返回原始错误码及说明并继续下一次调用；重复次数中的失败不跳过后续重复。取消、无法继续的环境错误和 Plan 自身错误结束执行，不回放已完成操作。
- [x] 执行器保留同一 Working Manifest、全部实际 Task 结果、Ledger、Trace、错误及取消证据；遍历完成与全部 Task 成功分别表达，不要求业务 Plan 自建结果账本。正常返回遵循 JSON 兼容契约。
- [x] Developer Agent 能编辑已有 Candidate Plan、Validate、Publish，再显式选择已保存 Manifest 试运行并查看结果；Python 宿主、pi 工具、提示词与权限/快照一致，不能执行可变 Candidate 路径，不开放外置 GUI 页面写入或运行时自动修复。
- [x] 已有 GUI/CLI 调用方、示例、fixtures 和相关断言同步移除 JSON Plan 执行，不留隐含旧分支或自动转换层，也不自动删除用户旧数据。
- [x] 用示例证明成功→失败→成功、取消跳过后续、Plan 自身错误保留已完成结果、不可变源码拒绝篡改及发布后试运行；普通回归通过，Agent 接入测试仅显式选择相关文件并标记 Agent，替身不计为真实模型验收。
- [x] 默认入口打开 User Dashboard，另有 Developer 启动入口；两窗口同进程、同一 Qt 事件循环，共用应用服务和 DeveloperHost。重复启动归并/唤起已有窗口，不能产生另一执行服务；User Settings 的开发者按钮提示用途后打开或激活 Developer，不关闭 User。
- [x] User 有左侧导航和 Dashboard/General Settings 固定页；Dashboard 左侧显示可实时刷新选择的 Default Manifest、开始按钮，右侧为后续信息区域。提供最小已发布示例 Plan，实际走启动、结果与日志，不伪造运行状态。
- [x] 执行窗口阻止所属 User 主窗口操作，提供暂停/继续/Stop；运行结束关闭执行窗口，使用统一应用内通知显示实际结果，多条可共存、用户关闭、不跨重启恢复。Developer 试运行模态范围不阻塞另一侧普通配置。
- [x] 服务门控保证 User Run（含暂停）占用期间不能启动 Developer Agent、Capture 或冲突 Candidate 操作；Developer 工作时 User Start 被拒绝，但 User 普通配置可编辑。按钮状态与服务检查一致，保留 Agent 自己的授权 trial_run 例外。
- [x] 空闲窗口独立关闭不影响另一侧活动；关闭工作所属窗口需确认停止，等待输入释放、日志和 Agent 清理；最后窗口关闭才退出。现有致命错误处理、取消及密钥边界保持。
- [x] 删除 Developer 独立 Runner 页，保留 Capture、Agent Settings、Agent Repair、修复试运行窗口及底层 Runtime/CLI；Developer Selected Manifest 不修改 Default 或 Candidate 来源。
- [x] 用两窗口及两入口测试证明互斥、普通配置可编辑、重复唤起、任务结果通知、暂停/取消和所属窗口关闭清理；替换固定四页断言但保留原有关键回归。

## 2 — 外置业务页面与共享 Agent 设置闭环

**GitHub：** [#332](https://github.com/HSLix/LixAssistantLimbusCompany/issues/332)

**直接阻塞：** [#331](https://github.com/HSLix/LixAssistantLimbusCompany/issues/331)

**交付行为：** 新增外置 Python 页面后即可保存业务参数、配置循环次数并运行 Plan；User/Developer 共用完整 Agent 配置内容但分别选用，User 开关不影响开发者。

- [x] 从明确外置目录自动发现 Python 页面，最小声明含稳定页面 ID、名称、创建入口及可选循环任务 ID；Dashboard/General Settings 固定置顶，纯设置页不强制注册任务。不做自动表单、复杂插件系统或内置 Agent 页面编辑。
- [x] Plan 显式声明支持任务 ID；Dashboard 常驻滚动条、每行启用/名称/正整数次数/设置跳转。未启用传 0；不匹配项保留保存值，以列表旁告警弹窗双向报告、不执行，不靠分析源码猜任务支持。
- [x] 各页约束自己的输入，Dashboard 只约束次数；设置按页面/任务 ID 存在 LALC 数据目录，跨 Manifest 共用且不静默重置。启动向 Plan 传独立次数/配置快照，运行中改设置只影响下次。
- [x] 一个循环示例和一个不注册任务的通用设置示例跑通页面→保存→Dashboard→Plan→Task 全链路；示例不是完整游戏业务迁移。
- [x] 单页导入/创建错误及冲突注册明确呈现，不静默覆盖；失败页跳过且不提供可执行注册，统一持久通知说明页面错误，其他页面仍可用。
- [x] 重新加载操作成功保存后重启整个应用并重新扫描，恢复设置；活动期间禁止重载，保存失败不重启，旧活动/线程/窗口正确清理。不实现模块热替换。
- [x] 验证新增页无核心修改、设置持久化/跨 Manifest 共用、任务 warning、纯设置页配置传入、快照、失败隔离通知及重启恢复；外置目录不得依赖源码工作目录才能找到。
- [x] 共享完整 Agent 配置内容，持久保存各套配置；User/Developer 分别保存当前选用项，切换 provider 不丢失另一套地址、模型、额度和 Agent 选项，不用一个全局选择联动两侧。
- [x] General Settings 提供 User Agent 区域，Dashboard 展示启用设置/状态及跳转按钮；只有 User 有启用开关，Developer 默认启用但仍需合法连接和主动发起。Stage 4 清楚说明运行时 Agent 尚未接入，不实现 Stage 6 故障修复。
- [x] 活动开始固定有效配置/认证与额度；另一侧修改已保存配置不改变进行中的轮次，普通配置编辑不因共享服务忙而全部禁用，连接检查等实际活动仍遵守互斥。
- [x] 保留 Windows DPAPI、macOS 进程内临时密钥、平台密钥分离、空输入不覆盖、明确清除和脱敏日志；已有用户配置平稳读入新共享设置，不泄露或丢失凭据。
- [x] 通过双窗口示例验证独立选用、交接编辑、切换后内容一致、User 禁用不影响 Developer、活动快照、重启恢复及凭据回归；相关 Agent 接入测试须显式选择，不默认调用模型。

## 3 — 双语 Dashboard 信息面板与 General Settings

**GitHub：** [#333](https://github.com/HSLix/LixAssistantLimbusCompany/issues/333)

**直接阻塞：** [#332](https://github.com/HSLix/LixAssistantLimbusCompany/issues/332)

**交付行为：** 交付 User GUI P0 布局、信息占位卡与 General Settings，保留双语及语言重启生效要求。真实信息内容移至 Stage 6 之后，不整体后移本票。

- [x] 按[User GUI P0 设计](user-gui-p0-layout.md)完成左右布局、占位卡、Agent 配置状态与启动门槛、密钥输入弹窗和统一折叠错误详情；不联网，Update 禁用。
- [x] General Settings 使用纵向选项布局，包含共享 Agent 配置/User 选择与开关、开发者入口及用途提示、页面重载和语言，不扩充无关设置。
- [x] 提供跟随系统/简体中文/English，默认跟随系统：系统中文用简体中文，其他用英文。保存语言后通过同一重启重载流程生效；翻译覆盖固定页面、通知和运行控制，并给外置页可复用的最小语言接口。
- [x] GUI 语言不改变游戏识别语言；语言/设置重启后保留，活动期间不允许重载。
- [x] 验证占位卡不联网、Update 禁用、P0 设置及启动规则、中文/英文/跟随系统、重启生效及游戏识别语言隔离。

#333 本地验证与尚未验收边界见[实施记录](stage-4-333-implementation.md)；开发者人工验收后已关闭 #333，不代表 #334 Windows 成品通过。

## 4 — Windows 打包成品与框架验收

**GitHub：** [#334](https://github.com/HSLix/LixAssistantLimbusCompany/issues/334)

**直接阻塞：** [#333](https://github.com/HSLix/LixAssistantLimbusCompany/issues/333)

**交付行为：** 交付可实际运行的 Windows 打包应用，现场证明外置页面、Python Plan、双窗口、共享设置及语言重载闭环，不以源码或 offscreen 结果代替打包版验证。

- [ ] 提供可复现构建、启动和示例说明；User/Developer 独立入口、重复入口窗口归并、外置页目录、翻译资源、信息占位卡及本地版本在打包版实际可用，不依赖开发工作目录。
- [ ] 打包后增加/修改外置示例页，无需修改核心或重打包即可重启发现；验证配置保存、跨 Manifest 共用、纯设置页、任务次数及不支持 warning、错误页持久通知/隔离、语言切换和重启。
- [ ] 通过打包界面实际启动唯一 Plan，验证 Task 普通失败后继续、Plan 自身失败结束、结果通知、多次循环、暂停/继续/Stop 及已完成结果保留。
- [ ] 双窗口/重复入口现场验证同一服务、互斥、User 普通配置可编辑、Agent trial 内部授权例外和窗口所属清理；无第二执行服务或遗留后台活动。
- [ ] 验证两侧 Agent 独立选用和共享配置、User 开关不禁用 Developer，Windows DPAPI 持久凭据按真实平台验证；区分不用模型的界面验证、pi/HTTP 替身、真实模型和真实游戏证据。
- [ ] 自动化/offscreen 与 Windows 打包现场证据分别记录；未执行项目明确保留未完成，不用前者替代后者。完整游戏业务和 Stage 6 Runtime Agent 不纳入本票，不新增自动更新器。
- [ ] 同步最终使用/验收文档及实施状态，确认所有前置票的功能在同一成品版本中协同可用，提供已知限制与产物定位。

## 验收纪律

每阶段完成自己的调用方、文档与相关测试，不把测试或 CLI/Agent 迁移留到最后。阶段 1 完成可运行示例 Plan 和双窗口运行壳，阶段 2 再以通用扩展页对接实际配置，不在核心硬编码游戏业务。阶段 4 交付并验证同一 Windows 成品，不能只验证构建成功。

JSON Plan 直接替换，不留产品兼容层；普通回归不启用 Agent/模型，涉及 Agent 接入时才显式选择相关测试；替身/offscreen 与 Windows/真实模型/游戏证据分别记录。
