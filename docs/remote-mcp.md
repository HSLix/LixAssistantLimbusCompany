# 远程 MCP V1：Mac Codex 接入 Windows LALC

V1 只面向 Mac 上的 Codex 桌面应用。Windows LALC 提供工具和执行环境，Codex 保留对话及推理；不需要 Windows 上安装或配置 pi／模型。它不是远程桌面、文件同步服务或 Python 沙箱。

## 首次设置

源码运行先安装可选依赖：`uv sync --extra gui --extra automation --extra mcp`。Windows 构建使用现有 `--all-extras`，两个分发包都包含 MCP 能力；Tailscale 仍需用户另行安装。

1. Mac、Windows 安装并登录同一 Tailscale 私有网络，确认网络访问策略允许两台设备连接。
2. Windows 打开 LALC **开发者面板 → 远程 MCP**，保留默认本机端口 `8765`。在 Windows 的 Tailscale 命令环境执行一次：

   ```powershell
   tailscale serve --bg http://127.0.0.1:8765
   ```

   根据 Tailscale 提示启用 HTTPS。使用命令显示的 `https://设备.私网.ts.net` 地址，在 LALC 中填写为 `https://设备.私网.ts.net/mcp`，保存连接设置。使用 Serve 的私网 HTTPS 转发，不使用 Funnel。已有 Serve 配置的设备需先检查目标和路径，避免覆盖其他服务。
3. 点击 **生成／重置连接令牌**。明文只在当前本地弹窗显示一次，复制并安全保存；LALC 磁盘仅保存随机令牌的校验哈希。重置会使旧令牌失效，并撤销当前授权、停止相关远程操作。
4. 在工作台选择明确 Manifest，或“最新已发布 Manifest”，初始化 Candidate。必须已有一个可用的已发布版本；不会把 Default 或空白误认为最新版本。
5. 点击 **开启 MCP 服务**，再点击 **允许远程控制**并阅读 Python 执行提示。开启服务不自动授予控制权。
6. 在 Mac 的个人 Codex 配置 `~/.codex/config.toml` 添加服务器配置，重新启动桌面应用／MCP 连接：

   ```toml
   [mcp_servers.lalc]
   url = "https://设备.私网.ts.net/mcp"
   bearer_token_env_var = "LALC_MCP_TOKEN"
   ```

   `LALC_MCP_TOKEN` 必须存在于 **Codex 桌面应用进程能读取的环境**。仅在某个终端中 export 后从 Dock 打开应用，不保证应用继承该变量。也可在个人配置中改用官方支持的固定请求头：

   ```toml
   [mcp_servers.lalc]
   url = "https://设备.私网.ts.net/mcp"
   http_headers = { Authorization = "Bearer 在本机填写连接令牌" }
   ```

   两种凭据配置择一使用。个人配置属于凭据文件，不放进项目、提交记录或聊天；LALC 的“复制 Codex 配置”只复制环境变量版，不包含令牌。

Tailscale Serve 可以持续保留转发配置，但不能启动 LALC 或开启 MCP。LALC 重启后仍须重新开启服务、允许远程控制；原连接令牌和工作台保留。

官方依据：[Codex MCP 配置](https://developers.openai.com/codex/mcp/)、[Tailscale Serve](https://tailscale.com/docs/reference/tailscale-cli/serve)。客户端菜单随版本可能不同，上述配置字段以官方文档为准。

## 外部开发顺序

MCP 初始化会向 Codex提供跨工具指导和实际工具 Schema；工具描述与参数可直接发现，不复制 pi 的工具循环。
复用本地工具的返回结果须先完整展开日志去重引用并校验内容哈希，再发送标准 MCP 文本／图片和结构化数据；`$lalc_log` 存储引用不作为传输格式。

1. `mcp_status` 查看服务、授权、工作台及当前控制者。它不返回控制凭据。
2. `mcp_acquire` 获取独占 `control_token`，同时返回上次使用时间；首次为 `null`。名称仅供显示，不是已验证的设备／聊天身份。
3. `list_skills` 发现指导，用 `read(scope="skills", path=...)` 读取固定副本；用 `action_contracts` 查询当前 Action 契约。
4. `read`、`edit`、新增组件、素材、知识库和页面工具按发现到的参数使用。Candidate 只允许编辑已有文件，新增仍走组件专用入口；只读参考不会获得写权限。
5. 写入、发布、试运行及可能等待人工确认的工具必须携带标准 UUID `operation_id`。先取得操作编号，再用 `mcp_query(operation_id=...)` 查询，直到 `finished`、`failed` 或 `unknown`；`waiting_local` 表示需在 Windows 确认。
6. `validate_and_publish` 完整校验后发布不可变 Manifest，不改变 Default；随后 `trial_run` 使用明确的已发布 ID。启动操作返回实际 Run ID 后，通过 `mcp_query(run_id=...)` 查询。
7. Run 查询只返回状态和最近五条业务／Trusted Action 日志，包含 Debug；停止后附最终结果。完整日志和引用图片通过 `read_run_log` 等工具按需读取。
8. `mcp_stop` 通过明确的 `run_id` 或 `operation_id` 请求停止；暂停／恢复只在本地。空闲后用 `mcp_release` 释放控制权，保留本地授权。

同一操作编号和参数的重试不会重新发布或启动；不同参数会被拒绝。故意再试一次使用新编号。重试返回的完成操作仍应检查内部工具结果的 `isError`／`ok`，不能仅凭 HTTP 成功或操作结束声称业务成功。

## 控制权和本地操作

- 一个持久工作台、一个控制会话。另一聊天即使共用连接令牌也不能接管；所有工作台工具携带独占控制凭据。
- HTTP 连接结束、Mac 休眠或关闭 Codex不释放控制权，也不取消已经发起的操作。使用原控制凭据查询／续接；凭据丢失须本地撤销，不能只用连接令牌取回。
- 撤销立即拒绝新操作，同时请求停止本地相关任务。等待输入释放、文件提交／回滚和日志收尾后才恢复本地执行权。致命运行错误保留互斥并提示检查日志、退出应用，不把环境当作安全空闲。
- 控制期间阻止本地 pi、新运行、手工发布和资源导入；CLI 的相关写入入口也通过跨进程控制锁拒绝。进程锁沿用当前系统用户范围，不承诺多 Windows 用户会话隔离，更不阻止用户绕过应用手工修改磁盘。
- 本地可查看 Asset、使用已有截图测试模板匹配／SIFT／OCR。空闲时可串行截图与保存素材，并留操作记录；Run 运行或暂停时禁止现场截图和写入。窗口尺寸、标签、素材删除等仍受限制。
- 运行期间远程可读 Candidate、代码和日志，不能编辑、发布、写素材或重新截图。协议控制查询始终可用；其他工具正在操作工作台时，数据读取提示稍后再试。
- 本地页面安装、页面启停、反馈等使用原有审批对话框和固定快照。MCP 素材归档统一要求本地确认，不接受外部 Agent 自报 `explicit_user_request` 跳过批准；这是相对 pi 的保守接入差异。
- 若关闭开发者面板但用户窗口仍开着，服务随应用存活；需要本地审批时须重新打开开发者面板。退出整个 LALC 会关闭服务及相关任务，不后台继续运行。

## 存储与失败处理

应用数据目录的 `remote-mcp/` 保存配置校验哈希、工作台 Candidate／固定基线／页面草稿、操作记录、审计及工具证据。普通工作目录和待提交文件继续复用 `work_files`，继承父目录权限。

- 初始化后的来源固定，不随新发布自动更新。更换来源需先释放控制权、本地确认，只替换 Candidate 和比较基线；页面草稿、Assets、已发布版本与操作历史保留。
- 每次新取得控制权先返回此前时间，再记录当前使用时间；状态查询、工具调用及持有同一凭据的断线续接不更新时间。
- 发布预先持久化目标 Manifest ID，Run 开始事件记录操作编号。应用异常退出后仅核对提交证据，不自动重放；无法确定的结果标 `unknown`，不能冒充成功或未执行。结束进程不恢复 Python 调用栈或继续旧 Run。
- 连接令牌不进入工具参数；控制凭据只返回给取得者，不写入 LALC 操作记录。外部 Codex 的工具历史可能保存控制凭据，LALC 无法清除客户端历史。
- 控制组独立列举 Construct 的能力，不自动跟随 pi 扩权；Runtime 工具 `recheck`／`read_run_state` 不开放。工作流的 Python 执行不是权限沙箱，发布加载模块时也会执行代码。
- 既有全局历史、外部知识和 Manifest 查询开关在取得控制权时固定，并由 MCP 服务端继续强制执行；不继承 pi 的模型配置、请求额度或对话内容。

## 验证与验收边界

自动测试覆盖控制会话、持久化、路径与权限拒绝、发布／Run 去重、取消、最近五条 Debug 日志、人工审批、GUI 门控、认证／Origin 检查和本机真实 HTTP 开发闭环。它们使用确定性执行替身，不调用真实模型或游戏。

Windows 打包成品、Tailscale HTTPS、Mac Codex 桌面应用和真实游戏的跨设备闭环仍须现场验收；本地协议测试通过不等于这些验收已通过。正式命令与结果见[实施记录](remote-mcp-implementation.md)。
