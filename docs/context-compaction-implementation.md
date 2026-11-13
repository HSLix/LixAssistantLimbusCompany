# 上下文压缩实施与验证

2026-11-12。依据[审查](context-compaction-impact-review.md)和 [ADR 0041](adr/0041-let-pi-own-effective-agent-context.md)实施；实现已完成，验证范围和限制如下。

## 实现

- Developer Session 私有 `pi/session.jsonl` 由 pi SessionManager 管理；首次迁入使用普通待提交文件，成功后发布。绑定稳定 Candidate 目录，避免进程工作目录清理使恢复失效。宿主只提交新增输入，不用 `context.json` 重建有效历史。
- `pi_context.ts` 通过 idle 准备命令及 `turn_end` boundary drafts 实现压缩和持久图片编辑。沿用 pi 的 Session 投影、工具消息关联及 compaction entry；自定义策略用于支持总目标语义，原生自动压缩关闭，避免另一套阈值及自动重试。
- DeepSeek 产品线 400k、llama.cpp 50k；若模型声明窗口更小，额外为输出留 8192 token 后采用更安全的线。本地 `/models` 未声明窗口时仍采用原有 65536 元数据回退，不能据此宣称已探明实际服务容量。
- 全局压缩策略在 DeveloperGUI Agent 设置编辑，下轮生效：比例 20–90%，首次 30%；固定正整数，默认 20k；本轮图片窗口正整数，默认 12。共享 GUI／CLI／Runtime 执行链。
- 图片淘汰变成带 Session／事件图片 ID 的文字引用；显式 `read_agent_session` 取回后进入本轮窗口。旧图、用户原始消息和工具结果仍在脱敏业务日志中。关闭历史权限不会静默恢复读取工具。
- 系统／工具不摘要但计入目标；摘要与近期原文分配剩余额度，工具调用和结果不从中间截断。总结分片避免超出服务窗口，失败／空／截断摘要不作为成功结果。未达目标但低于安全触发线可继续，否则停止。
- 总结不带业务工具，单独记录 `compact-N.json`、请求数、token／耗时相关事件；价格未知标记未知，不把 provider 的零价格元数据当作真实免费。最终 JSON 纠正仍计入业务额度。
- 聊天下方数字与短额度条以压缩线为分母；小于 50% 绿、50% 至小于 80% 黄、80% 起红。显示估算及 token 分母，未知状态不伪装为零。压缩生命周期进入“思考中”和持久日志，并支持历史回放。
- 40 MiB 最终请求体预算独立于 token；图片窗口先按字节收缩较早图片，最新单图与必要内容仍超限则停止，不静默降低图质。设置默认 DeepSeek，旧选择与 llama.cpp 独立默认值保持。

## 验证边界

普通与显式 Agent 测试分开串行执行，最终各组结果：

- 普通定向组：283 passed、1 skipped；日志 `.generated/context-ordinary-tests.txt`。覆盖设置、默认选择、会话／日志、GUI、颜色边界、打包清单、Sharing 和 CLI。
- 普通补充组：130 passed、2 skipped；日志 `.generated/context-ordinary-extra.txt`。覆盖 Runtime、权限、Sharing 资源／GUI、双语、User GUI、诊断及 pi 启动资源。
- 真实 pi 1.5.0＋本机 HTTP 替身相关组：95 passed、4 skipped；日志 `.generated/context-agent-regression.txt`。4 个跳过项未计为通过，未运行真实 Windows／模型测试。
- 最终压缩专项：12 passed；日志 `.generated/context-agent-new-final.txt`。包含比例／固定目标、轮内工具结果、图片回读和数量窗口、截断／空／HTTP 错误、一次性旧历史迁入、DeepSeek 400k 与 llama.cpp 50k 区别、取消后恢复、已知连接密钥在 pi 持久化前脱敏。与上述 Agent 组去重后共 101 个用例通过。
- 普通组曾发现既有 GUI 测试窗口关闭后未销毁会污染后续主题／聚焦检查，fixture 现显式销毁窗口，最终定向组通过。新默认服务和不再回放旧额度通知的断言已相应更新，本地服务用例明确选择 llama.cpp。
- 收尾检查：设置／校验组 37 passed、1 skipped，进程／启动组 26 passed，压缩后重启／迁入组 3 passed；均与前述组重叠，不累计虚增通过数。模型窗口元数据变化时重建 pi 进程，避免复用旧窗口配置。
- offscreen 中文聊天／设置界面已生成并检查：`.generated/context-ui-preview-2/chat.png`、`settings.png`；64% 为黄色，固定目标在比例模式下禁用，默认 30%／12 张／DeepSeek。这使用测试平台／macOS 标题栏替身，不是原生 Windows 验收。

未跑整个仓库全量回归；未调用真实 DeepSeek／llama.cpp 模型、真实游戏或验收 Windows 成品。token 估算与模型实际用量可能不同，保留图片采用固定额度估算；真实摘要质量和费用仍需真实服务验收。当前模型价格元数据不能用作真实费用证据。

此前 413 样本的字节测量见审查文档。本次实施阶段再次访问时，开发者原分享目录 `/Users/li/Downloads/lalc-sharing/` 已不存在，因此未能完成该原包的最新离线回放；不将之前的测量当作新实现的回放通过证据。
