# 识别调试页合并：影响审查

2026-11-14，基于当前工作树的源码、文档与测试静态检查。设计来源为
[逐项确认记录](recognition-lab-decisions.md)。本报告的实施前审查已获开发者确认并授权实现；实施与验证见文末。

## 设计变化

- 两个独立导航页 → 一个“识别调试”页，顶部标签切换模板匹配／OCR。
- 两份独立截图 → 一份固定原始截图、一个共用画布；各方式独立保存选区、参数和结果。切换只恢复状态，不截图、不执行。
- OCR 截图后自动识别 → 所有方式截图后均不执行；成功后清除全部选区、结果，保留参数、素材选择。截图失败保留全部旧状态。
- 模板框选只清除结果 → 松开非空框选时自动匹配；OCR 保留框选结束自动识别。按下和拖动期间不执行。
- 全图按钮只重置模板选区 → 当前方式清除选区并立即处理全图；不改变其他方式状态。
- 修改模板选择或参数后，仅清除模板旧结果、不自动执行；提供“匹配当前选区”重试。
- 素材截图／保存页继续独立；正式匹配算法、OCR 模型、Agent 工具及运行端权限不变。

这些决定在上述范围内替代 `template-match-lab.md` 与 `ocr.md` 的旧页面交互，
不否定历史验收记录。属于可逆的界面与状态调整，无新增领域术语或需要单独 ADR 的架构决定。

## 已确认的影响与实施建议

| 位置与证据 | 影响及处理 |
| --- | --- |
| `src/lalc/gui.py:MainWindow.__init__/render_state` 显式创建、导航和渲染两个旧页 | 替换为一个合并页和一个忙碌状态入口，删除两个旧导航入口。更新调用这些页面属性的测试，不保留仅为旧测试服务的兼容页。 |
| `src/lalc/developer_gui.py:OcrPage`、`src/lalc/template_match_gui.py:TemplateMatchPage` 各有 `snapshot` 和 `OcrView` | 合并页持有唯一 snapshot 与唯一画布；各方式只持有自己的选区、参数和结果。沿用现有 Fluent 标签组件与素材树能力。后续增加方式时添加标签及对应控件／执行逻辑，不引入动态插件框架。 |
| `developer_gui.py:CropView.set_image` 重置选区且发出 `selected({})`；鼠标按下也发空选区信号 | 设置新图、恢复方式状态和全图按钮不能走“框选完成自动执行”的路径；只对用户释放鼠标后的非空选区自动执行。标签切换不重新设置或复制图像像素。 |
| `developer_gui.py:OcrPage.capture` 成功回调立即 `recognize()`；两个旧页在截图开始前均清除结果 | 移除截图后的识别；截图请求开始时不清状态，成功后才统一替换／清除。失败沿用 `MainWindow.launch` 的错误入口，保留旧状态。 |
| `template_match_gui.py:full_image` 当前只清选区／结果；`view.selected` 仅连接 `clear_results` | 全图按钮改为清当前方式选区后直接运行；非空框选结束直接运行当前方式。未选择模板时禁止模板执行，保留选区供选择后手动运行。 |
| `template_match_gui.py:showEvent/refresh_assets/update_catalog/select_template` 在进入时检查素材，变化后重建并清结果 | 保留增量检查、目录展开与选择恢复。普通标签切换且素材未变时不得清结果；素材状态变更后清模板结果，避免把旧素材结果当作有效结果，OCR 状态不受影响。删除选中素材后禁用模板执行。 |
| `template_match_gui.py:run_match`、`developer_gui.py:OcrPage.recognize`，经 `MainWindow.launch` 提交后台工作 | 主线程提交前固定 snapshot、方式、选区及参数；工作线程仅处理固定输入。保留失败清除本次方式结果并报错的行为；执行失败与截图失败采用不同的状态保留规则。 |
| `gui.py:MainWindow.launch/render_state`、`application.py:ApplicationService.activity` | 复用现有排他执行。后台任务期间禁用截图、方式切换、框选及参数编辑，避免结果回到错误方式或错误截图；结束后恢复。保留 Run／Agent 活动互斥，不新增并行执行。 |
| `developer.py:DeveloperHost.capture/recognize_preview/match_template_preview` | 现有接口已支持固定内存截图，沿用 `capture(update_preview=False)`，避免更新素材页 `host.preview`。识别不需要再次连接窗口，无需改服务契约；相关 docstring 可同步合并页用语。 |
| `developer.py:match_template_preview` → `assets.py:AssetLibrary.match(record_usage=False)`，单图调用经过模板读取及正式检测 | 保留只读边界、优先标签与 NMS、路径／哈希校验，不写运行 Usage Index、素材或运行 Trace，不增加点击动作。 |
| `developer_gui.py:CapturePage.preview` 也使用 `OcrView`；`tests/test_capture_increment.py` 验证覆盖层 | 共用绘图组件不能随旧 OCR 页一起删除，也不能全局改变截图设置／框选语义；本次不改素材保存预览流程。 |

“共用截图”指业务上只有一份固定源截图与一个展示画布，不承诺零拷贝。
`CropView.set_image` 当前为安全展示复制 QImage，`recognition.py:client_image`
为匹配／OCR 转换 BGR 时也会复制；保留这些现有边界，消除的是两个方式重复保留截图与画布。

## 文档、翻译与测试

- 更新 `docs/template-match-lab.md`、`docs/ocr.md` 的现行用法和 `docs/current-state.md` 入口；历史 `ocr-test-page-impact-review.md` 保留并注明新交互的替代记录。
- 更新 `src/lalc/translations/lalc_zh_CN.ts` 及对应 `.qm`；按钮、提示和结果区随方式变化，避免同时显示含义相同的“恢复全图”和“全图执行”按钮。
- 迁移 `tests/test_developer_gui.py` 的旧导航及截图自动 OCR 断言，迁移 `tests/test_template_match_lab.py` 的独立截图和框选不执行断言，保留其后台算法、只读、哈希校验与增量素材检查。
- 增加针对性 GUI 场景：截图一次后两种方式使用同一 snapshot；切换恢复独立选区／结果且不执行；截图成功重置两边、失败保留两边；全图仅改变当前方式；框选只在松开后执行；参数改变清结果且可选区重试；忙碌时禁用入口；执行错误清本次结果；素材变化只使模板结果失效；标注不改原像素。
- `tests/test_gui_language.py` 的文本扫描文件列表需覆盖合并实现所在模块；若新增模块，同步列表。
- 建议实施后串行运行相关文件：

  ```sh
  QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest -q tests/test_template_match_lab.py tests/test_developer_gui.py tests/test_capture_increment.py tests/test_gui_language.py tests/test_developer_assets.py tests/test_ocr.py tests/test_assets.py tests/test_user_gui.py
  ```

  不涉及 Agent 接入，不添加 `--run-agent-tests`；跳过项不计通过。

## 潜在风险及验收边界

- 模板模式需要同时显示素材树、截图、参数与结果，1150 × 900 默认窗口下的空间需实施后实际渲染检查；预览图不证明真实布局合格。
- 框选自动模板匹配会比旧页更频繁运行算法；低阈值、关闭 NMS 或大量模板可能耗时较长。保留后台执行与忙碌禁用，不新增自动批量运行或缓存体系。
- 原生 OCR 推理不能即时取消，仍需等待当前推理返回；本次合并不改变该限制。
- 本次只检查了源代码和现有测试内容，未运行测试、未观察真实交互。Windows 成品、真实游戏与真实 OCR 效果均需与替身 GUI 验证分开报告。

## 实施顺序与确认点

1. 合并页与独立方式状态、唯一截图／画布、顶部切换和导航接线。
2. 截图成功提交、失败保留、框选／全图执行、结果失效和素材刷新互斥。
3. 翻译、现行用法、针对性测试与实际渲染检查。

无用户数据格式迁移，不涉及已发布 Manifest、素材文件或 Session 持久数据的变更。
实施前仅新增设计与审查记录；开发者确认本报告并回复“开始实现”后才修改产品代码。


## 实施与验证（2026-11-14）

- 已完成 `RecognitionPage`、唯一 snapshot／画布、顶部方式标签、模板侧栏与 OCR 扩展画布、导航及忙碌状态接线；删除旧 `OcrPage`，保留素材预览仍依赖的 `OcrView`。
- 已实现独立选区／结果恢复、截图不执行、成功统一重置、失败完整保留、非空框选结束自动处理、全图按钮立即执行、模板参数变化清结果与选区手动重试。截图保存页仍使用独立预览。
- 标签切换不重新赋值画布图像；新增测试同时检查 snapshot 对象身份及画布图像缓存身份未变。素材目录变化只清模板结果，删除选中模板后禁用模板执行。
- 已同步现行用法、双窗口导航测试及中英文翻译，重新生成 `.qm`。模板后台算法及 OCR 接口保持。
- 上述针对性命令最终结果：**164 passed、2 skipped**，跳过项不计通过；未添加 `--run-agent-tests`。测试涉及替身截图／OCR 与正式模板算法，不代表真实游戏验收。
- 使用合成截图、替身结果分别渲染并目视检查 1150 × 900 中文模板／OCR 状态：模板素材、参数、图像及结果均可见，OCR 隐藏侧栏并扩大画布。采用与现有测试相同的 macOS 系统标题栏替身，不代表原生窗口验收。
- `git diff --check` 通过。未运行全量回归、Agent 接入测试或 Windows／真实游戏验收；未新增依赖或用户数据迁移。
