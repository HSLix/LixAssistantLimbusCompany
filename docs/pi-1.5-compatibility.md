# pi 1.5.0 接入兼容记录

2026-11-06，按开发者要求将正式 Agent 接入及 Windows 构建资源基线从 1.4.0 升至 1.5.0。SOP／Skills 迁移不属于此次改动。

## 变化与边界

- `src/lalc/pi_probe.py` 更新已验证版本；非基线版本仍只警告，不硬性拒绝。
- `scripts/build_windows.py`、部署说明、资源来源声明与测试归档更新为官方 1.5.0。版本相关错误和下载 URL 使用现有版本常量，避免残留旧版提示。
- 官方 Windows x64 ZIP 的 SHA-256 为 `12d58a70e80b16ba9f764950b7a42bdeb07959495c0db68396cf2988c0b71af3`，已与 GitHub Release 资产摘要及官方 `SHA256SUMS` 核对，并以实际归档执行现有 `check_pi()`，验证版本、`pi.exe` 及安全路径。本地忽略的 `pi_resources/pi-windows-x64.zip` 已替换为该归档。
- 1.5.0 更换工具参数校验器；当前扩展未使用不再支持的 TypeBox 专有细化／编解码功能，保留现有 Type 导入和工具实现。新增测试通过真实 pi 验证缺字段、错误类型、数值下限及枚举错误回到模型，且不创建页面草稿。
- 新增长源码分段传输用例：含中文、引号和反斜杠的约 23 万字符页面源码，经 128 字符一段的工具参数流完整保存，逐字节核对。该测试验证正确性，不提供性能提升比例。
- 继续隔离个人配置，不启用通用终端、Skill 自动发现、自动压缩或内部重试；权限、请求额度、格式纠正及宿主级进程复用契约不变。

上游依据：[1.5.0 发布记录](https://github.com/earendil-works/pi/releases/tag/v1.5.0)、[工具参数校验说明](https://github.com/earendil-works/pi/blob/v1.5.0/packages/coding-agent/docs/extensions.md#tool-parameter-schemas-and-typebox)。

## 验证

使用开发者升级后的全局 `pi --version`，实际输出 `1.5.0`；临时安装未用于 Agent 回归且已移除。默认回归与 Agent 回归串行运行。

默认回归：

```sh
QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest -q
```

结果：923 passed、103 skipped、2 failed，进程正常返回失败码。两项失败均在已有未提交的 `tests/test_example_workflow.py::test_exp_mirror_pages_feed_plan_and_shared_actions`：工作区已删除 `example/workflow/exp.py` 并移除 Plan 的 exp 调度，但该测试仍读取 exp.py 并期待三个 Task 结果。与 pi 升级无关，未在此次改动中修复；不能报告全量回归通过。

Agent 接入检查仅使用真实 pi 和本机 HTTP 替身，不访问真实模型或操作游戏：

```sh
QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest --run-agent-tests -q \
  tests/test_agent_repair_agent.py tests/test_developer_session_agent.py tests/test_external_search_agent.py \
  -k 'not real_model and not windows_saved and not windows_real and not real_codesearch'
```

首次结果：86 passed、2 failed、5 deselected。两项失败均为 `test_actual_gui_page_install_returns_to_agent` 的旧断言：测试要求安装后无模态窗口，但现行流程已在本轮清理后显示 `PageInstalledDialog`。实际页面安装、Agent 同轮继续、最终状态和工具结果均已通过断言。按现行流程修正测试，检查清理后出现安装提示、取消提示且无自动重启；未修改生产 GUI 或 pi 扩展。

修正后仅复测失败的两个参数化用例：

```sh
QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest --run-agent-tests -q \
  tests/test_developer_session_agent.py -k actual_gui_page_install_returns_to_agent
```

结果：2 passed、40 deselected。两次检查合计覆盖 88 个通过用例，包括新增的长源码分段传输、四类无效参数、GUI／CLI 权限、原图、DeepSeek 推理上下文、格式纠正、续聊恢复、请求额度、错误／取消及 pi 进程复用。5 个真实模型／Windows／codesearch 用例在首次命令中明确排除，不计为通过；未重跑完整 Agent 集合。

运行及 Windows 构建版本一致性、实际本地官方归档校验，以及工作区与暂存区 `git diff --check` 均通过。

未运行 Windows 原生构建／成品、真实模型或真实游戏验收；未测量 LALC 的实际速度和内存改善。
