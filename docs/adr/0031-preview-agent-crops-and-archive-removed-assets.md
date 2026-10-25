---
status: accepted
supersedes: 0028 (Agent fresh-crop save rule); 0021 (explicit Agent Asset archive removal only)
---

# Preview Agent crops and archive removed Assets

2026-10-25：实机开发出现误裁模板长期参与匹配。Developer Agent 改为先 preview_crop(logical_name, region, threshold=0.9, tags=...)，返回带区域横纵线的全图、无覆盖层的小图、同图匹配结果及 preview_id；crop_asset(preview_id) 仅保存本对话预览的同一份像素、区域、逻辑名和标签，不重新截图。预览不进入活跃 Asset Library，仅在交互日志留证；预览可跨同一对话轮次重复使用，新对话不继承 ID。不提供任意文件导入或跳过预览的 Agent 保存路径，已有同名同哈希图仍复用原图及原标签。Workflow Trusted Action observe.crop_asset 保持原有新截图语义。

game_screenshot 同时返回原图和横纵每隔 40px 带坐标标记的网格辅助图。覆盖层只用于观察，不进入模板、匹配输入或原始截图证据。同图匹配复用普通模板算法及默认 NMS，结果提供位置、分数和中心点；不把命中次数作为保存门槛，也不把同图命中当作跨游戏状态可靠性的证明。本次不增加放大上下文图、锚点裁剪或自动吸附。

只提供 remove_asset(logical_name, sha, reason)，不提供 discard_asset。它允许归档任何既有合法 Asset，不限创建者或对话；归档先校验实际完整哈希和路径，再取得移除时当前原始游戏截图，截图失败不移除。agent_removed_asset/<UTC时间-UUID>/ 保留 asset.png、screenshot.png、record.json（原 Logical Name、SHA、Tags 快照、时间、理由、原路径与操作状态）；准备记录和图片保存完成后，才移除活跃图片及对应逻辑名 asset-tag.json 的 SHA→Tags 关系。其他 Logical Name 的图片与标签不变，不引入不存在的全局标签表。

归档文件先写入并刷新，准备记录成功后才修改活跃数据；普通失败或取消会回退已修改的活跃图片/标签，归档不删除。进程中断可能留下 prepared 记录，归档保存的图片与元数据供后续恢复；这不是多文件系统级原子事务，本次不提供自动恢复工具或恢复 GUI。显式归档是既有 Asset 保护的窄例外，不开放通用删除，不引入 Candidate Asset Store、Discard Index、Manifest Asset 映射或独立 Asset Library。Asset 独立于 Manifest，移除立即影响后续所有匹配。

连接诊断另在现有 pi 请求接口捕获底层 fetch 和响应流错误，保留请求序号、地址、阶段、耗时及异常 cause/错误码；不记录认证头/请求体、不新增自动重试。历史记录只能证明 Connection error 间歇出现，不能据此认定新增工具导致连接故障；真实 Windows 根因需结合新增诊断复现确认。
