---
status: accepted
supersedes: 0004 (JSON Automation Plan identity and Plan call hierarchy only), 0029 (fixed four-page Developer GUI and JSON Plan read-only rules only), 0030 (JSON plan_path trial entry only)
---

# Use a unique Python Plan per Manifest and coexisting User/Developer GUIs

2026-10-27：Stage 4 grill 结束，开发者确认[接受规格](../stage-4-extensible-user-gui.md)及[影响审查](../stage-4-design-impact-review.md)。为了让业务调度由 Python 表达、让新增业务设置页无需修改主 GUI，每个 Manifest 改为拥有唯一、内容哈希固定的正式 Python Plan，以稳定逻辑名通过统一调用边界执行，并由 Plan 调用 Task。直接替换 JSON Plan，不兼容、不自动转换或改写旧不可变发布物。Plan→Task 返回结构化成功/失败结果，普通 Task 失败可继续；取消、环境无法继续及 Plan 自身错误中断执行，完整实际结果由执行器保留，不能把遍历完成等同于全部成功。

User/Developer 双窗口同进程共享服务和活动门控，同时允许打开和独立关闭；选择并存而不强制关闭切换，以便开发活动期间用户仍可设置配置。User 修改 Default，Developer 保持独立 Selected；删除独立 Runner 页，保留试运行和底层执行能力。外置 Python 页面按稳定页面/任务 ID 与 Plan 对接，用户设置跨 Manifest 共用；重启整个应用实现重载，不建设热替换或自动表单。共享 Agent 配置内容、独立保存两侧选用和 User 启用状态。

允许 Developer Policy 编辑已有 Candidate Python Plan并发布后独立试运行，不开放外置 GUI 页面编辑。完整业务及内置 Agent 页面构建留到 Stage 5；原 Stage 3.5 Runtime Maintenance 已确定延到 Stage 6，Plan 失败后的 Agent 评估/修复/试跑也留在 Stage 6。Stage 4 用示例证明框架可用，并以 Windows 打包版页面逻辑作为验收门槛，不把源码完成或替身测试当作该验收完成。

既有不可变源码、Asset、Trusted Action、Step 恢复、Developer 认证/权限与证据边界保持；本 ADR 不开放任意层自动恢复或任意文件执行。旧文档的冲突范围按本决定替代，历史实施证据保留。#331 的 Python Plan 与双窗口闭环已在本地实现，证据及剩余边界见[实施记录](../stage-4-331-implementation.md)；#332 外置页面、共享 provider 配置、单一编辑入口及整应用重载也已完成本地实现，追加确认和证据见[#332 实施记录](../stage-4-332-implementation.md)；#333 双语与语言重载已完成本地实现，已获开发者人工验收确认并关闭 #333，见[#333 实施记录](../stage-4-333-implementation.md)；#334 Windows 打包验收仍未完成。

2026-10-27 经可行性实验后，开发者授权将两个窗口完整迁移为 FluentWindow，采用官方基础控件和导航；不改变本文的单进程/共享服务、独立窗口、页面/Manifest 分离及活动契约。当前实现、退出顺序适配和 Windows 未验收边界见[迁移记录](../fluent-gui-migration.md)。

2026-10-30 #334 分发细节已确认：Windows x64 onedir 双 ZIP（含／不含 pi），程序不附业务数据，后续数据导入导出另行实现；成品草稿随用户数据，源码草稿仍随项目。默认随包 pi 优先、请求前限定故障可回退一次，连接／图片预检 prompt 也关闭本轮回退。构建脚本从忽略的 pi_resources 读取固定原始 ZIP，通用 Windows 功能仅验一个包、pi 差异分别覆盖；真实模型验证不属于本票，Actions 在 Stage 6 完成后考虑。现有 main 增加共享实现的 console 打包入口，仅恢复 CLI 交互，不另建服务或 Developer 业务执行路径。见[决策](../stage-4-334-decisions.md)和[构建验收说明](../windows-packaging.md)；Windows 现场通过门槛及开发者确认后关闭规则保持。
