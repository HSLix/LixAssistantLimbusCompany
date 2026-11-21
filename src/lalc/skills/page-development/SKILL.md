---
name: page-development
description: 开发、修改和预览 LALC Business Settings Page 时使用，涵盖整包草稿、资源、配置兼容和 Plan 接线。页面操作要求当前入口具备页面权限，安装仍需专用人工审批。
---
# 页面开发

1. 明确新建或修改目标，检查已有页面、配置和相关 Plan，确认字段及业务用途；仅分析无需创建草稿。页面独立于 Workflow Candidate 和 Manifest，使用当前入口启用的页面工具及页面范围。
2. 保留稳定 PAGE_ID／各任务 id 和已有配置，核对字段变化及 Plan 参数。破坏兼容前必须取得开发者明确授权；通过已启用的 request_feedback 请求授权时参考 `../human-feedback/SKILL.md`，Skip 不授权。
3. 页面通过模块级 TASKS 列表注册零到多个任务。每项必须包含非空字符串 id、name 和布尔 show_task_count；可选 names={"zh_CN": "名称", "en_US": "Name"}。纯设置页使用空列表或省略 TASKS。旧 TASK_ID 和页面级 SHOW_TASK_COUNT 已移除，不能混用。任务 ID 在页内和全部已安装页面间唯一，停用页面仍占用 ID。Plan 的模块级字面量字符串列表 SUPPORTED_TASK_IDS 必须包含对应任务 id；配置从 ctx.run_state.settings[PAGE_ID] 读取，次数从 ctx.run_state.task_repetitions[任务id] 读取。各任务 show_task_count=False 隐藏次数控件，匹配且勾选传 1，否则传 0；旧保存次数保留。Dashboard 逐任务显示名称，设置按钮指向所属页面。安装、Publish、用户选择 Default 相互独立；Agent 不设置 Default。
4. 通过 page_create 新建草稿或复制已安装整包。GUI Construct 用 edit(scope="page_draft", path="sample.py", edits=[{oldText, newText}]) 局部修改当前草稿入口，每个片段须在原文唯一匹配且不重叠；整份替换用 source。受控远程 MCP 沿用 page_update。满足 PAGE_ID、PAGE_NAME、create_page(context)、返回 QWidget 的 submit() 契约。
5. 页面必须显式设置与业务主题相关的 PAGE_ICON，使用 qfluentwidgets.FluentIcon 的有效成员。新建或修改页面时检查图标与主题是否相符；不要省略 PAGE_ICON、设为 None 或使用默认的 FluentIcon.APPLICATION，不臆造枚举成员。
6. page_list(filename=...) 列举包内文件。GUI Construct 用 read(scope="page_draft" 或 "page_installed", filename="sample.py") 读入口，可指定包内 path 和 image=true 查看图片；用 read(scope="page_settings") 查看保存的配置。受控远程 MCP 沿用 page_read。page_resource 只改当前草稿资源。图片通过 context.resource_path("assets/banner.png") 定位。源码和资源共同构成批准版本。
7. 调用 page_preview 并提供简洁修改说明供审查。预览失败时按工具错误修正草稿，必要时重新预览；加载成功不表示配置兼容或业务验证通过。
8. 安装必须经过 page_preview 的专用人工审批，其他反馈不构成批准。等待结果：installed 表示固定内容版本已安装；关闭或跳过不安装，可继续修改；取消轮次则停止。草稿改变后重新预览和审批。
9. 总结页面修改、兼容性影响、预览和安装状态及未验证业务行为。试填配置不会随安装保存；提醒开发者主动重启应用以应用变更，安装不会自动重启。Workflow 修改和运行另读 `../publish-and-trial/SKILL.md`。
10. page_list(scope="installed") 包含启用及停用页面，enabled 表示重启后采用的保存状态。通过实际启用的 page_set_enabled(filename, enabled, summary) 请求启用/停用，必须等待专用弹窗的真实确认；普通反馈、历史确认、关闭或取消不授权。GUI Construct 与受控远程 MCP 可提供页面工具，按当前入口权限判断；没有页面永久删除工具，不新增管理入口。
11. 停用保留源码、资源、页面配置和任务勾选/次数，重启后隐藏页面及其全部任务，关联任务传 0；重新启用恢复原设置，但仍受 Plan 支持列表约束。更新、覆盖安装及 Sharing 不改变本机启停状态。启停与安装一样在轮次结束并清理后统一提示重启；未重启前不改变当前页面或运行任务。
