# #336 — 聊天界面交互修订

状态：两处疑问已确认，专项影响检查后按本轮授权完成本地实施；见[实施记录](stage-5-336-chat-ui-implementation.md)。本记录不表示开发者或 Windows 实机验收通过。

## 1. 不恢复人工运行入口（已确认）

开发者明确：新需求第 7 节允许保留 Manifest 选择 / 试运行 Plan 顶层区域的表述是疏漏。本轮不恢复 Developer GUI 的人工版本选择、运行或“应用到 User GUI”入口。新聊天的 Source Manifest 创建参数、Manifest 参考附件及 Agent 的显式版本 trial_run 能力保持。

New Chat 是已有 Developer Session 的界面用语，不引入另一种会话或独立 Candidate 生命周期。Developer GUI 最左侧应用级导航保持；本轮只重构 Agent 页面的视觉布局和交互。

## 2. 会话标题本地提取（已确认）

开发者同意：从首条实际用户消息提取第一句作为标题，超长截断，悬停显示完整内容；旧 Session 同样从已保存消息提取。UUID 只用于详情定位，不作主要展示，不额外调用模型、不增加后台命名服务或自动记忆。不把宿主文件权限前缀、参考附件协议文字或人工校验通知当作标题。

## 本轮其余已指定范围

按开发者给出的完整交互要求实施：默认展开的可折叠历史栏、New Chat、首次提交前的滑动分段模式选择、开始后只读模式标识、新聊天上下文中的 Source Manifest、底部圆角自适应输入框、Enter 发送及 Shift/Ctrl+Enter 换行、输入法组合保护、同位置发送 / 取消 / 取消中反馈、附件和分组 More 菜单、紧凑聊天与空状态。删除 Developer 窗口底部 Current activity 状态栏；最左侧导航、Capture / Agent Settings 及 Agent trial_run 权限和取消收尾保持。

本次请求已授权按“对齐 → 影响检查 → 实施”顺序完成；两处疑问确认后直接推进，不再另设设计批准关卡。专项影响检查见 [审查记录](stage-5-336-chat-ui-impact-review.md)。
