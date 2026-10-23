---
status: accepted
supersedes: 0025 (Stage 3 workspace and Agent Asset creation limits only)
---

# Bound manual Agent repair with live observation and Asset additions

2026-10-23 后续修订：[ADR 0029](0029-use-explicit-candidate-edit-selection-and-continuous-developer-chat.md) 取代本决定中每次从 Default 重建 Candidate、单目标编辑、候选 Manifest/Recovery Rule 不可编辑的范围。它允许人工明确初始化、多文件授权与连续对话；下文现场截图、Agent 素材新增及旧标签保护规则继续有效。旧范围的既有 CLI 实现不表示新 GUI 契约已经实现。

2026-10-23 确认：Stage 3 继续只做人工启动的单 Component 修复，但允许两个专用工具取得当前游戏截图、从新截图裁剪新增 Asset，避免 Agent 只能依赖启动时的一张截图。裁剪每次重新截图，返回实际裁剪图片、完整哈希及标签；同逻辑名同哈希已存在时复用图片和原标签，明确报告已存在，不通过裁剪修改旧标签。新增哈希可写入现有逻辑名的标签映射，但不得改动旧哈希的标签。人类开发工具按 ADR 0027 仍可整体替换标签，本决定只收窄 Agent 的写入权限。新增 Asset 立即进入共享库，不要求 Publish；修复失败、取消或拒绝均保留产物，不清理。

代码读取边界改为当前工作目录的 Developer Candidate：来源仅为 Default Manifest，先检查来源可用和目标存在，再清空或新建候选目录并物化全部源码。清空由 LALC 在 Agent 启动前执行，显式取代“不覆盖现有草稿”的旧约定；代价是会丢弃未发布草稿，收益是 Agent 看到完整、来源确定的代码。Agent 只读所有候选文件，只能修改指定 Component，不能改候选 Manifest。正式源码和已有 Manifest 仍不可变，原始对照、最终产物与交互日志独立留存在数据目录。

这不是运行时 Agent Recovery：没有自动异常接管、游戏点击/按键、候选自动试跑、自动 Publish、交互追问或运行续接。运行中 Working Manifest 的衔接、多组件修改及 Runtime Agent Session 仍属 Stage 3.5。pi 为首选接入，先在 Mac 验证模型、图片和受限工具循环，再固定跨平台版本；真实截图、裁剪、DPAPI 和游戏行为在 Windows 验收。工具限制与现有 Validator 均不构成操作系统安全沙箱。

详见 [Stage 3](../stage-3-agent-assisted-component-repair.md)。

2026-10-23 #326 实践边界补充：每次 Agent 截图或裁剪请求均允许重新恢复并置前唯一 Target Window，复用现有聚焦确认与取消边界；失败返回明确错误，Agent 可以再次调用，工具内部不自动重试或沿用旧截图。多图读取先校验全部请求，任何一项失败则整次失败，不返回部分图片。
