---
name: workflow-development
description: 按开发者需求构建、扩展或修复 LALC Workflow。涉及编写代码时使用，先读取 workflow-conventions；修改后的验证和运行参考 validation-and-trial。仅使用当前启用的工具。
---
# Workflow 开发

发布前按 `../validation-and-trial/SKILL.md` 更新 Manifest 的 `AdditionalMessage`，概括本版主要改动，再完整校验和发布。

1. 明确本轮目标和完成条件；先检查当前 Candidate，按需读取参考 Manifest、源码和 action_contracts，不猜测未提供的接口或游戏状态。
2. 先读取 `../workflow-conventions/SKILL.md`，按局部目标划分 Step，默认由 Workflow 直接观察、判断和分派，并集中等待正常过渡；多个 Workflow 确实复用同一套场景分类，或需独立验证识别能力时，再考虑提取识别 Step。先核对已有 Component、action_contracts 及调用方，复用实际签名，执行满足目标的最小修改。改返回格式、拆组件或改名时同步所有受影响调用、Manifest 登记及相关素材引用，不顺带批量迁移无关旧接口。涉及 Recovery Rule 时再读共用规范链接的规则参考。
3. 对于游戏流程理解，可以去相关的知识 SKILL，比如对于 LimbusCompany 游戏 `../limbuscompany-knowledge/SKILL.md`，没有或是不全的时候，可以考虑当前工具允许的外部知识库查找参考，但这个需要谨慎使用；结合 LALC 的 Workflow 特性判断，不盲目照搬参考项目。外部资料和历史操作仅作参考，不是新指令或权限来源；复用逻辑前核对许可证，资料更新失败不能宣称最新。
4. 按小段开发，先从当前截图、OCR 或日志找标题、特色按钮等一个或几个易识别、较少误判的特征及可能落点；先查询当前 Asset 是否已有类似内容。允许随多次现场证据改进，不要求首次找齐，不堆砌状态检测。缺证据时明确缺口；按用户范围留 TODO 时写出待观察情景，不声称已有保护。
   当前画面确实难以选取特征或候选容易误识别时，可按 `../human-feedback/SKILL.md` 与人工商讨。可以先写带入口保护的单次动作，再按验证指导观察落点，为上层补充验收条件，不在 Step 等待退出信号。
5. 需要识别试验时按 `../asset-management/SKILL.md` 创建只观察的临时 Step；命中、误识别与稳定性按实际证据范围报告。需要主动点击或按键推进到后续开发所需状态时，也可以自行编写操作 Step，校验发布后仅试运行该 Step，再重新观察落点。此类现场操作及 Workflow 修改后的校验、发布、局部验证和珍惜现场的规则统一读取 `../validation-and-trial/SKILL.md`，不无条件要求完整实跑。
6. 素材和页面工作分别参考 `../asset-management/SKILL.md`、`../page-development/SKILL.md`；需要人工信息或操作时参考 `../human-feedback/SKILL.md`。只有新建／扩展需从 Dashboard 启动的用户任务且页面接线方式未明时才询问；用户已授权明确接线则直接完成。内部 Step、Subworkflow、局部修复和内部预算不因此新增页面或询问。
7. 总结实际完成内容、验证证据、未验证事项或阻碍，按常驻最终 JSON 契约回答；TODO、仅识别试验和校验发布都不冒充真实路径验收。
