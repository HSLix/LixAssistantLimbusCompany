---
status: accepted
---

# Associate Agent history with per-round game observations

2026-11-11 局部替代：历史工具的只读语义保留，增加 Developer GUI 管理、覆盖所有 Agent 模式的历史检索总开关，默认开启、下一轮生效；不是删除历史或停止记录。 见 [ADR 0040](0040-share-run-state-and-reuse-agent-sessions-for-runtime-repair.md)。下文保留原决定，不代表新设计已实现。

每轮开发对话开始前观测本机已安装游戏的 `game_version` 与 `steam_build_id`；诊断在开始时观测一次，不要求启动游戏。两字段组合是历史分组身份，游戏内版本优先展示，缺失值不合并，双缺失为 Unknown；失败留诊断但不阻止对话。版本只表示采集时的安装状态，不证明经验仍有效或覆盖所有热更新。

每轮日志保留原始观测与时间，本轮用户上下文持久追加同一份观测，不重写历史或系统提示词。数据目录独立索引仅用于增量检索，可显式从已保存观测重建，不扫描导入未观测的旧历史；同一 Session 可关联多个版本组合，当前活动只更新当前组合的最近时间。此取舍保留对话自包含与失败恢复证据，接受索引出错时检索暂时不完整，并明确报错后重建。

GUI Construct / Repair 与 CLI Repair 均可通过三个只读工具列版本、查 Session、按需读取文字及图片。版本筛选用于定位，不作为同一 Session 其他轮次的读取限制；每轮显示其版本组，无关联显示 Unknown，不因此补索引旧轮次。路径、引用、哈希与分页边界不因 UUID 或索引命中而放宽；历史是参考而非新指令。Runtime 实际接入留 Stage 6。

Steam 客户端根目录由 User GUI 设置或自动发现并缓存，通过库配置查游戏；有效缓存优先，重新发现歧义不擅自选取。UnityPy 属 automation 可选依赖，未知解析布局失败而不是猜版本；只允许已验证的四字节布局例外。删除早期独立 `lalc pi-probe` 冒烟入口，不为其扩展持久日志；正式 Agent 仍复用的 pi 启动、RPC、工具扩展及测试继续保留。

具体决定、影响及验收边界见[确认记录](../game-version-session-decisions.md)、[影响审查](../game-version-session-impact-review.md)和[用法](../game-version-history.md)。
