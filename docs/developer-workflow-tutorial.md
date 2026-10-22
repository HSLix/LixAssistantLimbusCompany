# Developer Workflow

正式 Run 要求唯一可用的 Windows 游戏窗口。Run 开始时连接、聚焦并启动物理输入监听，结束时清理。纯观察任务也遵循此规则；自动化测试提供窗口和输入替身。

## 编辑与发布

```bash
uv run lalc init
# 编辑 candidate/manifest.json、candidate/assets.json 和 Component Python 源码
uv run lalc validate
uv run lalc publish
uv run lalc run <logical-name> --manifest <manifest-id> --inputs '{}'
uv run lalc set-default <manifest-id>
```

全新 Candidate 的 `manifest.json`：

```json
{"schema_version": 2, "components": {}, "recovery_rules": {}}
```

`candidate/assets.json` 初始为 `{}`。有已发布 Manifest 时，`init` 从 Default 复制 Component 源码和对应映射；`init --from <id>` 明确指定来源。已有非空 Candidate 不覆盖；`clear` 需要确认。

每个 Component 条目选择相对 `source_path` 或已有 `component_id`，不能同时提供两者。源码使用 `@task_workflow`、`@sub_workflow` 或 `@step` 标明角色；Recovery Rule 使用 `detect` 和 `recover`。跨组件使用字面量 `ctx.call()`，低层操作使用应用已注册的 `ctx.action()`，不创建 Action 源码文件或在 Manifest 注册动作。应用注册保存名称、Python callable 及 observe/control 分类；原有参数、defaults、权限、结果校验、Trace 和异常传播保留。

## Asset 模板

```bash
uv run lalc crop-asset ui/claim --language zh --region '{"x":2,"y":1,"width":20,"height":20}'
uv run lalc validate
uv run lalc publish
```

裁剪命令针对当前 Candidate：重新连接并截图，裁剪指定客户区区域，保存 PNG 和独立来源记录，返回图片路径供检查，并更新 `candidate/assets.json`。同语义名同语言已有条目时明确询问替换；拒绝、EOF 或取消不改条目和图片。内容相同无需替换。文件名为 `语义名-语言-完整SHA256.png`，不覆盖旧图。

库 JSON 直接使用 `语义名 → 语言 → {path, sha256}`，没有额外 `assets` 包装。图片路径相对于本地数据目录的 `assets/`。发布后映射存入 `asset-libraries/<manifest-id>.json`，已发布 Manifest 位于 `manifests/<manifest-id>.json`。只改模板也必须 publish 创建新的一组文件；旧 Manifest 和库不变，图片可共享。

加载时完整校验并读取库到内存。`observe.capture_screen` 显式截图，`observe.match_asset` 使用当前截图；`observe.crop_asset` 总是重新截图，仅创建新图及来源，不修改已发布库。每次匹配验证图片完整哈希，保留语言回退、NMS、完整客户区坐标和独立 Usage Index。

## 格式与执行边界

schema 2 不接受旧版本、内嵌 `assets` 或 `trusted_actions`，不提供迁移工具。保存的 Manifest 多一个 UUID `manifest_id`，Component 身份仍为源码 SHA-256。validate 不写发布物、不分配 ID、不修改 Default；publish 保留 Candidate，也不修改 Default。

`run-plan <plan.json>` 读取外部编辑的有序 Task 配置，一次 Run 共用窗口会话、输入监听和 Working Manifest。物理接管暂停执行、释放输入并等待明确 Resume；不重放被中断的动作。诊断 `connect` 仍独立保存截图和文本证据，不创建 Run 或 Ledger。

仓库不再提供 examples；回归测试自行构造 Component 和测试动作。Windows 真机与打包验收必须单独记录，不由测试替身结果代替。
