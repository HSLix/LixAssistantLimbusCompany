# #336 — 聊天交互重构影响检查

后续状态：已按本轮授权实施并进入最终检查，见[实施记录](stage-5-336-chat-ui-implementation.md)。下文检查阶段的边界和风险保持。

依据[已确认决定](stage-5-336-chat-ui-decisions.md)及开发者本轮完整交互要求。此记录来自源码 / 调用方 / 测试检查；检查阶段未修改产品代码或执行回归。用户已授权对齐和检查后实施。

## 变更及已确认影响

- **纵向控制台 → 聊天工作台**：`developer_gui.py:RepairPage.__init__ / render` 目前将模式下拉、诊断面板、工作区按钮、附件及 Validate / Publish 逐行加入布局。用现有 QFluentWidgets SegmentedWidget、RoundMenu / Action、工具图标按钮和原生 Qt 布局重排；保留 RepairChat 的独立滚动和工具摘要展开，不引入前端框架。
- **ID 列表 → 对话标题**：`RepairPage.refresh_sessions` 目前读 session.json 并显示模式加短 UUID。新增本地首条实际用户消息提取，跳过宿主协议及人工通知；读取需继续检查路径和已有会话锁，忙或损坏时使用明确回退，不能为标题访问阻塞正在执行的会话。CLI 历史同样兼容，不需要迁移 Session 或请求模型。
- **下拉模式 → 分段选择与只读标识**：`RepairPage.send / activate_session / new` 已按准备状态及持久 Session 区分。更换控件时直接使用其 route key 选择既有 Construct / Repair，不改 DeveloperSession、Prompt、白名单或首次提交固定来源的语义。开始后隐藏选择控件，新聊天的 Source 放在上下文设置中，历史不重新选择。
- **普通多行输入 → IME 安全发送输入**：现有 QPlainTextEdit 没有快捷发送或自动增高。用小型子类处理输入法 preedit / commit 及 Return、Shift / Ctrl+Return；禁止组合确认或连续按键意外发送。自动高度受上限约束，超出由输入框内部滚动，不推走聊天和发送控件。
- **两个文本按钮 → 同位置的状态按钮**：`Operation.cancel` 是协作式取消，`MainWindow.launch` 只在 QThread.finished 后清除 jobs。按钮从真实 jobs / 当前 Agent 活动计算 Running / Cancelling；取消请求发出后禁用重复取消，只有实际清理完成才恢复发送。其他 Validate / Publish / 历史加载作业不能被误当作可取消的 Agent 轮次。
- **常驻诊断 / 工具 → 分组菜单**：复用 `open_workspace / open_pages / show_diff / validate / publish` 及 DiagnosticPanel 的日志、错误选择、详情与复制操作。隐藏常驻面板不等于删除诊断对象；菜单需保留历史错误可选及动态启用状态，发布仍走原完整校验 / 不可变保存，不增加或撤销权限。
- **底部状态栏删除**：`gui.py:MainWindow.__init__ / render_state / closeEvent` 维护 Current activity 和退出收尾提示。只移除 Developer 的重复显示，必要进展由工作台状态与按钮承担；UserWindow 和全局执行状态 / TrialDialog 不改。

## 直接受影响的测试与文档

`tests/test_workbench.py`、`test_developer_gui.py`、`test_repair_chat.py`、`test_image_attachments.py`、`test_gui_language.py` 直接依赖旧模式下拉、按钮、工具行层次及文案，需要换成新控件的行为断言。保留已有 Session 隔离、CLI-GUI 续聊、实际 pi 事件、权限和原图留存证据；本次没有修改 Agent 接入，不以默认全量隐式开启真实 pi。

新增检查覆盖两模式首发 / 固定和恢复、标题过滤与旧历史、输入法组合 / 提交、三种快捷键、真实取消收尾和防重复、菜单原操作路由 / 权限、侧栏折叠、窄窗口和输入增高。更新中英翻译和 #336 实施记录，原人工运行入口删除的决定保持。

## 潜在风险与检查方式

- Qt 输入法原生事件顺序因平台 / IME 而异：组合输入、提交后同一事件周期以及按键事件应自动检查，真实 Windows 中文输入法仍需实机验证，不能用 offscreen 代替。
- 固定底部输入和文本宽度可能抬高最小尺寸：用至少宽 / 窄两种窗口截图及控件几何检查，收起历史后聊天应扩展，文本只在聊天和输入内部滚动。
- 菜单打开后活动可能变化：每次打开刷新启用状态，底层原宿主活动 / Candidate 锁仍是最终约束；避免菜单禁用仅有取消出口。

未发现需要调整 Session / Runtime 架构的阻塞项。实施保持局部控件与既有调用链，首句标题无需新 ADR 或领域对象。
