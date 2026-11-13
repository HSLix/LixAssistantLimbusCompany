# 聊天附件托盘：设计与影响审查

日期：2026-11-13。范围：Developer GUI 聊天附件；不涉及模型请求、执行授权或正式资源的删除。

## 已确认的交互

- 用户选择第三张参考图：折叠附件托盘。待发送附件放在输入区顶部；已发送附件放在对应用户消息正文上方。
- 图片使用缩略图，工作流版本显示 Manifest UUID 前八位；待发送附件悬停时显示右上角 ×，可单独移除。
- 附件多时默认折叠，提供展开与收起；展开区域高度有界，其余附件滚动查看，不新增附件总数限制。
- 用户确认：待发送和已发送的图片都支持点击放大预览；× 仅用于移除待发送附件。
- 用户最终确认：折叠时按可用宽度显示一行，其余以“+N”入口展开；展开最多显示两行高度并滚动，保留收起入口。历史附件只读；缺失或损坏图片显示不可用占位；完整文件名和 UUID 通过悬停提示提供。

## 设计变化

原来在输入文字下方显示数量摘要、只能整组清除，改为输入文字上方的逐项卡片；原来用户消息仅显示文字，改为显示当轮附件及文字。折叠只影响展示，不影响提交数量；移除仅改变待发送列表，不删除原始文件，也不撤销历史引用。

## 已确认的实现差距（实施前）

1. `src/lalc/developer_gui.py:RepairPage` 的 composer 在 `message` 后添加 `attachment_notice`；`update_attachment_notice()` 仅写数量和路径提示。`attach_image()`、`attach_manifests()` 和 `clear_image()` 必须接入卡片增删与折叠状态；`update_actions()` 的活动互斥须覆盖删除按钮。
2. `send()` 已冻结图片和 Manifest 引用，但 `workbench_session` 事件只携带文字；`show_event()` 添加纯文字消息后立即清空输入附件。即时显示须携带本轮冻结的附件快照，不能事后从已清空列表获取。
3. `RepairChat.add_message()` 只保存角色、文字、轮次；`render()` 通过 QTextBrowser 富文本绘制。不能直接假定 HTML/CSS 能提供嵌套滚动区和原生悬停按钮。实现须兼顾当前工具记录、生成过程、上滚补载和贴底行为。
4. `replay_history()` 从 `session_message` 取文字，未读取当轮附件记录。`agent_repair.image_attachments()` 已留存原图、原名与 MIME，`round-N/input.json` 已保存 `attachments` 和 `manifest_references`；历史卡片应复用这些记录，并经 `agent_log.read_json()` 展开去重引用。
5. `docs/stage-5-agent-workbench.md` 的 Session 恢复与 Manifest 参考附件约定仍适用；`docs/agent-repair.md` 部分历史实施说明描述数量与整组清除。应补充当前交互规格，保留历史验证记录的时点含义。

## 潜在风险与检查方法

- 大量或大尺寸图片同步解码可能阻塞界面；应按可见卡片生成有界缩略图，并用较多附件检查响应与高度。
- Session 历史路径与导入记录属于读取边界；不得通过附件文件名越出所属日志目录，不跟随外部链接。缺失或损坏图片应保留附件占位并说明不可用，不能阻断整段历史。
- 旧轮补载和每秒工作时长刷新会重绘聊天；折叠选择与阅读位置不能被刷新重置。
- 八位 UUID 是显示缩写；实际引用仍用完整 UUID，提示中应保留完整值，防止前缀相同被合并。

## 后续顺序与验证边界

先确认交互共识，再补充规格、实现可复用附件托盘与即时/历史数据接入、更新翻译，最后执行普通定向测试。重点覆盖逐项删除、折叠展开、多附件与窄窗口、即时发送快照、重开 Session、补载旧轮、缺失/越界图片与既有滚动行为。

以上差距依据实施前源码检查；下节单独记录实施证据。无需为纯显示改动启动 pi 或模型服务；Windows 与真实游戏验收单独报告。

## 实施

- `chat_attachments.py` 提供可复用原生卡片和托盘；图片按可见行读取缩略图，展开后最多保留三行卡片（两行可视区加一行滚动余量），不按附件总量一次性解码。键盘聚焦也可访问删除入口。
- `RepairChat` 沿用富文本正文、工具和生成过程，以透明图像占位定位原生托盘；聊天滚动与缩放同步调整托盘位置。刷新复用现有托盘，轮次结束重新加载时恢复展开状态与托盘滚动位置。
- `RepairPage` 使用冻结快照呈现即时附件，历史按轮读取留存原件与完整 Manifest 引用。只展开日志中的附件元数据，不为卡片展开 Prompt 内全部图片。每次读取历史图片重新检查路径，拒绝目录越界和符号链接。
- 图片预览为只读非模态窗口，按比例适配窗口；仅移除待发送列表，不删除原件。缺失图片保留占位；无需迁移历史日志、变更模型请求或新增依赖。
- 领域术语沿用 `CONTEXT.md` 中 Developer Session、Manifest Reference Attachment 和 Component Manifest；本次是展示交互调整，不新增领域对象或 ADR。

普通定向回归：`QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest -q tests/test_chat_attachments.py tests/test_chat_ui.py tests/test_repair_chat.py tests/test_gui_language.py tests/test_session_management.py tests/test_image_attachments.py`，**113 passed**，1 条既有 Qt 菜单弃用警告。新测试覆盖 100 个附件的有界布局和滚动、窄窗口、同前缀完整 UUID、逐项移除与活动互斥、原图预览、缺失图片、符号链接/越界路径、即时快照、原文件删除后恢复、重新打开 Session、刷新后展开与滚动位置、键盘删除和深色卡片。

离屏截图已检查折叠、展开以及附件卡片的明暗主题；使用原生标题栏与游戏窗口替身，不构成 Windows 或真实游戏验收。未运行全量测试、真实 pi/模型服务或真实游戏。此次仅修改 GUI 展示与历史附件读取，未添加依赖或修改 Agent 请求协议。
