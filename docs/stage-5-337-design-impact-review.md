# #337 — 外部知识库与受控 Git 设计影响审查

2026-11-01 更新：开发者已授权开始实施，见[本地实施记录](stage-5-337-implementation.md)。开发者随后人工验收通过，#337 已关闭。下文为实施前审查证据，非当前代码差距清单。

2026-11-01。依据 [#337](https://github.com/HSLix/LixAssistantLimbusCompany/issues/337)、[Stage 5 规格](stage-5-agent-workbench.md#外部知识与-git-内容的版本语义)、[ADR 0034](adr/0034-extend-developer-agent-with-reviewed-page-drafts.md)及[本轮已确认决定](stage-5-337-decisions.md)。当前为评审结果，等待开发者确认后实施；不表示 #337 已完成。

## 设计变化与保留边界

| 原有要求 / 未细化点 | 本轮确认 |
| --- | --- |
| 每轮首次访问每个仓库自动尝试一次 fetch | 列目录不触发；读取文件、内容检索及 Git 历史访问触发；跨库检索对实际参与的仓库分别处理 |
| 支持文档与图片，未限定格式 | 文本读取与检索、图片查看；无 OCR；PDF / Word 等仅列出并提示不支持解析 |
| fetch 失败可读本地、不得遗留等待 | 使用预先配置的非交互认证；每次 fetch 最长 30 秒；失败后 status、不自动重试；取消清理进程 |
| 未确定 Git 分发方式 | 使用系统 Git，不捆绑或自动安装；不可用则跳过、记日志、本地访问继续，不弹窗；结果保留未检查状态 |
| Git 不得绕过受控执行边界 | 保留开发者正常连接与认证，禁用外部 diff / textconv 等非必要扩展；Agent 不改配置、不指定额外命令；不建设全面配置审查机制 |

保留：仅 GUI Construct / Repair 接入，CLI / Runtime 不自动继承；知识库限数据目录且只读，Git fetch 是对象与引用元数据同步的限定例外。禁止 clone、参考项目执行、工作区更新、push 和任意命令 / 写出路径。默认 upstream 的 before / after 完整区间、HEAD / 指定提交 / 工作区的区别、缺失 upstream 或 detached HEAD 时的不确定状态均保持。

不存在需要新 ADR 的架构替换，也未新增领域术语；本轮细化写入专项决定即可。曾提出的“拒绝所有仓库级执行配置”已撤回，不进入实现。

## 已确认的实现差距与影响

### 1. 工具权限必须按入口拆分，不能直接扩大共用集合

证据：`src/lalc/agent_policy.py:3–16` 的 BASE_TOOLS 同时构成两种模式和 GUI / CLI 的白名单；返回值也按 BASE_TOOLS 排序。`src/lalc/agent_repair.py:234–244` 将交集传入 RepairTools，`src/lalc/repair_tools.py:RepairTools.call` 在分发前检查权限。TypeScript 的实际授权及启用工具另见 `src/lalc/pi_probe.ts:108–110,266–285`。

结论：当前没有知识库工具的完整可达路径。实施需同时更新 Python 策略、宿主分发表、TypeScript Schema / 注册与启用集合；保留既有 CLI 集合，GUI 两种模式显式增加新能力。不得只向 BASE_TOOLS 追加名称而使 CLI 一并获权。生产调用已传 allowed；直接构造 RepairTools 的默认值也需保持保守。

### 2. 应增加独立只读知识库入口，不放宽 Candidate read / edit

证据：`src/lalc/pi_probe.ts:178–214` 的原生 read 和 edit 共用 Candidate 根目录；edit 进一步限制为本轮已有文件。`src/lalc/manifest_reference.py:16–28,62–75,85–101` 已有纯数据读取、真实路径 / 符号链接约束与分页模式，但针对的是 Manifest 成员及哈希身份，不能直接当作外部资料读取器。

实施建议：在 `data_root / knowledge` 下提供独立列目录、文本检索、文本 / 图片读取及受控 Git 操作。名称与分页参数可在实现时细化；不新增通用 shell 或可透传的 Git 参数串。根目录、文件、仓库目标、提交引用及路径均在实际访问时校验，Git 元数据不作为普通资料遍历。复用现有分页、错误与工具结果约定，不新建索引服务或复制 Manifest 身份协议。

返回来源路径、读取范围及工作区 / 提交身份；工作区内容需要实际内容标识，不能仅用 HEAD 代表未提交字节。检索及 diff 必须限制输出、明确截断并支持续读；续读遇到来源变化应提示失效或变化，不能将不同版本拼成完整结果。列出不支持文件不代表解析成功。

### 3. 自动 fetch 的轮次状态与 Git 取消需要新增实现

证据：`src/lalc/agent_repair.py:260–290` 每次用户消息启动一轮并清除工具取消状态；RepairTools 在连续对话内复用。`agent_repair.py:412–423` 将工具交给后台线程，取消时设置事件并等待线程结束。`src/lalc/pi_probe.py:170–232` 的进程清理仅拥有 pi 进程，不能替未来 Git 进程完成清理。

实施：以每轮实际开始时清空的仓库尝试集合记录自动 fetch，失败同样算已尝试；列目录不入集合，显式 fetch 独立执行且不引起随后的重复自动同步。重启 / 续聊不恢复旧后台操作，也不自动重放；下一条用户消息是新轮次。

Git 子进程使用固定参数、无 shell 拼接；读取 before / after upstream、fetch 与随后 status 分别保留结果。fetch 失败或部分更新不能伪造无更新，status 失败也不抹掉 fetch 结果。无 upstream / detached HEAD 不猜远端或分支。fetch 的 30 秒超时、输出上限、取消及必要的子进程清理须贯穿宿主线程等待；取消后的状态采集也必须有界。

### 4. 图片与日志可复用传输，但不能直接复用 Asset PNG 限制

证据：`src/lalc/repair_tools.py:RepairTools.image` 要求 PNG；`src/lalc/agent_repair.py:171–191` 的附件读取已有实际图片识别与原字节留存路径。`src/lalc/pi_probe.ts:269–277` 可通过独立结果文件传输图片；`src/lalc/agent_repair.py:54–55,74–92`、`src/lalc/agent_log.py:44–48,73–86` 已负责脱敏、结果留存及内容引用。`src/lalc/developer_session.py:18–68` 恢复已有工具结果，不重放调用。

实施：保留知识库原图及其来源 / 内容身份，沿用结果文件、日志图片引用与恢复关联；按实际图片内容识别格式，不能因为 Asset helper 只接受 PNG 就把所有资料图片都限定为 PNG。读取失败不返回上次图片。无需改日志格式或迁移旧 Session。

潜在风险：`src/lalc/agent_diagnostics.py:11–25` 主要清除已知密钥及常见认证字段，尚不能据此证明所有 Git URL / stderr 都已安全。Git 输出可能包含独立于模型密钥的 URL 凭据；需在展示、模型返回及落盘前针对这类诊断清理并补测试，不记录完整认证配置。

### 5. GUI 入口、提示与发行说明需要一起交付

证据：`src/lalc/developer_gui.py:890–906,1189–1205` 已有 More 菜单和目录打开模式，但当前工作区 / 正式页入口不承担知识库目录职责。`src/lalc/pi_probe.ts:89–104` 从实际启用工具生成概览，运行规则仍说明 Candidate 相对路径。`scripts/build_windows.py:66–95` 打包应用及可选 pi，没有 Git 运行时分发步骤。

实施：复用菜单与 open_directory 增加知识库文件夹入口，延续现有中英文机制；工具说明明确知识库相对根、外部资料只是参考以及 fetch 跳过状态。补充 Windows 需系统 Git、不可用降级及非交互认证说明，不增加安装器、Git 设置页或新依赖。保持发布包既有资源校验。

评审后补充：开发者要求知识库目录不存在时可直接创建空目录。当前 open_directory 仅对不存在目录报错，而 open_pages 已有先 mkdir 再打开的局部模式。知识库入口采用同类局部处理，不修改所有目录打开入口的缺失语义；使用应用数据目录，不依赖 Session。测试覆盖两种模式、未开始会话可用、首次创建 / 再次打开不损坏内容、普通文件占位及创建 / 打开失败，且点击不触发 fetch。创建由 GUI 执行，不扩大 Agent 写权限。

## 潜在风险与验收边界

- 正常 Git 连接 / 认证允许调用开发者已有辅助程序；这不是对恶意本机配置的隔离承诺。禁用内容查看的非必要扩展与限制 Agent 参数，不能宣称建立了操作系统安全沙箱。
- 多个 Session / 进程仍共享仓库引用；同一进程的 Session 活动互斥不证明跨进程 fetch 已串行。实施应复用现有 ProcessLock 对同一真实仓库的同步采集做互斥，并验证可取消等待与失败释放，不新建常驻服务。
- 远端更新或人工修改可发生在分页之间，磁盘及子进程输出也可能很大；需要版本 / 内容标识、输出限额与续读一致性测试。
- Windows 上系统 Git、凭据管理器、SSH 辅助进程及取消清理需要原生验证；Mac 替身或本地仓库结果不能代替 Windows 成品、真实模型或游戏验收。
- 评审收尾时工作区出现并行 OCR 开发改动，包含 `repair_tools.py`、`pi_probe.ts`、运行服务与依赖；已核对两个共享工具文件的差异，目前为游戏截图 OCR 接入，并非知识库功能。后续实施须重新读取实际接口，不覆盖该工作；本票知识库图片不做 OCR 的决定保持。
- 本次已读取的远端 #336 仍为 OPEN；其本地实现可供接续，关闭与开发者验收状态不可代为推断。本票不自动关闭 #336 或 #337。

## 后续动作与验证顺序

1. 开发者确认本报告后，将五项决定同步到 Stage 5 规格、拆分与 Agent 使用说明 / 领域导航；复用 ADR 0034 与现有 External Knowledge Library 术语，不新建 ADR。
2. 实现独立只读资料 / 受控 Git 核心，完成真实路径、参数、输出与取消约束；以临时本地仓库和假进程验证，不连接真实远端。
3. 接入 GUI 两种模式的双端白名单、工具声明 / 分发、每轮状态、图片日志及文件夹入口；保留 CLI 拒绝和历史续聊行为。
4. 普通测试覆盖目录不 fetch、每轮每仓库一次、失败不重试、显式 fetch、跨库检索、完整 upstream 区间 / 非快进变化、无 upstream / detached HEAD / 无 Git、格式与分页、路径 / 引用注入、禁用外部 diff / textconv、URL 脱敏、超时 / 取消 / 互斥清理和不改工作区。
5. 涉及真实 pi 或 Agent 工具循环的新增集成测试标记 agent；确需验证接入时，仅选择相关文件并显式 `--run-agent-tests`。使用本机服务替身，不附带调用真实模型。最后记录 Windows / 真模型的实际验收与未验证项，开发者确认后再关闭 #337。

## 本次实际检查

- 只读检查上述源码、相关现有测试、项目约束、#337 正文 / 评论与 #336 状态；没有执行 Git 同步或调用模型。
- 执行：`QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest -q tests/test_workbench.py tests/test_agent_prompts.py tests/test_repair_tools.py tests/test_agent_log.py`。
- 结果：**51 passed in 1.70s**。这是既有边界的回归基线，不是未实现知识库功能的验收。
- 本轮仅新增 / 更新 #337 决策与评审文档；未改产品代码、依赖、打包或远端 issue。工作区另有并行 OCR 文档 / 源码 / 依赖改动，未修改；51 项结果仅对应测试执行时点，不宣称验证了随后出现的并行改动。
