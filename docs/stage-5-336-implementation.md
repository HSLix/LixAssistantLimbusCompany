# #336 — Agent 工作台本地实施

2026-10-31。依据[已确认决定](stage-5-336-decisions.md)与[专项影响审查](stage-5-336-design-impact-review.md)实施。本地实现和下述检查已完成；等待开发者试用确认，#336 保持开放。本文不把本机替身、offscreen 或源码检查当作真实模型 / Windows / 游戏验收。

## 使用

运行 `lalc --developer`，打开 **Agent 工作台**：

1. 左侧“新建会话”进入准备状态，选择 Construct / Repair 及来源。Construct 可选空白或已发布 Manifest；Repair 必须选已发布版本。首条消息发送前可以调整模式和来源，此时不创建持久 Session 或触碰草稿。
2. 发送首条消息时才初始化独立 Session、Candidate 和固定 Diff 基线，之后模式 / 来源固定。失败的初始化保留输入；开始对话后模型错误或取消不解锁模式。换基线使用新建会话，旧会话始终保留。
3. 侧栏按创建时间倒序展示历史会话及真实模式，短 ID 的提示包含完整 UUID；可打开 GUI 或 CLI 创建的 Repair 会话续聊。Construct 仅 GUI 运行；CLI 恢复时明确拒绝。
4. 可附加多张图片或多个已发布 Manifest，参考重点写在消息中。Manifest 附件只是上下文提示，发送时不注入全部源码；Agent 无须先附加即可使用专用工具查看任意已发布版本。
5. 工作区打开、累计 Diff、Validate、Publish、诊断及请求计数均对应当前 Session。发布后显示新 Manifest ID，不自动改变 Default。Developer GUI 不再提供人工版本选择 / 运行或“应用到 User GUI”；普通启动继续走 User GUI。

Agent 仍保留完整的修改 → Validate → Publish → 明确版本 `trial_run` → Run 结果 / 日志闭环；试运行日志窗口及暂停、恢复、停止和整轮取消收尾保持。活动期间禁止新建 / 切换会话，取消实际收尾后才恢复。Capture、共享 Agent 设置与非 Windows 内存凭据保持原职责，不保存凭据到 Session 元数据。

## 存储、权限与只读参考

沿用 #335 的 `developer-sessions/<UUID>/`，保存 `session.json`、独立 `candidate/`、固定基线及自包含 `log/`。不迁移手工 Candidate、旧日志或旧 Runner 设置文件；废弃 Runner 设置停止读写。无 Session 删除 / 重建 / 清理入口；全局 Asset 的既有变更不会因切会话回滚。重启仅恢复已保存内容和未知结果，不重放请求、工具、Publish 或试运行。

- `developer_session.py` 扩展模式及当前入口校验；`manifest.py` 的显式 `empty=True` 不改变旧手工 init 的 None / Default 语义。
- `agent_policy.py` 定义模式白名单和入口能力交集；两种模式分别提供初始 Prompt，当前工具集合可以相同。声明和 TypeScript execute、Python validate / 宿主工具分发均检查权限，不从历史恢复授权。
- `manifest_reference.py` 纯数据读取，不调用 load / validate 或导入模块。`list_manifests(offset, limit)`、`read_manifest(manifest_id, offset, limit)` 返回版本及成员分页；`read_manifest_source(manifest_id, section, logical_name, offset, limit)` 按行读取已登记源码，返回 Component ID、起始行、总数和续读位置。offset 从 0 开始，limit 为 1–200。
- 版本、登记成员、源码哈希、真实路径及符号链接边界逐次检查；失败不切换其他版本。不增加通用 read 根目录，不提供参考文件写出、编辑、删除或执行入口；不修改 Candidate、固定基线、Default 或 Working Manifest。

#337 知识库 / Git、#338 人工反馈、#339–#340 页面工具及 Stage 6 Runtime 均未提前接入；对应工具不向模型暴露。

## 验证

普通全量及相关 Agent 集成测试串行执行，避免共享 game 锁竞争。真实 pi 使用本机 HTTP 替身，不调用真实模型；本机监听受限时在允许监听的环境重跑，初次监听失败不计通过。

- 普通全量：`QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest -q -x -ra`，**602 passed，63 skipped**。默认跳过 Agent 测试，Windows DPAPI、原生焦点及当前环境不允许的 IPC / 重载检查亦不计通过。
- Agent 集成：`QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest --run-agent-tests -q -x -ra tests/test_developer_session_agent.py tests/test_agent_repair_agent.py tests/test_pi_probe.py`，**55 passed，4 skipped**。跳过两项真实模型、一项 Windows DPAPI、一项 Windows 游戏现场。
- 新增检查覆盖空白不依赖 Default、首次发送前切换和失败保护、GUI / CLI 持久续聊及真实 GUI 发送、共享内存凭据、手工 Validate / Publish 的历史归属、历史读取互斥和失败诊断去重、并发创建的临时目录忽略，以及模式白名单的实际工具拒绝。
- 参考检查覆盖多 Manifest 提示与原图共存 / 恢复、未附加版本可查看、分页续读、同名不同版本、未登记成员、身份 / 路径 / 符号链接 / 哈希异常和不执行源码；Agent 从空白新增 Task、编辑 Plan、Validate / Publish / 实际运行新 Plan 的工具闭环亦已通过 HTTP 替身检查。
- 修复初始设置失败时丢失已提交消息：现在即使尚未请求模型，仍保留用户消息、有效图片与 Manifest 提示；不因失败解锁模式或自动重发。
- 已生成并查看 offscreen 工作台截图，检查历史侧栏、紧凑新建按钮、固定模式 / 来源、聊天输入及附件布局；此证据不代替 Windows 原生呈现。

未进行真实模型、pi-probe、真实游戏、Windows 成品 / DPAPI 或原生焦点验收；未提交 Git。需开发者试用确认后再关闭 issue。

文档检查：本轮涉及文档的 175 个本地链接目标存在，git diff --check 通过。#336 原生依赖仍指向 #335，issue 等待开发者验收，未关闭。
