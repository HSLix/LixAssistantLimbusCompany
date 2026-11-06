# SOP 转 Developer Skills 设计影响评审

2026-11-06。依据[已确认讨论](agent-skills-decisions.md)、当前工作区源码及本机 pi 1.5.0 实现。开发者在完整汇总后要求进入影响评审；本报告是实施前评审，不表示已迁移、模型遵循性或 Windows 验收通过。本轮不修改运行代码、不删除 SOP、不改动实际数据目录。

后续开发者已授权实施，迁移和验证见[实施记录](agent-skills-implementation.md)。下文源码位置与差距保留评审时点，不作为实施后仍未接入的结论。

## 结论与设计变化

方案可实现，未发现与既有 Session／Developer Policy／人工页面审批／进程复用决定的阻断冲突。影响集中在 Prompt、开发轮次的 Skill 内容生命周期、pi 扩展读取边界、诊断展示、资源打包与相关测试；不需要重写 Workflow 执行器或增加通用插件框架。

- 旧：按模式选定 SOP 三段全文注入；文件或 XML 损坏会阻止模型请求。新：从数据目录 skills/ 发现 Skill 元数据，三个开发入口统一展示，正文和参考资料按需 read；单个无效文件按 pi 规则警告后继续。
- 旧：详细 Workflow 规范和跨工具流程常驻 Core／Mode。新：迁入七个默认 Skills；常驻简短角色／模式、安全原则、最终 JSON 契约，system prompt 后部保留指定的一句领域知识。
- 新增：目录不存在时初始化、轮内固定的只读工作副本、每轮刷新、日志中的目录与读取结果、加载诊断。目录存在时不补齐或覆盖，空目录合法。
- 废弃：sop.md、XML 解析、固定模式组合、包内可编辑 SOP 的现行用法。先完成当前内容承接，再删除旧资源与引用；不增加旧安装 SOP 的自动迁移或双轨回退。

ADR 0034／0036 的入口权限和页面审批、ADR 0038 的 pi 按需启动与跨轮复用、现有日志的完整可还原要求继续适用。此次改变指导内容的组织和读取范围，不授予 Runtime、新工具执行或 Skill 写权限。

## 已确认的接入差距及处理要求

下列是新设计落地所需的修改，不把尚未实施的设计差距称作当前运行缺陷。

| 范围与源码证据 | 已确认现状 | 实施影响 |
| --- | --- | --- |
| [agent_prompts.py:9](../src/lalc/agent_prompts.py#L9)、[load_sop:76](../src/lalc/agent_prompts.py#L76) | Core／Mode 保存详细指导，system_prompt 全文拼入固定 SOP 组合 | 精简常驻 Prompt，保留最终输出契约；移除 load_sop／SOP_PATH，接入元数据目录而非正文全文 |
| [RepairConversation.run:324](../src/lalc/agent_repair.py#L324) | 每轮同步读取 SOP，input.json 保存 sop 正文 | 增加初始化和轮内内容准备，删除新轮次的 sop 字段；保留目录和诊断，旧日志不迁移 |
| [configured_pi:322](../src/lalc/pi_probe.py#L322)、[before_agent_start:97](../src/lalc/pi_probe.ts#L97) | 关闭 Skill 自动加载，并以宿主 Prompt 覆盖 pi 最终系统消息 | 必须显式把原生生成的 Skill 目录纳入最终 Prompt；仅移除 --no-skills 或加 --skill 不能证明目录最终可见 |
| [PiProcess.session:70](../src/lalc/pi_process.py#L70)、[扩展加载轮次配置:55](../src/lalc/pi_probe.ts#L55) | 轮次信息经过白名单写入 round.json；进程复用取决于归一化命令和连接信息 | 将本轮 Skill 路径等加入轮次传递，不能仅修改子进程启动环境；不得把每轮变化的临时路径变为导致进程重建的命令签名 |
| [read:193](../src/lalc/pi_probe.ts#L193)、[checkedEdit:209](../src/lalc/pi_probe.ts#L209) | read／edit 分别检查路径，目前都限定 Candidate | 仅 read 新增本轮 Skill 的只读范围，保持 edit 的 Candidate 和文件白名单检查；不能把共用 checkedPath 简单放宽后同时影响编辑 |
| [RepairLog.record:58](../src/lalc/agent_repair.py#L58)、[LogStore.pack:94](../src/lalc/agent_log.py#L94) | 已保存工具事件、实际请求、大文本及图片内容对象 | 实际 read 结果可复用现有留存机制；工作副本放临时目录，避免把全部未读内容意外纳入长期日志／Sharing |
| [Workbench 事件处理:1676](../src/lalc/developer_gui.py#L1676) | 对 pi_version_warning 有专用显示分支 | Skill 警告需明确接入当前聊天展示与历史还原；仅写 pi stderr 或事件日志不满足可见诊断要求 |
| [pyproject.toml:42](../pyproject.toml#L42)、[LALC.spec:17](../LALC.spec#L17)、[Windows 资源检查:93](../scripts/build_windows.py#L93) | wheel、冻结包及组装检查均指定 sop.md | 改为分发完整内置 Skill 目录及参考资源，更新组装检查和测试，不依赖源码树存在 |

建议复用 pi 导出的 loadSkills 和 formatSkillsForPrompt，显式指定本轮固定内容目录并关闭默认来源。loadSkills 已包含重名诊断；不必另写 YAML 解析器，也不必为此启用个人 Skill／扩展／提示模板发现。保留现有 pi 进程和就绪握手；目录及诊断可以经现有事件通道传给宿主，不引入新的后台服务。

## 内容承接清单

实施时逐项对照当前有效正文和 Core／Mode，语义合并后仍须能找到每项指导的归属；不能只检查七个文件存在。

| 默认 Skill | 当前内容来源与必须保留的要点 |
| --- | --- |
| Workflow 开发 | sop.md Construct：目标与证据、检查 Candidate、最小修改、外部知识库参考及适配 LALC 的提醒、纯分析无需修改、按实际要求验证与总结；共用规范和验证流程改为引用相应 Skill |
| 故障修复 | sop.md Repair：现场证据与旧截图区别、定位原因、证据不足不大改、最小修复、按日志调整、用户停止后的处理；引用共用规范和验证流程 |
| Workflow 编写规范 | Core 角色与架构细节及 Construct／Repair 重复规范：调用层级、ctx.call／ctx.action、Recovery Rule、Step 可恢复职责、完成证据、完整匹配结果及歧义日志、动作与包装签名复用、Plan 状态／详细失败字段／成功 output、取消传播、ctx.log、中文 docstring |
| 素材处理 | sop.md Asset 及 Core 素材约定：共享影响、完整匹配结果、同图 OCR 与失败含义、坐标／干净像素、韩文限制、少掺文字与 OCR 替代建议、preview_id 原像素保存、同图不等于跨状态可靠、标签和同哈希复用、归档删除及验证 |
| 页面开发 | sop.md Page 及 Construct 页面约束：稳定 ID 和配置兼容、明确的破坏性变更授权、SUPPORTED_TASK_IDS／PAGE_ID／Default 的接线、整包草稿与资源、页面契约、不加依赖、失败后修订、专用人工审批、固定版本、试填不落正式配置及安装后主动重启 |
| 验证与试运行 | Core 跨工具及各 SOP 验证步骤：完整 Validate、校验会导入代码且不是安全隔离、Publish 不执行／不设置 Default、显式已发布版本运行、运行证据及拒绝无 Run ID、等待结果、不并行改动或操作游戏、停止后总结、静态与真实验证区别 |
| 人工反馈 | Core 跨工具和 Page 反馈指导：仅实际启用时使用、同轮等待、Confirm 可空且不证明状态或审批、Skip 不授权也不代表完成、不重复追问、观察与授权的区别、信息不足时如实结束 |

专用工具边界已有程序承接：crop_asset 校验本会话 preview_id（[repair_tools.py:527](../src/lalc/repair_tools.py#L527)），trial_run 使用明确 manifest_id（[repair_tools.py:278](../src/lalc/repair_tools.py#L278)），page_preview 走人工请求（[repair_tools.py:150](../src/lalc/repair_tools.py#L150)）。移出 Core 不代表删除这些校验，也不将所有规则都声称为可由程序强制证明：例如“完成证据是否可靠”和“不夸大真实验证”仍需要指导及模型验收。

## 读取、生命周期与潜在风险

**已确认：pi 原生发现不是 LALC 的读取安全边界。** 本机 pi 1.5.0 的 skills.js 会跟随目录及 SKILL.md 链接。只在模型 read 时检查路径仍太晚：元数据发现可能已读到目录外内容。必须在交给 pi 发现之前限制可见文件范围，校验根目录、符号链接及 Windows junction 等边界；越界项诊断，不复制目标内容，不反向改写源目录。普通 Candidate 的读写检查原样保留。

**已确认：仅保存源路径或哈希不能冻结内容。** 本轮需要独立固定正文和附带参考资料；硬链接也会受原地写入影响。现有 [FileContent／copy_content](../src/lalc/file_content.py#L115)、[页面磁盘副本方式](../src/lalc/page_packages.py#L134)可供复用，但不能直接套用页面特有的 page.py／页面契约。采用磁盘临时副本和清理所有权即可，无需版本数据库。初始化的失败、并发创建、复制途中变更、取消或磁盘耗尽必须不覆盖已有 skills/、不遗留被当作完整默认资源的半成品。

**潜在风险：大目录的轮次准备成本。** 轮内固定且允许附带资源，会产生复制、空间和时间成本。按实际可用资源处理并清楚报错，不为“快照”把全部文件常驻内存；本次未测量大目录性能或 Windows 复制行为。

**潜在风险：Skill 选择与每轮重读的可靠性。** 当前历史重放只过滤 system 消息（[pi_probe.ts:66](../src/lalc/pi_probe.ts#L66)），旧 read 结果继续存在，符合保留历史的决定。应在当前 Prompt 明确“本轮使用前重新读取”；保留历史而不扩大旧路径的访问范围。不应擅自新增“未读完全部 Skill 就禁止工具”的状态机；本机 HTTP 替身只能证明接入行为，不能证明真实模型总会选择和重读正确 Skill。

**格式兼容范围。** 按 pi 原生诊断处理缺 description、重名及命名警告，不把所有 warning 一律跳过。原生 formatSkillsForPrompt 会隐藏 disable-model-invocation 项。当前 LALC 用户消息包在 runtime_context／user_request 中，而 pi 的 /skill:name 展开只检测消息开头；采用原生格式和发现不等于自动获得完整 pi 命令界面。第一版不额外承诺 /skill 命令、安装／更新管理器或 allowed-tools 自动授权，避免超出已确认的手工维护范围。

## 测试与文档迁移

| 验证层次 | 必须覆盖 |
| --- | --- |
| 普通文件与初始化测试 | 不存在则完整初始化；已有空目录／自定义内容不补齐、不覆盖；同名普通文件、链接、复制失败／磁盘耗尽、并发与取消不损坏原内容 |
| 普通 Prompt／内容检查 | 保留 JSON 和安全原则、领域句在后部；目录不含正文全文；七类指导逐项承接；最终移除 SOP 解析及新包中的旧资源 |
| 真实 pi＋本机 HTTP 替身 | 三入口同目录但原工具集不变；先看元数据再 read 正文和引用文本／图片；缺 description／重名／空目录；原始可编辑目录及 Skill 写入拒绝；Candidate 权限保持 |
| 跨轮与生命周期 | 同轮改源文件不改变正文和参考资料；下轮添加／修改／删除生效且 PID 可复用；跨 Session 不串内容；格式纠正禁工具不污染下轮；中途退出不重放、取消释放临时副本 |
| 日志与恢复 | 目录和诊断可见，读取内容能在源文件删除及临时副本清理后独立还原；未读正文不进入长期日志；旧 SOP／Skill 历史保持可恢复，实际请求与日志内容一致 |
| wheel／冻结包 | 内置七个 SKILL.md 及参考资料随包存在，离开源码树可初始化；Windows ZIP 检查更新；Windows 原生权限／路径／junction／成品另验 |

现有 [test_agent_prompts.py](../tests/test_agent_prompts.py)、[SOP 集成测试](../tests/test_agent_repair_agent.py#L33)直接断言 XML 和按模式正文，必须替换为新契约。保留 [进程复用测试](../tests/test_external_search_agent.py#L63)并增加 Skill 更新场景；现有 Session 权限、格式纠正、图片及页面审批回归不能因迁移被移除。

现行用法须更新 docs/agent-repair.md 的“Prompt 与 SOP”及 input.json 说明、docs/windows-packaging.md 的 SOP 资源章节、docs/current-state.md 的入口；其中 Windows 章节仍称“三个正文区”，而当前是四段，这是此次检查确认的现有文档漂移，应随旧章节替换一并消除。历史 agent-prompt-impact-review／implementation、pi-1.5-compatibility 等保留原时点证据，只加清晰的后续替代链接，不能把旧通过数字当作新设计验收。

## 执行顺序与本轮证据

1. 固定当前 SOP／Core／Mode 内容承接清单，先创建七个默认 Skills 并去除重复规则，保留依赖指引。
2. 加入只在目录缺失时初始化及本轮固定副本，明确失败和清理；沿用 pi 原生发现和目录格式。
3. 串联轮次配置、最终 Prompt、只读 read、诊断展示和日志；保持进程复用和原有权限／最终协议。
4. 更新打包及现行文档；内容和资源接线齐备后删除 sop.md 和旧加载逻辑，不留兼容回退。
5. 先普通回归，退出后再显式运行相关 Agent 回归；真实模型、Windows 成品和游戏证据分别记录。

本轮执行了源码追踪和一个临时目录中的 Node 断言检查，直接调用本机 pi 1.5.0 的 loadSkills／formatSkillsForPrompt，共 8 项断言通过：元数据不含正文、路径展示、有效项展示、缺 description 诊断、重名诊断及保留一项、禁用自动调用项隐藏、目录链接跟随。临时目录已清理，未启动 pi 进程、Agent 工具循环、模型服务或游戏。

未运行 pytest、构建包或性能基准；本文列出的测试是实施验收计划，不是已通过结果。此前测试和平台问题不在此次复验范围内。无新增阻断性的产品决策；上述边界检查和原生功能限制需要在实施与说明中落实。
