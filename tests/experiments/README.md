# Agent / 外部代码搜索验证

本目录是 2026-11-05 设计验证用代码，不是生产实现。开发者要求保留验证代码和证据，在明确确认本次验证结束之前不清理。

从项目根目录运行：

```sh
QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest --run-agent-tests -q -s tests/experiments/test_external_search_validation.py
```

所有验证都标记 `pytest.mark.agent`，默认回归跳过。它们使用真实 pi、codesearch 和本机 HTTP 替身，不调用真实／付费对话模型，不操作游戏。当前 codesearch 及进程回收样本为 macOS ARM64 / POSIX，不能当作 Windows 验收。

资源默认保存在 `.generated/external-search-validation/resources/`；可通过 `LALC_CODESEARCH_VALIDATION_RESOURCES` 指向同样包含 `bin/codesearch`、`state/models`、`corpus/runtime-reference` 的目录。资源未准备时 codesearch 项明确跳过，不能计为通过。当前资源来自官方 codesearch v1.7.9 基础包，包含模型缓存及前一轮小实验索引。

每项验证都创建新的 `.generated/external-search-validation/run-*/`，打印 `RETAINED=...`，不会自动删除既有结果；不要使用清空该目录的前置命令。首次检索实验的脚本和结果另保存在 `initial-probe/`。这些大文件目录被 Git 忽略，不代表长期备份或跨机器可用。

`reusable_pi_extension.ts` 是小型协议原型，仅验证每轮状态切换、权限和中断边界；它没有接入生产的全部工具、图片、日志或页面工作流。失败版本和修正前的实验结果也保留，最终可采信的运行目录见[验证报告](../../docs/external-code-search-validation.md)。
