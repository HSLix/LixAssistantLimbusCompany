## Parent

Spec #323；原 Stage 3 跟踪 #312。已确认步骤 5/6。

## What to build

准备一个真实游戏中的可重复失败案例，确定只需修改一个现有 Component，保存原始版本、初始截图、异常、输入、复现步骤和预期行为，为最终前后对照提供固定基线。

## Acceptance criteria

- [ ] 不是单纯语法错误；原始 Component 在既定前置状态下能够重复表现行为缺陷。
- [ ] 缺陷种子、所需资源和人工准备游戏状态的方法被保存，不依赖已清空的 Developer Candidate。
- [ ] 确定人工如何观察修复成功，以及如何安全重建前置状态；不实现游戏状态模拟或离线行为判定工具。
- [ ] 由开发者选择并提供案例，作为最终 demo 的外部输入；不阻塞前四项的工具开发与接入验证。

## Blocked by

None — can start immediately.
