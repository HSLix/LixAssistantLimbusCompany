# #339 / #340 — 页面草稿、模态审查与人工安装

2026-11-02 验收状态：开发者明确确认 #339 通过，已按 completed 关闭；#340 保持 OPEN，等待开发者 Windows 实验验证后另行确认。此前“两票待验收 / 一起关闭”状态由本条替代；不表示 Windows 成品或真实游戏已验收。见[当前记录](page-review-tabs-implementation.md)。

2026-11-02 试用修订：已改为默认 Proposed 的三 Tab 审批；拟安装页失败直接返回 Agent，不再留窗等待人关闭。当前行为及新验证见[修订记录](page-review-tabs-implementation.md)，旧版验证数据保留在本文。

2026-11-02。开发者已确认[决定](stage-5-339-340-decisions.md)和[影响审查](stage-5-339-340-design-impact-review.md)，授权合并实现。两票保留 OPEN，等待开发者验收。

## 使用与边界

在 Developer GUI 的 Construct Session 中让 Agent 创建或修改业务设置页。草稿保存在 `data_root/developer-sessions/<Session ID>/page-drafts/<filename>.py`，相邻 JSON 记录固定目标及新增 / 替换身份；More → Workspace and pages → Open Session page drafts 可打开目录。每份草稿为一个完整 Python 文件，复制正式页须保留原文件名；正式文件仍在 `data_root/pages/`。Session / Candidate / Manifest 和正式配置不混用，重开 Session 可继续修改，不自动清理草稿。

Construct 专属工具：

| 工具 | 行为 |
| --- | --- |
| page_list | 列出 installed 或 drafts 的文件名及 SHA-256，offset / limit 分页，不执行代码 |
| page_read | 只读 installed / drafts 源码和目标元数据；scope=settings 读取已保存 pages / tasks 配置 JSON；按字符分页，续页应核对 SHA-256 |
| page_create | filename + 完整 source 新建页；或 copy_from=filename 复制当前正式页，固定替换目标；不覆盖草稿 |
| page_update | 替换当前 Session 已有草稿的完整源码，检查语法，固定原目标 |
| page_preview | filename + summary；先检查拟安装页，失败直接返回 preview_failed / isError；成功才发起三 Tab 人工审查。summary 说明字段、旧配置、Plan 影响及已授权的不兼容变化 |

模型声明和宿主分发同时限 GUI Construct；Repair / CLI 不开放这些工具，Runtime 不继承。没有可独立调用的 Agent 安装工具；原生 read / edit 继续限 Candidate。正式页只读入口不导入源码；预览及安装注册检查会执行可信页面模块，不是安全沙箱。

Agent 读取页面、正式配置与对应 Plan，负责说明变化与影响；不建设固定配置兼容检查，不自动调用 submit()，不增加检查配置按钮。保留必要页面契约：PAGE_ID / PAGE_NAME、可选 TASK_ID、create_page(context) 返回带 submit 方法的 QWidget；可选双语名及导航图标保持。破坏兼容先取得明确人工授权，普通反馈仍不等于安装批准。

## 对比、安装与重载

- Qt 主线程先检查拟安装页加载 / 契约 / 注册，失败直接返回同轮 Agent，不显示审批、不等待人工关闭。成功后复用该实例打开应用级模态 Current / Proposed / Review 三 Tab，默认 Proposed；切换不重新加载。两页保留独立模块、实例及旧配置内存副本；context.load / context.save 只访问该页内存。宿主不调用 submit()，不产生试填配置文件。无旧页时 Current 标明新增，旧侧加载失败显示错误，仍可安装有效修复草稿。
- 窗口顶部保留目标文件名，Review 集中显示 Agent 影响总结、Session、PAGE_ID / TASK_ID 与版本哈希；无需先浏览其他 Tab 才能安装。两页可分别交互。其他 LALC 窗口被模态锁住，提示在现有预览窗口完成 / 关闭审查，不另叠警告框；游戏和其他应用不锁定。
- “安装此版本”只批准并提交本窗口固定代码快照；即使磁盘草稿后来变化，也不会被读入这次批准。“关闭不安装”及关闭 / Esc 返回 not_installed，Agent 可继续；“取消本轮”结束当前轮次。取消、退出和中断作废未完成请求，迟到回调不能授权下一轮。等待无自动超时，仍占当前 Session / Agent 活动。
- 安装检查正式路径、文件新增 / 替换和 PAGE_ID / TASK_ID 注册冲突；不做正式代码版本冲突检测或自动合并。新增使用原子不覆盖提交，替换用同目录临时文件原子 replace，失败保留原页和草稿。目标路径 / 文件及草稿元数据拒绝符号链接。其他 Session 已更新正式页时，由人对照当前正式侧决定覆盖。
- 安装结果包含文件名、SHA-256、页面 / Task ID 与 reload_required。安装不改变 Default、不导入试填值、不清空正式配置、不自动重启。当前 Agent 轮次结束后，由开发者从 User GUI 使用既有整应用重载；按稳定 ID 进入既有 Dashboard / Plan 配置链路。
- 轮次日志保留预览源码快照（按既有规则脱敏）、哈希、总结、工具结果与 Session / 轮次关联。重开只恢复草稿和已保留证据，不自动重放预览或安装；中断安装结果可能为 unknown，应检查当前正式页。

## 初版验证（试用修订前）

已执行：

- `QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest -q`：772 passed、87 skipped；默认不启用 Agent 测试，跳过不计通过。
- `QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest --run-agent-tests -q tests/test_developer_session_agent.py tests/test_agent_repair_agent.py`：79 passed、4 skipped。真实 pi 与本机 HTTP 替身覆盖新页面工具声明 / 模式拒绝、草稿恢复、预览结果回到同轮及真实 GUI 信号 → 人工点击安装 → Agent 继续；4 项真实模型 / Windows DPAPI / Windows 游戏检查跳过，不计通过。
- 最终窗口布局 / 模态提醒调整后，再显式运行同文件中 `-k 'page_tool or actual_gui_page'`：3 passed、33 deselected，不调用真实模型。
- 新增 `tests/test_page_drafts.py` 覆盖 Session 持久化 / 隔离、只读不执行、配置读取拒绝链接、Windows 文件名边界及中文名、CRLF 字节哈希、两侧内存配置、无需 submit、旧侧 / 新侧错误、快照安装、新增不覆盖、冲突、写入失败、取消及旧请求失效。补充安装错误脱敏及修改后重新预览当前字节。
- 安装后的闭环：实际点击安装 → 既有 request_reload 保存旧正式配置及生命周期退出链 → 新宿主重新扫描页面 → 实际运行无游戏操作的示例 Python Plan 两次，返回值均使用正式配置；试填值未带入。不将新宿主重建称为 Windows 成品重启验收。
- 新窗口中英文文案加入现有 TS / QM，扩展语言目录检查；离屏渲染人工检查双栏、版本信息及三按钮布局。沿用测试 conftest 的 macOS 标题栏替身，无原生 NSWindow 证据。
- `git diff --check` 无空白错误。

最初将默认回归与 Agent 接入测试并行运行，触发共用 ProcessLock("game") 的活动锁冲突并使旧运行等待，已终止旧测试进程，单独重跑。该失败运行不作为验收证据；测试分开串行执行。

最终默认回归 772 passed、87 skipped；本地自动检查不等于开发者验收。

## 开发者验收建议

1. 在 Construct Session 要求 Agent 新增一个业务页，检查草稿文件夹及模式权限；关闭 / 重开 Session 后继续修改。
2. 打开审批窗口，确认默认 Proposed，切换 Current / Proposed 分别试填，再到 Review 查看 Agent 总结和版本详情；验证切换保留试填、其他 User / Developer 窗口被锁住、游戏可操作，关闭不安装后正式文件和配置不变。
3. 修改草稿后再次审查，检查 Agent 影响总结及当前正式侧，人工安装；等本轮结束后从 User GUI 主动重载，检查页面、旧配置、Dashboard / Plan 参数。
4. 验证取消本轮解除等待，旧正式页失败仍可安装修复页；拟安装页缺 PAGE_ID 等加载 / 契约 / ID 注册错误不出现审批，直接反馈 Agent 修正后重新请求。Windows 成品另查缩放、模态、文件占用和重载。

收到开发者明确验收确认后，才关闭 #339 / #340；当前未关闭。

## 已接受的限制

同进程 Python 页面可以绕过配置接口写盘 / 联网，卡死或退出可能影响主应用；两份内存配置只约束宿主提供的配置接口。新开预览使用当前草稿字节及独立模块身份，不保证卸载所有导入依赖。没有通用配置迁移、资源包管理或自动版本合并。

新增源码 / 目标的原子不覆盖提交使用同目录硬链接；文件系统不支持时明确失败，不降级为可能覆盖旧文件的写法。Windows 成品文件系统行为未实测。

重载会先提交当前已加载的旧页面；旧页 submit() 失败会按原规则阻止重载，不自动丢弃旧输入。必要时正常退出后重新启动，加载已安装修复页。真实模型、Windows 成品的模态 / 缩放布局 / 文件占用 / 重载和真实游戏业务须另行验收；本机替身或 offscreen 测试不能替代这些证据。
