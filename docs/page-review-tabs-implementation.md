# 页面审批三 Tab 与加载失败自动退回 — 修订实施

2026-11-02。开发者逐项确认[修订决定](stage-5-339-340-decisions.md#2026-11-02-试用反馈后的修订讨论)后，按其要求完成[影响审查](page-review-tabs-design-impact-review.md)并实施。开发者随后明确确认“339可以通过，关闭339，我会去windows实验验证，之后再关340”：#339 已按 completed 关闭，[验收说明](https://github.com/HSLix/LixAssistantLimbusCompany/issues/339#issuecomment-6569572512)已记录；#340 保持 OPEN，等待 Windows 实验验证及开发者另行确认，不将 Windows 未验证项计为通过。

## 当前行为

- GUI Construct 的 page_preview 在 Qt 主线程先加载拟安装页，并检查现有页面契约和注册边界；缺 PAGE_ID、无效保留 ID、create_page 异常、返回值 / submit 方法不符合接口或注册冲突，均直接以 `status=preview_failed` 和 `isError=true` 返回同轮 Agent，不显示审批窗口、不等人关闭。正式配置无法读取时同样返回错误。不调用 submit() 或检验字段兼容，不把 Task ID 改成必填。
- Agent 按具体错误修改自己的草稿，再次调用 page_preview；宿主不代改代码、不创建新用户轮次、不重置请求额度或自动无限重试。已保存草稿保留。错误按既有日志规则脱敏，绑定原工具 / 轮次。
- 成功后显示 Current / Proposed / Review 三 Tab，默认 Proposed。Current 是当前正式页，无旧页显示新增说明；旧页加载失败在 Current 显示错误，仍可审批正常修复版。Proposed 是已通过加载的同一个拟安装实例，不重复执行模块或 create_page。切换 Tab 只切换显示，不重建实例、不丢失各自内存试填。
- Review 集中显示 Agent 的改动 / 影响说明、文件名、Session、拟安装 / 当前页面和 Task ID、完整 SHA-256；顶部保持简洁目标文件名。不强制先浏览任何 Tab 才能安装。
- 窗口底部始终提供安装此版本、关闭不安装、取消本轮，保留应用级模态及窗口内取消出口。安装继续使用固定代码快照；不导入试填配置、不自动重载、不改变 Default。安装时再次检查路径 / 注册，写入失败仍保留原正式文件并在窗口显示错误，不把它误报成预览未发生。
- 失败 / 准备期间取消时，不显示窗口，已创建但未展示的控件随隐藏窗口延迟清理；迟到请求 / 旧确认继续失效。同进程可信 Python 卡死或崩溃仍无法保证自动返回，主线程加载期间不保证即时响应取消。

## 变更位置

`page_preview.py` 改为构造时隐藏准备、准备成功才允许显示，使用既有 Fluent SegmentedWidget 与 Qt stacked 容器呈现三 Tab；保留单次结算与安装核心。`developer_gui.py` 在原身份 / 权限校验后仅展示 ready 的窗口；`repair_tools.py` 将 preview_failed 转成工具错误。`pi_probe.ts` / `agent_prompts.py` 同步自动修正重试指导；中文 TS / QM 和目录检查保持。

无新依赖、持久数据迁移、模式权限扩张或 Agent 安装工具。原 [#339 / #340 实施记录](stage-5-339-340-implementation.md)中安装、重载及其限制继续适用，旧左右双栏 / 失败留窗行为由本记录替代。

## 本地验证

- 聚焦普通回归：`QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest -q tests/test_page_drafts.py tests/test_gui_language.py tests/test_human_feedback.py tests/test_workbench.py`：87 passed。
- 默认全量：`QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest -q`：779 passed、88 skipped。未启用 Agent 测试，跳过不计通过。
- 显式 Agent 接入：`QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest --run-agent-tests -q tests/test_developer_session_agent.py tests/test_agent_repair_agent.py`：80 passed、4 skipped。与默认回归串行执行，使用真实 pi 与本机 HTTP 替身；覆盖真实 GUI 发送链路中缺 PAGE_ID 自动失败返回 → 同轮 page_update 修正 → 再次审批 / 人工安装 → Agent 继续。4 项真实模型 / Windows DPAPI / Windows 游戏检查跳过，不计通过。
- 新增 / 调整测试覆盖缺 PAGE_ID、保留 ID、顶层 / create_page 异常、无效返回 / 缺 submit、PAGE_ID / TASK_ID 冲突自动退回；默认 Tab、Review 身份 / 哈希、切换保留配置、成功页模块与 create_page 只执行一次、准备时取消不展示、旧页损坏仍可修复。既有快照安装 / 失败保留 / 重载及 Plan 输入回归继续通过。
- 三 Tab 离屏渲染已检查；macOS 沿用测试环境的原生标题栏替身，不能当作真实原生窗口或 Windows 成品验收。
- `git diff --check` 通过；无新增依赖或数据迁移。

开发者可先让 Agent 提交缺 PAGE_ID 的测试页，观察无审批窗口而自动收到错误，再修正后进入默认 Proposed；切换 Current / Review 检查试填状态与版本。Windows 成品模态 / 缩放、真实模型和真实游戏业务尚未验收。

## 页面契约说明补充

2026-11-02，开发者确认按反馈影响审查实施说明改进。已有接口要求未改变：将 page_create 说明分为模块属性、create_page 工厂、返回 QWidget 实例三个层级，强调仅显示标签也需满足三层契约；补充带实例 submit() 返回空字典的最小完整纯设置页。page_update 提醒沿用同一契约，Construct Prompt 简要引用，不要求属性是字面量或添加返回注解。示例文档同步已实现状态及正式目录仍不可通用编辑的边界。

不改变加载器、创建 / 更新时仅检查语法、预览不调用 submit、人工安装或权限；不新增模板系统和配置迁移。反馈中的遗漏原因是 Agent 的事后解释，本次只改善说明清晰度，不据此证明模型犯错的因果。

文档示例已由共享加载器创建页面并实际提交空配置。页面 / Prompt 聚焦测试 34 passed、1 skipped；显式运行 `tests/test_agent_repair_agent.py -k test_sop_round_snapshot_and_actual_tool_guidance --run-agent-tests`，2 passed、45 deselected，确认实际传给模型的多行示例与已测试文档一致。测试串行执行，仅连接本机 HTTP 替身；未重复全量回归。上述检查不能证明真实模型的遗漏率已经降低。
