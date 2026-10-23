# Developer Candidate 修复

#330 按 [ADR 0029](adr/0029-use-explicit-candidate-edit-selection-and-continuous-developer-chat.md) 升级了 GUI/CLI 共用修复宿主。使用当前 Candidate，显式选择可编辑的已有文件，按每条用户消息处理一轮并保留上下文；不会自动重建草稿、执行候选、Publish 或设置 Default。

## Developer GUI

安装已有 `gui`、`automation` extras 后运行 `uv run --frozen lalc`。普通执行不启动 pi；Agent 当前接入回归基线为 pi 1.4.0；其他版本也允许启动，版本不匹配会写 WARNING 日志，在 CLI 终端及 GUI 对话提示，兼容性须另行验证。

- **Capture**：主动截图后拖动框选，填写完整 Asset 逻辑名和 JSON tag 列表，查看裁剪预览并确认保存。保存使用同一张原图和同一区域；取消不写 Asset。已有图片预览不依赖游戏继续前台。坐标监测须手动刷新，显示客户区物理像素坐标及客户区外状态，失效后停止，等待再次刷新。监测不抢焦点，主动截图按原有规则恢复并置前游戏。Agent 的 `crop_asset` 仍每次新截图。
- **Runner**：刷新 Manifest 与入口，选择 Task Workflow、Subworkflow、Step 或 Automation Plan。前三种输入 JSON 对象，空白按 `{}`；Plan 选择已有配置文件。可暂停、恢复、取消，查看真实 Base ID、结果、Trace 和 Ledger。Runner 选择持久保存，只作用于后续执行，不改变 Default 或 Candidate；重启恢复后先刷新核验，不可加载时禁止启动，须重新选择或清除。
- **Agent Settings**：保存完整 Base URL、Model 和每轮请求上限，默认 20、最小 2。API Key 普通空输入保留原值；新输入覆盖，明确清除解除凭据。界面仅显示是否设置，不回读旧明文。Windows 使用当前用户 DPAPI；其他平台仅在本次 GUI 内存中保留输入的临时密钥。不会读写其他 pi 实例的个人配置。
- **Agent Repair**：从已有 Manifest 明确初始化或重建 Candidate；非空替换须确认，成功后开启新对话，失败保留原草稿及原对话。多选已有文件或全选，`plan.json` 始终只读；无选择仍可分析并使用既有素材工具。支持纯文字和可选 PNG，每条消息启动一轮，最终回答后等待主动发送下一条。New Conversation 保留 Candidate 和固定 Diff 基线，旧日志保留。

实际 Diff 与 Validator 结果供人工审阅。Publish 重新校验并生成新的不可变 Manifest，不运行它，也不设置 Default；设置 Default 是另一个明确操作。GUI 不增加运行时审批流程。

Runner（包括暂停）、Agent 一轮处理、人工截图和保存由同一应用服务互斥。被动坐标和已有图片框选/预览可以继续。候选初始化、校验、发布也通过共享宿主活动检查。关闭时可返回继续，或取消并等待输入释放、日志保存和 pi 回收；切换页面不取消任务。

## CLI

```sh
uv run --frozen lalc init --from <saved-manifest-uuid>
# 明确确认替换现有草稿时才使用：
uv run --frozen lalc init --from <saved-manifest-uuid> --replace

# 文件路径相对 candidate/；不是 Component 逻辑名
uv run --frozen lalc repair steps.your_step.py manifest.json \
  --problem '问题、复现步骤和预期行为' \
  --image /absolute/path/to/optional.png

# 不选择文件：分析与素材工具可用，Candidate 不可编辑
uv run --frozen lalc repair --problem '请分析这个问题'

# 全选除 plan.json 外的已有文件；主动续聊，空行退出
uv run --frozen lalc repair --all --chat --problem '请修复所述问题'
```

CLI 的 `--image` 可省略，`--chat` 的下一条消息沿用当前对话。模型连接可由 `agent-config` 保存，也可用本次 `--base-url`、`--model`、`--max-requests` 覆盖，覆盖不回写。`--ask-api-key` 从终端临时输入，不接受明文参数。Windows 的 `secret-set <name>` 保存命名 DPAPI 密钥；`agent-config --secret-name <name>` 引用它，`--clear-secret` 解除引用。

旧 `repair <Component逻辑名>`、自动 Default 重建及必填图片不再是当前契约。`pi-probe` 仍是独立的图片/受限读取检查，不使用连续修复宿主，不作为普通回归附带运行。

## 权限、上下文和日志

授权集合每轮固定，只允许修改选中的已有 Candidate 文件，包括候选 `manifest.json` 和 Recovery Rule。拒绝目录外路径、符号链接、新建、删除、`plan.json` 和未选中文件。修复入口不区分候选或文件是否校验失败；失败结果保留在上下文。完整候选仍由既有 Validator 检查，Publish 校验失败不发布。

pi 继续使用原有 read/edit 工厂、受限 Asset 工具、动作契约查询和 Validator RPC；不提供终端、通用写入、删除、发布或设置 Default 工具。Candidate Python 校验会导入模块，Validator 不是操作系统沙箱；生成代码的副作用约束不能被描述为进程隔离保证。

每个对话在数据目录 `agent-interactions/<UTC日期>/<UUID4>/` 下独立留存：

- `events.jsonl`：实际模型/工具/校验和逐轮结束事件；预检事件也在相应轮目录保留。
- `baseline/`：该对话首次处理时固定的候选物化基线。
- `round-N/input.json`、可选 `input.png`：用户消息、附件、授权集合、基础 Manifest UUID、实际 pi 版本、已验证版本、非密钥配置与提示词。
- `round-N/request-K.json`：实际模型请求；连接预检消耗计入同一轮额度。
- `round-N/original/`、`final/`、`cumulative.diff`、`result.json`：真实候选快照、相对固定基线的累计 Diff、请求次数及结束原因。
- `context.json`、`tool-N.json` 和图片：保留消息、图片及工具结果；工具序号跨轮递增，不覆盖旧产物。

每轮回收 pi 进程，下一轮通过 pi context hook 显式带入此前消息、图片和工具结果，不重写模型工具循环。最终回答、超限、服务错误或取消结束本轮，不自动续跑。最终 JSON 中 `revise_success` 是模型报告，不能代替 Validator、人工审阅或游戏验收。

Candidate 基线保存在工作目录的 `.candidate-baseline.json`，不进入 Candidate 或正式 Manifest。它保存初始化时的 UUID 和物化文件，跨 New Conversation、Default 变化和 Runner 选择不变；明确重建时才更新。源码内容标识仍是 SHA-256，Manifest 标识仍是 UUID。

## 验证与验收

普通回归默认跳过 Agent 测试：

```sh
QT_QPA_PLATFORM=offscreen uv run --frozen --extra gui --extra automation pytest -q
```

本需求的真实 pi + 本机 HTTP 替身检查必须显式运行：

```sh
QT_QPA_PLATFORM=offscreen uv run --frozen --extra gui --extra automation pytest \
  --run-agent-tests -q tests/test_component_repair_agent.py tests/test_pi_probe.py
```

真模型检查需另外提供 `LALC_REPAIR_TEST_BASE_URL`、`LALC_REPAIR_TEST_MODEL`，再显式选择 `test_real_model_repairs_fixed_pure_case` 或 `test_real_model_inspects_assets_and_actions`。Windows 实际认证另需 `LALC_REPAIR_TEST_SECRET_NAME`，选择 `test_windows_saved_dpapi_secret_authenticates_real_model`；实时截图/重复裁剪需 `LALC_REPAIR_TEST_REGION`，选择 `test_windows_real_model_captures_and_reuses_crop`。这些测试均使用测试自有 Candidate/数据目录，缺少环境时跳过，不报告通过。

Windows GUI 仍须人工核对跨 DPI、窗口移动/尺寸变化、客户区外、窗口失效后手动刷新、焦点、框选像素和真实保存内容，以及 DPAPI 的 GUI 设置/清除、实际认证、Runner/Agent/手工截图互斥和关闭清理。offscreen 和平台替身不替代这些证据。#329 仍需完成 #328 真实案例的游戏前后对照。

历史 #325–#327 的单目标 CLI、Mac Gemma4 纯计算修复、Asset 工具与 Windows 原生 DPAPI 验证证据保留于 [实施切片](stage-3-implementation-slices.md)。其中已记录的 Windows DPAPI `1 passed in 2.43s` 只证明当时的原生存取及损坏密文检查；早期真模型结果不能代替本次多文件连续修复和 GUI 验收。
