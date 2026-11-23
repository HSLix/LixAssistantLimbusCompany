# User GUI 数据与清理影响评审

2026-11-22。依据 [ADR 0043](adr/0043-allow-user-cleanup-of-retained-data.md) 及首版页面讨论。评审阶段核对源码与现有测试，并提供静态界面预览。

## 页面与统计口径

垃圾桶入口位于 User GUI 的「通用设置」上方，进入「数据与清理」。运行日志和工作流版本支持按日期筛选、选中、预览及确认永久删除。组件和素材提供只读统计。运行日志详情复用现有「日志」页。[UserWindow](../src/lalc/gui.py#L548) · [RunLogPage](../src/lalc/run_log_gui.py#L208)

| 分类 | 展示与口径 |
| --- | --- |
| 运行日志 | 本机和导入分别显示。用 Run 开始时间转换为应用所在地日期，起止日期都包含；未知开始时间不进入日期批量选择。本机删除 Trace、同 Run 的工作版本状态文件及截图目录。导入按独立导入副本删除。 |
| 工作流版本 | 显示发布说明、发布日期、Default／最新保护状态、运行次数与最近使用。运行中作为初始或工作版本选择过的 Manifest 按 Run 去重，同一 Run 多次选中只计一次。预览列明会随版本删除的源码。 |
| 组件 | 列出逻辑名和源码版本、引用它的保留版本数、调用次数与最近使用。按逻辑名和完整 Component ID 统计一次实际开始的调用。恢复规则的检测及恢复都可从各自的调用开始事件统计；Step 前置条件有独立事件。 |
| 素材 | 按逻辑名显示图片数量、占用和最近命中。最近命中来自现有素材使用索引。该索引仅保留最新有命中结果，首版没有可跨清理的累计素材命中数。 |

覆盖范围为当前保留的本机 Trace 加已保存的运行使用摘要。导入日志可查看和清理，使用统计排除导入副本。历史缺失或不可读应显示覆盖限制。现有的 Workflow Ledger 继续用于 Workflow 健康、耗时和恢复统计。

## 已确认的实现影响

1. **Manifest 清理需要在存储层保护相互竞争的写入。** 发布先存源码再提交 Manifest，Workflow 导入独立走相同顺序，CLI 也可直接切换 Default。单靠 User GUI 的忙碌状态无法挡住这些入口。应让发布、导入、Default 切换与清理共用按数据目录的跨进程互斥；检查 Run 持有游戏锁的范围和取锁顺序。当前启动先加载 Manifest 再取得游戏锁，清理和启动之间要避免凭过期加载结果建立 Run。测试要覆盖预览后 Default 切换、同哈希被新发布引用，以及两个进程的冲突。 [ManifestManager](../src/lalc/manifest.py#L147) · [Workflow 导入](../src/lalc/workflow_sharing.py#L87) · [CLI](../src/lalc/__main__.py#L283) · [Run 启动](../src/lalc/application.py#L213)
2. **清理预览必须计算完整的引用差集。** 只从本次选中 Manifest 的组件和恢复规则取候选，减去全部保留 Manifest 的引用。未被本次删除影响的旧无引用源码不纳入。普通版本列表会跳过某些损坏或不支持的文件，不能直接当作完整引用扫描。任何保留 Manifest 的引用无法可靠判定时，应拒绝相关清理并说明原因。利用纯数据读取，避免在打开页面或预览时导入 Python。 [版本列表](../src/lalc/manifest.py#L284) · [ManifestReference](../src/lalc/manifest_reference.py#L32)
3. **运行使用摘要与详细日志有不同的生命周期。** Trace 的启动、版本切换及调用开始事件分别提供版本和组件事实，Workflow Ledger 只覆盖部分角色。清理本机详细日志时先落盘每个 Run 的使用摘要。按本机 Run ID 只汇总一份，重试或回滚时摘要与 Trace 并存也不会重复。无法可靠生成摘要的 Run 应保留日志并报告原因。保持 Run 序号单调，不将导入副本及其数字 Run ID 当作本机运行。 [Trace 写入](../src/lalc/application.py#L991) · [Run 序号](../src/lalc/application.py#L1034) · [调用事件](../src/lalc/runtime.py#L873) · [Workflow Ledger](../src/lalc/ledger.py#L75) · [导入日志身份](../src/lalc/run_log_sharing.py#L41)
4. **运行日志清理与可续接会话的保留边界需要写入规格。** 本机详细日志分布在 `traces/<id>.jsonl`、`runs/<id>.json` 和 `evidence/<id>/`。Runtime Repair 现在使用有父 Run ID 的 Developer Session，持有自己的对话和 Candidate，应整体保留。这个行为细化了术语表对 Run Log Bundle 的旧描述。导入副本有独立目录和元数据，删除目标应按导入身份定位。 [运行状态文件](../src/lalc/application.py#L976) · [截图](../src/lalc/application.py#L383) · [Runtime Repair](../src/lalc/application.py#L855) · [日志导入](../src/lalc/run_log_sharing.py#L196) · [术语表](../CONTEXT.md)
5. **两处 GUI 都需要适应清理造成的目录变化。** 现有导航测试固定前三条路由，新入口需要更新其预期和中英文翻译。清理完成后，「日志」页需要刷新，并处理当前选中 Run 已被移除的情况。数据扫描及占用统计应放到后台，沿用日志页的有界列表加载方式。 [导航验证](../tests/test_user_gui.py#L111) · [导入日志同号测试](../tests/test_run_log_sharing.py#L155) · [日志列表](../src/lalc/run_log_gui.py#L393)

## 潜在风险与拟定处理

- **日期来源。** 本机盘点的两份旧 Manifest 都缺少 `published_at`。现有排序回退到文件修改时间。预览建议标记回退日期为「文件时间」，并用同一排序定义计算默认保护之外的「最新发布版」；回退时间可能因复制而变化。 [现有版本日期](../src/lalc/manifest.py#L284)
- **已开始删除后的部分失败。** 预览和执行之间可能有数据变化。执行前重新核对对象身份、保护规则、引用集和路径，发现变化则要求重新预览。提交阶段使用同盘隔离，提交前失败回滚，回滚失败保留唯一旧副本。提交后清理残留失败时报告真实结果和残留位置。用故障注入验证 Windows 文件占用、链接／目录联接和重试。 [工作目录约定](../src/lalc/work_files.py) · [现有会话删除模式](../src/lalc/developer_session.py#L209)
- **过往引用在详情里的可用性。** 保留的 Trace、Ledger 或 Agent 附件仍可提及已删版本。历史记录继续展示原 ID，原版本和对应源码可能无法再次打开。旧 Trace 缺失与已经删掉的旧版本需在界面上明确反馈。 [按版本读取源码](../src/lalc/manifest_reference.py#L103)

## 实施顺序与验收

1. 记录新版 Run Log Bundle 与 Developer Session 的保留边界，确定存储层锁和删除提交边界。
2. 实现纯读取的盘点和使用摘要，再实现清理预览、执行前复核、失败回滚及日志列表刷新。
3. 接入 User GUI 双语导航和四类列表。用合成数据验证同号导入、共享源码、日期边界、未知日期、保护状态、摘要去重和无 Trace 历史。最后在 Windows 成品中验证文件锁及清理后的实际磁盘占用。

## 实施验证

用户确认预览后，已接入 [数据盘点和事务](../src/lalc/data_maintenance.py) 及 [User GUI 页面](../src/lalc/data_maintenance_gui.py)。隔离数据验证了本机与导入日志同号、日志清理后摘要仍可统计、Default 变更后的重新检查、共享源码和旧孤立源码保留、目录移动失败回滚，以及回滚失败时保留唯一旧副本。GUI 测试覆盖日期边界、详情跳转、取消和确认。中英文资源均已接入。

相关回归 314 项通过，3 项跳过。另有 4 项原有失败在改动前的版本复现，1 项真实 HTTP 测试因本机环境禁止监听回环端口而排除。Windows 成品和真实游戏尚未验收。
