# Session 身份与分享列表展示：决定、影响审查

2026-11-12，经逐项讨论确认；范围为 GUI 展示，不修改分享 ZIP 格式。

## 已接受决定

- Session 页面保留标题，在标题下显示完整 UUID，可选中复制；新建未发送会话不显示 UUID。
- 2026-11-14 展示补充：完整 UUID 前增加“聊天 ID：”（英文 `Chat ID:`），直接解释编号用途，保留文字选中复制。只更改标签和翻译，不改持久身份、历史选择或分享格式；新建未发送时仍隐藏。
- Workflow 导出项保留 Manifest UUID，新增已有 AdditionalMessage（缺省留空）及 Manifest 文件修改时间。
- Agent History 导出项保留来源路径，Session 新增标题及会话目录修改时间。本地时间显示到秒。
- Session 按历史会话侧栏的目录修改时间倒序排列；独立 developer-operations、agent-interactions 日志保留在 Session 后方，无标题时留空，显示目录修改时间。
- 时间仅采用已有文件系统信息；重命名继续保留历史排序位置，不新增持久时间字段。

## 影响审查（实现前源码检查）

### 已确认差距

- `developer_gui.RepairPage.refresh_sessions` 仅把 UUID 放入 tooltip，标题本身截短；需增加独立身份标签，并覆盖新建／切换／删除当前会话的刷新路径。
- `sharing.catalog` 按路径字典序枚举日志，与侧栏按目录 mtime 倒序不同；需对 Session 枚举复用相同排序键，其他日志仍保留在后。
- `sharing_gui.ExportDialog` 直接把对象 ID 作为列表文字。选择与导出使用 UserRole 中的 ID，可只替换展示文字，不改变选择契约。
- `ManifestManager.list_manifests` 已提供 AdditionalMessage；其 saved_at 是发布时间，不能冒充本次要求的文件修改时间。
- `RepairPage.saved_title` 已处理人工标题、旧会话首条用户消息及链接拒绝和 Candidate 锁。提取共用读取逻辑供导出使用，保留 GUI 缓存与锁边界，避免第二套标题规则。

### 潜在风险与验证

- 目录 mtime 不等于所有子文件的最新变更；这是本次明确接受的现有排序／时间语义，不递归扫描或迁移。
- 损坏／忙碌 Session 不应阻断其他对象的展示；标题不可读时留空，导出仍按已有完整校验处理。
- `catalog` 也由测试和导出调用：保留返回结构与对象身份，验证 ZIP 往返和选择值未变。
- 覆盖附加信息缺省、人工标题、旧日志标题、倒序、独立日志排后、时间显示及 UUID 清理；不启动真实 Agent。

## 文档与实施顺序

先记录决定与本审查，再提取标题读取、更新 GUI／排序，补充 Sharing 与 Workbench 说明，运行相关默认测试。领域术语和存储边界未改变，无需新增词条或 ADR。


## 实施与验证

已完成上述展示、排序和共用标题读取；未新增依赖、持久字段或 ZIP 字段。

- 执行 `QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest -q tests/test_sharing_gui.py tests/test_session_management.py tests/test_sharing.py tests/test_developer_session.py`：82 passed；未启用 Agent 集成测试。第三方菜单弃用警告 5 条，退出时报告 Qt 对象回收警告，进程正常退出。
- `git diff --check` 通过。
- 对四个修改的产品模块执行 Pyright（指定 `.venv/bin/python`）仍报告 130 项错误，均定位于本次未修改的代码行；本次新增行上的两处列表／树联合类型错误已通过显式 QListWidget 判断修正。静态检查整体未通过，不宣称全仓类型检查通过。
- 未进行 Windows 原生界面、真实模型或游戏验收；目录 mtime 的边界保持上述已接受语义。
