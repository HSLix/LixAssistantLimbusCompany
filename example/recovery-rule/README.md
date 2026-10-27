# Recovery Rule：关闭教学弹窗后重试 Step

这是确定性恢复示例，不调用 Agent。规则是独立的 Python Component，登记在 Manifest 的 `recovery_rules`，不使用角色装饰器；普通 Step 登记在 `components`。

先在 Capture 页为一个可安全关闭、能人工复现的外部弹窗截取**关闭按钮**，保存为 `tutorial/recovery-popup`。模板来自当前游戏截图，不随样例附带；语言/DPI/窗口尺寸变化后需重新确认模板。没有模板时，匹配报错，不会点击。请先确认按钮可安全点击，勿使用确认消费等不可逆操作的按钮。

在测试工作目录明确初始化 Candidate，将本目录的 manifest.json 和两个 Python 文件复制到 candidate/（先保存自己原有草稿，再明确替换）。也可在 Agent Repair 中要求通过两个新增工具创建这些源码和逻辑名。校验、发布和运行仍须分别进行：

```sh
uv run --frozen lalc validate
uv run --frozen lalc publish
# 使用上一步实际返回的 Manifest UUID，不必设置 Default：
uv run --frozen lalc run steps.check_popup --manifest <实际UUID>
```

游戏窗口恢复为可观察状态、显示教学弹窗时运行：

1. Step 截图发现按钮后抛出 ExecutionFailure。
2. 执行器按逻辑名顺序检查公共 Recovery Rules；本规则的 `detect(ctx) -> bool` 只观察。
3. 唯一规则匹配时执行 `recover(ctx) -> None`。它重新截图，按钮唯一才通过现有 `control.click` 点击中心；目标缺失或多匹配时报错。
4. 执行器重新调用当前 Step 一次。Step 重新观察，按钮消失才完成。若点击没有生效、按钮仍在，重试失败后停止，不循环恢复。

没有弹窗时 Step 直接完成，不执行规则。多个不同规则同时匹配时报错，不按优先级猜测；不要把同一弹窗重复登记为多个规则。detect/recover 均不调用其他正式 Component，recover 可以使用应用已注册的 observe/control 动作。该示例不新增业务专属 Trusted Action，也不会恢复整个 Task/Subworkflow。

对应 Run 的 Trace 中可检查 `component_failed`、`recovery_rule_started/returned` 的 detect/recover 阶段、`step_reinvocation_started/returned/failed` 和实际动作调用。每次截图均可保存证据。查看对应 Run 的结果与 Trace，不能仅凭规则返回 None 判定游戏恢复成功。

自动化回归使用生产动作和测试自有平台图像验证“匹配 → 点击 → 图像变化 → 重试”，另覆盖未生效、目标不唯一及规则多匹配；这些不是 Windows/真实游戏验收。真实按钮的模板、点击效果及跨 DPI 定位需在 Windows 上人工核对。
