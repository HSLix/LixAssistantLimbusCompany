# Sharing 分批实施与接续

2026-11-04 资源规则修订已实施：开发者同意撤销 Sharing 导入／导出、源码／标签／像素和 Agent 页面资源的固定准入限额。现改为磁盘／内存预检、文件流式处理、可取消 Worker 和按需预览；旧批次中的 2 MiB 等阈值及“同步检查”描述仅保留为历史。当前规则见 [Sharing](sharing.md)、[ADR 0037](adr/0037-budget-sharing-against-available-resources.md) 和[本次影响审查](sharing-resource-impact-review.md)。

2026-11-04。开发者已批准实现并要求直接推进收尾。四类 ZIP 后端、Sharing GUI、目录页面及全部相关工具已完成本地实现；最终契约见 [Sharing](sharing.md)，架构取舍见 [ADR 0036](adr/0036-share-selected-objects-and-install-complete-page-packages.md)。下列第一至第三批保留当时的范围与证据，其中“未接 GUI／留下一批”不再代表当前状态。

## 第一批：Workflow 导入底层

已完成：新增 `src/lalc/workflow_sharing.py` 和 `tests/test_workflow_sharing.py`。未改现有发布／加载入口，未接 GUI、ZIP 或 CLI，不创建用户真实数据。

接口：

- `inspect_workflow_import(manager, source_root, manifest_id)`：检查已准备好的暂存 Workflow，返回 `source_manifest_id`、建议 `manifest_id`、`uuid_conflict`、规范化 Manifest 的 `manifest_sha256` 和 Component 数量；只读取数据。暂存目录布局为 `manifests/<uuid>.json` 和 `components/<sha256>.py`。
- `import_workflow(manager, source_root, source_manifest_id, *, manifest_id, manifest_sha256)`：由未来 GUI 在明确确认后调用。重新静态检查暂存内容，对照检查时的内容指纹，保存哈希源码，并排他创建确认 UUID 的 Manifest。不会调用源码加载或修改 Default。
- UUID 未占用时沿用；占用则 inspect 建议新 UUID，但不会提前写入。commit 不重新生成 UUID；再次占用只报错。实际弹窗及取消行为留 GUI 批次。
- 复用 `ManifestManager._prepare(saved=True)` 和 `_store_component`，未复制静态校验规则。Component 复用完全相同字节，拒绝本地损坏／链接文件；Manifest 排他写入前准备完整临时文件。失败可留下未引用的共享哈希源码，符合既有约定。
- 目录链及直接 Component 文件拒绝链接。该接口只接收暂存目录，不是 ZIP 安全解析器；ZIP 的成员登记、大小／数量／解压限制仍未实现。调用方必须先完成受控 ZIP 检查／暂存，并在最终提交持有活动互斥。

测试覆盖：检查无写入、提交不调用源码加载、未占用 UUID 沿用、占用 UUID 提议新身份、原 Manifest／Default 保持、同哈希源码不重写、检查后内容变化拒绝、检查后 UUID 被占用不覆盖、临时文件清理、输入哈希损坏／链接拒绝、本地 Component 损坏／链接拒绝。

执行命令：

```text
.venv/bin/python -B -m pytest -q -p no:cacheprovider tests/test_workflow_sharing.py tests/test_manifest.py
```

最终结果：**20 passed，0.27s**；`git diff --check` 通过。没有运行真实 Agent、模型、游戏或 Windows 成品；无新增依赖。测试是本地替身验证。

## 第二批：页面包底层

已完成：新增 `src/lalc/page_packages.py`、`tests/test_page_packages.py`；接入 `user_pages.py` 的普通发现／加载和 PageContext 资源定位；调整 `PageDrafts.check_registration`，确保旧 Agent 安装入口不能漏掉目录页面的 ID 冲突。原 `page_filename`／`real_directory` 移入共同模块，并从旧导入位置保持可用。页面示例说明已补目录格式与当前实施边界。

当前底层契约：

- 新页面根目录内固定 `page.py`，资源放在页内路径，如 `assets/banner.png`；普通加载器兼容旧顶层 `.py`，只发现一层页面目录，不把资源子目录中的 Python 当独立页面。
- `PageContext.resource_path(relative)` 返回本页普通资源文件的绝对 Path，拒绝越界、Windows 保留名及链接；配置仍由目录外的 UserSettings 管理。
- `snapshot_page(path)` 接受旧文件或页面根目录，返回不可变 `PageSnapshot`。旧文件包装为 `page.py`，源码和全部资源文件的相对路径／字节共同决定 `sha256`；不会执行 Python。
- `materialized_page(snapshot)` 在上下文存续期间提供固定临时整包入口，便于下一批预览绑定整包；尚未接入现有 PagePreviewDialog。
- `install_page_package(directory, name, snapshot, replace=False, legacy_filename=None)` 是无 GUI、无源码执行的底层提交；调用方须先取得人工批准并持有活动互斥。替换整个目标包，不混入旧资源；`legacy_filename` 只允许对应的 `<name>.py`，成功后转成目录。普通失败恢复旧包／旧文件；恢复再次失败时保留旧副本并在错误中给出路径，不能清理唯一旧数据。没有承诺崩溃／断电恢复。
- 当前 Agent 创建／读取／更新／预览仍是原单文件接口，没有对外宣称资源工具已升级；下一批必须完整接通。现有单文件流程继续通过回归。

新增测试覆盖真实 PNG 加载及配置保留、快照只读／不执行／图片变化使版本变化、整包替换清除旧资源、旧单文件转换、资源写入失败／提交失败回退、恢复失败保留原数据、Windows 路径／别名／文件目录冲突、资源链接拒绝、新旧页面 ID 冲突及旧 Agent 安装入口的冲突检查。

验证结果：

- `test_page_packages.py + test_user_pages.py + test_page_drafts.py`：**77 passed，1 skipped，4.77s**。跳过项是当前环境禁止本地 IPC 的真实进程重载检查。
- `test_gui_language.py` 单独：**23 passed，1.90s**；`test_example_workflow.py` 单独：**2 passed，0.73s**；`test_user_gui.py` 单独：**11 passed，2 skipped，2.61s**，跳过项为原生焦点及受限 IPC。上述已正常退出的测试共 **113 passed，3 skipped**。
- `.venv/bin/pyright --pythonpath .venv/bin/python src/lalc/page_packages.py src/lalc/user_pages.py src/lalc/page_drafts.py`：**0 errors**。首次未指定解释器时只报告现有 Qt 依赖未解析，明确解释器后通过。
- 把相关 GUI 文件放在同一进程的大组合，以及单独 `test_user_gui_p0.py`，均在测试进度到 100% 后、pytest unconfigure 的 `gc_collect_harder` 阶段发生原生 Segmentation fault，未正常退出，**不能计为通过**。临时使用 HEAD 版 `user_pages.py/page_drafts.py` 跑原有 GUI 组合也重现同一 GC 崩溃（退出 -11），对照过程未改动工作区。不要以删除 GC 检查或隐藏退出码宣称通过。
- 后续同样使用 HEAD 页面模块单独运行 `test_user_gui_p0.py` 也重现相同退出 -11，已将该独立文件的问题与本次页面包实现隔离；其 18 个进度标记不计入通过数。该既有退出崩溃尚未修复。

本批未运行真实 Agent／模型／游戏／Windows 成品。不要将普通图片加载及文件故障注入当作 Windows 文件占用或崩溃恢复验收。

## 第三批：page_* 工具及 Agent 整包预览

已接通：`page_drafts.py`、`repair_tools.py`、`agent_policy.py`、`pi_probe.ts`、`agent_prompts.py`、`sop.md`、`page_preview.py`，补 `tests/test_page_package_tools.py` 并调整旧测试的安装路径／整包版本断言。示例页面及 Prompt 文档同步。

接口与兼容：

- 工具 `filename="sample.py"` 仍是逻辑名称，新增草稿存为 `page-drafts/sample/page.py`，目标元数据仍在根目录 `sample.json`。旧单文件草稿／元数据不迁移，继续可读可改；旧 Session 的正式目标即使被其他 Session 转成目录也能继续修改、审批安装。
- `page_create(copy_from="sample.py")` 复制完整正式包及资源。`page_update` 只原子替换源码，保留资源。`page_list(filename=...)` 分页列文件路径／大小／哈希，顶层列表 sha256 是整包版本；`page_read(path=...)` 默认读取文本，返回文件自身哈希，`image=true` 返回原图及内容 MIME。
- 新 `page_resource` 仅 GUI Construct 可用，宿主分发和 pi 声明均检查权限。对当前草稿的一个非 Python 资源执行严格 Base64 写入、受控复制或移除。来源限 installed/drafts 页内文件、带哈希的 Asset、当前知识库明确文件；不自动 fetch，不接受任意本地路径，不写正式页面或用户配置。单文件读取／资源写入限 2 MiB。修改旧单文件草稿的资源时整包转换，元数据保留。
- `PageDrafts.snapshot` 包含不可变 `PageSnapshot`、入口 source、整包 sha256 和目标信息；不要把该 Python 对象直接交给 JSON。`PagePreviewDialog` 的 Current／Proposed 分别 materialize 固定完整包，资源用该副本路径；关闭、失败、取消清理临时包，安装只提交已预览包，后续草稿变更不授权新版本。
- Agent 预览日志除原 source／目标／版本外，还保留 `tool-N-page-package/` 完整快照及每文件哈希，不只留资源清单或引用可变草稿。没有改变本地历史格式／重放权限。
- Agent 保持“专用人工批准即安装”，三 Tab、内存配置、旧页失败仍能修复、取消唤醒及模式／入口边界保持。未来 Sharing 需要单独的“Review 返回批准、不立即安装”适配和未 Review 名单确认；本批未连接该 Sharing 入口，不能复用 Agent 按钮提前安装。

测试／验证：

- 普通定向检查：`test_page_drafts.py test_page_packages.py test_page_package_tools.py test_agent_prompts.py test_workbench.py test_developer_session.py`，**104 passed，4.30s**。
- 普通检查退出后，另串行运行真实 pi＋本机 HTTP 替身：`test_developer_session_agent.py::test_page_tool_declarations_same_round_and_restored_drafts`、`::test_actual_gui_page_install_returns_to_agent`，及 `test_agent_repair_agent.py::test_sop_round_snapshot_and_actual_tool_guidance`，**6 passed，7.29s**，使用 `--run-agent-tests`。验证新资源工具的实际声明／调用／恢复、人工页面安装和 SOP 轮内冻结；不是模型或游戏验收。
- 发现 HEAD 中 SOP 已要求四段（含 Page），旧单元／Agent 夹具与断言仍按三段。本批更新夹具／断言及说明、补 Page 嵌套检查，保持原先“模式＋Asset＋Page”的实际加载行为。第一次针对这些旧断言的失败已修正并以上述两套最终结果收尾。
- `.venv/bin/pyright --pythonpath .venv/bin/python` 检查 page_drafts/page_packages/user_pages/agent_policy/agent_prompts：**0 errors**。额外查看 page_preview／repair_tools 的完整检查仍有 30 条位于既有 Qt window 属性、可空对象及截图／错误结构代码的诊断，未将这两个模块报告为全量类型干净，未扩展到无关类型修复。
- 大组合包含 `test_user_pages.py`，以及该文件独立进程，均在进度到 100% 后退出 -11，不能计为通过。第二批已记录 HEAD 页面模块可重现 GUI GC 退出崩溃；本批保留此未解决问题，没有关闭 GC 或隐藏非零退出。当前 104／6 的计数只包括正常退出的进程。

无新增依赖，未调用真实模型、游戏或 Windows 成品。相关 GUI 原生回收问题及 Windows 资源占用／替换验收仍未完成。

## 最终批次：完整 Sharing 交付

已完成 `sharing.py`、`sharing_gui.py`，General Settings 入口、中文／英文文案及 `.qm`，并扩展 `knowledge.py` 支持 JSONL。没有新增依赖、CLI 分享入口或 Package Manager。

- 四类对象可组合选择，导出两步固定实际文件快照。Assets 默认全选，Agent History 默认不选；仅隐私提示，不做扫描。ZIP 清单版本、路径别名、重复键、哈希、成员登记、大小／数量限额、链接及 Git 元数据检查均在暂存边界完成，不执行源码。
- Manifest UUID 不覆盖，包含悬空 Default 引用的 UUID 保留；弹窗明确原、新身份，提交不静默换号。同哈希 Component 复用，原 Default／历史映射保持。
- Assets 树状整组选择、冲突组／文件计数、默认收起的全部变动详情、新旧图片／标签预览、重检和全部替换／跳过。替换父逻辑组保留独立子组；失败恢复旧直属文件。
- 页面左多选右详情，逐页显示独立 Review 状态。复用 Current／Proposed／Review，通过 `PreviewRequest(review_only=True)` 返回固定版本批准，统一提交才整包安装；不创建伪 Session。未 Review 弹窗明确确认；已知失败阻止所选页面，动态运行声明不伪装成静态验证成功。
- 历史完整保留原始日志、初始基线、导出时 Candidate／页面草稿及相关 Run 日志／证据。导入只写外部知识库，生成有界阅读块、大图片缩略图；损坏草稿及非 UTF-8 原始资源保留，不作为日志协议误解析。日志引用继续检查路径／哈希／循环，并对累计展开引用字节设置上限，防止引用图放大。
- `sharing_activity` 覆盖文件选择、审查到提交；应用活动＋跨进程游戏锁与现有运行互斥。逐对象提交失败停止，报告完成／失败／未处理项；页面不自动重载，Workflow 不自动运行。
- `CONTEXT.md` 用 Sharing Package 取代旧 Capability Bundle，明确四类独立选择。ADR 0036、页面示例、Prompt／工具声明／SOP、最终用法和历史讨论指针已同步。

验证结果（仅正常退出的进程计入）：

- 最终普通全量回归：`QT_QPA_PLATFORM=offscreen .venv/bin/python -B -m pytest -q -p no:cacheprovider`，**856 passed，88 skipped，45.92s，退出 0**。包括损坏 Candidate 原样保留、引用展开上限和重复图片只验证一次等最后补充。跳过项不计为通过，Agent 默认不运行。
- 普通回归退出后，单独开启 `--run-agent-tests`，对 `test_developer_session_agent.py::test_page_tool_declarations_same_round_and_restored_drafts`、`::test_actual_gui_page_install_returns_to_agent`、`test_agent_repair_agent.py::test_sop_round_snapshot_and_actual_tool_guidance` 串行检查：**6 passed，7.16s，退出 0**。这是真实 pi＋本机 HTTP 替身，不是真实模型／游戏。
- 针对 agent_log／sharing／sharing_gui／page_packages／workflow_sharing／page_drafts／user_pages 的 pyright（指定 `.venv/bin/python`）：**0 errors**。page_preview／repair_tools 的既有类型诊断仍按第三批记录，不声称全项目类型检查通过。
- 用临时四类示例包进行中文无界面截图检查：页面左侧 Review 状态、全选／取消、资源树及新旧图片可见。静态检查和界面创建没有执行示例页面代码；没有修改真实用户数据。
- TS／QM 文案同步，`git diff --check` 通过。无界面测试不代表原生窗口焦点／Windows 文件占用／成品打包验收。

已知限制：此前记录的 Qt 退出回收崩溃未作为本功能修复；最新全量回归正常退出，但仍出现 35 个 Qt 不可回收对象的 ResourceWarning。未关闭 GC 或隐藏退出码。接近包限额时检查为同步操作；不承诺断电恢复或跨对象整体回滚。没有运行真实模型、游戏或 Windows 成品，也没有据此关闭 issue。

## 必须保持的最终边界

- Manifest **永不覆盖已有 UUID**；早期允许覆盖 Default 的决定已撤回，不做该旧方案的刷新／历史映射改写。
- Asset 独立于 Workflow，不做引用推导；逻辑名是最小选择单位。只有 Assets 有“全部替换／全部跳过”。
- 页面源码＋资源为整包，整目录替换；旧单文件继续可读，新建统一目录；旧页导出包装，安装新版后替换对应旧文件，不批量迁移。
- Review 可选，未 Review 页面额外明确确认后才安装；只保证可静态检查项，运行身份／加载／接口可能重载时失败，不能偷偷执行代码补检查。
- 不新增隐私扫描，只提示风险；不导出私人设置或凭据存储，不恢复已有日志已脱敏内容。
- 不新增通用 Package Manager、备份／云同步、自动依赖安装或跨对象整体回滚。

## 资源规则修订：实现与验证

- 新增 `file_content.py`：磁盘文件引用、分块哈希／固定版本复制、当前磁盘与内存估算、图片按需预览。文件内容不随对象清单常驻内存；页面批准的不可变快照改存磁盘副本，完整资源与日志证据仍保留。macOS 内存采样短时共享，避免按文件反复启动系统查询。
- `SharingPackage` 先检查中央目录／sharing.json 声明及成员登记，再分别估算暂存与正式副本所在磁盘。Worker 按实际字节与 SHA-256 暂存一次；最终只核验受控暂存，不再读原 ZIP。专用暂存 UUID 目录持有跨进程锁，应用启动只清理锁已释放的旧目录。
- `sharing_task` 复用现有 Operation 线程基础，进度窗保持 GUI 事件处理，取消在块／文件检查点生效并等待清理；不会因原生解析还未返回而关闭正在写入的 Worker。单对象事务及部分成功结果保持。容量未知必须额外明确确认；确认只跳过未知磁盘容量预检，不跳过结构、哈希或写入故障。
- Agent `page_resource` 的页面／Asset／知识库复制改用文件流，不再由知识库普通阅读接口的 2 MiB 限制阻断资源复制；Base64 写入仅受实际内存和消息容量约束。`page_read` 文本真正分页读取，图片返回 JPEG 预览且保存原始资源。列表、源码更新、复制、固定版本审批和日志快照全部同步文件内容表示，工具声明及示例更新。
- 新增 `test_sharing_resources.py`：超过旧对象／文件数量、超过 128 MiB 单文件流式往返、旧 36 MP 以上图片、同盘需求合并、空间不足／未知、解压取消、活跃与遗留暂存隔离。更新旧限额断言，补 GUI 响应／取消／未知容量确认。

最终结果：

- 普通全量：`QT_QPA_PLATFORM=offscreen .venv/bin/python -B -m pytest -q -p no:cacheprovider`，**865 passed，88 skipped，45.80s，退出 0**。此前两轮发现并修复进度窗与 Qt 退出状态的交互；不将失败轮次计为通过。
- 全量后补源码解析前的内存预检及失败不改草稿测试，`test_page_package_tools.py test_page_drafts.py`：**46 passed，3.80s，退出 0**。不把新增这一项算进上一轮全量计数。
- 普通测试均退出后，另串行显式 `--run-agent-tests` 运行页面工具声明／资源／恢复、真实 GUI 人工安装及 SOP 冻结三个受影响入口：**6 passed，7.17s，退出 0**。真实 pi＋本机 HTTP 替身，不连接真实模型或游戏。
- 类型检查（file_content／sharing／sharing_gui／page_packages／page_drafts／workflow_sharing）**0 errors**；双语 TS／QM 覆盖及 `git diff --check` 通过。

限制：空间与内存估算不是资源预留；原生 ZIP／JSON／Python 解析、图片解码期间不能强行中断，取消在其返回后的检查点生效。固定阈值撤销不等于本机能解析任意规模源码或索引。未运行真实模型、游戏或 Windows 成品；没有关闭 issue。
