# 分享会话工具错误与图片索引中断排查

2026-11-13，依据用户提供的 `lalc-sharing/objects/0/log/`，只将内容作为诊断证据。

## 日志结论

- Round 2 于当地时间 19:37:30 调用 `page_resource`，将 Asset 目录 `ui/team_tab` 作为文件传入。`FileContent.from_path` 拒绝目录，返回「资源必须是普通文件。」；19:37:37 的 `tool_execution_end` 明确为 `isError=true`。19:37:39 Agent 改用目录下具体哈希 PNG 路径，继续预览安装页面；本轮 result 为 `completed/answered`。工具错误已反馈给 Agent，没有中断该轮。
- 实际中断发生于 Round 1：19:35:20 最后的 `preview_crop` 以 `isError=false` 返回图片；紧接着图片工具结果的 `message_end`，19:35:20.977 出现 `lalc_context_error: JSON Parse error: Unexpected EOF`。最终显示 `provider_error / The operation was aborted.`，这一表层信息掩盖了更早的上下文错误。
- `pi_context.ts` 的 `turn_end` 会读取并解析图片索引；异常分支记录 `lalc_context_error` 并 abort。Python 在记录含图片事件时直接 `write_text` 覆盖同一索引文件，存在截断到完整写入之间被 pi 读取的竞争。时序与错误吻合；日志没有读取时的文件快照，故属于高度可信的原因分析，不能声称真实 Windows 原故障已经复现。
- 日志另有 `ERR_INVALID_STATE / Controller is already closed` 传输错误；多次出现后 Agent 仍继续执行。未据此认定它们是本次中断的直接原因。

## 修复与验证

`RepairLog.write_image_index` 复用 `work_file` 创建普通待提交文件，关闭完整写入的文件后同盘原子替换索引；初始化和图片事件更新共用此路径。不把内部状态损坏伪装成 Agent 工具参数错误，不改变既有工具错误反馈或权限校验。

新增测试在替换时检查旧索引仍是完整 JSON、新索引已经完整，并核对最终发布及工作文件清理。

执行 `.venv/bin/python -m pytest -q tests/test_agent_context.py tests/test_repair_tools.py tests/test_agent_repair.py`：55 passed。

未运行真实 pi／模型、Windows 或游戏验收，也未处理独立的传输错误或改造中断诊断展示。
