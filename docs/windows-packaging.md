# Windows x64 本地构建和 #334 验收

2026-11-05 双包更新：以下 with-pi／without-pi 命名由 with-agent／without-agent 替代，两包仍共用相同应用。新增输入和当前行为如下；原 #334 验收数字仅为历史。

需另外准备官方 codesearch 1.7.9 基础版 `codesearch_resources/codesearch-windows-x86_64.zip`，SHA-256 为 `235d47228f53b6cc822a6cf924f83011aefc0f098fd8fb9f8f8c8f9091e20f6a`，以及 `codesearch_resources/models/models--Xenova--all-MiniLM-L6-v2/snapshots/751bff37182d3f1213fa05d7196b954e230abad9/` 的固定模型文件，清单与哈希见 `src/lalc/codesearch.py:MODEL_FILES`。资源目录被 Git 忽略，需要复制到 Windows 构建机，不会由普通启动下载。可用 `--codesearch-zip` 和 `--models` 指定离线资源路径。

输出为 `LALC-<version>-windows-x64-with-agent.zip` 与 `LALC-<version>-windows-x64-without-agent.zip`。自带包额外含完整 pi/ 和 agent/（codesearch.exe、固定 MiniLM 模型及许可／来源说明）；精简包不禁用功能，允许外部安装资源。主体文件排除这两个资源目录后逐项相同，build-info 记录资源版本／哈希。模型复制到可写的数据目录缓存，程序安装目录保持只读。Windows 本机 PyInstaller 构建与断网运行仍须原生验收。

2026-11-01 游戏版本读取：automation 固定 UnityPy 1.25.4，冻结配置收集 UnityPy/resources/lzma.tpk，组包检查其存在；不再提供独立 pi-probe 命令。真实 Windows 冻结运行未在 macOS 验收，见[游戏版本历史](game-version-history.md)。

2026-11-01 #337 知识库增量：成品使用系统已安装的 Git，不额外捆绑或自动安装。Git 不可用时跳过同步与提交查看、记录日志，本地资料仍可读取；不弹安装窗口。私有仓库须由开发者预先准备非交互认证，首次内容访问才会尝试 fetch。目录与操作见[知识库实施记录](stage-5-337-implementation.md)；Windows 上的 Git / 凭据辅助程序 / 取消清理尚待原生验收。

2026-11-01 OCR 增量：两个 ZIP 均包含 RapidOCR 3.10.0、ONNX Runtime 1.31.1 CPU 及 PP-OCRv6 Small 的 det/rec ONNX 模型。字典内嵌于识别模型，不需要额外下载。构建与归档前校验固定模型摘要，启动不自动下载；必须另行验收断网后的首次识别、工具 OCR 故障降级和 Run 中断。此增量尚不代表 Windows 冻结包或真实游戏验收通过。接口见 [OCR 用法](ocr.md)。

2026-10-30：以下为已实现的构建和验收流程；尚无本票 Windows 成品现场通过记录。真实模型验证不属于本票，回归不调用真实模型。GitHub Actions 在 Stage 6 完成后再考虑。

## 构建输入与两个输出

在 Windows x64 安装 uv，准备同一源码快照和锁文件。把官方 **pi 1.4.0 Windows x64 原始 ZIP** 放到源码根目录：

```text
pi_resources/pi-windows-x64.zip
```

`pi_resources/` 已由 `.gitignore` 排除。无需手动解压；不要将 macOS pi、重新压缩的归档或本机已安装 pi 目录替代它。当前开发者提供的原始 ZIP 已核对版本及 SHA-256：`0f7256ea8bdac3af20012b94fdc1252a31cc6dc0d2f9b9eb539555d22e3e321b`。Windows 构建需把这个 ZIP 复制到 Windows 源码的同名目录。

在源码根目录运行：

```powershell
uv run --no-project --python 3.12 python scripts/build_windows.py
```

也可指定外部路径：

```powershell
uv run --no-project --python 3.12 python scripts/build_windows.py --pi-zip 'D:\Resources\pi-windows-x64.zip'
```

脚本校验原始 ZIP 和版本，使用独立的 `.generated/windows-build/venv`、锁定依赖及同一次 PyInstaller onedir 构建，检查必需资源，然后生成：

- `dist/LALC-0.1.0-windows-x64-without-agent.zip`
- `dist/LALC-0.1.0-windows-x64-with-agent.zip`
- `dist/SHA256SUMS`

两个 ZIP 都以 `LALC/` 为顶层目录。公共文件逐项比对；自带 Agent 版本多出 `pi/` 与 `agent/`，分别保留 pi 运行资源及 codesearch／MiniLM，并补带许可与来源说明。`build-info.json` 记录源码文件摘要、commit、锁文件摘要及 pi／codesearch／MiniLM 来源、版本与摘要；未提交源码也计入实际快照。输入文件夹不会整目录归档。首次同步依赖需要网络或预先填充的 uv 缓存。

这不承诺不同构建时间所得 ZIP 字节完全相同；可复现指锁定输入、依赖和步骤。仅在 Windows x64 构建，不在 macOS 交叉生成 Windows 程序。

## 启动、数据及 pi 选择

- User：双击 `LALC.exe`。
- Developer：双击 `Developer.cmd`，实际启动同一 `LALC.exe --developer`；重复入口归并到现有应用。
- CLI：在终端运行 `LALC-console.exe` 加原有命令，保留标准输出与交互；它使用同一 main、服务及数据，并非另一套执行实现。
- 两个 EXE 沿用根目录 `MagicAndWonder.ico` 作为程序图标；同一 ICO 随包提供给 Qt，User／Developer 窗口与任务栏显式使用该图标。若覆盖旧成品后文件图标未更新，可先临时改名 EXE 验证 Windows 图标缓存。
- Windows 的所有 GUI 入口（User、Developer、语言重启，以及源码 GUI）在创建服务、读写数据或归并窗口前检查管理员权限；未提权时通过 UAC 重新启动，保留启动参数与工作目录。拒绝或提权启动失败时显示中英双语提示并退出。CLI 命令不主动提权；其他平台维持原行为。若 UAC 使用另一个管理员账号，数据目录和 DPAPI 凭据也会属于该账号。
- 成品数据统一在 `%LOCALAPPDATA%\LALC`：`candidate/`、`.candidate-baseline.json`、`pages/`、Manifest、Component、Assets、配置、日志与证据。替换程序目录不搬移数据；源码运行仍沿用项目 `candidate/`。不自动寻找、迁移或删除旧草稿。
- 两个程序包不带业务数据或示例，首次启动不自动生成示例。数据导入导出使用 [Sharing](sharing.md)，不随应用 ZIP 自动导入。
- 默认 pi 选择：`LALC.exe` 同级 `pi/pi.exe` 优先，其次环境路径；显式 CLI `--pi` 保持调用者指定。
- 随包缺失直接使用环境 pi；随包启动／版本探测失败或 RPC ready 前退出，清理后最多回退一次并留日志。版本不同仅警告。超时、协议／工具集错误、取消、清理失败、模型错误不触发回退。第一条正式模型 prompt 发送前即关闭本轮回退，之后不因进程故障改换 pi；每轮图片／连接推理预检已取消。
- 没有可用 pi 时只拒绝实际 Agent 启动；User Agent 关闭时仍可执行确定性任务，不自动联网安装 pi。

## 开发者单独准备验收示例

使用专门的 Windows 测试账号，保留其数据作为证据。先验证无数据成品的空 Dashboard、三张占位卡、不联网和 Update 禁用，再退出。以下步骤仅用于空测试环境，不应覆盖已有用户数据或草稿。

准备源码目录 `$repo` 和已解压程序目录 `$app`：

```powershell
$repo = 'D:\Code\LixAssistantLimbusCompany'
$app = 'D:\LALC'
$data = Join-Path $env:LOCALAPPDATA 'LALC'
if ((Test-Path "$data\candidate") -or (Test-Path "$data\pages")) {
    throw '测试目录已有 Candidate 或 pages，请保留原数据，改用干净测试账号。'
}
New-Item -ItemType Directory -Force $data | Out-Null
Copy-Item -Recurse "$repo\example\acceptance" "$data\candidate"
Copy-Item -Recurse "$repo\example\pages" "$data\pages"
& "$app\LALC-console.exe" validate
& "$app\LALC-console.exe" publish
```

检查 validate 成功、publish 返回 UUID 后，用实际值替换下方 `<UUID>`：

```powershell
& "$app\LALC-console.exe" set-default '<UUID>'
& "$app\LALC-console.exe" init --from '<UUID>' --replace
```

此处 replace 只重建刚创建的验收 Candidate 及其基线，不能用于覆盖实际开发草稿。外置页面仍独立放在 pages，不进入 Manifest。

启动唯一可用的游戏窗口，再从成品 GUI 开始 Plan。该示例只等待，不发送点击／按键，正式运行仍使用原有焦点、接管和互斥契约；不代表完整游戏 Workflow 验收。

- exp 消息 `Hello`，次数 3：三个 Task 成功，各协作等待五秒，可观察暂停／继续／Stop。
- exp 消息 `task-fail`，次数 3：成功→普通失败→成功；Plan completed 与所有 Task 成功须区分，Ledger／Trace 保留三个结果。
- exp 消息 `plan-fail`，次数 3：首次成功后 Plan 自身失败，中断并保留首次结果，不执行后续。
- mirror 可填另一消息，验证另一页面配置与 Task 输出；legacy 是纯设置兼容页。复制／修改页面后通过 General Settings 保存并重启验证重新发现，而非修改核心或重新打包。

切换到另一已发布 Manifest，验证页面配置及次数仍保留。不匹配项 warning 可通过在 Candidate 修改 SUPPORTED_TASK_IDS 后另行发布、切换版本演示；保留原版本以恢复。错误页可在 pages 临时加入单行 `raise ValueError('acceptance page failure')`，重载后应通知并隔离该页，其他页面可用；移走此测试文件后再次重载。

## 验收矩阵与记录

通用功能只用一个包；记录所选 ZIP 名称、SHA-256、build-info、Windows 版本／缩放、测试账号和数据目录，以及每项实际结果／日志或截图。未执行写“未执行”，不要以本地替身结果填“通过”。

| 范围 | 检查 | 证据边界 |
| --- | --- | --- |
| 一个包的通用功能 | User／Developer 入口与重复归并，同一服务，独立关闭、活动所属窗口取消清理 | Windows 成品现场 |
| 图标与管理员启动 | 两个 EXE 图标；User／Developer 未提权启动的 UAC 允许／拒绝、双语拒绝提示、已提权不重复请求、语言重启恢复窗口 | Windows 成品现场；源码入口亦需检查 |
| 外置页与 Plan | 新增／修改无需重打包；保存、跨 Manifest、纯设置页、次数、warning、错误页隔离；上述失败／暂停／Stop 结果 | Windows 成品现场及 Trace／Ledger |
| 语言／布局／资源 | 两语与跟随系统、整应用重启和恢复窗口、中文／空格路径、模态、缩放；占位卡不联网、Update 禁用 | Windows 成品现场 |
| Agent 设置 | 两侧独立选用、共享内容、User 开关、Developer 独占编辑与保存交接、无效文本保存／修正、API Key 弹窗与原生 DPAPI、详情折叠／复制和脱敏 | 不要求真实模型 |
| 含 pi 包 | 随包优先；临时移走 pi 时走环境路径；用测试替身或受控坏随包进程检查版本／启动／ready 前失败的一次回退 | 分别记录选中路径、版本与原因 |
| 不含 pi 包 | 环境 pi 可选中；无环境 pi 时明确拒绝 Agent，确定性任务仍可用 | 不重复通用全套 |
| Agent 回归 | 真实本机 pi + 本地 HTTP 替身，仅显式选择相关 agent 测试，排除真实模型测试 | 不等于 Windows 成品／真实模型证据 |

GUI Agent 对话会请求配置中的模型，不能为了“检查路径”随意发消息到真实服务；无真实模型验收要求，可使用受控替身。两包选择／回退的自动化边界检查参见 `tests/test_pi_startup.py`，冻结资源／双包内容检查参见 `tests/test_windows_packaging.py`。

2026-10-30：开发者试用反馈“没明显问题”，明确决定不等待完整验收并关闭 #334；见[关闭记录](stage-3-4-closure-2026-10-30.md)。上表保留可执行的验收方法，未执行项仍未验证，不因关闭变成通过。


## 开发 Agent SOP 资源

程序包包含 `_internal/lalc/sop.md`，wheel 包含 `lalc/sop.md`；组装 Windows ZIP 时检查该资源存在。开发者按文件内说明编辑三个正文区，保留标题和 XML 标签，UTF-8 保存。源码运行对应 `src/lalc/sop.md`；每条用户消息执行时读取，轮内固定，无需重启。不存在用户数据目录覆盖文件或 GUI 编辑器。更新程序可能替换 SOP，请自行备份填写内容。标签损坏或缺少文件时 Agent 在调用模型前报告错误；普通确定性执行不依赖该文件。
