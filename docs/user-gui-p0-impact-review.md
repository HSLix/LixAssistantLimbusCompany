# User GUI P0 影响审查

2026-10-28：用户已确认审查结论并授权实施；设计以 [P0 决策](user-gui-p0-layout.md)为准。

- 配置：`agent_settings.py` 的保存与读取共用严格校验，且读取检查所有 provider。必须允许保存/读取无效文本，使用选定 provider 前严格校验；结构、凭据、原子写入、旧配置迁移和轮次认证快照不放宽。临时验证确认另一 provider 无效地址会阻断当前读取与关闭 User Agent。
- 启动：`UserWindow.start_plan` 无条件提交 Agent 表单，`render_state` 仅按活动禁用启动。User 开启时增加当前 provider 完整性门槛，关闭时不被隐藏配置阻断；不能把 User 限制加到共用执行服务而阻断 Developer trial/CLI。外置页提交校验保持。
- 界面：复用 SettingsPage 与 ErrorDialog；User 移除常驻密钥框和诊断面板，同步错误处理对 key/diagnostics 的依赖及脱敏。共享错误弹窗默认折叠详情，Developer 诊断面板保留。
- 布局：重排现有 Manifest、任务列表和 Start Plan，加入三张离线占位卡、两种空状态及 Agent 定位；Manifest 加载失败弹窗，不删除告警与持久通知。
- 文档/Issue：#333 真实信息功能移至 Stage 6 之后，双语、语言重载及 General Settings 不后移；#334 保持依赖调整后的 #333，验收用占位卡替代真实公告/声明/版本联网功能，仍要求 Windows 成品、翻译、双窗口和 DPAPI 证据。已核对 GitHub 正文及原生依赖：#333 ← #332，#334 ← #333。
- 测试：修改无效文本阻止交接的旧断言，保留实际写入失败阻止交接/重载；新增无效配置可修正、启动状态组合、密钥弹窗、折叠详情、布局和导航回归。

审查阶段定向基线：115 passed，4 skipped；未改实现，未运行真实模型、真实游戏或 Windows 验收。实施顺序：同步文档/Issue → 配置读写/启动门槛 → 界面 → 定向及普通回归。
