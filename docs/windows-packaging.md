# Windows x64 本地构建和 #334 验收

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

- `dist/LALC-0.1.0-windows-x64.zip`
- `dist/LALC-0.1.0-windows-x64-with-pi.zip`
- `dist/SHA256SUMS`

两个 ZIP 都以 `LALC/` 为顶层目录。公共文件逐项比对；含 pi 版本仅多出 `pi/`，该目录保留完整上游运行资源并补带 MIT 许可文本。`build-info.json` 记录源码文件摘要、commit、锁文件摘要及 pi 来源／版本／摘要；未提交源码也计入实际快照。输入文件夹不会整目录归档。首次同步依赖需要网络或预先填充的 uv 缓存。

这不承诺不同构建时间所得 ZIP 字节完全相同；可复现指锁定输入、依赖和步骤。仅在 Windows x64 构建，不在 macOS 交叉生成 Windows 程序。

## 启动、数据及 pi 选择

- User：双击 `LALC.exe`。
- Developer：双击 `Developer.cmd`，实际启动同一 `LALC.exe --developer`；重复入口归并到现有应用。
- CLI：在终端运行 `LALC-console.exe` 加原有命令，保留标准输出与交互；它使用同一 main、服务及数据，并非另一套执行实现。
- 两个 EXE 沿用根目录 `MagicAndWonder.ico` 作为程序图标。
- Windows 的所有 GUI 入口（User、Developer、语言重启，以及源码 GUI）在创建服务、读写数据或归并窗口前检查管理员权限；未提权时通过 UAC 重新启动，保留启动参数与工作目录。拒绝或提权启动失败时显示中英双语提示并退出。CLI 命令不主动提权；其他平台维持原行为。若 UAC 使用另一个管理员账号，数据目录和 DPAPI 凭据也会属于该账号。
- 成品数据统一在 `%LOCALAPPDATA%\LALC`：`candidate/`、`.candidate-baseline.json`、`pages/`、Manifest、Component、Assets、配置、日志与证据。替换程序目录不搬移数据；源码运行仍沿用项目 `candidate/`。不自动寻找、迁移或删除旧草稿。
- 两个程序包不带业务数据或示例，首次启动不自动生成示例。数据导入导出以后另做。
- 默认 pi 选择：`LALC.exe` 同级 `pi/pi.exe` 优先，其次环境路径；显式 CLI `--pi` 保持调用者指定。
- 随包缺失直接使用环境 pi；随包启动／版本探测失败或 RPC ready 前退出，清理后最多回退一次并留日志。版本不同仅警告。超时、协议／工具集错误、取消、清理失败、模型错误不触发回退。第一条模型 prompt 发送前即关闭本轮回退，包括图片／连接预检；预检后的正式修复进程失败也不换 pi。
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

Windows 现场检查完成后，由开发者确认结果，再关闭 #334。功能实现、构建成功、源码／offscreen／HTTP 替身通过都不能单独替代该确认。
