---
name: page-development
description: 开发、修改和预览 LALC Business Settings Page 时使用，涵盖整包草稿、资源、配置兼容和 Plan 接线。只有实际启用 page_* 工具的 GUI Construct 可以执行页面操作。
---
# 页面开发

1. 明确新建或修改目标，检查已有页面、配置和相关 Plan，确认字段及业务用途；仅分析无需创建草稿。页面独立于 Workflow Candidate 和 Manifest，仅通过 page_* 专用工具管理。
2. 保留稳定 PAGE_ID／TASK_ID 和已有配置，核对字段变化及 Plan 参数。破坏兼容前必须取得开发者明确授权；通过已启用的 request_feedback 请求授权时参考 `../human-feedback/SKILL.md`，Skip 不授权。
3. 注册循环任务时，Plan 的模块级字面量字符串列表 SUPPORTED_TASK_IDS 必须包含页面 TASK_ID；配置从 settings[PAGE_ID] 读取。PAGE_ID、TASK_ID 和 Component 名不同。核对当前 Default，Dashboard 只显示已加载页面与其 Plan 支持任务的交集；页面安装、Workflow Publish、用户选择 Default 相互独立，Agent 不设置 Default。不能只靠重载或宣称注册成功。页面模块可选布尔 SHOW_TASK_COUNT（默认 True）；False 隐藏整组次数控件，匹配且启用传 1、未启用/不匹配传 0，旧保存次数保留。
4. 通过 page_* 创建或修改当前 Session 草稿。新页面为独立目录中的 page.py 加资源，修改页面复制已安装整包；工具 filename 仍是 sample.py 这类逻辑名称。满足 PAGE_ID、PAGE_NAME、create_page(context)、返回 QWidget 的 submit() 契约。
5. page_list(filename=...) 列举包内文件；page_read(path=..., image=true) 查看图片；page_resource 只改当前草稿资源。图片通过 context.resource_path("assets/banner.png") 定位。源码和资源共同构成批准版本，不写私人配置，不新增第三方依赖，不因此取得正式页或共享素材的写权限。
6. 调用 page_preview 并提供简洁修改说明供审查。预览失败时按工具错误修正草稿，必要时重新预览；加载成功不表示配置兼容或业务验证通过。
7. 安装必须经过 page_preview 的专用人工审批，其他反馈不构成批准。等待结果：installed 表示固定内容版本已安装；关闭或跳过不安装，可继续修改；取消轮次则停止。草稿改变后重新预览和审批。
8. 总结页面修改、兼容性影响、预览和安装状态及未验证业务行为。试填配置不会随安装保存；提醒开发者主动重启应用以应用变更，安装不会自动重启。Workflow 修改和运行另读 `../validation-and-trial/SKILL.md`。
