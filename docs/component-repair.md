# 单 Component 修复（#325）

`lalc repair` 从 Default Manifest 固定一个已有 Task Workflow、Subworkflow 或 Step，通过 pi 0.86.1 的受限 `read`、`edit` 和 LALC `validate` 工具修订。需要已有 Default；不自动创建案例、运行候选、Publish 或更改 Default。

**有效启动会替换当前工作目录的整个 `candidate/`，包括未发布草稿。** Default 加载失败、目标不存在或不属于上述角色时保留旧草稿，不改选其他历史 Manifest。服务、版本及输入检查失败也不会重建草稿。完整基线先在临时目录物化成功，再替换候选；原有 `lalc init` 仍拒绝覆盖非空草稿。

## 运行

```sh
uv run --frozen lalc repair steps.your_step \
  --problem '复现步骤、观察到的问题以及预期行为' \
  --exception '实际异常或 traceback；没有时可省略此参数' \
  --image /absolute/path/to/screenshot.png \
  --base-url http://localhost:12138
```

可用 `--model` 指定模型、`--pi` 指定固定版本二进制；默认从服务模型列表选择唯一的 Gemma4，要求服务声明支持图片，实际图片随请求发送。地址、模型和密钥传递沿用 #324，不自动切换服务或模型。`--ask-api-key` 在终端临时输入认证密钥，密钥只在内存中使用；不放进命令参数或 pi 持久配置。

`--max-requests` 默认 20，可在本次调用覆盖。它计算全部实际模型请求，包括工具反馈和格式纠正，不是交互分组数。持久设置属于 #327。

模型可读取全部候选文件，只能编辑指定源码；候选 Manifest、其他源码、正式源码和素材不可写。终端、通用 write 和个人 pi 扩展/配置不开放。`validate` 由 Python 宿主调用现有 `ManifestManager.validate()`，通过 pi RPC 的请求/响应通道把实际反馈返回模型，没有人工追问。

Validator 会导入候选 Python；这些工具边界不构成操作系统安全沙箱。#326 再增加素材、动作说明与实时游戏观察工具，本命令当前只接受初始 PNG 和文字材料。

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
LALC_REPAIR_TEST_BASE_URL=http://localhost:12138 \
UV_CACHE_DIR=.generated/uv-cache uv run --frozen pytest --run-agent-tests -q -s \
  tests/test_component_repair_agent.py::test_real_model_repairs_fixed_pure_case
```

可额外设置 `LALC_REPAIR_TEST_MODEL` 指定模型。此测试使用无认证的本地开发服务，不读取持久密钥。每次都会重新创建缺陷，不以此前模型输出作为下次基线；模型请求和结果可能不同，断言不变。测试打印证据目录；pytest 临时目录受其自身保留策略管理，需要长期保存时复制该目录，或给每次运行指定不同的 `--basetemp`。

上述 Agent 测试默认跳过，不因安装了 pi 而运行；普通全量回归不加 `--run-agent-tests`。固定响应测试不证明模型能力；真模型纯计算案例也不替代 #328/#329 的真实游戏缺陷和 Windows 前后对照。
