# SIFT Trusted Action 影响审查

2026-11-14，用户要求先审查再实现：最小内点比例默认改为 0.4，并将 SIFT 纳入 Trusted Actions。

## 设计变化

- 原设计：SIFT 仅用于固定截图的识别调试，不注册正式动作（`docs/template-match-lab.md`、`docs/feature-match-lab-impact-review.md`）。新决定新增 `observe.match_feature`，旧记录保留时点含义。
- 新动作显式指定 Asset 逻辑名，提供调试页相同的 SIFT 参数和 region／NMS；最小内点比例 0.4，NMS IoU 0.4。尝试整组所有模板，不引入优先标签短路或单图哈希选择。
- 使用当前已捕获的客户区帧，不隐式截图或输入；返回全部经统一 NMS 的命中，包含原图框、centerxy、内点数／比例、覆盖与几何指标、模板路径／哈希／标签、逻辑名、归一化框和 observation。score 是内点数，不是模板相似度。
- 沿用正式 Asset 匹配的事件和非空使用索引写入；事件注明 SIFT 方法与参数。匹配不自动保存图片，需截图证据时显式 capture(save=True) 或 log(screenshot=True)。
- 应用注册的 observe 分类及现有执行权限矩阵已覆盖新增动作，无须新增权限或改变 Manifest。现有模板接口与默认值保留。

## 已确认影响

- `actions.py:application_actions` 当前无 SIFT 动作。需提供完整有类型的参数签名，供动作校验、Agent 动作目录及声明生成使用。
- `RunContext` → `WorkflowExecutor.match_asset` → `ApplicationService._match_asset` 是现有素材调用链；直接调用 Context 的底层方法受到活动 observe 门禁保护。新增特征入口必须保留此门禁、会话检查、输入检查、暂停／取消与统一 Trace。
- `DeveloperHost.match_feature_preview` 已执行整组校验、检测、排序和统一 NMS，但只返回调试元数据；`AssetLibrary.match` 已提供正式素材边界、来源、Trace 和索引。共享库复用正式路径的校验／记录逻辑，以内部特征参数选择既有 detect_features；不复制一套文件和索引逻辑。
- `feature_matching.py:detect_features` 与 GUI 默认表均为最小内点比例 0.5，必须一起改为 0.4；恢复按钮读取默认表。
- `run_context.pyi` 需重新生成；`image_annotations.action_annotations`、`run_logs.log_text` 当前只识别模板匹配动作，需包含新动作。
- 动作集合测试、类型测试及正式运行测试需更新；现有 SIFT 测试覆盖合成多实例、几何过滤、参数校验、整组 NMS 和只读预览，但不能证明正式执行接线。

## 潜在风险与验证计划

- 放宽内点比例可能增加误检；SIFT 放大和整组匹配可能增加计算耗时。合成场景验证坐标、排序及记录，真实 Windows／游戏准确率、耗时和长计算期间响应性仍需验收。
- 原始像素不得进入动作结果。覆盖正式动作返回、无截图拒绝、直接调用门禁、非法参数、跨模板 NMS、素材完整性，以及不隐式刷新／保存截图。
- 依次修改默认值、共享匹配、动作及运行接线、类型与日志、规格／用法和测试，串行执行相关普通回归。该改动不涉及 pi 接入，不附带真实 Agent 测试。

本审查依据当前源码与现行 Trusted Action／Asset 契约；无阻塞性设计冲突，无需进一步设计访谈。实施与执行证据另附于下方。

## 实施与验证

已实现 `observe.match_feature` 及有类型的 Context 入口；执行器复用现有 observe 素材门禁和会话回调，以内部 `_feature_options` 参数进入共享 AssetLibrary 校验／记录路径。未新增回调类别、权限类别、依赖或 Manifest 字段。Agent 的动作目录自动从注册表读取完整签名。已同步声明、结果标注、日志分数、调试默认／恢复值及用法；默认 workflow-conventions Skill 新增 SIFT 指导，已有数据目录副本需人工合并，不自动覆盖。

普通针对性回归：

```sh
QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest -q tests/test_sift_trusted_action.py tests/test_feature_matching.py tests/test_assets.py tests/test_manifest_transition.py tests/test_stubgen.py tests/test_template_match_lab.py tests/test_workflow_observability.py tests/test_log_diagnostics.py tests/test_run_logs.py tests/test_runtime_repair.py tests/test_workflow.py
```

201 passed。新增正式动作测试使用窗口替身与真实 OpenCV，覆盖整组多实例／统一 NMS、关闭 NMS、ROI、当前帧无隐式刷新、元数据与非空索引、无匹配不写索引、无截图失败、直接底层调用拒绝、非法比例与坏哈希失败、Trace 返回、日志分数和结果框。声明一致性及 Pyright 检查通过。原有截图夹具在内点比例放宽后，宽松几何设置产生的大框从一个变为两个；默认覆盖率与几何过滤仍得到原有五个有效结果，相关断言已同步。

未运行全量回归、真实 pi／模型、Windows 成品或真实游戏。计算阶段仍是既有同步 SIFT，长耗时检测中途的响应延迟和真实误检率尚未验收；放宽比例可能增加误检。
