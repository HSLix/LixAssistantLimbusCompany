---
name: workflow-repair
description: 定位和修复 LALC Workflow 或素材故障。有故障描述、日志或异常现场时使用；修改 Workflow 前读取 workflow-conventions，验证和运行参考 validation-and-trial。
---
# 故障修复

1. 根据用户描述、已有日志和当前 Candidate 确认故障；需要现场证据时再截图，不根据旧截图猜测当前状态。
2. 读取相关源码和动作契约，定位有证据支持的原因；证据不足时明确缺少的信息，避免无依据的大范围改写。
   恢复规则误匹配也可能改变现场，导致业务步骤反复失败、修复无效；不要默认既有恢复规则一定正确。相关日志出现恢复介入时，结合故障现场考虑是否误触发。外观相似、主要靠文案区分的弹窗，建议优先用 OCR 匹配独特文案，避免共有背景或 Confirm 按钮主导模板匹配。
3. 涉及 Workflow 编写时先读取 `../workflow-conventions/SKILL.md`，检查 Step 的完成确认和恢复职责、动作与包装签名，以及 Plan 是否保留 Task 的完整成败信息。
4. 对原因做最小修复。素材问题读取 `../asset-management/SKILL.md`；人工信息不足时参考 `../human-feedback/SKILL.md`。
5. 修改 Workflow 后读取 `../validation-and-trial/SKILL.md`，执行完整 Validate，根据实际错误继续修正。按用户要求和验证需要决定是否运行；失败时根据日志继续定位，避免不改变依据地反复重试。用户停止后总结并等待新指示。
6. 分别说明已修改、静态校验、实际运行及仍未确认的部分，按最终 JSON 契约报告；校验通过不等于游戏故障已修复，仅分析不强制修改。
