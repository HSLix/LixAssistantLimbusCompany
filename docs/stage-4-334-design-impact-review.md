# #334 Windows 成品与双包分发影响评审

2026-10-28：依据开发者已确认的 [grill 决策](stage-4-334-decisions.md)，检查当前工作区源码、构建配置及测试。状态：评审完成，待开发者确认后实施。仅新增本报告并更新决策状态，未修改产品实现、构建产物或 GitHub issue。

2026-10-30 继续评审时复核：基线已提交至 `e744d94`（Agent 日志去重），复核前工作区干净；下列 Candidate、pi 启动及构建资源差距仍存在。评审结论不变，尚未授权实施。

随后开发者确认继续实施，并指定 `pi_resources/` 保存原始 pi ZIP；影响审查已获确认。下文保留实施前证据，最新实施状态与验证限制见[实施记录](stage-4-334-implementation.md)。

## 结论与设计变化

可以沿用 PyInstaller onedir 和既有应用服务，不需要新的分发框架。当前内部打包试验尚不满足 #334，需要补齐构建交付、pi 启动和数据路径三条链。

- 内部单目录试验 → Windows x64 本地脚本一次构建应用，再生成含 pi／不含 pi 两个 ZIP；除 pi 目录外应用内容一致。
- 仅环境路径 pi → 默认随包优先，允许在首个模型请求／工具执行前按已确认故障范围回退一次；不做模型错误重试。
- Candidate 随启动目录变化 → 成品统一在 `%LOCALAPPDATA%\LALC\candidate`；已有配置、Manifest、Assets、日志、外置 pages 仍在同一用户数据根目录。
- 程序与数据分开交付：不随包带 Candidate、Manifest、Assets、页面或用户配置；首次启动不自动生成示例。验收数据留在仓库，由开发者另行准备。
- 通用 Windows 功能验收只选一个包；pi 差异覆盖两个包。回归不调用真实模型，Windows 真实模型验证不属于本票。导入导出、安装器、单文件、自动更新和 Actions 均不加入。

## 已确认的差距与影响

### 1. Candidate 路径必须同时覆盖 GUI、CLI、元数据和锁

证据：`src/lalc/gui.py:97,801` 的宿主默认 Candidate 和 `src/lalc/__main__.py:239` 的 CLI Candidate 都来自 `Path.cwd()`；CLI 在 `:346` 又单独按工作目录构造锁。`src/lalc/developer.py:65` 的基线元数据位于 Candidate 父目录，`:74` 的锁按实际 Candidate 路径生成。

后果：仅改 GUI 会让 CLI 校验／发布／清理操作另一份草稿，并持有不同锁；快捷方式、不同工作目录及重启后的实际行为不稳定。基线元数据也必须跟随成品 Candidate，不能留在源码目录。

最小方案：集中计算默认 Candidate 路径，并替换全部默认调用方及 CLI 锁；成品使用数据根目录，源码启动继续采用项目工作目录，保留 `DeveloperHost(service, candidate)` 显式注入。两种模式均不自动搬移、覆盖或删除旧草稿。`default_data_root()`（`application.py:736`）、页面发现（`gui.py:420`）和 Manifest 存储（`manifest.py:138`）已有正确的数据根目录，无需重构。

测试影响：`tests/test_cli.py:56,60,160` 明确断言源码工作目录语义，须保留；新增 frozen 模式下改变工作目录仍使用同一 Candidate、元数据和锁的检查，以及重载后的路径一致性检查。`CONTEXT.md` 的 Developer Candidate 当前限定为 project checkout，需窄幅调整为开发者工作区的唯一草稿，不把路径实现写入术语表。

### 2. pi 选择与回退必须共享实现，且不能按进程重置边界

证据：`pi_probe.py:199` 仅调用 `shutil.which(args.pi)`；`:239` 探测版本，`:252` 选择宿主扩展；`developer_gui.py:869` 固定传入默认名称 `pi`。`agent_repair.py:325` → `check_model_image(:218)` → `rpc_session` → `configure_session` → `:231` 发出模型预检 prompt；之后 `:356` 又启动正式修复进程。

后果：现有路径没有随包选择或自动回退。若在每次 `rpc_session` 内独立重试，预检已经请求过模型后，第二个进程启动失败仍可能换 pi，违反本轮已确认边界。不能仅以工具尚未执行或新进程尚未 ready 判断是否可以回退。

最小方案：GUI、repair CLI 和 pi-probe 共用默认 pi 解析及启动机制；建议随包位置为 `LALC.exe` 同级的 `pi/pi.exe`，不修改全局 PATH。默认名称走随包→环境路径；保留显式 `--pi` 指定路径的现有调用者控制，不静默覆盖。记录选中路径、实际版本及回退原因，去重相同可执行路径，最多回退一次。

随包缺失、启动失败、版本探测失败或 ready 前进程退出可以触发已确认回退；版本差异仍仅警告。未知 RPC 文本、工具集不符、配置拒绝或单纯等待超时不得通过宽泛捕获擅自变成回退。原子边界应在发送本轮第一个模型 prompt 前关闭；包含连接／图片预检，不能等到收到计数事件才关闭。预检后修复进程失败直接保留错误，取消／清理失败也不得触发回退。回退前须完成旧进程及临时环境清理，保留配置和认证快照、额度、日志及取消契约。

测试建议：不用真实模型，覆盖随包优先、无随包走环境路径、已确认故障的一次回退、同路径不重试、两处均不可用、版本差异不回退、请求发送后错误不回退、预检后第二进程失败不回退、取消和清理失败不回退。纯路径／模拟故障检查可普通运行；真实 pi、Agent 工具循环及模型服务替身检查仍标记 agent 并显式选择。

### 3. Agent 扩展未显式进入冻结资源清单

证据：`pyproject.toml:39` 把 `pi_probe.ts` 声明为 Python 包数据，但 `LALC.spec:13` 的 PyInstaller datas 只显式收集许可、通知、翻译和列出的 GUI 库 metadata；没有收集该扩展。`pi_probe.py:252` 在运行时要求它存在于 Python 模块旁。

后果：Python 包含该文件不等于冻结构建会收集它；仅证明 `pi.exe --version` 成功，不能证明 Agent 扩展可加载。此处确认的是构建声明差距，未运行新 Windows 构建，不声称已观察到该成品的报错。

最小方案：显式加入 `lalc/pi_probe.ts`，沿用模块相对路径。保留应用／Qt／Fluent 三类翻译、公开 Runtime API 与必要库。构建后按实际冻结文件检查扩展和翻译存在，进一步检查扩展导入及 ready；不把任意第三方 Python 库都加入 hiddenimports。不要把宿主扩展缺失伪装成随包 pi 本身坏了。

### 4. 现有构建说明不能直接交付两个可追溯 ZIP

证据：`README.md:92` 仅给依赖安装和 PyInstaller 试验命令；`LALC.spec` 仅产生一个 COLLECT 目录。该流程没有双 ZIP 组装、pi 固定来源、两包内容比对或源码／依赖记录。`LALC.version` 的数值为 0.1.0，描述仍是 Internal Packaging Spike；`pyproject.toml:7` 也是 0.1.0。

最小方案：新增 Windows 本地构建脚本，使用锁文件、Python 3.12 和既有 build/gui/automation 依赖，从一次干净构建目录形成公共应用内容，再添加完整 pi 运行目录生成第二包。ZIP 采用明确文件清单；不遍历打包整个仓库、用户数据或开发工作目录。分别计算归档校验值，核对移除 pi 目录后的相对路径和文件内容完全一致。

记录应用版本、实际源码快照、锁文件及 pi 来源／版本／摘要；若构建时存在未提交修改，单记 HEAD 不能标识实际构建源码。构建清单是程序说明，不属于用户可修改数据。以相同输入和锁定工具版本可重复构建为目标，不额外承诺 ZIP 时间戳或所有 PE 字节必然一致。

### 5. 现有 windowed 成品不能直接承担文档中的交互式 CLI

证据：`LALC.spec:40` 使用 `console=False`；`__main__.py` 的 publish/data-dir 等结果靠 print，clear 使用 input。PyInstaller 官方说明 noconsole 模式可能没有标准输入输出对象，源码终端测试不能证明这些入口在打包版可用。

后果：直接把源码 `lalc publish` 等命令改写成 `LALC.exe publish` 并不能构成可用的验收准备说明；发布 UUID、错误及交互输入必须确实可获得。

建议：GUI 继续无终端启动，Developer 入口采用同一 `LALC.exe --developer` 的轻量启动文件，保留归并逻辑。打包 CLI 如作为示例准备入口，须在命令模式建立可用标准输入输出，或由现有 GUI 完成准备并给出明确步骤；不另建业务服务、第二套 CLI 逻辑或安装器。实施时以实际 Windows 命令输出／交互确认方案有效。

### 6. 示例与验收材料需要补齐故障场景，而非加入程序包

证据：`example/workflow/README.md` 的正常 exp/mirror 演示需要既有唯一游戏窗口，默认截图和等待；该文档没有提供 Task 普通失败→继续、Plan 自身失败、各阶段 Stop 的成品验收准备步骤。`tests/gui_native_probe.py` 是从源码创建临时数据、使用 Python 启动的 GUI 探针，不是 Windows 冻结应用验收。

最小方案：复用现有页面和 Plan 示例，在仓库补充最少的故障演示素材／操作步骤；保存到独立测试数据或测试 Windows 账号，准备前检查已有草稿和数据，不覆盖用户实际工作。通过成品 GUI 运行已发布 Manifest，记录实际结果通知、Trace／Ledger、后续 Task、暂停／继续／Stop、重启重载和双窗口活动清理。真实游戏业务成功不作为框架成功的替身，焦点／接管现场观察单列。

沿用 `test_user_pages.py` 的实际 Plan／配置快照和重载检查、`test_user_gui.py` 的互斥／窗口清理／跨进程归并检查、`test_gui_language.py` 的资源检查，以及 P0 的启动门槛／密钥／错误详情回归。现有 `test_user_pages.py:347` frozen 重启用例替换了 os.execv，仅证明命令参数；仍需现场验证 Windows 成品真正恢复两窗口和页面目录。

## 外部分发核查与潜在风险

- **pi 官方来源已核实。** 当前回归基线仍是代码中的 1.4.0；[官方 v1.4.0 发布](https://github.com/earendil-works/pi/releases/tag/v1.4.0) 有 `pi-windows-x64.zip` 和 SHA256SUMS，GitHub 发布 API 给出的该 ZIP 摘要为 `0f7256ea8bdac3af20012b94fdc1252a31cc6dc0d2f9b9eb539555d22e3e321b`。建议使用此固定发布，不从构建机 PATH 随意拷贝 pi。未下载或运行该 Windows 文件，摘要目前是发布元数据证据。
- **不能只复制 pi.exe。** [该版本官方构建脚本](https://raw.githubusercontent.com/earendil-works/pi/v1.4.0/scripts/build-binaries.sh) 除 exe 外还分发 WASM、原生平台辅助文件及其他资源。保留完整官方运行目录及来源记录；这些是 pi 依赖资源，不是项目的可修改业务数据。其在 LALC 限权扩展下的完整性仍需实际 Windows 加载检查。
- **分发许可有可用依据，但附件仍需落实。** [该版本 LICENSE](https://raw.githubusercontent.com/earendil-works/pi/v1.4.0/LICENSE) 为 MIT，要求随分发保留版权与许可文本；构建需携带 pi 及其实际运行依赖的通知／许可。现有 THIRD_PARTY_NOTICES.md 只列 GUI 库，不能当成 pi 通知已经齐备。此结论只核查所读源码与资料，不声称已逐项核验尚未下载归档的所有依赖许可。
- **冻结环境的子进程影响尚未实测。** `packaging_hooks/rthooks/pyi_rth_lalc_pyside6.py:15` 会将 `_MEIPASS` 加入 PATH；现有版本探测及 RPC 子进程均继承环境。[PyInstaller 官方说明](https://pyinstaller.org/en/stable/common-issues-and-pitfalls.html#launching-external-programs-from-the-frozen-application) 指出 Windows DLL 搜索目录也会影响子进程。需检查随包及环境 pi 两条路径是否受到影响；若需隔离，只处理 pi 子进程启动边界并恢复宿主环境，不全局破坏 Qt 查找路径。不宣称已观察到 DLL 冲突。
- **原生 Windows 行为仍需现场证据。** DPAPI、窗口焦点／接管、模态、缩放、路径含中文／空格、无系统 Python、重启清理和跨进程归并无法由本次源码检查证明。按已确认安排，通用部分只验一个包，pi 差异分别覆盖；真实模型验证不纳入本票。
- **本地版本与占位卡措辞需同步。** 旧 #334 文案仍提及本地版本，P0 要求信息卡占位。建议保留三卡占位和 Update 禁用，以 EXE 版本资源及构建清单标识本地版本；不借此恢复联网版本比较或新增卡片功能。

## 实施顺序与文档同步

1. 确认本评审建议；同步 Stage 4 规格、拆分、ADR 0032 的分发细节、domain 指南及 Candidate 术语边界，保留历史验收记录。无需为可逆的 ZIP 目录选择另建 ADR。
2. 统一成品默认 Candidate 路径和所有锁调用方；实现默认 pi 选择和严格回退边界，复用既有 RPC 清理及轮次证据。Agent 日志去重变更已在复核基线提交，基于实际最新接口接入，不回退或重写它。
3. 补冻结资源和入口，完成 Windows 本地脚本、两个 ZIP、公共内容比对、固定 pi 来源及构建记录。应用版本从既有版本源保持一致，不擅自提升版本号。
4. 补最小故障验收示例及准备说明、两包差异矩阵和结果记录模板；程序包无业务数据、无首次自动示例生成。README 的内部 spike 说明改为实际成品构建／启动／数据定位说明。
5. 执行改动对应检查和普通回归；Agent 接入确有变更时才显式选择 agent 测试，可使用 HTTP 替身，不调用真实模型。随后由开发者完成 Windows 成品验收并明确确认，再同步实施状态和关闭 #334。

本次未执行测试、构建、pi、模型请求或游戏操作；没有把旧 macOS 构建文件当作当前 Windows 成品证据。源码行号对应评审时工作区，实施时需适应并行变更。尚无 Windows 产物及完整归档许可清单，相关验证保持待完成。
