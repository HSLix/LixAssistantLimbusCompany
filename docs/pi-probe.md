# pi 最小接入验证（#324）

此命令只验证 Python → 独立 pi 二进制 → 图片模型 → 受限源码读取 → 最终回答，不创建 Workflow Run，不重建 Developer Candidate，不编辑源码、不执行游戏点击。仅终端展示过程，不保存 Agent Interaction Log 或 pi 会话；#325 的正式修复入口与日志见 [单 Component 修复](component-repair.md)。

## 运行

当前接入回归基线为 **pi 1.4.0**，但启动不再硬性锁定版本。实际版本不一致时写 WARNING 日志并在 CLI 终端提示，仍继续启动；修复 GUI 同时在对话中显示警告，交互日志保留实际与已验证版本。Mac 当前使用 `/Users/li/.local/bin/pi`；Windows 使用 `pi.exe`，可通过 `--pi` 指定路径。无需为本扩展单独安装 Node 或 npm 依赖；Windows 扩展加载和进程退出仍需实机复核。

从项目根目录运行：

```sh
uv run --frozen lalc pi-probe \
  --image test_pi_img.png \
  --source-root tests/fixtures/virtual-workflow \
  --source steps.say_hello.py \
  --model YOUR_MODEL_ID
```

默认连接 `http://localhost:12138/v1`；必须使用 `--model` 显式指定模型，不再自动寻找 Gemma4。`--base-url` 要求完整 API 基础路径，不自动追加 `/v1`。要求服务声明支持图片，明确报告非 loaded 状态，不自动加载或换模型；实际图片输入由真实请求验证。`pi-probe` 继续使用临时参数，不读取修复的持久设置；请求上限必须至少为 2。

`--source-root` 是允许读取的完整目录，`--source` 指定首次必须读取的样例；模型仍可只读该目录内的其他文件。路径解析后必须留在此目录内，包括符号链接；这不是操作系统安全沙箱。不要把含凭据的目录作为读取范围。

默认问题为：识别游戏界面，并分析进入关卡下一步应点击哪个按钮及其大致位置。可用 `--prompt` 替换问题，源码读取验证仍保留。图片由 RPC 实际传入，终端展示文件位置、SHA-256 及请求中的图片标记，不输出大段 base64。

需要认证时加 `--ask-api-key`，在终端临时输入；密钥仅供本次服务认证，不放在命令参数、提示词、持久配置或输出中。本机无认证服务可直接省略。

## 请求与结束

- 临时空目录承载 pi 工作目录与配置；关闭个人扩展、技能、提示模板及 AGENTS/CLAUDE 上下文发现，只加载 LALC 指定扩展，只启用受限 `read`。终端、PowerShell、edit、write 均不开放。
- 关闭会话重试、自动压缩、缓存预热及启动联网；现成 pi 模型客户端设置 `maxRetries: 0`，避免内部 HTTP 重试绕过计数。
- `--max-requests` 默认 20，在发送前计数并拒绝超限请求。到达上限后若模型已正常回答仍可完成；需要下一次请求时结束为未完成。
- 终端展示实际模型请求（省略图片编码）、工具参数和结果、响应与最终状态。以 `agent_settled` 判断停止，不把 `agent_end` 当作最终结束。
- 模型报错或上限触发返回 1；必须实际成功读取源码并收到正常非空回答才返回 0。这里的 completed 只代表验证流程完成，不评判模型建议是否正确。
- Ctrl+C 请求 RPC abort，关闭输入并回收子进程；必要时 terminate/kill。取消返回 130，不自动续接。

## 验证边界

pi/Agent 测试属于按需集成验证，默认回归跳过，即使本机已安装 pi 也不会自动执行。仅当改动涉及 Agent 接入、工具或模型交互，或任务明确需要检查 Agent 功能时，才显式开启并选择相关文件：

```sh
UV_CACHE_DIR=.generated/uv-cache uv run --frozen pytest --run-agent-tests -q tests/test_pi_probe.py tests/test_cli.py
```

普通全量回归不添加 `--run-agent-tests`；只指定 `tests/test_pi_probe.py` 也不会隐式开启。后续新增涉及真实 pi、Agent 工具循环或模型服务的测试统一标记 `pytest.mark.agent`，遵守根目录 `AGENTS.md`。`lalc pi-probe` 真实模型验证也只按需执行，不能附带在普通回归中；报告时区分默认跳过、集成测试通过与真模型验收。

契约测试使用真实 pi 0.86.1 与本机 HTTP 替身，覆盖图片实际传输、工具调用、内存认证、个人配置隔离、目录越界与链接拒绝、请求上限和 503 无重试；SIGINT 取消测试只在 POSIX 运行。缺少 pi 时相关测试跳过。它们不能代替真实 Gemma4 图片理解或 Windows exe 验收。

2026-10-23 Mac 实测：上述 10 项测试通过；安装 wheel 包含 `lalc/pi_probe.ts`。真实本机 Gemma4（`HauhauCS/Gemma4-26B-A4B-QAT-Uncensored-HauhauCS-Balanced-MTP:Q4_K_M`）用 2 次请求完成样例源码读取和 `test_pi_img.png` 分析，返回右下角 Enter 按钮，收到 `agent_settled`，退出码 0。图片 SHA-256 为 `263f14295f589436c61165951355ddf4195197e05182e03cb19db60624184327`。仅保留此验证结论，模型交互本身不落盘。Windows 同版本 exe 尚未验收。

同日开发者独立复测并确认符合预期：所提供终端输出为 `completed`、`requests=2`、`source_read=true`、`stop_reason=stop`、`error=null`，#324 Mac 最小接入验收通过。此确认未再次启动 Agent 测试或模型调用。

2026-10-23 升级复测：pi 1.4.0 的 stdout 接管要求自定义协议事件直接按行写原始描述符；当前实现已修复，且保留 stderr 诊断。探针 8 项均通过，包含有效一像素 PNG、实际截图尺寸、权限拒绝、额度、错误无重试及取消。全套回归 258 passed、5 skipped，不使用临时超时插件；真模型和 Windows 跳过项不计通过。历史 0.86.1 的 Mac 真模型证据仍仅属于原版本。
