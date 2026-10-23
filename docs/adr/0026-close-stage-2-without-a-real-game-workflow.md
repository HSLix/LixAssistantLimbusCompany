---
status: accepted
---

# Close Stage 2 without requiring a real game Workflow

Asset ownership, language selection, naming and Candidate/publication instructions in this ADR are superseded by [ADR 0027](0027-resolve-assets-independently-with-optional-priority-tags.md). Component immutability, fresh-crop provenance and the accepted stage boundaries remain in force.


开发者于 2026-10-22 确认：Stage 2 按确定性执行与基础交互能力收尾，取消以邮箱真实端到端任务作为完成门槛。截图、输入及 Asset 已有各自验收，真实业务编写又依赖尚不完善的 GUI 开发工具，例如坐标显示和区域选择；继续强制邮箱验收会把开发工具的手工成本纳入当前阶段。

Stage 2 保留完整 Manifest/Component 校验与发布、三层调用、确定性 Step Recovery、Working Manifest、Automation Plan、Trace/Ledger、前台观察、控制接管与释放、Asset 匹配/裁剪的既有要求和证据。#310、#311、#313 须按现行契约完成核对。增加已有裁剪的 `add-asset` 登记和教学样例，验证开发闭环后收尾 #307；不接入模型或重开执行器架构。

#317 邮箱任务延期，待 GUI 开发工具支持后再实施。#321 移交的 Windows 新格式 Asset 集成、当前 Workflow 接管和 Windows onedir 无系统 Python 验收保留在 #317 的独立清单中，也不再作为 Stage 2 结束门槛。Stage 2 完成不表示这些集成场景已验证，不以平台替身、macOS 包或已完成的单项实机实验冒充业务端到端通过。

保留 schema 2、应用注册 Trusted Actions、每 Manifest 专属库及全局不可变图片。Candidate 和样例旁的外部库文件统一为 `asset-library.json`，发布库仍为 `asset-libraries/<Manifest ID>.json`。不自动读取旧名 `assets.json`；已有草稿须由开发者明确改名，已发布库不受此次工作台文件改名影响。

`add-asset` 仅登记已有本地裁剪产物，核对 crop 来源、语义名/语言、图片完整哈希及解码，只原子更新当前 Candidate 库。同名同语言、不同内容需确认，相同映射为无写入成功；拒绝、EOF、取消不写入。它不连接游戏、不导入外部 PNG、不复制或改写已有图片，也不自动 publish 或修改 Default。`crop-asset` 仍可现场裁剪并自动登记，Workflow 的 `observe.crop_asset` 仍只产生图片及来源。

新 `example/trusted-actions/` 展示 Task Workflow → Subworkflow → Step 及全部应用动作调用。空库 `{}` 仍需存在；默认入口只截图和等待，匹配须先登记模板并发布，点击等控制用独立入口明确启动。旧 `examples/` 的删除是历史迁移决定，不禁止新的正式格式教学样例，测试继续拥有自己的夹具。

本决定修订 #307/#317、Stage 2 实施切片的 Slice 8 和完成规则，以及 ADR 0023/0024 的样例范围说明；不变更后续 Stage 3 独立 Component 修复和 Stage 3.5 Runtime Agent 的范围。
