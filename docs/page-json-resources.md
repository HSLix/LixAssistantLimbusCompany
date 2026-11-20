# 页面 JSON 资源

页面按 `PAGE_ID` 拥有可持久化的 JSON 资源。每个资源是一个 JSON 对象，名称使用小写字母、数字、点、下划线和连字符，以字母或数字开头。读取缺失资源会返回 `None`。写入整份原子替换，调用成功后，页面和后续 Workflow 立即可读。

```python
rotation = ctx.action("page_resource.read_json", page_id="mirror.settings", name="rotation")
ctx.action("page_resource.write_json", page_id="mirror.settings", name="rotation", value={"next_team": 5})
```

Plan、Task Workflow、Subworkflow 和 Step 可从 `execute` 调用。正式运行和 Developer Trial 使用同一本机资源，试跑成功写入会影响下一次正式运行。页面包审批预览的两侧各用独立内存资源。资源值会随动作记录到 Trace，适合存放队伍游标等业务数据。

## 页面引用共享素材

可信页面可用 `PageContext.read_asset_image(logical_name, sha256)` 读取指定 Asset 的原图。素材已移除时返回 `None`，哈希不符会报错。页面预览不读取现场素材。

`PageContext.list_asset_images(logical_name)` 枚举同一逻辑名下直接存放的候选图片哈希，不遍历子组，也不读取图片内容。目录不存在或仅有预览上下文时返回空列表。页面需要实际显示候选时，再逐张读取校验哈希并解码。

`PageContext.list_asset_image_groups(group)` 枚举一个组及其子组的候选图片，返回逻辑名到哈希列表的映射。不跟随目录链接。页面可据此通过实际逻辑名定位已有图片。

页面可用 `commit_resource_json(name, expected, value, asset_rename=(old, new))` 保存更新后的引用。该操作取得游戏活动锁，比较最新 JSON 与 `expected`，然后在同一组内重命名 Asset 目录并写入 JSON。目标已存在时拒绝覆盖，JSON 写入失败会尝试恢复目录。仅更新 JSON 时可省略 `asset_rename`。Workflow 继续通过已有 Resource 和 Asset Action 收录。

## 镜牢轮换

1. 进入镜牢循环前，Plan 读取 `rotation.next_team` 槽位号，并在当前 `mirror_teams` 中查找该队；找不到就从第一支开始。用这个位置初始化 Run State 的队伍下标。
2. 每场实际结算后，用本场所选下标加一并对队伍数取模，将对应槽位写入 `rotation.next_team`。下一场使用该下标。取消、执行失败或尚未确认结算时，无需写入。
3. 镜牢页以 `next_team` 为首项显示接下来的队伍顺序。比如循环设置是 `[2, 5, 8]`，下一支为 5 时显示 `[5, 8, 2]`。编辑弹窗调整循环设置，页面提交继续保存原有字段。

## 影响范围

- 原来的 `RunState.settings` 是单次 Run 的快照。显式动作给跨 Run 数据提供了持久化入口，`user-settings.json` 的表单提交与它独立。页面替换和 Manifest 切换共用已保存资源。
- 静态校验和执行器使用同一动作权限表，保证 Plan 能写游标，同时保留原有观察和游戏输入权限。动作进入 Trace，类型声明由注册表生成。
- 页面包和现有 Sharing 格式继续收录页面源码、静态素材及显式选择的表单配置。页面 JSON 资源独立于这些对象。运行时图片资源后续另行设计。
