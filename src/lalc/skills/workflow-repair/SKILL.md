---
name: workflow-repair
description: 定位和修复 LALC Workflow 或素材故障。有故障描述、日志或异常现场时使用；修改 Workflow 前读取 workflow-conventions，验证和运行参考 publish-and-trial。
---
# 故障修复

发布前按 `../publish-and-trial/SKILL.md` 更新 Manifest 的 `AdditionalMessage`，概括本版修复及主要变更，再完整校验和发布。

1. 根据用户描述、已有日志和当前 Candidate 确认故障；需要现场证据时再截图，不根据旧截图猜测当前状态。
2. 读取相关源码和动作契约，定位有证据支持的原因；证据不足时明确缺少的信息，避免无依据的大范围改写。
   相关日志出现恢复介入时，结合故障现场检查是否误触发，读取 `../workflow-conventions/references/recovery-rules.md`；不要默认既有规则正确。正常加载在局部超时后可能已经结束，零规则匹配不能证明业务仍有故障或已完成。
3. 修改前读取 `../workflow-conventions/SKILL.md`，检查动作入口保护、Workflow 验收分派、正常过渡与两个循环上限，以及 Plan 是否保留 Task 完整结果。改签名、返回值或拆组件前检查所有调用方与 Manifest 登记，保留原有接口验证和异常，不把真正错误转换成正常返回。
4. 对原因做最小修复。素材问题读取 `../asset-management/SKILL.md`；人工信息不足时参考 `../human-feedback/SKILL.md`。
5. 校验、发布及试运行统一读取 `../publish-and-trial/SKILL.md`；利用已有现场、日志和截图按影响范围验证，不为重复试跑擅自复位。识别证据不足时允许渐进补特征或记录用户要求的 TODO，不堆叠猜测检测。
6. 按验证指导区分实际修改与证据，依最终 JSON 契约报告；未解决的入口保护 TODO 仍是缺口，校验通过不等于游戏故障已修复，仅分析不强制修改。
