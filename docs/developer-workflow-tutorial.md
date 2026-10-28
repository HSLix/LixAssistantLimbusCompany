# Developer Workflow

2026-10-27：#331 已实现 Python Plan、双窗口及跨进程互斥，当前用法见下文和[实施记录](stage-4-331-implementation.md)。[Stage 4 规格](stage-4-extensible-user-gui.md)中的外置页面、共享 Agent 配置、双语信息面板及 Windows 打包验收仍由后续票完成。

正式 Run 要求唯一可用的 Windows 游戏窗口。运行开始时连接、聚焦并启动物理输入监听，结束时清理；自动化测试提供平台替身。

## Component 工作台与发布

```bash
uv run lalc init
# 编辑 candidate/manifest.json 和 Component Python 源码
uv run lalc validate
uv run lalc publish
uv run lalc set-default <publish输出的UUID>
uv run lalc run <logical-name> --inputs '{}'
uv run lalc run-plan
uv run lalc --developer
```

常规使用按 publish → set-default → run / run-plan 进行，后续省略 `--manifest`。每次发布并希望使用新代码版本时，再设置 Default；临时运行其他版本才用 `--manifest <id>`。

Manifest schema 2 只管理 `components` 和 `recovery_rules`，保存格式另有 UUID `manifest_id`。Asset 与 Trusted Action 都不是 Manifest 条目，不接受内嵌 `assets` / `trusted_actions`。Candidate 不需要素材映射文件；init 不复制素材，validate 不验证素材或写发布物，publish 不改 Default。已有非空 Candidate 仅在明确使用 `init --replace` 或 GUI 确认后重建；clear 需要确认。初始化同时保存独立的固定 Diff 基线。User Dashboard 与三页 Developer GUI、多文件连续修复见 [修复指南](agent-repair.md)。

初始化即生成并登记空调度 `plan.py`；Manifest 必须恰有一个 `@automation_plan`，其仅通过字面量 `ctx.call()` 调用 Task，不能直接调用动作。其固定输入为 `task_repetitions: dict[str, int]` 与 `settings: dict[str, Any]`，由宿主规范化并复制；完整示例见[实施记录](stage-4-331-implementation.md)。其余源码用 `@task_workflow`、`@sub_workflow`、`@step` 标记角色，Recovery Rule 使用 detect/recover。字面量 `ctx.call()` 调用正式 Component，`ctx.action()` 调用应用统一注册的动作；不直接调用原生截图或控制后端。

## Trusted Action 类型补全

开发者从根包导入 `RunContext`，给 execute、condition 或 detect/recover 的 ctx 参数添加注解。IDE 使用项目的 Python 环境，即可补全 Action 名称、对应关键字参数和返回类型；其他 Context 成员（例如 `ctx.call()` 和 `ctx.game_language`）也保留类型信息。

```python
from lalc import RunContext, step


@step
def execute(ctx: RunContext, *, x: int, y: int) -> None:
    ctx.action("observe.capture_screen")
    ctx.action("control.click", x=x, y=y)
```

新增或修改应用 Trusted Action 的注册、函数签名，或修改 RunContext 公开接口后，在源码 checkout 中运行：

```bash
uv run lalc generate-stubs
```

命令直接从 `application_actions()` 和真实函数签名生成完整的 `src/lalc/run_context.pyi`，保留默认值并移除执行器注入的 Context 参数；装饰器需通过 `functools.wraps` 或准确的 `__signature__` 保留签名。注解须能解析，Action 参数和返回值采用运行时支持的 JSON 类型；无法表达的签名、缺失注解或写入失败会报错并返回非零。生成成功后把声明与源码一起提交，不手工编辑声明。命令无需 Candidate、Manifest、游戏窗口或模型服务。

`tests/test_stubgen.py` 比较声明与当前注册、Context 接口是否一致，并使用 Pyright 验证典型合法与非法调用。静态声明对应应用正式注册，不随测试替身表或 Manifest 切换；角色/阶段权限仍由现有 Validator 和执行器检查，`ctx.call()` 仍保持现有动态参数与返回类型。

## 独立素材与标签

完整逻辑名对应完整目录，例如 `ui/claim` 对应数据目录的 `assets/ui/claim/`。每张图为 `<完整SHA256>.png`，目录下 `asset-tag.json` 保存 `哈希 → tag列表`。语言只是普通可选 tag，无特殊筛选规则。所有有效图片都参与候选；缺 tag 文件或缺哈希条目时按 `[]` 处理，不需要登记白名单。

```bash
uv run lalc crop-asset ui/claim --region '{"x":2,"y":1,"width":20,"height":20}' --tags zh event
uv run lalc tag-asset ui/claim --image <crop返回的image_path> --tags dark event
```

裁剪重新连接游戏并截图，保存图片、实际观察/区域来源和标签。tag-asset 仅给已有本地裁剪设置标签，核对逻辑名、来源、完整哈希及解码，不连接游戏、不接受外部 PNG、不复制图片。两个命令都无需 Candidate 或 Manifest 发布。

标签按本次输入整体覆盖：原为 `["zh", "event"]`，再传 `--tags dark event` 后为 `["dark", "event"]`。不追加、不合并、不去重，输入顺序与重复项原样保留。省略 `--tags` 或传空列表会写入 `[]`，清空已有标签。新图片和不同主题可并存；相同字节复用同一哈希图片，图片字节从不覆盖。重复裁剪相同图片时也按本次 tags 替换标签列表。标签更新无需确认，不改变其他哈希的标签。

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

[三层教学样例](../example/workflow/README.md) 不附图片或素材映射文件，默认只截图和等待。Plan 从已发布 Manifest 加载不可变 Python 源码，按普通 Python 控制流调用 Task，共用 Run、会话和 Working Manifest；物理接管需明确 Resume，Stop 后释放持有输入并收尾。

[ADR 0027](adr/0027-resolve-assets-independently-with-optional-priority-tags.md) 取代旧专属库。旧 Asset 布局、Candidate 素材库及已发布专属库废弃，清理后重新准备，不做迁移或兼容；Component、Manifest、Default 和运行历史保留。相同 Manifest 的素材结果可随文件更新而变化。

Stage 2 已按 [ADR 0026](adr/0026-close-stage-2-without-a-real-game-workflow.md) 收尾；邮箱和 Windows 集成/打包验收仍在 #317。Stage 3 不包含 Agent Asset 新增；未来 Stage 3.5 可新增素材，但仍不允许覆盖已有图片。

## 外置业务页面与共享 Agent 设置

Developer GUI → Agent Repair 中，“打开 Agent 工作区”右侧的“打开扩展配置页面文件夹”会打开数据目录下的 `pages/`，目录不存在时先创建。添加、编辑或删除页面文件后，通过 General Settings 的整应用重载使其生效；此入口不授予内置 Agent 读取或编辑页面的权限。

#332 已接入数据目录 pages/ 中的可信 Python 页面、按任务 ID 配置的循环次数和纯设置页输入。最小页面/Plan 示例、安装及创建契约见[示例](../example/workflow/README.md)，双窗口即时保存、单一编辑入口和整应用重载见[实施记录](stage-4-332-implementation.md)。旧 Plan 未声明支持列表时会告警，不改写旧发布物。
