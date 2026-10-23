# Developer Workflow

正式 Run 要求唯一可用的 Windows 游戏窗口。运行开始时连接、聚焦并启动物理输入监听，结束时清理；自动化测试提供平台替身。

## Component 工作台与发布

```bash
uv run lalc init
# 编辑 candidate/manifest.json 和 Component Python 源码
uv run lalc validate
uv run lalc publish
uv run lalc set-default <publish输出的UUID>
uv run lalc run <logical-name> --inputs '{}'
uv run lalc run-plan <plan.json>
```

常规使用按 publish → set-default → run / run-plan 进行，后续省略 `--manifest`。每次发布并希望使用新代码版本时，再设置 Default；临时运行其他版本才用 `--manifest <id>`。

Manifest schema 2 只管理 `components` 和 `recovery_rules`，保存格式另有 UUID `manifest_id`。Asset 与 Trusted Action 都不是 Manifest 条目，不接受内嵌 `assets` / `trusted_actions`。Candidate 不需要素材映射文件；init 不复制素材，validate 不验证素材或写发布物，publish 不改 Default。已有非空 Candidate 不覆盖；clear 需要确认。

源码用 `@task_workflow`、`@sub_workflow`、`@step` 标记角色，Recovery Rule 使用 detect/recover。字面量 `ctx.call()` 调用正式 Component，`ctx.action()` 调用应用统一注册的动作；不直接调用原生截图或控制后端。

## 独立素材与标签

完整逻辑名对应完整目录，例如 `ui/claim` 对应数据目录的 `assets/ui/claim/`。每张图为 `<完整SHA256>.png`，目录下 `asset-tag.json` 保存 `哈希 → tag列表`。语言只是普通可选 tag，无特殊筛选规则。所有有效图片都参与候选；缺 tag 文件或缺哈希条目时按 `[]` 处理，不需要登记白名单。

```bash
uv run lalc crop-asset ui/claim --region '{"x":2,"y":1,"width":20,"height":20}' --tags zh event
uv run lalc add-asset ui/claim --image <crop返回的image_path> --tags dark event
```

裁剪重新连接游戏并截图，保存图片、实际观察/区域来源和标签。add-asset 仅给已有本地裁剪追加标签，核对逻辑名、来源、完整哈希及解码，不连接游戏、不接受外部 PNG、不复制图片。两个命令都无需 Candidate 或 Manifest 发布。

标签稳定去重并追加合并：原为 `["zh", "event"]`，再传 dark event 后为 `["zh", "event", "dark"]`。省略 `--tags` 或传空列表时，新条目写 `[]`，已有条目不清空。新图片和不同主题可并存；相同字节复用相同哈希图片，已有图片从不覆盖。标签更新无需重名替换确认。

## 匹配规则

Step 先 `ctx.action("observe.capture_screen")`，再执行：

```python
ctx.action("observe.match_asset", asset="ui/claim", priority_tags=["zh", "event"])
```

priority_tags 默认 None，空列表也表示全部匹配。包含任一优先 tag 的模板组成优先组，组内全部匹配；有达标结果则只返回该批，不读取其余模板。优先组无结果时，剩余模板全部匹配，包括无标签图片。语言不会从 `--language` 自动转成优先 tag。

选定批次统一 NMS（默认启用、IoU 阈值 0.5），按分数降序、同分按稳定位置和哈希返回；关闭 NMS 保留所有达标结果。结果包含模板路径、完整哈希、tag、客户区坐标、分数、归一化区域和观察 ID。未知逻辑名是错误，存在但无命中的目录返回 `[]`；哈希、解码或标签文件格式错误保留原始异常，不伪装成未找到。

每次匹配重新读取该逻辑名目录和标签，并固定本次候选/标签。新增图片或改标签从下一次匹配生效，包括同一 Run；不需要 publish 或 set-default，也不建立跨调用缓存。observe.crop_asset 同样可传 tags，始终重新截图，保存后立即可被后续匹配发现。

## 证据和边界

`lalc data-dir` 查看数据根。图片在 assets/，裁剪来源在 asset-provenance/。Trace 的 asset_matched 记录优先条件、实际尝试模板、所选批次和最终检测结果；asset-usage.json 按逻辑名保存最近一次非空返回及来源，空结果不更新，不等待 Step 成功，也不影响搜索区域。普通截图不落盘，显式 `save=True` 才保存证据。

[三层教学样例](../example/trusted-actions/README.md) 不附图片或素材映射文件，默认只截图和等待。Plan 从外部 JSON 读取有序 Task，共用 Run、会话和 Working Manifest；物理接管需明确 Resume，Stop 后释放持有输入并收尾。

[ADR 0027](adr/0027-resolve-assets-independently-with-optional-priority-tags.md) 取代旧专属库。旧 Asset 布局、Candidate 素材库及已发布专属库废弃，清理后重新准备，不做迁移或兼容；Component、Manifest、Default 和运行历史保留。相同 Manifest 的素材结果可随文件更新而变化。

Stage 2 已按 [ADR 0026](adr/0026-close-stage-2-without-a-real-game-workflow.md) 收尾；邮箱和 Windows 集成/打包验收仍在 #317。Stage 3 不包含 Agent Asset 新增；未来 Stage 3.5 可新增素材，但仍不允许覆盖已有图片。
