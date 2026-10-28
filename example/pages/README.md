# exp、mirror 教学页面

将本目录 `exp.py`、`mirror.py` 手动复制到 `lalc data-dir` 显示的数据目录下的 `pages/`。同名用户页先检查，不能直接覆盖。重启应用或在通用设置中保存并重新加载整个应用。

两个页面分别使用 `PAGE_ID = TASK_ID = "exp"`、`"mirror"`，配置教学消息；Dashboard 管理是否启用和重复次数。页面 ID、任务 ID 与 Component 名称是不同概念，这里只是有意取相同字符串。

搭配 [workflow](../workflow/README.md) 发布的 Plan 使用，链路为页面消息 → `settings[任务 ID]` → Plan → `tasks.exp` / `tasks.mirror` → 共享 Subworkflow / Step → 应用 Trusted Actions。样例只观察和等待，不实现经验本或镜牢的真实游戏流程。

外置页是可信、同进程的 Python 模块，提供 `PAGE_ID`、`PAGE_NAME`、可选 `TASK_ID` 和 `create_page(context)`。返回的 QWidget 提供 `submit() -> dict`，输入非法时抛出明确错误。`context.load(defaults)` 读取配置副本，`context.save(config)` 保存 JSON 配置；宿主开始运行和整应用重载前提交所有页面，包括未启用的任务与纯设置页。页面不随 Manifest 发布，内置 Agent 无权编辑。

页面 ID、任务 ID 各自唯一；冲突注册全部排除，普通导入或创建失败只跳过本页。配置保存在数据目录 `user-settings.json`，切换 Manifest 不删除配置。页面改动需整应用重载。Plan 的 `SUPPORTED_TASK_IDS` 必须是模块级字面量字符串列表；Dashboard 只提供页面与 Plan 的任务 ID 交集，缺项会提示。纯设置页可省略 `TASK_ID`，其配置仍传入 Plan。
