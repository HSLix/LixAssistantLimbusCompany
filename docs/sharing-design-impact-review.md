# Sharing 设计影响审查

当前本地实现及最终规则见 [Sharing](sharing.md) 和 [ADR 0036](adr/0036-share-selected-objects-and-install-complete-page-packages.md)，验证见[实施记录](sharing-implementation-progress.md)。本文保留讨论／审查历史，早期 Manifest 覆盖、独立草稿导入等方案已由后续决定替代。

2026-11-04。状态：审查及 Manifest UUID 简化修订后，开发者明确同意开始实施，要求控制每批范围。本文保留审查时证据；当前已完成本地实现及回归，见[实施记录](sharing-implementation-progress.md)；本文保留实施前的分析，不代表真实环境验收。

输入：[逐项决定](sharing-decisions.md)和本次聊天最终汇总。开发者明确要求先 review，review 同意后再实施。以已确认决定为目标，不因既有代码或旧文档而撤销决定。本报告检查本地 `architecture-refactor` 工作区；未读取远端 issue 当前状态，不作票据状态结论。

## 结论

方案可实施，但不是只在 Settings 增加两个按钮。主要工作是页面由单文件扩展为整包、导入专用非执行式检查／提交、Manifest UUID 冲突时分配并确认新身份，以及外部历史真正可读。可复用现有 Manifest 静态解析、Component 内容寻址、Asset 名称／图片校验、Session 锁、日志内容引用和页面三 Tab 预览。

审查后修订：开发者撤回 Manifest 覆盖，改为 UUID 占用时分配新 UUID 并弹窗确认。本文已按新决定更新；上一版关于允许覆盖、Default 间接变更及历史映射失效的实施要求撤销。

不新增 Workflow→Asset 分析、隐私扫描、通用 Package Manager、跨对象整体事务、自动安装依赖、云同步或运行时 Agent 授权。批准本报告不代表这些附加能力获准。

## 设计变化及文档影响

| 既有约定／草稿 | 本轮设计 | 需同步的权威说明 |
| --- | --- | --- |
| Capability Bundle 绑定 Manifest 与所需 Assets | 四种可组合对象；Assets 独立树选，默认全选；不推导依赖 | `CONTEXT.md:135` Capability Bundle；Stage 2 分发远景及 Stage 5 规格的相关描述 |
| 发布产生新 UUID，既有 Manifest 不覆盖 | 导入保留未占用来源 UUID；占用时分配新 UUID，显示原／新 UUID 并确认；不覆盖本地 Manifest | 补充导入身份重分配说明，与 ADR 0003 的不可覆盖约定一致；不改变 publish、Default 或 Agent 权限 |
| Page Draft 是一个完整 Python 文件，资源目录不支持 | 每页源码＋资源目录整包版本；旧单文件继续可读，不自动批量迁移 | Stage 5 #339/#340 决定、ADR 0034、`docs/agents/domain.md`、页面示例及工具契约 |
| Preview 人工批准即安装 | Agent 原流程保留；Sharing Review 只批准待提交版本，Import Selected 才安装；未 Review 可额外确认后安装 | Page Draft／Page Preview 术语需明确人工导入例外；页面审批及安装文档 |
| 草稿建议隐私扫描／三类别 Tab | 不新增隐私扫描；只提示风险；四个 Tab | Sharing 最终规格、双语文案；不把旧提案当验收标准 |
| 每次导入一次整体动作，失败语义未定 | 按对象提交，失败即停止，已完成保留，结果列出未处理项 | Sharing 错误处理及验收 |

`docs/sharing-decisions.md` 中保留了讨论演进，部分早期段落仍写“待确认”，实施前应整理最终规格并保留历史指针，不能把这些早期语句与后续确认并列为当前规则。建议新增一份 ADR 记录页面整包／可跳过 Sharing Review 的取舍，并说明包导入身份规则；Manifest 不再需要人工覆盖例外，不重写历史验收证据。

## 已确认的实施差距

以下“已确认”表示源码证明与新目标有差距，不表示旧实现违反当时要求。

### 1. [P1] Manifest 现有公开检查路径会执行源码

证据：[`ManifestManager.validate`](../src/lalc/manifest.py#L244) 调 `_prepare` 后调用 `_load`；[`load`](../src/lalc/manifest.py#L182) 同样调用 `_load`；[`publish`](../src/lalc/manifest.py#L145) 生成新 UUID、写 Components 并加载模块。`_load_module` 在 `manifest.py:993` 使用 `exec(compile(...))`。所以三者均不能直接用于包检查或导入确认。现有 [`ManifestReference.read/source`](../src/lalc/manifest_reference.py#L29) 已展示不加载源码的成员／哈希访问边界。

必要修改：复用或适当提取 `_prepare` 的静态阶段，按 ZIP 中的受控成员解析 Manifest／Plan／源码、检查哈希及登记关系，不调用加载器。Component 落盘复用内容寻址及相同字节去重思想；不删除共享 Component 源码。Manifest 准备完整后以不覆盖方式创建，已占用来源 UUID 先走新 UUID 确认流程。原 publish 的新 UUID、运行时加载与 Agent 权限保持。

### 2. [P2] Manifest UUID 冲突改为显式重分配，保留已有映射

证据：ADR 0003 要求 Manifest 新建不覆盖，当前 `publish` 也是新 UUID／不覆盖创建。Default 仅存 UUID（`manifest.py:209–239`）。原提案同 UUID 覆盖会影响依赖 UUID 判断变化的 [`UserWindow.render_state`](../src/lalc/gui.py#L704)，修订后已不存在该触发条件；原 Default／历史内容不因导入被改写。

必要修改：UUID 未占用就保留；占用时（包含同 UUID 同内容）为该对象分配新 UUID，弹窗同时列原 UUID 与新 UUID。确认后仅改本地导入副本 `manifest_id`，不改 Component 哈希或来源 ZIP。导入结果记录原→新身份，不新增保存 Manifest schema 字段。最终排他创建，新 UUID 若再次被占用就写入失败并报错，不能覆盖或静默换号；按用户进一步确认的简化，不另设计再次冲突交互流程。用户取消时不为该对象写入 Manifest，其他已完成对象按逐对象提交规则保留。

取消上一版为 Manifest 覆盖增加的任务强制刷新、历史映射警告、Default 内容替换与缓存处理范围。导入不改变 Default；不强制调用会执行源码的 [`refresh_tasks`](../src/lalc/gui.py#L604)，不清空基于 Component ID 的有效缓存，不重建 Session 或改写已有历史。新增版本会由现有 Manifest 枚举入口读取。外部历史保留原始来源 ID，原→新映射只是导入说明，不把来源批准迁移为本地权限。

### 3. [P1] 页面目录化必须贯穿所有工具与版本快照

证据：[`discover_pages`](../src/lalc/user_pages.py#L119) 只扫描顶层 `*.py`；[`PageDrafts.path/list/create/update`](../src/lalc/page_drafts.py#L72) 只接受单个 Python 文件；[`snapshot`](../src/lalc/page_drafts.py#L159) 只保存源代码字节／哈希；`check_registration` 只枚举正式顶层 Python 文件；`install` 只替换一个文件。[`RepairTools.page_preview`](../src/lalc/repair_tools.py#L104) 的证据日志也只存单个 source／sha256。模型声明 [`pi_probe.ts:240`](../src/lalc/pi_probe.ts#L240) 明确写 single-file、No resources；[`PAGE_TOOLS`](../src/lalc/agent_policy.py#L10) 是显式权限集合。

必要修改：引入共同的页面包读取／快照／整包安装能力，在现有页面模块边界内复用，不建设第二套页面管理系统。新页面采用固定入口（建议 `page.py`）与页内资源目录；资源路径相对包根，预览使用固定整包副本，正式加载使用正式包。包版本由规范化相对路径及每个文件哈希共同确定，新增／删除／修改图片均改变版本。源码检查与资源读取不得执行模块。

调用方清单：`user_pages.py`、`page_drafts.py`、`page_preview.py`、`repair_tools.py`、`pi_probe.ts`、`agent_prompts.py`、`agent_policy.py`、`developer_gui.py` 的预览及证据链、Session 恢复与导出、示例和页面测试。扩展 page_* 的目录列举、相对文件读写及图片复制／查看能力；资源输入只能来自明确受控的字节或已授权资料，不能借资源接口获得任意本地文件读取／通用终端。CLI／Repair／Runtime 不继承写页工具，Agent 不获得独立安装或删除正式页的能力。不自动新增第三方依赖。

兼容：旧正式单文件及旧 Session 草稿继续读取；新建为目录。复制旧页、导出旧页时包装为目录，批准安装后移除对应旧正式文件，防止重复 PAGE_ID／TASK_ID。替换失败保持原目标，配置仍在 `user-settings.json`，不导入预览试填、不自动重载。不要移动全部现存页面或修改旧日志格式。

### 4. [P1] Sharing Review 不能直接照搬现有“安装”按钮

证据：[`PagePreviewDialog.install`](../src/lalc/page_preview.py#L201) 在确认时立即调用 `drafts.install`。`load_pages` 创建页面并运行注册检查；`check_registration` 会导入其他正式页。[`Developer GUI.show_page_preview`](../src/lalc/developer_gui.py#L1457) 依赖当前 Agent 轮次及 Construct Session；Sharing 没有这些前提。

必要修改：共享页面比较组件及安装底层，但分别传入 Agent 的“批准并安装”和 Sharing 的“批准版本、返回审查界面”行为；不能为了复用而伪造可恢复 Developer Session。Sharing Review 回调不写正式页，取消导入不遗留提前安装结果。列表每页独立记录 Review 状态与整包版本。

未 Review 路径只运行包／路径／哈希／可静态核对的声明检查，不调用 `load_page_module`、`create_page` 或现有会加载模块的 registration 检查。已检查失败项不能冒充未 Review；确定的结构／哈希／注册冲突仍阻止对应项提交。未 Review 页面清单的额外确认授权安装固定包，不等于运行验证。

**审查补充边界，须随本报告批准：** 现有契约允许 PAGE_ID／TASK_ID 不是字面量（`pi_probe.ts:243`），所以跳过运行式 Review 后不能保证获知实际运行时身份，也不能证明 QWidget／submit 契约有效。包内声明及可静态提取的信息只能标为声明／静态检查结果；无法核实的运行时身份、加载与接口明确显示“未验证”，额外确认中说明可能在重载后报错。正常重载仍执行实际注册检查并拒绝冲突页面，不能把失败页面注册进可运行列表。若要求所有安装都事先证明完整运行契约，则与已接受的可跳过 Review 冲突，需要重新决定，不能偷偷自动运行源码补检查。

### 5. [P1] Asset 逻辑组不能当作可任意递归删除的目录

证据：[`asset_name`](../src/lalc/assets.py#L17) 允许 `a/b` 层级；[`match`](../src/lalc/assets.py#L258) 仅读取该逻辑名目录的直接 `*.png` 和本层标签。因此 `a` 与 `a/b` 可以是两个独立逻辑组。直接删除 `assets/a` 来替换 `a` 将连带删除未选的 `a/b`。

必要修改：树的父节点批量操作与逻辑组选择分别表达，允许节点既有本组内容又有子组。整组替换范围是该逻辑名直属图片集合及标签，保留其他逻辑名的子目录；同路径相同字节去重，不能只按文件名认定相同。采用受控准备／替换与普通失败恢复，不调用需要游戏截图的 [`AssetLibrary.remove`](../src/lalc/assets.py#L183)，也不扩大 Agent 的删除权限。图片解码需有尺寸／像素上限，避免预览异常图片耗尽资源。

### 6. [P1] “GUI 运行中不可操作”不是完整的现有保证

证据：[`ApplicationService.activity`](../src/lalc/application.py#L104) 拒绝同进程运行／其他活动，但仅 Agent／Capture 名称取得跨进程 game 锁。GUI 各控件分开按 busy 更新，并非整个 General Settings 一律禁用。`tests/test_user_gui.py:179` 验证运行时仍可修改 Agent 设置；`:211` 验证 Agent 活动期间仍可导航到 General Settings。两项本次执行通过。

必要修改：为 Sharing 入口、Review、重新检查和最终提交显式接入互斥；按钮禁用不是唯一保护。最终检查／写入期间持有共享活动边界，GUI 对话应用级模态防止另一窗口启动活动，涉及 CLI 同数据根并发时需协调既有 game／Session 锁；不能只假设打开窗口时空闲就永远空闲。历史快照还需取得对应 Candidate／Session 锁，保证聊天、基线、草稿在同一稳定导出状态。避免已持 Agent game 锁的预览再次获取同一排他锁。

### 7. [P2] 历史入库之后还需要可读入口

证据：[`AgentHistory.rebuild`](../src/lalc/agent_history.py#L206) 仅扫描本地 Session／interaction／diagnostic 固定目录，`read` 依赖本地轮次索引。外部知识库 [`KnowledgeLibrary.read/view`](../src/lalc/knowledge.py#L260) 拒绝超过 2 MiB 的文件；文本后缀表 `knowledge.py:22` 没有 `.jsonl`，原始事件日志将进入图片分支而无法正常阅读。[`LogStore.unpack`](../src/lalc/agent_log.py#L118) 已处理相对内容引用、哈希与循环，能复用。

必要修改：使用独立 `knowledge/imported-agent-history/` 命名空间，保留完整对话及内容对象；不写本地 history DB、不调用 DeveloperSession.restore、不因外部 UUID 相同覆盖本地 Session。相同导出内容可去重，不同内容保持独立来源。提供既有 knowledge 工具可读取的分块文字／图片索引，或对这一受控格式增加有界读取；不以摘要替代完整信息，不为大文件关闭所有大小限制。无需新增独立历史应用或语义检索系统。

导出明确选择 Session 的基线、当前 Candidate、页面包及该对话的日志／引用内容，不复制整个 data_root 或知识库。复用 `LogStore` 的自包含引用；不把来源中任意绝对路径当作需要读取的附件。私人配置和凭据存储不在对象清单内；不新增内容隐私检测，保留已有脱敏字节。

### 8. [P1] ZIP、重检和逐对象提交需要新受控边界

已有 ZIP 代码 [`scripts/build_windows.py:33`](../scripts/build_windows.py#L33) 用于固定官方摘要的 pi 构建输入，检查后在构建中解压；不是用户共享包导入器，不能直接套用或宣称已覆盖不可信导入。

建议最小实现：标准库 ZIP＋版本化索引，明确对象成员、相对路径、大小和 SHA-256；先在独立临时区验证，再触及目标。逐成员有界读取，拒绝路径穿越、绝对路径、Windows 保留名称／大小写别名冲突、重复成员、符号链接／特殊文件、文件目录碰撞、超数量／大小／解压上限、未登记可安装内容及缺失成员。ZIP 哈希证明内容一致，不证明作者身份或源码安全；不引入签名体系。

导出从明确选择快照生成清单，成功写完临时 ZIP 才替换用户目标，失败不留下被误认为成功的包。导入重新检查读取当前目标占用／内容，最终提交再次核对所确认版本；包或目标变化时要求重新检查／确认，不能复用旧的 Asset／页面替换许可或 Manifest 新 UUID 确认。Tab 已查看、对象选中、检查错误、Review 和对象提交确认分别保存，红点只表示查看状态。

提交顺序固定并在界面说明；每对象完成准备后再改活动目标，失败停止并返回成功／失败／未处理。Manifest 的 Components 可先写共享哈希库再提交 Manifest；失败留下未被引用的相同哈希文件符合原 ADR 0003，不属于损坏原对象。目录替换至少覆盖普通异常回退，不能声称 Windows 两次 rename 或旧单文件→目录替换天然是单步原子事务。恢复再次失败时保留可定位的旧副本，报告位置，不能清理掉唯一旧数据。

## 潜在风险与待验证事项

- **Windows 文件占用／崩溃中断**：已加载图片、页面或外部进程可能妨碍改名／删除；当前证据只支持提出风险，未实机复现。普通异常故障注入与 Windows 实机测试必须分开报告，不承诺断电级恢复。
- **资源加载版本一致性**：页面可能懒加载图片，若预览引用可变草稿路径就可能显示与批准版本不同的资源。整包快照目录须在预览结束前保持稳定，并测试资源单独变化导致 Review 失效。
- **旧单文件的外部资源依赖**：旧契约没有登记任意外部资源；包装旧 `.py` 不能证明捕获了作者自行读取的外部文件。无法识别的旧页资源不能自动猜路径复制；需要作者整理为页内资源，并在清单中说明范围。
- **日志的额外 Run 证据**：对话内引用自包含可验证，工具结果中的 Run ID 或外部路径不一定等于日志目录内文件。应检查真实记录形态，仅按已知受控 Run 关联收集必要证据，缺失明确列出，不递归扫描任意路径。
- **无隐私扫描的已接受风险**：聊天、截图、源码及页内资源可能包含私人信息；仅显示警示，不声称检测过或阻止过泄露。

## 测试影响与实施顺序

重点阅读了 `test_page_drafts.py:130,181,398` 的失败保护、精确预览版本和重载后 Plan 配置测试，以及 `test_user_pages.py:30` 的旧单文件发现用例；执行了下述四项现有检查。还按名称定位了 `test_assets.py`、`test_manifest.py`、`test_agent_history.py`、`test_knowledge.py`、`test_developer_session.py` 等相关测试入口，未逐个执行或审计其全部断言。这些旧测试不能证明新 Sharing、整包版本或不经 Review 导入通过。

按依赖顺序实施：

1. 整理最终规格及 ADR 例外；确定页包入口／资源定位和 ZIP 对象索引，不改变 Manifest schema 或 Component ID。
2. 完成共享页包读写／整包快照／安装，兼容旧页与旧 Session，接通全部 page_* 声明／权限／提示／证据链；补目录图片、单独资源变化、旧页转换、配置保留、失败恢复和工具越界测试。
3. 完成 ZIP 检查与四类对象导出／导入，补非执行哨兵、损坏哈希、异常路径、大小限制、UUID 冲突重分配／取消／再次占用、原 Manifest／Default／历史不变、同哈希复用、嵌套 Asset 组不误删、外部历史不混入本地 Session 及大日志可读测试。
4. 接入 Sharing GUI 和双语文案，补四 Tab 红点、树半选、页面多选／Review 状态、未 Review 名单确认、重检失效、取消不提前安装、逐对象部分完成及活动期间拒绝提交测试。
5. 执行相关普通回归；因页面 Agent 工具契约确实改变，再按项目规则选择相关 Agent 接入测试单独串行运行。真实模型、Windows 成品／真实资源文件占用及游戏验收另列，跳过项不得记通过。开发者验收前不关闭票据。

## 本次验证及批准范围

本次只改文档，无业务实现、无新增测试、无模型请求、无页面安装或数据迁移。执行四项现有定向检查：

```text
QT_QPA_PLATFORM=offscreen .venv/bin/python -B -m pytest -q -p no:cacheprovider \
  tests/test_user_gui.py::test_user_run_blocks_developer_activity_but_allows_settings_and_idle_close \
  tests/test_user_gui.py::test_agent_activity_blocks_user_start_but_not_navigation_or_settings \
  tests/test_page_drafts.py::test_preview_independent_memory_no_submit_and_install_exact_version \
  tests/test_knowledge.py::test_limits_and_invalid_text_are_explicit
```

结果：**4 passed，0.96s**。这是当前行为的替身／离屏验证，不是新功能验收。

建议开发者批准上述修改范围及未 Review 的验证能力边界后再实施。若不接受“未 Review 安装不能预先证明运行时页面身份与契约”，需先调整该一项设计；其他已经确认的决定无需重新讨论。
