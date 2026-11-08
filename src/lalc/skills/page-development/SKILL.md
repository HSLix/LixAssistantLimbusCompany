---
name: page-development
description: 开发、修改和预览 LALC Business Settings Page 时使用，涵盖整包草稿、资源、配置兼容和 Plan 接线。只有实际启用 page_* 工具的 GUI Construct 可以执行页面操作。
---
# 页面开发

1. 明确新建或修改目标，检查已有页面、配置和相关 Plan，确认字段及业务用途；仅分析无需创建草稿。页面独立于 Workflow Candidate 和 Manifest，仅通过 page_* 专用工具管理。
2. 保留稳定 PAGE_ID／各任务 id 和已有配置，核对字段变化及 Plan 参数。破坏兼容前必须取得开发者明确授权；通过已启用的 request_feedback 请求授权时参考 `../human-feedback/SKILL.md`，Skip 不授权。
3. 页面通过模块级 TASKS 列表注册零到多个任务。每项必须包含非空字符串 id、name 和布尔 show_task_count；可选 names={"zh_CN": "名称", "en_US": "Name"}。纯设置页使用空列表或省略 TASKS。旧 TASK_ID 和页面级 SHOW_TASK_COUNT 已移除，不能混用。任务 ID 在页内和全部已安装页面间唯一，停用页面仍占用 ID。Plan 的模块级字面量字符串列表 SUPPORTED_TASK_IDS 必须包含对应任务 id；配置从 settings[PAGE_ID] 读取，次数从 task_repetitions[任务id] 读取。各任务 show_task_count=False 隐藏次数控件，匹配且勾选传 1，否则传 0；旧保存次数保留。Dashboard 逐任务显示名称，设置按钮指向所属页面。安装、Publish、用户选择 Default 相互独立；Agent 不设置 Default。
4. 通过 page_* 创建或修改当前 Session 草稿。新页面为独立目录中的 page.py 加资源，修改页面复制已安装整包；工具 filename 仍是 sample.py 这类逻辑名称。满足 PAGE_ID、PAGE_NAME、create_page(context)、返回 QWidget 的 submit() 契约。
5. page_list(filename=...) 列举包内文件；page_read(path=..., image=true) 查看图片；page_resource 只改当前草稿资源。图片通过 context.resource_path("assets/banner.png") 定位。源码和资源共同构成批准版本，不写私人配置，不新增第三方依赖，不因此取得正式页或共享素材的写权限。
6. 调用 page_preview 并提供简洁修改说明供审查。预览失败时按工具错误修正草稿，必要时重新预览；加载成功不表示配置兼容或业务验证通过。
7. 安装必须经过 page_preview 的专用人工审批，其他反馈不构成批准。等待结果：installed 表示固定内容版本已安装；关闭或跳过不安装，可继续修改；取消轮次则停止。草稿改变后重新预览和审批。
8. 总结页面修改、兼容性影响、预览和安装状态及未验证业务行为。试填配置不会随安装保存；提醒开发者主动重启应用以应用变更，安装不会自动重启。Workflow 修改和运行另读 `../validation-and-trial/SKILL.md`。

9. page_list(scope="installed") 包含启用及停用页面，enabled 表示重启后采用的保存状态。通过 page_set_enabled(filename, enabled, summary) 请求启用/停用，必须等待专用弹窗的真实确认；普通反馈、历史确认、关闭或取消不授权。仅 GUI Construct 提供此工具，没有永久删除工具，不新增管理入口。
10. 停用保留源码、资源、页面配置和任务勾选/次数，重启后隐藏页面及其全部任务，关联任务传 0；重新启用恢复原设置，但仍受 Plan 支持列表约束。更新、覆盖安装及 Sharing 不改变本机启停状态。启停与安装一样在轮次结束并清理后统一提示重启；未重启前不改变当前页面或运行任务。
