# 单 Component 修复（#325、#326、#327）

`lalc repair` 从 Default Manifest 固定一个已有 Task Workflow、Subworkflow 或 Step，通过 pi 0.86.1 的受限 `read`、`edit` 和 LALC `validate` 工具修订。需要已有 Default；不自动创建案例、运行候选、Publish 或更改 Default。

**有效启动会替换当前工作目录的整个 `candidate/`，包括未发布草稿。** Default 加载失败、目标不存在或不属于上述角色时保留旧草稿，不改选其他历史 Manifest。服务、版本及输入检查失败也不会重建草稿。完整基线先在临时目录物化成功，再替换候选；原有 `lalc init` 仍拒绝覆盖非空草稿。

## 运行

```sh
uv run --frozen lalc repair steps.your_step \
  --problem '复现步骤、观察到的问题以及预期行为' \
  --exception '实际异常或 traceback；没有时可省略此参数' \
  --image /absolute/path/to/screenshot.png \
  --base-url http://localhost:12138/v1 --model YOUR_MODEL_ID
```

可用 `--model` 指定模型、`--pi` 指定固定版本二进制；默认沿用当前保存设置，合并后没有模型就禁止启动，不再自动寻找 Gemma4。地址必须是完整 API 基础路径，不自动追加 `/v1`；例如自定义 `/custom/api` 就直接访问 `/custom/api/models` 和 `/custom/api/chat/completions`。不自动切换服务、加载模型或更换模型。

`--max-requests` 默认 20，可保存或在本次覆盖，必须至少为 2。它计算一次 `lalc repair` 从启动到退出的全部实际模型请求，包括启动图片检查、工具反馈和格式纠正，不是交互分组数或 Plan 周期。请求上限为 2 时，图片检查成功后还剩 1 次修复请求。

## 当前连接设置与命名密钥

一套当前设置保存在 `lalc data-dir` 对应目录的 `agent-settings.json`，不随源码工作目录切换，不提供多套配置档案：

```sh
uv run --frozen lalc agent-config --base-url http://localhost:12138/v1 --model YOUR_MODEL_ID --max-requests 20
uv run --frozen lalc agent-config
```

传入字段只更新这些字段；不传字段时只查看。修复命令的 `--base-url`、`--model`、`--max-requests` 和 `--secret-name` 临时覆盖保存值，不回写。未保存请求上限时为 20，未保存地址时为 `http://localhost:12138/v1`；模型无自动选择或缺省值。非法配置报错，不静默重置。

Windows 使用当前用户 DPAPI 独立保存命名密钥，密文位于 `secrets/`；普通设置仅保存名称。名称可以供其他密钥用途复用，本阶段只接入模型认证：

```powershell
uv run --frozen lalc secret-set llama-service
uv run --frozen lalc agent-config --secret-name llama-service
```

`secret-set` 通过终端隐藏输入，写入同名密钥时原子替换密文；不提供明文参数或回显。引用不存在或解密失败时报错结束。`agent-config --clear-secret` 清除当前连接的引用，保留已存密文。密文不支持跨机器/用户迁移。

Mac 不保存密钥，使用 `repair ... --ask-api-key` 临时输入。该选项在 Windows 同样可覆盖本次认证，包括留空以连接无认证服务，不修改保存的密钥。没有引用也没有临时输入时使用无密钥连接；需要认证的服务在预检时报错。密钥不写入 pi 配置、普通设置、命令行参数、模型上下文或交互日志。

## 启动检查

先固定 Default、目标及有效连接设置，检查输入、服务、模型及 pi 版本。服务提供模型状态时必须是 `loaded`；`unloaded`、`loading` 等状态与图片不支持分别报告，不发送加载请求。单模型服务没有状态字段时，以实际图片请求验证可用性。

随后通过 pi 0.86.1 发送初始截图，执行一次无工具的图片描述请求；它不开放候选读取、编辑或其他修复工具。请求成功后才重建候选并进入修复。失败或取消时保留旧草稿，在独立交互日志记录有效非密钥配置、检查请求、响应、已用次数和结束原因。日志的第 0 组表示启动检查，不是修复交互组；预检失败没有新的最终候选文件。启动成功时，完整原始/最终产物仍按下文留存。

模型可读取全部候选文件，只能编辑指定源码；候选 Manifest、其他源码、正式源码及已有素材/标签不可写。新增素材仅通过专用 `crop_asset` 工具。终端、通用 write 和个人 pi 扩展/配置不开放。`validate` 由 Python 宿主调用现有 `ManifestManager.validate()`，通过 pi RPC 的请求/响应通道把实际反馈返回模型，没有人工追问。

Validator 会导入候选 Python；这些工具边界不构成操作系统安全沙箱。启动时仍需提供初始 PNG 和文字材料，模型可按需调用以下工具：

| 工具 | 参数与结果 |
| --- | --- |
| `asset_tree` | 无参数，返回共享库的逻辑名文字树。 |
| `asset_directory` | `logical_name`：完整逻辑名；返回全部文件名与原始标签内容，缺失明确报告、不自动补写。 |
| `asset_images` | `images: [{logical_name, sha256}, ...]`；必须完整哈希，返回逐张标识的实际图片。先校验全批次，任一失败整次失败。 |
| `action_contracts` | 无参数，从实际注册表、签名及 docstring 派生全部动作契约，不提供实现源码或执行能力。 |
| `game_screenshot` | 无参数，每次恢复并置前唯一游戏窗口后重新截图，返回实际图片与客户区尺寸。 |
| `crop_asset` | `logical_name`、`region: {x, y, width, height}`（客户区像素）、可选 `tags`；重新截图后裁剪，返回图片、完整哈希、标签、来源及 `existed`。 |

同名同哈希裁剪保留原图及旧标签；新哈希加入共享库，未给标签明确存 `[]`，无需 Publish。失败、取消或拒绝不会删除新增产物。开发者 `crop-asset` / `tag-asset` 仍替换标签。每次截图和裁剪都可恢复、置前游戏窗口，聚焦等待可取消；工具不自动重试，错误返回后由 Agent 决定是否再次调用。不支持的平台明确返回实时工具不可用，Mac 可正常使用四个只读工具。

## 分组、结果与留存

从发起交互到模型给出最终回答为一组，期间可有多次模型请求、编辑和校验。最终回答必须是 JSON，例如：

```json
{"revise_success": true, "message": "已修改目标文件并通过工具校验，请人工审阅。"}
```

改不了则用 `false` 并说明原因或缺少的材料，结束本次调用。不是合法 JSON、布尔字段缺失/类型错误或说明缺失时，将格式错误反馈给模型纠正，仍计入请求上限。

每组按模型最终回答记录判断，后续实际校验不回头改写该判断。声称完成后，LALC 再次校验最终文件；失败则把错误反馈给模型开始下一组，仍属于同一次 CLI 调用、共用请求上限。输出中的 `completed / validated_candidate` 只表示模型报告完成且最终候选通过契约校验，游戏行为是否修复仍需人工验证。模型报告改不了时也独立记录候选校验结果，不把校验通过转成修复成功。

超限、服务错误或 Ctrl+C 后停止，不自动重启；保留候选和已有记录。退出码：校验完成为 0，未完成/错误为 1，取消为 130。取消后不再导入候选进行校验。

终端显示 `Agent Interaction Log` 路径及最终结果。日志位于 `lalc data-dir` 所示目录的 `agent-interactions/<UTC 日期>/<UUID4>/`，包含：

- `input.json`、`input.png`、`original.py`：实际非密钥配置、提示、截图和固定源码基线。
- `request-N.json`：发送给模型的完整请求载荷，含实际图片；RPC 只传文件引用，避免大图与协议输出交错。
- `events.jsonl`：按时间及组编号保存模型消息、工具参数/结果、校验反馈、格式错误和结束原因；不重复存储逐 token 增量。
- `tool-N.json`、`tool-N-image-M.png`、`tool-N-screenshot.png`：专用工具的实际返回、逐张图片与裁剪前的完整截图；裁剪来源关联本次交互和完整截图。图片实际回传模型，不仅返回本机路径。
- `group-N.py/.diff`：每组结束时的实际源码与相对基线的 Diff。
- `final.py`、`final.diff`、`result.json`：最终产物、实际校验结果、模型请求数和整次调用结束原因。错误/取消时校验未执行会明确标记。

日志独立于 `candidate/`，后续修复重建候选不会删除前次日志。人工审阅后沿用 `lalc publish`，再单独决定是否设置 Default。

## 可重复检查模型是否真的改对文件

固定种子在 `tests/fixtures/component-repair/`：`steps.total` 错误地忽略负数，相邻 Component 应保持不变。每次测试在独立临时目录发布同一原始版本、设置测试专用 Default，再走实际修复 CLI；不会使用或更改项目当前的 Default 与草稿。

模型不知道测试断言。测试检查真实文件与 Diff、Validator 结果，并只对这个测试自有的纯计算样例运行空列表、负数和混合整数的输入输出断言；这不是生产修复命令的执行能力，也不是游戏状态模拟。

固定 HTTP 响应配合真实 pi 检查编辑边界、校验失败后继续、最终 JSON 分组、超限、错误、取消和日志保留：

```sh
UV_CACHE_DIR=.generated/uv-cache uv run --frozen pytest --run-agent-tests -q \
  tests/test_component_repair.py tests/test_component_repair_agent.py tests/test_pi_probe.py tests/test_cli.py
```

显式连接真实模型重跑同一个案例：

```sh
LALC_REPAIR_TEST_BASE_URL=http://localhost:12138/v1 \
LALC_REPAIR_TEST_MODEL=YOUR_MODEL_ID \
UV_CACHE_DIR=.generated/uv-cache uv run --frozen pytest --run-agent-tests -q -s \
  tests/test_component_repair_agent.py::test_real_model_repairs_fixed_pure_case
```

必须设置 `LALC_REPAIR_TEST_MODEL` 显式指定已加载模型。此测试使用无认证的本地开发服务，不读取持久密钥。每次都会重新创建缺陷，不以此前模型输出作为下次基线；模型请求和结果可能不同，断言不变。测试打印证据目录；pytest 临时目录受其自身保留策略管理，需要长期保存时复制该目录，或给每次运行指定不同的 `--basetemp`。

上述 Agent 测试默认跳过，不因安装了 pi 而运行；普通全量回归不加 `--run-agent-tests`。固定响应测试不证明模型能力；真模型纯计算案例也不替代 #328/#329 的真实游戏缺陷和 Windows 前后对照。

## #326 工具验收

无需 pi 的工具权限与素材检查：

```sh
UV_CACHE_DIR=.generated/uv-cache uv run --frozen --extra automation pytest -q tests/test_repair_tools.py
```

真实 pi 配合 HTTP/窗口替身检查多图实际传输、现场工具路由与聚焦等待取消：

```sh
UV_CACHE_DIR=.generated/uv-cache uv run --frozen --extra automation pytest --run-agent-tests -q \
  tests/test_component_repair_agent.py tests/test_pi_probe.py
```

Mac 真模型只读验收会准备独立素材库，让模型读取两个逻辑名、在同一次调用查看红/蓝两张图、查询动作契约并尝试越界读取；检查真实请求中的图片及原文件不变：

```sh
LALC_REPAIR_TEST_BASE_URL=http://localhost:12138/v1 \
LALC_REPAIR_TEST_MODEL=YOUR_MODEL_ID \
UV_CACHE_DIR=.generated/uv-cache uv run --frozen --extra automation pytest --run-agent-tests -q -s \
  tests/test_component_repair_agent.py::test_real_model_inspects_assets_and_actions
```

2026-10-23 Mac Gemma4 实测通过，6 次请求、1 组交互，实际读取多图并正确报告红、蓝，越界路径被拒绝，素材、正式源码、Manifest 和 Default 均不变。证据留存于本次工作区的 `.generated/issue-326-real-model/`，不随普通测试自动清理；其有效性不代表 Windows 实机通过。

Windows 实机工具验收需先打开唯一游戏窗口，准备静止画面，选择一个两次截图间像素保持一致的客户区区域。PowerShell 示例（区域值应按实际画面填写）：

```powershell
$env:LALC_REPAIR_TEST_BASE_URL = 'http://localhost:12138/v1'
$env:LALC_REPAIR_TEST_MODEL = 'YOUR_MODEL_ID'
$env:LALC_REPAIR_TEST_CROP_REGION = '{"x":0,"y":0,"width":64,"height":64}'
uv run --frozen --extra automation pytest --run-agent-tests -q -s tests/test_component_repair_agent.py::test_windows_real_model_captures_and_reuses_crop
```

测试仍走公开修复 CLI 和真实 pi/模型，只使用测试自己的数据目录。核对新截图、首次裁剪与再次请求不同标签时的复用、旧标签及原基线不变，保留完整截图、裁剪来源和交互。此检查不在 Mac 或普通回归中运行；游戏状态变化导致重复裁剪内容不同，不能作为旧标签保护已通过的证据。当前 Windows 实机检查尚未执行；开发者确认 #326 按实现与测试结果关闭，后续结合 #328 准备的真实样例在 #329 中综合验收。

## #327 配置与认证验收

普通配置/密钥边界测试和完整非 Agent 回归不调用模型：

```sh
QT_QPA_PLATFORM=offscreen UV_CACHE_DIR=.generated/uv-cache uv run --frozen --extra automation pytest -q
```

真实 pi + HTTP 替身集成检查包括保存值/单次覆盖、自定义完整 API 路径、无模型、上限小于 2、未加载与图片不支持的区分、启动图片请求、共用上限、失败保留草稿、取消和密钥脱敏：

```sh
UV_CACHE_DIR=.generated/uv-cache uv run --frozen --extra automation pytest --run-agent-tests -q tests/test_component_repair_agent.py tests/test_pi_probe.py
```

Windows 首先执行原生 DPAPI 存取与损坏密文检查；该测试在其他平台跳过：

```powershell
uv run --frozen pytest -q tests/test_agent_settings.py::test_windows_native_dpapi_roundtrip_and_corruption
```

实际认证需要一个拒绝匿名访问、已加载图片模型的 llama.cpp 服务。先以 `secret-set` 保存真正服务密钥，然后设置非密钥的测试连接与名称：

```powershell
$env:LALC_REPAIR_TEST_BASE_URL = 'https://YOUR_SERVER/v1'
$env:LALC_REPAIR_TEST_MODEL = 'YOUR_MODEL_ID'
$env:LALC_REPAIR_TEST_SECRET_NAME = 'llama-service'
uv run --frozen --extra automation pytest --run-agent-tests -q -s tests/test_component_repair_agent.py::test_windows_saved_dpapi_secret_authenticates_real_model
```

测试先确认匿名认证失败，再把已有 DPAPI 密文复制到测试自有数据目录，以保存设置运行公开修复 CLI，核对实际修复结果和明文不落盘，打印独立证据目录；不修改开发者原密文、Default 或草稿。若服务允许匿名访问，该测试不能通过，避免将无认证服务当成实际认证证据。

2026-10-23：本次配置实现的 Mac 自动化与真实 pi/HTTP 替身结果见步骤 4。默认本地服务实查返回模型 `unloaded`，按约定不主动加载，因此本轮未执行真模型图片/修复验收。早先 #325/#326 的真模型证据不能代替新启动流程复测；Windows 原生 DPAPI 与实际认证均仍待执行，#327 未达到全部验收条件。
