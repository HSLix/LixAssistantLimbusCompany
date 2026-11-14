# 窗口级通知卡片组：设计影响与实施

## 接受的变化

2026-11-14，用户接受文字细化及收起／展开缩略图，并明确通知不自动消失，随后授权审查和实现。本次是交互呈现替换，不改变执行器或 Run Result。

- 旧：User Dashboard 的通知参与左栏布局，Developer 的通知参与窗口底部布局，多条持续纵向累积。
- 新：每个窗口持有右下角浮层，距右／下边缘 20 逻辑像素，通常宽 400，小窗口按宽度缩小；页面切换不影响提醒。只显示最新一条，角标统计全部保留条目，超过 99 显示 `99+`。
- 展开：最新在上，最大高度约为窗口可用高度一半，内部滚动；收起按钮、外部点击及本窗口 Esc 都回到单卡片。展开时新通知先隐藏并计数，通过“有新通知”入口显式刷新，避免改变阅读位置。
- 关闭单条会减计数并呈现剩余最新条目；全部清除或关闭最后一条隐藏浮层；详情查看不清除提醒。通知不跨窗口合并、不跨重启恢复、不删除 Run 数据。
- 继续保留页面加载错误、修复版本选择反馈及已有详情入口；不新增运行中／进度呈现、系统通知、通知持久化或最小化入口。

## 审查证据与影响范围

实施前逐一核对了 `CONTEXT.md`、当前状态、Stage 4 通知规格、Fluent 迁移及可行性记录，以及以下实际调用路径。

| 范围 | 已核实的旧行为及实施影响 |
| --- | --- |
| `src/lalc/gui.py`：两个窗口构造函数 | `NotificationList` 分别加入 User 左栏与 Developer 根布局，确认是占用纵向空间的直接原因；改为窗口子浮层，移除两个布局中的通知项。 |
| `MainWindow.render_state`、`UserWindow.render_state` | Run 收尾生成完成／含失败／中断通知；改走共用 `notify_result`，保留原诊断和运行归属，按 `reason=user_cancelled` 区分手动停止。 |
| `UserWindow.__init__` 的页面错误通知、结束时 Default 更新 | 仍走 `notify(message, details)`；保留既有页面错误隔离和版本反馈，不要求调用方迁移。 |
| 原 `gui.NotificationList.notify` → `ErrorDialog` | 原详情按纯文本展示且可复制；新组件继续使用同一对话框与原详情，不把原始诊断变成卡片正文。 |
| `tests/test_user_gui.py`、`tests/test_gui_language.py`、`tests/test_error_handling.py` | 原测试依赖多个可见 InfoBar、旧控件名或仅接收位置参数的通知替身；调整到卡片模型及带呈现类型的调用，仍验证通知次数和原始诊断。 |
| `translations/lalc_zh_CN.ts`／`.qm` | 新增展开、清除、数量及手动停止文案；语言覆盖检查纳入新模块，重新编译资源。 |

**已确认的不一致（实施前）：** Stage 4 允许多条同时保留，但新决定要求收起只显示最新条；Fluent 迁移记录明确写 InfoBar 内联堆叠；现有实现和相应测试均保留旧形态。本次同步更新现行规格、实现及断言，并为可行性记录补充替代说明，未把历史验证改写为新行为证据。

**潜在风险：** 浮层会遮住右下角局部页面，这是已接受的覆盖式呈现；小窗口应内部滚动而非撑大窗口。Windows 原生字体、缩放与窗口层级尚需成品验收，离屏测试无法证明这些效果。

## 实施与验证

新增 `src/lalc/notifications.py`，共用 Fluent CardWidget／按钮、Qt 滚动区和既有详情对话框。通知仅在窗口内存留存，无文件格式、配置、导出、权限或数据迁移，无新增依赖。窗口事件用于重新锚定，应用事件过滤用于外部点击及 Esc；Esc 只消费所属窗口的事件，避免拦截独立详情对话框操作。

新增 `tests/test_notifications.py`，覆盖布局不变、跨页保留、窗口缩放、持续显示、单条关闭和计数、展开限高和滚动、新通知不打断阅读、Esc／外部点击、全部清除、再次通知、原始详情和结果分类。

执行以下普通定向回归，结果 **128 passed、2 skipped**：

```sh
QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest -q -rs tests/test_notifications.py tests/test_user_gui.py tests/test_gui_language.py tests/test_error_handling.py tests/test_page_drafts.py
```

两项跳过分别为原生焦点验收及受环境限制的本地 IPC 真进程测试，不能视为通过。有一项来自 Fluent 导航组件的旧 Qt 鼠标事件 API 弃用警告。新通知测试不调用 pi／模型或游戏，未添加 `--run-agent-tests`。

离屏检查包含中文浅色收起／展开、英文深色收起／展开及 760×550 小窗口。检查中修正了 QScrollArea 原生白底和 CardWidget 默认半透明导致的深色对比与背景透字问题；浮层改为不透明主题底色，滚动内容不填充原生底色。预览使用指定可写可视化目录内的普通工作目录，不使用 tempfile。

未运行全量回归、真实 Agent／模型、Windows 打包或真实游戏验收。
