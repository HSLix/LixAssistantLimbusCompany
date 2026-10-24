# Agent Repair 错误呈现待修事项

2026-10-24，开发者明确要求：宿主报错必须以“错误”形式呈现，不能伪装为 Agent 对话回复，并且必须能查看详情。状态：本机实现及自动化回归完成；Windows 与真实模型验收单列，尚未执行。

## 已确认的问题与边界

- `RepairPage.answered()` 将 `result.error` 与模型最终回答一起显示为 `Agent：…`。缺少模型配置、获取模型列表 HTTP 502 等均发生在宿主启动检查，不是模型回复；不得合成 Agent 回复。
- `RepairConversation.run()` 每轮调用 `effective_settings()` 读取已保存配置；设置生效不需要 New Conversation。New Conversation 不作为网络错误的修复步骤，也不清空 Candidate。
- `_models()` 将 HTTPError 压成状态码摘要，并用 `from None` 丢弃原始异常链，也未保留响应正文。当前交互日志虽有 `repair_error` 和 traceback，仍不足以定位 502 的具体来源。
- 本次出错 GUI 运行于另一台 Windows，模型服务在 Mac 的 `100.85.237.51:39678`，需要认证。Mac 的成功请求不能替代 Windows 客户端验证。先前 `localhost:12138` 属于另一个服务。
- Windows 对比结果为继承代理 HTTP 502、明确直连超时；开发者随后确认 Windows 未启动 Tailscale，启动后已能访问模型列表并收到 unloaded 提示。不能由此前的 502 单独推断模型服务内部失败。

## 本轮明确的 Settings 范围

开发者要求先适配 llama.cpp，未来按 provider 切换对应设置预设；本轮不接入 DeepSeek 等其他服务。

- 服务商选择按下拉单选理解，同一时刻使用一个 provider；当前只有 llama.cpp。预设不是每次刷新表单时覆盖用户自定义地址、模型或密钥。是否需要保存多套 provider 配置，留到第二个 provider 接入时明确，不提前实现。
- llama.cpp Settings 提供“测试连接”和“检查模型加载状态”。前者验证当前表单的完整 Base URL 和认证能否获取模型列表；后者检查指定精确模型 ID 是否存在、实际状态是什么。检查不发起推理、不加载或卸载模型，不修改 Candidate、不写入 AI 对话。
- 未保存的表单也可测试；测试不等于保存配置。结果关联本次测试的配置快照，修改地址、模型、provider 或密钥后旧结果不能继续显示为当前设置已通过。
- 区分连接/认证失败、模型不存在、unloaded、loading、loaded 和服务返回的其他状态；模型列表可读不等于模型推理可用，loaded 也不等于工具调用或图片能力验收通过。
- 诊断异步执行，避免界面卡住；不自动改用直连、切换模型、重试或加载模型。
- 现有配置没有 provider 字段，迁移时兼容为 llama.cpp，保留已有完整 API 路径、模型和凭据引用。CLI 本次不增加新的诊断界面，但共享配置读取不能因新增字段而损坏。
- Settings 诊断单独记录在应用数据目录，不能要求先开始 Repair 对话；提供“查看错误详情”“复制详情”“打开日志目录”。Repair 同样应能打开当前对话日志和重新查看本轮错误。

### 已确认的启动策略

开发者已明确确认允许 unloaded 状态继续发起正常 Agent 请求，由 router 的按需加载策略决定是否加载。启动不再以 loaded 状态作硬门槛；检查状态按钮仍如实显示 unloaded。状态查询不执行加载；应用不调用加载/卸载管理接口、不修改 router 参数。若服务端仍关闭自动加载，推理失败将作为模型预检错误留证，不自动重试。

## 当前实现与日志入口

- Settings 增加 Provider 下拉单选（仅 llama.cpp）、“测试连接”“检查模型加载状态”，使用当前表单与当前/待覆盖的凭据。旧配置只读兼容 provider 缺省值，不自动改写地址或凭据。
- 每次 Settings 检查独立保存在 `<数据目录>/agent-diagnostics/<UTC日期>/<UUID>/`，包括 `events.jsonl` 和 `result.json`。检查不保存配置、不创建 Repair 对话、不发起推理。编辑表单后测试结果失效；在途检查结束也不能覆盖新表单状态。
- Settings 与 Repair 均提供错误列表、“查看错误详情”“复制详情”“打开日志目录”和“打开应用日志目录”，允许关闭弹窗后重开错误详情。应用日志为 `<数据目录>/logs/lalc.log`。Repair 同一对话中保留已收集的错误，New Conversation 清空本页错误列表，旧证据目录不删除。
- Repair 失败结果含 `diagnostics`，保留阶段、完整 API 请求 URL、HTTP 状态与响应正文（最多读取 64 KiB）、原始异常链、模型配置、pi 版本、对话/轮次和日志路径。配置错误发生在读取实际 pi 版本之前时只记录已验证版本，不虚构实际版本。
- 已知密钥、认证字段和 Bearer 值在落盘、应用 ERROR 日志及 GUI 展示前统一脱敏。宿主异常不再追加为 Agent 发言；合法模型回答仍正常显示。工具/校验错误有独立可查看详情，不因此自动结束本轮或删除候选。
- CLI Repair 返回同一份脱敏诊断；pi-probe 失败也输出阶段与异常链。连接查询保留原代理行为，不增加直连回退。
- 最终回复严格限定为一个完整 JSON 对象，不接受说明文字或代码块；提示词要求所有说明放在 `message` 内，`revise_success` 为布尔值、`message` 为非空字符串。JSON 解析或字段校验失败时，将具体错误与格式要求反馈给同一 pi 会话，要求只重新生成最终回答，扩展同时禁用本轮剩余工具以避免重复修改。纠正请求与预检、工具循环共用本轮额度，不另设无限重试；合法回答结束本轮，额度耗尽以 `request_limit` 结束并保留最后的原文和详情。网络/认证/工具失败不适用这一格式纠正机制。
- 解析失败阶段为 `final_answer`，详情保留脱敏后的实际回复 `raw_text`、完整解析输入 `json_text`、行/列/偏移和原始异常链；字段校验失败保留实际解析值。GUI 以多行原文展示回复，格式纠正期间提示剩余请求数，并保留每次失败的详情入口。日志保存 `final_answer_retry`、具体错误、反馈消息与后续模型回答；纠正消息保留在连续对话上下文。历史日志不重写。
- 服务结束原因不得统称 `provider_error`：`stopReason=length` 为 `output_limit`，表示单次输出被截断，与本轮请求次数上限独立；详情保存实际 stop reason、usage、已用请求数/上限、文本与思考内容的长度，不把模型思考原文塞入错误摘要。只有显式请求计数拒绝或额度内格式纠正耗尽才为 `request_limit`。截断不作为 JSON 格式错误自动重试，也不自动调高输出上限；预检阶段同样保留这些证据。未知服务失败即使没有 errorMessage，也说明实际 stop reason，不能仅显示 `provider_error`。
- 单次输出上限仅支持 `output_limit = server_default`，Settings 显示唯一选项“使用服务端默认值”；旧配置缺省兼容，不提供自定义数值。移除应用固定 4096 的请求预算，并在 pi 的最终载荷回调中移除 `max_tokens`、`max_completion_tokens`、`max_output_tokens`，避免 SDK 根据模型元数据重新补入上限。预检、修复、格式纠正和 pi-probe 均沿用此规则；实际默认预算由服务决定，仍可能受服务配置限制而截断。本轮请求次数上限、取消和流式传输独立保留。

### 直接影响与验证

- `agent_settings.py`：provider 字段、旧配置兼容、校验与现有 CLI 设置覆盖语义；本轮只允许 llama.cpp。
- `developer_gui.py::SettingsPage`：provider 选择、对应预设、两项异步诊断、结果失效、诊断日志入口。
- `pi_probe.py::_models/configured_pi`：复用模型列表读取与诊断，保留完整失败证据；启动策略按最终确认更新，避免 GUI 和 Repair 各自解释 loaded。
- `agent_repair.py::RepairLog/RepairConversation` 与 `RepairPage`：沿用每对话/每轮证据，补足错误详情与日志入口；Settings 测试日志独立于对话。
- 复用已有 `gui.py::ErrorDialog` 与本地目录打开方式，统一脱敏后再向界面、应用日志及交互日志传递，不创建第二套聊天记录。
- 自动化覆盖旧配置迁移、provider 拒绝、表单测试不保存、状态分类、配置变更后旧结果失效、HTTP 正文及底层异常保留、密钥脱敏、日志重新打开，以及 Repair 错误不显示为 Agent 回复。真实 Windows 和模型加载/推理验收单列，不以 HTTP 替身测试替代。

## 开发者要求的呈现

1. 宿主配置、认证、服务连接、模型预检、pi 启动、工具执行、校验及取消清理等错误，使用明确的错误呈现；复用既有 ErrorDialog/原始错误详情能力，不伪装为 Agent 发言。
2. 主界面显示可读摘要、真实失败阶段，提供详情入口；详情可选择、复制，包含原始 traceback 和日志定位。窗口关闭后仍可重新查看本轮详情，不仅瞬时弹窗或聊天中的一行文字。
3. 网络详情保留实际请求 URL、HTTP 状态、经过脱敏的响应正文与底层原因；配置详情保留实际模型 ID、pi 版本、对话/轮次和证据目录。不能只显示“502”或空的 TimeoutError。
4. 明文 API Key、Authorization 值和其他认证信息不能出现在 GUI、可复制文本或日志中，复用现有脱敏机制。
5. 错误应以 ERROR 级别进入应用日志，并保留交互事件的原始诊断；模型的合法“无法完成/信息不足”回答仍是模型回复，不与宿主异常混为一类。
6. 错误后保留 Candidate、已有对话、修改、日志和 Diff；不自动清空、重建或切换连接。仅最终回复格式错误按上述规则在本轮额度内自动反馈纠正，网络和执行错误不自动重试。

## 影响范围与验收

- `pi_probe.py::_models`：保留可检查的 HTTP/连接失败证据与异常原因，不泄露认证值。
- `agent_repair.py::RepairConversation.run` / `RepairLog`：传递同一份可读错误与详细诊断，保存本轮原始证据。
- `developer_gui.py::RepairPage.answered/show_event`、`gui.py::ErrorDialog`：宿主错误与模型回答分别呈现，提供可重新查看/复制的详情。
- CLI 同样输出准确阶段和非空详情，错误不标成模型答复；GUI/CLI 不各自猜测网络失败原因。
- 测试覆盖未配置 Model、401/403、502（含响应正文）、连接拒绝/超时、pi 启动错误、取消清理错误、密钥脱敏和错误后保留数据；确认修改已保存设置后下一轮立即使用，无需新对话。
- 代理处理先依据 Windows 实测确认，不在缺少证据时全局禁用代理或为所有服务添加自动回退。

## 2026-10-24 验证记录

- 服务端默认输出预算：普通回归 **293 passed, 29 skipped**；显式选择 `--run-agent-tests tests/test_agent_repair_agent.py tests/test_pi_probe.py` 为 **24 passed, 4 skipped**。HTTP 替身检查真实 pi 发出的请求，验证预检、正常修复、格式纠正及图片 probe 均无输出 token 上限参数；配置兼容、唯一 Settings 选项和非默认值拒绝检查通过。未重新调用真实模型，真实模型及 Windows 验收仍单列。

- 输出截断分类修复：普通回归 **292 passed, 29 skipped**；显式执行 `--run-agent-tests tests/test_agent_repair_agent.py` 为 **16 passed, 4 skipped**。真实失败轮次离线重分类为 `output_limit`，实际 2/20 次请求、4096 输出 token、无最终文本。新增替身验收覆盖预检和正常 Agent 请求的 length 截断，确认不进入格式纠正循环；原请求额度与格式纠正测试继续通过。未改动单次输出上限或触发真实模型请求。

- 最终严格 JSON 与额度内格式纠正回归：普通回归同下述命令为 **290 passed, 27 skipped**；显式选择 `tests/test_agent_repair_agent.py tests/test_pi_probe.py` 为 **22 passed, 4 skipped**。验证代码块、普通文本及字段类型错误会携带具体错误反馈重新生成，纠正请求不携带工具，Candidate 不重复修改，纠正消息与失败原文进入历史和日志；额度为 2/3 时实际请求绝不超额。4 项真实模型/Windows 跳过原因不变。以下保留此前设置与诊断实现时的历史结果。

- 普通回归：`QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest -q -x -ra`，**282 passed, 22 skipped**。跳过项为 21 项需显式开启的 Agent 测试和 1 项 Windows 原生 DPAPI。
- 所选 Agent 回归：`QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest -q -x --run-agent-tests tests/test_agent_repair_agent.py tests/test_pi_probe.py -ra`，**17 passed, 4 skipped**。通过项使用真实 pi 与本机 HTTP 替身；跳过 2 项缺少显式连接配置的真实模型验收、1 项 Windows DPAPI 认证、1 项 Windows 游戏截图验收。
- 旧 unloaded 失败用例首次触发停止：它仍要求新契约已允许的请求失败。已替换为 unloaded 请求到达推理接口且不调用加载管理接口的用例，先单项通过，再完成上述所选 Agent 回归。
- Settings 已做 offscreen 截图检查；错误详情、脱敏复制、日志打开、未保存表单检查及在途结果失效由 GUI 自动化验证。未以 offscreen 结果冒充 Windows 原生窗口验收。
- 保留已关闭自动加载的 router 配置时，应用无法替服务端加载模型；应由开发者移除 `--no-models-autoload` 并重启 router，或在服务端手工加载。本次未修改服务配置，也未触发真实模型加载或推理。


## 2026-10-24 已确认修订

2026-10-24 修订：取消 selected files 设置及 CLI 文件参数/`--all`。Agent 每轮可尝试修改 Candidate 内全部已有文件（含候选 `manifest.json`、Recovery Rule），`plan.json` 始终只读；不开放新建、删除、重命名、符号链接、目录外或正式源码写入。宿主按轮开始时的已有文件冻结边界，工具检查与结束快照共同执行约束。文件是否被 Manifest 引用、是否通过校验均不决定编辑权限；临时测试文件不新增警告，不自动登记 Component，新增 Component 接口留待后续。手动 Validate 在已有对话中立即写入 `context.json` 和事件日志，成功/失败在聊天区各只显示一次，失败保留详情入口；尚无对话时不隐式创建对话。此规则覆盖首次发送前、发送后和 New Conversation 后。


## 2026-10-24 文件编辑与手动校验修订实施结果

- 已取消 GUI 文件多选/全选和 CLI 文件参数/`--all`，共享宿主每轮列出全部已有 Candidate 文件，`plan.json` 由工具和结束快照双重检查；Manifest、相邻 Component 和未登记的临时文件可在同轮编辑，未新增警告或自动登记。
- 手动 Validate 标记 `source=manual`，立即保存 `context.json`；GUI 仅由完成回调显示一次，失败详情和事件记录保留。覆盖首次发送前、已绑定 Agent 事件回调后及 New Conversation 后；没有对话时不隐式创建。
- 相关普通测试 **84 passed**；全量普通回归 `QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest -q -x -ra`：**303 passed, 29 skipped**（28 项 Agent 默认跳过、1 项 Windows 原生 DPAPI）。
- 显式 Agent 接入回归 `QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest -q -x --run-agent-tests tests/test_agent_repair_agent.py tests/test_pi_probe.py`：**24 passed, 4 skipped**。通过项使用真实 pi + 本机 HTTP 替身；2 项真模型、1 项 Windows DPAPI 认证、1 项 Windows 现场游戏截图未执行。
- `git diff --check` 通过。Windows 实机和真实模型/游戏验收未由这些检查代替，#330 保持打开。
