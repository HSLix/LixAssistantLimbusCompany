# pi 1.4.0 接入阻塞与下次修复范围

2026-10-23。状态：以下历史阻塞已修复，完整回归通过；修复与复测结果见文末。

## 修复前证据

- 本机 `pi --version` 为 `1.4.0`；已验证基线仍为 `0.86.1`。版本差异当前只警告，不阻止启动；CLI 终端和 WARNING 日志均已有实际输出。
- 全套测试包含 Agent：**243 passed、12 failed、5 skipped**，耗时 385.64 秒。最终测试已允许本机 HTTP 端口，不将第一次沙箱拒绝监听的错误算作兼容性失败。
- 完整输出：`.generated/pi-1.4.0-full-tests.log`。
- 为避免现有取消测试无限等待，本轮临时插件 `.generated/test-support/lalc_test_timeout.py` 给每项测试加 60 秒外部截止；其中修复取消测试因该截止失败。插件未改动项目或测试源码，不是永久测试方案。

## “缺少真模型配置”的准确含义

`tests/test_component_repair_agent.py::live_conversation` 在任何连接请求前检查两个专用环境变量：

| 变量 | 含义 |
| --- | --- |
| `LALC_REPAIR_TEST_BASE_URL` | 测试调用的真实模型服务完整 API 基础地址，例如服务实际使用的 `/v1` 路径 |
| `LALC_REPAIR_TEST_MODEL` | 该服务返回的准确模型 ID |

缺少任一变量就主动 skip；它没有检测服务是否启动，也不表示本机没有模型。即使 GUI 已保存连接，该测试也会先因环境变量缺失而跳过，不会自动使用个人连接。测试使用临时独立数据目录，不写开发者草稿或 Default。

此次跳过的两项是纯计算缺陷真实修复、真实模型素材/动作契约查询。其余三项需要 Windows 原生 DPAPI 或真实游戏窗口。安装真实 pi 不等于调用真实模型：本轮执行的其他 Agent 测试通过真实 pi 调用本机 HTTP 替身，验证工具与宿主契约。

下次真模型验收前须明确这两个变量；服务要求认证时，还须确认测试凭据来源，不能把密钥写进提示词、命令参数或报告。本次未尝试真实模型连接，不宣称模型不可用。

## 修复前确认的阻塞点

### 1. 自定义 RPC 事件输出通道

`src/lalc/pi_probe.ts` 的公共 `emit()` 使用 `console.log(JSON.stringify(...))`。本轮 pi 1.4.0 实际将 `lalc_ready` 输出到 stderr；测试日志已保留该完整事件。`src/lalc/pi_probe.py::rpc_session` 把 stderr 当诊断文本记录，而 `event()` 只从 stdout 解析协议，所以就绪消息无法到达等待者。

直接影响：

- `component_repair.py::configure_session`：连接预检和正式修复共用的就绪/工具集合确认。
- `pi_probe.py::_interact`：独立图片/只读探针的就绪等待。
- CLI `repair`、GUI Agent Repair、独立 `pi-probe` 都复用上述路径，不应分别补丁。
- 同一个 `emit()` 还发送 `lalc_request`。虽然此次未进入模型请求，修复时必须连同计数与 payload 引用验证，不能只让 `lalc_ready` 通过。

建议从扩展公共发送点修复：显式向协议 stdout 按行写 JSON，保持 stderr 为诊断通道；不把 stderr 中所有 JSON 都当作可执行协议事件。

### 2. 启动超时诊断为空

就绪等待使用 30 秒 `asyncio.wait_for()`；修复入口最后仅保存 `str(error)`，`TimeoutError` 的字符串为空，所以当前产物出现 `reason=error`、`error=""`、`requests=0`。探针终端也出现空的 `pi probe failed:`。

修复范围：对就绪/配置响应等待提供明确超时说明，保留原始异常原因和相关 stderr；CLI 与 GUI、交互日志使用同一真实错误，不猜测模型阶段。无需新增重试、回退或自动续跑。

### 3. 取消测试没有等待失败的退出条件

`tests/test_component_repair_agent.py::test_cancel_reaps_process_and_keeps_candidate_and_log` 在发出取消前一直等待 HTTP 替身的 `started`。当启动任务已经失败且未发模型请求时，等待仍不结束；本轮由外部 60 秒截止终止。

修复范围：等待有明确截止，且发现任务已结束时报告其实际失败；失败路径也回收任务/子进程。不能通过跳过或放宽断言隐藏取消功能的问题。

## 一起修复与验收的顺序

1. 修复公共事件发送通道，覆盖就绪事件、工具集合、模型请求计数与 payload 引用；修复可读超时诊断。
2. 修正上述取消测试的等待/清理，确保正常取消仍在真实请求开始后进行，不依赖本轮临时插件才能结束。
3. 用 pi 1.4.0 显式运行 `tests/test_pi_probe.py`、`tests/test_component_repair_agent.py` 的 Agent 集成检查，再跑全套测试；保留版本差异 warning，不恢复硬锁。
4. 检查 CLI/GUI：就绪、实际工具/计数、超时错误和取消日志可见。源码与测试定义应覆盖多文件授权、plan.json 拒写、零选择、跨轮历史/图片、素材旧标签保护与进程回收。
5. 在显式提供真实服务地址与模型 ID 后运行两项真模型验收；Windows 三项保持独立实机验收，不能用 Mac/HTTP 替身替代。
6. 更新 `docs/pi-probe.md`、`docs/component-repair.md`、Developer GUI 实施状态和新的测试证据；只有实际验证后才调整“已验证 pi 版本”记录。

## 修复前结论的边界

12 项失败不是已证明存在 12 个独立缺陷。已确认的共同阻塞在自定义事件通道，另有空超时诊断和测试等待缺陷；工具调用、模型流、上下文 hook 等后续接口被启动失败挡住，其与 1.4.0 的兼容性仍待通道修复后验证。此次没有修改运行时代码、测试源码或 pi 安装。


## 修复与逐项复测结果

- 自定义事件改为通过 `node:fs.writeSync(1, ...)` 按行写原始 stdout 描述符。实测 1.4.0 同时重定向 `console.log` 与 `process.stdout.write`，不能仅替换后者；stderr 仍保留为诊断通道。就绪、实际工具集合、请求计数与请求文件引用均已通过真实 pi/HTTP 替身检查。
- 公共 `rpc_event()` 对就绪及配置响应给出具体的 30 秒超时说明，保留原始异常原因。修复交互日志额外保存原始异常诊断与 traceback；GUI/CLI 使用同一非空错误说明。
- 取消测试增加 15 秒等待截止和任务提前结束检查，失败也取消/等待任务并释放替身服务；不再依赖临时外部超时插件。
- 修通事件后发现旧一像素 PNG 的 IDAT CRC 无效，新版 pi 图片预处理会丢弃它。已更换为有效 PNG，并新增实际截图尺寸的传输检查，未关闭或绕过图片预处理。
- 按首个失败立即停止的方式执行：图片检查失败时先修正图片，再继续探针其他检查，随后逐项执行修复集成检查，最后运行整个测试集。探针 8 项通过；修复集成 9 项通过、4 项因外部环境跳过。
- 全量命令：`QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest -v -x --run-agent-tests --tb=short -ra`，**258 passed、5 skipped、零失败**。日志为 `.generated/pi-1.4.0-regression-fixed.log`；没有加载 `.generated/test-support/lalc_test_timeout.py`。
- 接入回归基线更新为 **pi 1.4.0**，不同版本仍仅 WARNING，不恢复硬锁。本次证明的是 Mac 上真实 pi 与本机 HTTP 替身的接入、权限、上下文、图片、计数及取消回归，不是所有平台/模型的验收。
- 5 项跳过保持明确：2 项缺少显式真模型测试连接，3 项需要 Windows 原生 DPAPI 或游戏窗口。它们不计为通过，真实游戏修复与 #329 验收也未由本次回归替代。
