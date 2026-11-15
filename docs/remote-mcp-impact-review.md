# 远程 MCP V1 影响审查

2026-11-15。以本轮逐项确认的[设计](remote-mcp-decisions.md)为输入；本报告记录实施前的审查结果，不把当时差距当作实施后的缺陷。用户先要求只审查，阅读后明确授权开始实现，并决定 Developer GUI 独立一页。

## 设计变化

pi 对话持有整轮 Agent 活动 → 外部控制会话跨调用持有开发权；独立持久工作台不保存外部对话。权限初始对齐 Construct，但独立列举。同步 trial_run → 启动、查询、停止分离；断线不取消、不放权。保留单 Runner、不可变 Manifest、Publish 不改变 Default、Windows 人工审批和 Runtime 边界。

## 已确认的改动影响

| 证据与调用链 | 影响与要求 |
| --- | --- |
| `application.py:activity/start/_begin_run`，`process_lock.py` | 当前只有活动与运行互斥，需增加独立控制权检查，不能长期占用 `activity("Agent")`；否则本地辅助调试无法使用。跨进程游戏锁继续保留。 |
| `pi_probe.ts:checkedRead/checkedEdit`，`agent_skills.py` | 源码读写和 Skills 发现依赖 pi，需独立 MCP 适配，保留路径、可编辑集合、固定 Skill 副本；不能把 Windows 路径当 Mac 文件。 |
| `developer_session.py:create/check`，`developer.py:initialize`，`manifest.py:list_manifests` | Session 绑定对话／模式；复用草稿和事务能力，不伪造 pi 对话。未指定来源的旧默认／空白语义不等于最新版本。 |
| `repair_tools.py:trial_run` → `ApplicationService.start` | 原工具等待完成，取消及异常 finally 会 Stop；MCP 应调用底层异步 Runner，保留 Developer Trial 禁用 Runtime Agent。 |
| `run_logs.py:is_live_log` → `ApplicationService._live_logs` | 现有缓存过滤 Debug，不能拿最后五条作为 MCP 返回；需包含 Debug 的有界记录。 |
| `page_drafts.py:PageDrafts`，`developer_gui.py:show_page_preview/show_feedback` | 页面入口和审批绑定 GUI Construct Session／pi 作业轮次；需新增明确 mcp 入口及操作身份，同时保留固定快照与迟到批准失效。 |
| `manifest.py:publish` | 每次生成新 UUID，调用后再记结果不足以可靠去重。必须预记录发布身份，并关联 Run 启动证据。 |
| `gui.py:render_state/closeEvent/request_reload`，`developer.py:match_*_preview` | 统一 busy 禁用整页无法表达本地只读匹配例外；要细化门控，并把远程活动纳入退出／重载清理。 |
| `pyproject.toml`、`LALC.spec`、构建脚本 | 新增官方 SDK 与 HTTP 依赖，补充元数据／许可证；无 pi 包也须验证 MCP。 |

## 需明确的取舍及潜在风险

- `remove_asset(explicit_user_request=True)` 可跳过反馈，外部对话不在 LALC，服务无法核实此声明。实施采用统一 Windows 归档确认，不把自报布尔值当作授权。
- 人工审批等待可能超过 Codex 工具超时，采用异步操作及 `waiting_local` 查询，不新增远程审批通道。
- 重置令牌复用撤销流程；更换 Manifest 只替换 Candidate／基线，保留页面草稿并在本地确认中明确范围，避免无意删除。
- 控制凭据不证明真实聊天身份；客户端可能持久保存工具历史。凭据丢失走本地撤销，不凭共享 Bearer Token 接管。
- `ManifestManager._load_module` 在发布阶段也执行 Python；只能承诺工具权限检查，不能承诺 Python 沙箱或强制即时退出。
- HTTP 断线不等于取消，认证和 Origin 检查不能由 Tailscale 转发替代。真实客户端的环境变量可见性、重连和图片显示需现场验证。

## 跟进顺序与证据

控制权／工作台存储 → 工具与操作去重 → 异步 Runner／审批 → GUI 和退出门控 → 打包及跨设备验收。相关规格补充 MCP 局部范围，原 pi／Runtime 历史决定保留。

审查时执行了 `test_developer_policy.py`、`test_process_lock.py`、`test_developer_session.py`、`test_page_package_tools.py`、`test_template_match_lab.py`，57 passed，4.68 秒，未启用 Agent 测试。后续实现及验证另见[实施记录](remote-mcp-implementation.md)；上述审查检查不证明 MCP 当时已可用。
