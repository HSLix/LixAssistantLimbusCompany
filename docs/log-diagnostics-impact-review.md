# 日志诊断改进影响审查

2026-11-12，依据 [已确认决策](log-diagnostics-decisions.md)。本节为实施前源码审查，非运行或 Windows 验收。

## 设计变化

- 全量自动 Match 截图 → 仅保留 Match 文字，OCR、click、drag、显式截图继续保存；Run 日志图片改为 AVIF 65 / speed 8 / 默认色度采样。素材与现场 Agent 截图仍保留原始像素。
- ID 列表及无条件 Trace 读取 → Run 元数据、条件分页和关键词检索，保留完整原始 Trace。
- 外部知识库固定可用 → 默认开启、每轮固定的共享开关，两类 Agent 均受控。
- 用户对话时间缺乏上下文 → 本轮新增 prompt 携带本地时间快照，历史前缀不因时钟更新而改写。
- 工具摘要仅名称状态 → 补充操作对象；日志阅读采用较小固定滚动步长、短标量数组单行展示。

## 已确认影响

- `runtime.WorkflowExecutor.trusted_action` 在调用前对 click/drag/OCR/match 共用 `_debug_screenshot`，只需移除 match，异常路径无需另建截图逻辑。完整动作输入、结果和错误仍走 `_invoke`。
- `application._save_screenshot` 固定 `.png`；`focused.FocusedAutomationSession.save` 还服务 Agent 截图、素材及开发捕获，不能整体改为有损。仅 Run 证据选 AVIF，原 PNG 保存行为保留。
- `run_logs.image_path`、`run_log_sharing.export_log/import_log`、`sharing` Session 导出均固定 PNG；必须同时支持新 AVIF 和旧 PNG，继续校验路径、引用、哈希和事务。历史记录不自动重写。
- `RepairTools.read_run_log` 整文件加载；现有 `run_logs.lines/snapshot` 可复用作有界内存扫描，分页必须按过滤后匹配事件推进，图片读取继续校验 Run 真实引用。模型传输沿用 JPEG 预览，不能假设模型直接支持 AVIF。
- `agent_policy.allowed_tools`、`agent_repair.AgentConversation` 两处初始化及每轮快照、`agent_settings`、Developer `SettingsPage` 都需接线；`RepairTools.page_resource` 的 knowledge 复制分支需单独检查授权。
- `pi_probe.ts` 是模型工具参数与描述来源，新增搜索必须同步工具注册、权限、宿主分派和说明。Session 分享还需识别搜索实际引用的 Run。
- `agent_repair` 已将每轮 runtime_context 追加为用户消息，可以在此加入本地时间，不需要动态系统提示。常驻提示只记录稳定的转换规则。
- `repair_chat.RepairChat.tool_html` 当前摘要无操作对象，完整参数已有 host/start 事件可复用。
- 讨论后新增“已工作”计时：`RepairPage.show_event(workbench_session)` 启动现场轮次，`answered/render` 与清理停止；`RepairChat` 仅刷新 GUI，历史回放和模型上下文不引入动态计时。
- `run_log_gui.RunLogPage` 像素滚动未固定步长；`run_logs.log_text` 对返回值使用完全展开 JSON。仅改显示，不改存储或搜索证据。

## 潜在风险与实施顺序

1. 先改证据解析与导入导出，再切换新证据编码；新包包含 AVIF，旧版程序可能不支持，PNG 旧包继续可读。
2. 新搜索流式扫描，不引入持久索引；跨 Run 稀疏搜索仍可能耗时，必须响应取消、提供可续读游标，不能将损坏记录当成完整无匹配。
3. 缺少 run_finished 不证明仍在运行；仅当前宿主活动状态可支持 running，旧记录缺失信息明确 unknown。
4. AVIF 本机 Pillow 编解码及现有 JPEG 预览链路已实际验证；Windows 打包、持续游戏性能与真实模型尚未验收。需确保打包包含 Pillow AVIF 插件与编解码组件。
5. 默认回归串行运行，真实 Agent 测试按需单独显式执行；本次先使用不启动真实 Agent 的 focused checks，跳过不能报告为通过。

## 后续验证

覆盖新旧图片的读取、Run ZIP 与 Session 分享；Match 成功／失败均不自动截图，OCR／click／drag 保留；查询组合过滤、跨 Run 游标、损坏和半行；知识库禁用旁路；本地时间快照不改历史；工具文件名摘要；短数组格式和滚轮步长。

## 接入验证发现与修正

真实 pi + 本地 HTTP 替身发现：关闭知识库后再开启，旧 pi 的启动工具白名单在 new_session 后仍限制可用集合，第二轮被 `configure_session` 的工具一致性检查拒绝。`PiProcess.session` 的复用签名此前忽略 `--tools`。现保留工具参数参与签名，权限集合变化重建进程，集合不变继续复用；对话由宿主历史恢复，不修改既有消息。

## 最终实施与验证

- 已接线本次全部接受范围；新证据为 AVIF，现场 Agent 截图及素材仍为无损 PNG。旧日志不迁移；Session 分享与单 Run ZIP 均读取 PNG／AVIF，模型侧使用 JPEG 预览。
- 最终普通定向回归串行执行，合计 **366 passed、1 skipped**（平台条件），各进程正常退出：核心证据／权限／查询等 144 passed、1 skipped；聊天 20 passed；日志页面／传输 38 passed；Developer GUI／语言／Workbench／pi 资源 101 passed；Sharing／Prompt／打包配置／Runtime 修复 63 passed。
- 单独显式 Agent 回归：`tests/test_agent_repair_agent.py -k 'log_tool_schema_round_time or developer_publish_trial_and_logs or text_only_and_context_retained' --run-agent-tests`，**3 passed、44 deselected**。使用 pi 1.5.0 与本地 HTTP 替身，覆盖实际模型可见工具参数、跨轮知识库开关、时间快照及历史用户消息／系统提示稳定；不代表真实模型行为。首次受本机监听权限限制，允许本地监听后发现并修正前述工具复用问题，最终重跑通过。
- `git diff --check` 通过；中文翻译资源已重新编译。离屏实际截图检查显示“已工作 1分5秒”和 read 文件名摘要；滚轮事件检查验证长项展开后仍按小步长移动。
- 修正一处测试数据不确定性：导入副本与后续 Run 使用相同时间，UUID 排序会随机挤入首批断言。测试为导入副本使用更早时间，不改变产品排序。
- 按最终规则对提供的 Trace 只读复核：仅 Match 自动引用的图片为 561/574（约 97.7%），其余 13 张还关联 OCR、click／drag 或显式保存；仅是样本引用分类，不是修改后实际运行的产量承诺。
- 未运行全量回归、真实模型、Windows 打包成品或真实游戏／数小时持续运行。AVIF 新包可能需要新版应用读取；跨 Run 搜索无持久索引，大范围查询仍可能耗时。普通 Qt 检查有退出期资源回收警告，但上述最终进程均为退出码 0。
