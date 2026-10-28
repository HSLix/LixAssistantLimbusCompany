# User 导航分组与图标：影响审查

2026-10-28。输入为本轮已确认设计与 [Stage 4 接受规格](stage-4-extensible-user-gui.md#导航分组与页面图标)。以下为实施前的审查快照，当时未实现产品代码、未运行测试或原生窗口验收。后续本地实施记录见 [Fluent GUI 迁移记录](fluent-gui-migration.md#user-导航分组与页面图标)，不将下表的历史实现差距当作当前状态。

## 设计变化

原先固定页与业务页平铺，业务页统一使用齿轮。新设计在展开导航显示 `GENERAL` → Dashboard → General Settings → Separator → `WORKFLOW SETTINGS` → 全部已加载业务页；收起导航隐藏标题，但保留 Separator 与两组图标。空业务分组仍保留。没有新增页面父子关系、分组开关、排序配置或导航框架。

外置模块新增可选 `PAGE_ICON = FluentIcon.…`，缺省或 `None` 使用 APPLICATION；无效值回退并记录警告，页面继续加载。固定页图标保持原值。该声明为展示元数据，不进入用户配置或 Manifest；旧页面无需迁移或补写。图标修改与页面代码一样通过整应用重载生效。

`WORKFLOW SETTINGS` 是现有 Business Settings Page 的 UI 分组名，不是新 Workflow、Task 或 Manifest 类型。CONTEXT.md 现有术语足够；该局部且易逆的展示变更不需要新 ADR，与 ADR 0032 的页面/Manifest 分离及单进程 Fluent 导航边界一致。

## 已确认的影响与实现差距

| 位置 | 检查证据与影响 |
| --- | --- |
| `src/lalc/gui.py:UserWindow.__init__`（约 394、483、539–545 行） | 展开宽度为 220；先添加 HOME Dashboard，再添加 SETTING General Settings，随后对 business_pages 逐个使用 SETTING。当前无上述分组或独立图标消费；需要在原添加顺序中插入原生标题和 Separator，并读取业务页图标。保留页面 objectName、路由与 stackedWidget。 |
| `src/lalc/user_pages.py:BusinessPage`、`discover_pages`（约 64–112 行） | 元数据只有 page_id/name/task_id/widget/context，模块读取 PAGE_ID、PAGE_NAME、可选 TASK_ID；当前没有图标读取或存储。需增加带默认值的图标元数据，保留旧页及已有构造调用。发现顺序、导入/创建异常隔离、ID 冲突规则保持。 |
| `src/lalc/gui.py:UserWindow.__init__`（约 543–545 行） | 当前 page_errors 每项均显示为“外置页面加载失败”。无效图标警告不能直接混入这个列表并沿用该文案，否则会把可用页面误报成加载失败。最小实现可记录带页面身份的日志警告；真正导入/创建失败继续走现有通知。 |
| `src/lalc/gui.py:submit_pages`、`refresh_tasks`；`src/lalc/user_pages.py:task_inputs` | 配置提交依赖业务页列表，Dashboard 依赖 task_id 与 Plan 支持交集。导航应仍列出全部业务页，包括纯设置页及当前 Plan 不支持的页；分组不能复用任务列表过滤来生成。此处只需回归验证，无需改动业务路径。 |
| 本地 QFluentWidgets 1.11.3 的 `navigation_interface.py:addItemHeader/addSeparator`、`navigation_widget.py:NavigationItemHeader/NavigationSeparator` | 已存在公共原生分组标题与分隔线接口。标题在 compact 模式高度归零，Separator 在 compact 模式仍绘制；无需自绘分组标题、修改依赖或添加树形导航。展开/收起由现有 panel 处理。 |
| `example/pages/exp.py`、`mirror.py`、`README.md` | 实施时给两个教学页展示各自的 PAGE_ICON 声明并补充契约说明；保留旧测试页面不声明图标，以验证兼容默认值。无需修改 workflow 样例的 Plan/Task/Recovery Rule。 |
| `docs/stage-4-extensible-user-gui.md`、`docs/fluent-gui-migration.md` | 前者已记录接受设计并明确待实施；后者当前迁移记录仍是平铺顺序，实施后追加分组证据，不把历史迁移记录误写为本轮已完成。 |

## 潜在风险与必要检查

- **图标声明错误的边界**：`PAGE_ICON = "invalid"` 是可回退的无效值；`PAGE_ICON = FluentIcon.NOT_EXISTS` 会在模块求值时先抛异常，属于原有模块加载失败。不能通过忽略模块异常来保证后者仍加载，也不应为此改变页面加载机制。文档与测试应区分两者。
- **标题误入页面路由**：原生 ItemHeader 不作为页面加入 stackedWidget。需检查固定页面索引仍为 0/1、默认首页与任务行“设置”跳转仍选中原页面。
- **空分组和紧凑模式**：展开无业务页时仍有两个标题与 Separator；收起时不应残留标题空白，也不能同时移除分隔线。需实际检查展开、收起、菜单展开和业务页较多时的滚动。
- **平台显示差异**：本次只检查本地库源码，没有观察新布局的原生显示。此前记录的 macOS 原生窗口启动中止和部分 GUI 测试组收尾崩溃不在本次只读审查中解决；offscreen 证据不能代替 Windows 或 macOS 原生验收。

## 实施顺序与验证范围

1. 在现有 BusinessPage/发现流程增加可选图标元数据与无效值日志警告；不改变 discover_pages 返回结构或 page_errors 的失败含义，不增加磁盘配置格式。
2. UserWindow 使用原生 ItemHeader/Separator 分组并消费图标；Developer 导航、220 展开宽度、样式、路由和所有页面业务行为保持。
3. 更新 exp/mirror 页面与 README，实施完成后补充迁移记录中的证据与限制。
4. 聚焦 `tests/test_user_pages.py` 与 `tests/test_user_gui.py`：覆盖自定义图标、缺省/None/无效值回退、警告与页面可用性，空分组、两种导航状态、固定顺序及全部业务页归属；继续验证配置保存、快照、冲突隔离与页面跳转。分组标题不能改变页面数量或索引。
5. 视觉检查两种导航状态、空/非空业务组和原生选中样式；只在新的失败或更广影响需要时扩展回归。本次无需真实 Agent、模型调用或游戏操作。

结论：影响局限于 User 导航构建、业务页展示元数据、两个教学页和直接相关文档/测试；不需要数据迁移、新依赖、Runtime/Plan/Manifest 修改。已确认事项足以开始实施，无剩余阻塞设计问题。
