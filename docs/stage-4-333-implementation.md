# #333 双语组件与语言重载实施记录

2026-10-28：开发者确认 [grill 决策](stage-4-333-decisions.md)及[影响评审](stage-4-333-design-impact-review.md)后授权实施，现已完成本地实现及下列验证。尚未提交 Git，#333 已经开发者人工验收确认（“没看出明显问题”）并按明确指令关闭为 completed；本记录不表示 #334 Windows 成品通过。

## 使用与实现

- User GUI → General Settings → 应用 → 界面语言：跟随系统（默认）/ 简体中文 / English。中文系统含繁体地区统一使用简体中文，其余使用英文。两窗口共享，Developer 无独立语言入口，单独启动也读取共享选择。
- 选择立即原子保存到数据目录的 `gui-settings.json`，不修改 `user-settings.json` 或 Plan 的业务 settings。保存失败显示原始错误并恢复已保存选择。当前进程与其新弹窗、重开窗口、外置页继续使用启动语言；点击既有“保存并重新加载整个应用”后统一生效。
- 语言控件位于 Agent 区域之外，Developer 持有 Agent 编辑权时仍可修改；活动期间可保存，但现有活动/线程/后台作业门控禁止重载。重载继续先提交、保存、清理、释放锁，再替换进程并恢复原先打开的窗口。不新增自动重启或热切换。
- `src/lalc/i18n.py` 持有启动语言及 Qt 翻译器。英文使用源文案；中文在创建窗口之前安装 Qt 标准按钮翻译、FluentTranslator 和应用 QTranslator，翻译器随 QApplication 保留。未能加载所需中文资源会明确报错，不伪装翻译成功，不修改全局 QLocale 默认值。
- `gui.py`、`developer_gui.py`、`repair_chat.py` 接入统一入口，覆盖导航、设置、密钥输入、运行/暂停/恢复、通知、活动名、检查结果、对话轮次/工具状态及弹窗控件。服务活动标识、消息角色、原始事件和业务结果不变。检查结果增加 `model_count` 呈现数据，服务日志及原有 message 保持原文。
- 错误摘要、详情、Trace、模型回答及用户输入无需翻译，允许原文或中英混合；GUI 通用错误标题、解释与操作按启动语言显示。详情默认折叠、复制/脱敏和失败退出保持，CLI 或 GUI/翻译初始化失败的双语终端兜底保留。ADR 0004 已记录该窄范围呈现替代。
- GUI 语言与 `ApplicationService.game_language` / CLI `--language` 分离，不影响识别、Asset tag 或执行输入。公告/声明/版本卡继续占位且不联网，Update 禁用。

## 外置页与示例

`PageContext.language` 提供本次生效的 `zh_CN` / `en_US`；`context.translate(中文, English)` 供作者直接选择自带文案。可选 `PAGE_NAMES` 按相同语言键提供导航名，缺当前语言时回退原有 `PAGE_NAME`；不改变必需 PAGE_NAME、create_page/submit、页面/任务 ID、保存键或页面异常隔离。现有页面不需要迁移，宿主不自动翻译页面。

`example/pages/exp.py`、`mirror.py` 已支持双语导航、标签与输入校验，保留原 ID 和 message 输入。新增 `legacy.py` 是固定中文的纯设置兼容页，不使用语言接口、不注册 TASK_ID，note 配置照常保存；它在英文模式下有意保留中文，和第三方未翻译页面同属已确认的例外。详见[页面说明](../example/pages/README.md)。本次不自动安装/覆盖用户数据目录中的页面，需手动复制更新后整应用重载。

## 翻译资源交付

应用英文源文案经 `tr()` 查找 LALC 上下文，中文翻译位于 `src/lalc/translations/lalc_zh_CN.ts`，当前 **209 条已完成翻译**。新增组件文案时同步维护该目录，并在项目根目录编译：

```sh
.venv/bin/pyside6-lrelease src/lalc/translations/lalc_zh_CN.ts
```

`.ts` 与编译后的 `.qm` 随 Python 包交付；`LALC.spec` 显式包含应用 `.qm` 及 Qt `qtbase_zh_CN.qm`，Fluent 继续使用依赖自带的资源。运行时按包路径加载，不依赖当前工作目录。目录覆盖测试逐项比较源文案、中文格式占位符和 `.qm` 实际查询结果，避免只改 `.ts` 而忘记编译。

## 已执行验证

- 普通回归：`QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest -q`，**516 passed，53 skipped**。未加 `--run-agent-tests`，跳过项不视为通过。
- 最后示例名称精简和标签自动换行后，定向运行 `tests/test_gui_language.py tests/test_example_workflow.py`，**25 passed**。语言专项覆盖中文系统/繁体地区/非中文、显式选择、保存失败、坏文件保留、待生效与启动语言分离、双窗口与活动门控、独立新进程读取共享语言、Qt/Fluent/应用资源、动态控件与原始内容、双语示例及旧页/缺单语名称回退。
- 原普通回归中的真实重启测试因环境 IPC 限制跳过；随后在允许本地 IPC 的环境单独运行 `tests/test_user_pages.py::test_reload_through_real_process_restores_both_windows_and_rescans`，**1 passed**。本机 macOS 原生进程实际从中文保存英文，重载后恢复 User/Developer、重新发现新增外置页，并检查两窗口英文按钮及外置页英文上下文，最终正常关闭。这不是 Windows 成品证据。
- 离线构建 wheel：`UV_CACHE_DIR=/tmp/lalc-i18n-uv-cache uv build --wheel --no-build-isolation --offline --out-dir /tmp/lalc-i18n-wheel` 成功。检查 wheel 同时包含 `.ts/.qm`，解包到临时目录后在 `/tmp` 从该包加载，确认中文翻译可查询；未运行 PyInstaller Windows 构建。
- 两语 Dashboard、General Settings、Developer 三页、exp/mirror/legacy 及窄设置窗口截图位于 `.generated/gui-language/`，已检查[对照图](../.generated/gui-language/overview.png)、英文 Developer 修订页和设置页。offscreen 沿用测试的 macOS 标题栏替身；英文示例名称使用简短的 EXP example / Mirror example，避免长名称挤占导航与任务行。截图不证明原生 Windows 缩放、字体或模态行为。
- `git diff --check` 及改动 Python 文件语法检查通过。测试及预览全部使用临时配置，不修改用户已安装页面或凭据，未调用 pi、真实模型或真实游戏。

2026-10-28：开发者已人工验收，反馈“没看出明显问题”，明确要求关闭 #333；GitHub 已关闭为 completed，并附上实现、验证及未验收边界说明。

剩余验收：#334 继续负责 Windows 成品、原生焦点/模态/缩放和 DPAPI 现场证据。真实公告、旧版声明核实及版本联网功能留在 Stage 6 之后。
