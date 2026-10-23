# Developer Workflow

正式 Run 要求唯一可用的 Windows 游戏窗口。Run 开始时连接、聚焦并启动物理输入监听，结束时清理。纯观察任务也遵循此规则；自动化测试提供窗口和输入替身。

## 编辑与发布

```bash
uv run lalc init
# 编辑 candidate/manifest.json、candidate/asset-library.json 和 Component Python 源码
uv run lalc validate
uv run lalc publish
uv run lalc set-default <publish输出的UUID>
uv run lalc run <logical-name> --inputs '{}'
```

全新 Candidate 的 `manifest.json`：

```json
{"schema_version": 2, "components": {}, "recovery_rules": {}}
```

`candidate/asset-library.json` 初始为 `{}`。有已发布 Manifest 时，`init` 从 Default 复制 Component 源码和对应映射；`init --from <id>` 明确指定来源。已有非空 Candidate 不覆盖；`clear` 需要确认。

旧工作台的 `assets.json` 须由开发者明确改名为 `asset-library.json`；程序不自动回退读取旧名。已发布库的 `asset-libraries/<manifest-id>.json` 不改名。

每个 Component 条目选择相对 `source_path` 或已有 `component_id`，不能同时提供两者。源码使用 `@task_workflow`、`@sub_workflow` 或 `@step` 标明角色；Recovery Rule 使用 `detect` 和 `recover`。跨组件使用字面量 `ctx.call()`，低层操作使用应用已注册的 `ctx.action()`，不创建 Action 源码文件或在 Manifest 注册动作。应用注册保存名称、Python callable 及 observe/control 分类；原有参数、defaults、权限、结果校验、Trace 和异常传播保留。

常规使用按“publish → set-default → run / run-plan”进行；设置后运行命令省略 `--manifest`。每次重新发布并希望使用新版本时，再设置一次 Default。`--manifest <id>` 仅用于临时指定其他版本，不改变 Default。

## Asset 模板

```bash
uv run lalc crop-asset ui/claim --language zh --region '{"x":2,"y":1,"width":20,"height":20}'
uv run lalc validate
uv run lalc publish
uv run lalc set-default <本次publish输出的UUID>
```

裁剪命令针对当前 Candidate：重新连接并截图，裁剪指定客户区区域，保存 PNG 和独立来源记录，返回图片路径供检查，并更新 `candidate/asset-library.json`。同语义名同语言已有条目时明确询问替换；拒绝、EOF 或取消不改条目和图片。内容相同无需替换。文件名为 `语义名-语言-完整SHA256.png`，不覆盖旧图。

库 JSON 直接使用 `语义名 → 语言 → {path, sha256}`，没有额外 `assets` 包装。图片路径相对于本地数据目录的 `assets/`。发布后映射存入 `asset-libraries/<manifest-id>.json`，已发布 Manifest 位于 `manifests/<manifest-id>.json`。只改模板也必须 publish 创建新的一组文件；旧 Manifest 和库不变，图片可共享。

加载时完整校验并读取库到内存。`observe.capture_screen` 显式截图，`observe.match_asset` 使用当前截图；`observe.crop_asset` 总是重新截图，仅创建新图及来源，不修改已发布库。每次匹配验证图片完整哈希，保留语言回退、NMS、完整客户区坐标和独立 Usage Index。

### 登记已有裁剪

Workflow 的 `observe.crop_asset` 返回图片与来源，但不编辑工作台。检查返回的图片后，用语义名、语言及 `image_path` 登记，无需手写库 JSON：

```bash
uv run lalc add-asset ui/claim --language zh --image <crop返回的image_path>
uv run lalc validate
uv run lalc publish
uv run lalc set-default <本次publish输出的UUID>
```

只接受当前数据目录中有对应 crop 来源记录的图片；名称和语言必须与来源一致，完整哈希和解码须通过，不支持外部 PNG 导入。登记不连接游戏、不重新截图、不复制图片，仅原子更新当前根目录的 `candidate/asset-library.json`。不同内容的同名同语言条目需确认替换，拒绝、EOF 或取消不写入；完全相同的映射直接成功且不重写。已发布库、旧图片和 Default 均不变，publish 仍是独立步骤。

`crop-asset` CLI 已自动登记，无需再执行 add-asset；重复登记已有映射也是无写入成功。

## 格式与执行边界

schema 2 不接受旧版本、内嵌 `assets` 或 `trusted_actions`，不提供迁移工具。保存的 Manifest 多一个 UUID `manifest_id`，Component 身份仍为源码 SHA-256。validate 不写发布物、不分配 ID、不修改 Default；publish 保留 Candidate，也不修改 Default。

`run-plan <plan.json>` 读取外部编辑的有序 Task 配置，一次 Run 共用窗口会话、输入监听和 Working Manifest。物理接管暂停执行、释放输入并等待明确 Resume；不重放被中断的动作。诊断 `connect` 仍独立保存截图和文本证据，不创建 Run 或 Ledger。

新的 [三层教学样例](../example/trusted-actions/README.md) 展示全部应用 Trusted Action 调用，默认只截图和等待，外部库为 `{}`，无需模板即可校验发布；实际匹配需先登记模板并重新 publish。旧 examples 不恢复，回归测试仍有自己的夹具。

[ADR 0026](adr/0026-close-stage-2-without-a-real-game-workflow.md) 取消 Stage 2 的真实邮箱验收门槛；邮箱与剩余 Windows 集成/打包验收延期保留在 #317。Windows 真机与打包验收必须单独记录，不由测试替身结果代替。
