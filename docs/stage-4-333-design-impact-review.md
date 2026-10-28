# #333 双语与语言重载影响审查

2026-10-28：基于开发者已确认的 [grill 决策](stage-4-333-decisions.md) 完成只读源码审查。本报告已获开发者确认并授权实施。以下为审查时的源码证据与实施建议；后续实现及验证见[实施记录](stage-4-333-implementation.md)。关闭 issue 仍等待开发者验收确认。

## 设计变化

- 混合中英文界面 → User/Developer 应用自有 GUI 组件文案及现有 example/pages 示例支持简体中文/English；中文模式以中文为主，英文模式的自有组件文案全部英文。原始异常、Trace、模型回答和用户内容保持原文。开发者在审查期间明确：错误详情无需中英分开，可原文或中英混合；本票不承担诊断详情翻译。
- 尚无 GUI 语言设置 → 默认跟随系统，中文系统归到简体中文，其余英文；两窗口共享，仅 User General Settings 提供编辑入口。立即保存，下次整应用启动生效；活动期间可保存，禁止重载。GUI 语言与游戏识别语言隔离。
- 外置页仅静态显示名 → 增加本次生效语言、最小翻译能力和可选导航名称翻译，旧页面仍按原接口加载。现有 exp/mirror 示例支持双语，另增一个不支持切换的纯设置兼容示例；该示例与第三方未翻译页面是英文模式全英文要求的明确例外。
- 本票不恢复 Release/旧版声明/版本联网功能；信息卡继续占位、不联网、Update 禁用。Windows 成品现场验收归 #334。

## 已确认的影响与差距

| 证据位置 | 已确认事实及影响 |
| --- | --- |
| `src/lalc/gui.py:43` ErrorDialog、`:334` 完成通知、`:490` General Settings、`:718` render_state；`src/lalc/developer_gui.py:67` TrialDialog、`:464` SettingsPage、`:723` RepairPage | 静态与运行时文案均直接写入控件；仅翻译初始化标签会漏掉按钮状态、通知、菜单/提示、密钥弹窗及后台完成后的状态。需要把全部应用自有文案接入统一翻译入口，不修改实际执行结果和 ID。 |
| `src/lalc/repair_chat.py:29` upsert_tool、`:59` render | 工具状态、角色标题、轮次和展开链接也是应用自有文案。须翻译呈现层，保留内部角色判断、工具调用 ID、原始事件和消息正文。不能只处理两个主 GUI 文件。 |
| `src/lalc/developer_gui.py:638` check → `src/lalc/agent_diagnostics.py:71` 成功消息 → SettingsPage 回调；`src/lalc/gui.py:345` 活动显示 → `application.py:190` / `developer.py:99` 活动名称 | 动态可见文本还来自服务层。须在展示端为应用定义的活动与检查结果提供本地化呈现，避免引入 Qt 到无 GUI 服务或改写日志；原始错误继续放入可复制详情。不能把应用生成的成功提示都当成原始诊断豁免。 |
| `src/lalc/gui.py:882` run_gui → GuiCoordinator → open_window；`src/lalc/user_pages.py:108` PageContext → create_page | 创建控件前尚未安装应用翻译器；外置页面在首次打开 User 时创建并缓存在 coordinator。必须在应用启动时确定语言并持有翻译器，后续打开/关闭任一窗口、新建弹窗都使用同一本次语言，不在每次打开窗口时重读待生效选择。 |
| `src/lalc/user_pages.py:22` UserSettings | 配置严格要求顶层仅有 pages/tasks。直接追加 language 会导致旧校验拒绝读取；把语言放进 pages 还会把应用设置传入 Plan 的业务 settings。推荐独立最小 `gui-settings.json` 保存语言，沿用 atomic_write_json；旧业务配置无需迁移、不重写。读写校验和失败提示不能省略。 |
| `src/lalc/user_pages.py:49` PageContext、`:91` PAGE_NAME 校验、`:116` BusinessPage.name | 只有 load/save 和静态字符串显示名。新增语言接口与可选本地化名称时保留旧 PAGE_NAME、create_page(context)、submit 契约；翻译只影响显示名，不改变 page_id/task_id 或配置键。保持普通页面异常隔离与全部冲突注册排除。 |
| `example/pages/exp.py`、`mirror.py`、`README.md`；`tests/gui_native_probe.py:37` | 两个自带页当前标签、导航名、校验提示为中文；需一起双语化。新增不使用语言接口、不注册 TASK_ID 的纯设置示例，展示旧接口回退，避免额外修改 Plan 或其任务支持列表。原生检查脚本按目录复制示例，现场说明需覆盖新增页。 |
| `src/lalc/gui.py:816` request_reload → `lifecycle.py:119` restart → `gui.py:846` restart_process | 已有活动/线程/后台作业门控、提交保存、清理后替换进程、窗口恢复链，可直接复用。语言编辑控件放在 Agent 区外，避免 Developer 持有编辑权时连语言也被禁用；保存失败不能显示保存成功或悄然切换界面。 |
| `src/lalc/application.py:65,522`；`src/lalc/__main__.py:85,94` | game_language 从应用执行配置传到 RunContext，CLI --language 也是游戏语言。GUI 语言使用独立配置和解析，不改这些入口，不全局改写业务语言或 Asset tags。 |

### 需要显式修订的旧规定

`docs/adr/0004-use-python-workflows-with-centralized-exception-control.md:71,78` 要求致命错误固定中英并列；`src/lalc/errors.py:8` FATAL_MESSAGE 与 `lifecycle.py:69`、`tests/test_error_handling.py:131` 实现/断言该行为。本轮已接受的“GUI 组件按语言呈现”仅替代正常 GUI 中固定组件文案中英并列的规则：致命错误 GUI 标题、通用解释及操作按本次语言显示；具体错误摘要及详情不要求翻译，允许原文或中英混合。原始诊断、日志、复制、主线程呈现和失败退出保持。

推荐在翻译器尚未建立、Qt 无法初始化或 CLI 路径中保留现有独立双语终端兜底，不能让错误报告反过来依赖成功加载语言资源。此窄范围替代应在 ADR 0004 和本票规格中明确记录，无需另建架构 ADR。错误详情默认折叠继续遵循已接受的 P0 规则，不借本票改变详情交互。

## 最小实施方案

1. 同步 Stage 4 规格、实施拆分、domain 指南和本票记录，明确两个窗口的翻译覆盖、唯一编辑入口、示例例外及致命错误呈现的窄范围替代。历史验证证据不改写为本票已通过。
2. 用英语作为应用翻译源文案，中文目录使用 Qt `.ts` → `.qm`。启动时安装 FluentTranslator 和应用 QTranslator，并处理 Qt 标准对话框按钮翻译；翻译器与 QApplication 同生命周期。既有 PySide6 已提供 lupdate/lrelease，无需新增依赖，不建设运行时热切换或第二套应用翻译系统。
3. 独立持久化语言选择，在窗口与外置页创建前解析启动语言；General Settings 加三选一控件和“重启后生效”提示，复用现有重载。翻译动态呈现及共享弹窗，不更改服务结果、Trace、Agent prompt 或执行语义。
4. 为 PageContext 增加本次语言与最小翻译接口，并支持可选本地化导航名；外置页可自带两语文案，不要求另行编译资源。更新 exp/mirror，新增旧接口纯设置示例及使用说明。稳定 ID、保存键和 Plan 保持。
5. 将应用翻译资源加入 Python 包数据和 PyInstaller 数据收集，路径相对包资源解析，不依赖工作目录。源码和构建产物需可复现地产生/携带 `.qm`；Windows 成品实际验证继续由 #334 完成。

依据：已安装 `PySide6-Fluent-Widgets==1.11.3` 的 `qfluentwidgets/common/translator.py` 确认 FluentTranslator 继承 QTranslator 并加载自带资源；[Qt 官方翻译流程](https://doc.qt.io/qtforpython-6/tutorials/basictutorial/translations.html) 说明 `.ts/.qm`、QTranslator 与资源随包交付。Fluent 官方网站检索失败，不宣称已核实其最新在线推荐。

## 验证工作与潜在风险

- 新增定向测试：系统中文（含繁体地区）归简体、非中文归英文、显式覆盖、旧环境无设置默认跟随、选择落盘失败、待生效与本次语言分离；切换后同进程重开窗口仍用旧语言，新进程才使用新语言；双窗口一致且 Developer 无新增入口；活动期间保存可行而重载被拒。
- 两语检查覆盖固定页面、导航、动态运行控制、通知、Agent 检查结果、对话呈现和普通/致命错误控件；错误详情不做单语断言，原始异常、Trace、消息与脱敏结果不被翻译或丢失。现有 `tests/test_error_handling.py`、`test_developer_gui.py`、`test_user_gui.py`、`test_user_gui_p0.py` 的固定组件文案断言按测试语言显式固定，不能依赖运行机器的系统语言。
- 扩展 `tests/test_user_pages.py`：两语自带页导航/内容/校验、旧接口页原文回退、缺少单条翻译时回退、稳定 ID 与配置保持，继续覆盖提交失败阻止启动/重载、错误隔离、冲突与页面缓存。现有“两页”断言使用独立 fixtures，不因新增 example 页面而机械改成“三页”。
- 复用既有清理失败、保存失败、重载恢复两窗口、执行与 Agent 编辑权门控回归。新增翻译资源可加载/随包交付检查，并检查两语和窄窗口截图；offscreen 不能证明 Windows 字体、原生按钮、缩放、模态或成品资源完整性。
- 潜在风险：翻译遗漏或格式占位符错配，需目录完整性与两语实际控件检查；Qt/Fluent/应用三类资源分别加载，未成功加载不能伪称翻译完成；构建资源存在不等于 Windows 成品验收。不要以修改 QLocale 全局默认或翻译业务数据来补漏。

本次仅检查源码与既有测试内容，未执行测试、构建、模型调用或真实游戏操作。实施时不启用 Agent 测试、不调用 pi-probe；#333 维持 OPEN，开发者验收确认后才关闭。
