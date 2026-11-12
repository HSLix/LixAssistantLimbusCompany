---
name: validation-and-trial
description: 修改 LALC Workflow 后进行完整校验、发布、试运行或解释运行证据时使用。区分静态 Validate、不可变 Publish、显式保存版本运行和真实游戏验收。
---
# 验证与试运行

1. 工具成功不等于完整 Validate 通过。修改 Candidate 后执行完整 Validate，按实际错误继续修正；校验失败仍可修改。Validator 会导入 Python，不是安全沙箱；校验通过不等于真实游戏验证通过。
2. 新修改运行前必须先 Publish 为不可变版本，不执行可变 Candidate。Developer 用明确 Manifest ID 的 trial_run；Runtime 用 publish(summary="修复问题简述") 写入 AdditionalMessage，再 recheck(manifest_id) 结束本轮并交还 Runtime，仅重调当前失败入口。Publish 本身不执行、不设置 Default，不存在额外永久批准流程。
3. Developer trial_run 的 use_saved_config 默认 true，采用已保存页面配置及启用任务次数；设为 false 才使用显式 run_state（task_repetitions、settings），省略为空。inputs 只承载普通 Component 参数，Plan 无业务入口参数。试运行失败交回当前 Developer Session，不启动 Runtime Agent。
4. 按用户要求和验证需要决定是否试运行；仅分析、查看资料不强制修改或发布。每次试运行前简要拟定本次起点与期望（要验证的变化、终点或输出），根据当前证据确认起点；不能把多个页面共有的标志当作测试准备完成。试运行期间等待工具结果，不并行修改或操作游戏。
5. 启动拒绝没有 Run ID，不能当作已运行；启动后的结果和 Run 日志才是运行证据。完成后对照实际起点与预期变化、终点或输出；必要时读取日志和截图，确认不是起点错误、零动作直接返回或恢复后成功而被误当作原路径顺利完成。失败后依据新证据修订，不无依据反复重试。用户停止运行后总结并等待新指示。
6. 总结实际修改、静态校验、已发布版本、真实运行及未验证事项。不编造工具结果或验收结论；依照常驻最终 JSON 契约判定 revise_success。用户明确要求成功试运行时，未运行或失败不能报告修订任务已完成。
