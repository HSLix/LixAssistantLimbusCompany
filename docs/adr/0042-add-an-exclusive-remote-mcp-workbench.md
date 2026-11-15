---
status: accepted
---

# 用独立远程 MCP 工作台接入外部开发 Agent

2026-11-15，经逐项设计确认、影响审查并获准实施：Mac Codex 桌面应用通过 Tailscale 私网 HTTPS 使用 LALC 工具；LALC 保留一个持久 MCP Candidate 和页面草稿、版本发布及游戏执行权。MCP 的权限组独立，初始对齐 Construct；复用现有服务，不借用 pi 对话／上下文或另建 Runner。此新增入口不替换 ADR 0034 的内置 Session 契约，不继承 ADR 0040 的 Runtime Recheck 权限。

连接认证、本地授权、控制会话和实际执行分别管理；断线不放权、不停止 Run，凭独占控制凭据续接，丢失则本地撤销。操作以编号异步查询并去重，本地只在安全收尾后交还执行权。选择这一边界以支持长时间跨设备开发，接受断线后需主动释放／本地接管的成本；不建设多用户调度、对话同步或远程审批，保留 Windows 人工审批和 Python 非沙箱边界。

具体规则、审查后的保守接入差异及证据见[设计记录](../remote-mcp-decisions.md)、[用法](../remote-mcp.md)、[实施记录](../remote-mcp-implementation.md)。
