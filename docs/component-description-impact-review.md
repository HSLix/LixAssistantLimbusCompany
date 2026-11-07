# Component 说明来源修订

## 设计变化（2026-11-07，开发者已确认）

旧契约（ADR 0004、Stage 2）：模块 docstring 是 Component 唯一自然语言说明且必填。
新契约：Automation Plan、Task Workflow、Subworkflow、Step 优先读取顶层 execute docstring，缺失时回退模块 docstring，两者皆无时拒绝。
Recovery Rule 仍要求模块 docstring，不从 detect/recover 或额外 execute 提取说明。
无独立 description 字段，不改变签名、Manifest 格式、权限、源码哈希或发布边界。

## 审查结论（实施前源码检查）

- **已确认**：manifest.py 的 _parse_sources → _validate_source_structure 对所有分区统一检查模块 docstring；必须按 components/recovery_rules 分区分别选择来源。
- **已确认**：runtime.py 的 _wait_manual_resume 仅 inspect.getdoc(component.module)，因此放宽校验不足以让暂停提示显示新说明；需同步 execute 优先及模块回退。
- **已确认**：ADR 0004、Stage 2、CONTEXT、reconstruction-plan 仍声明模块唯一来源；Workflow Skill 也要求模块 docstring。需同步现行契约与指导。
- tests/test_manifest.py 使用模块说明的完整发布样例；tests/test_input_control.py 覆盖真实执行器的暂停/恢复路径。应新增函数说明独用、缺失拒绝、Recovery Rule 例外及暂停显示优先级的覆盖。
- **潜在风险**：已有源码同时写了两处不同说明时，暂停展示将改用 execute 说明。这是此次接受的优先级变化；源码不变则 ID 不变。外部旧版本应用仍可能拒绝仅函数说明的新版源码，不增加向后导出转换。

## 后续顺序

先修订契约和指导，再调整校验及暂停展示，补充针对性测试并记录结果。
旧源码无需批量迁移，不重写已发布文件或示例，不触发真实 Agent/模型/游戏操作。
审查为源码检查，实施验证结果另记如下。

## 实施与验证

已同步上述契约、Workflow Skill 和开发教程；校验按 Manifest 分区选择要求，暂停提示采用 execute 优先、模块回退。新增四类入口的独用说明/缺失拒绝、发布后加载、Recovery Rule 例外及暂停提示优先级测试。保留已有模块说明样例，未迁移已发布源码。

验证命令：
`QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest -q tests/test_manifest.py tests/test_input_control.py`
结果：53 passed。未开启 Agent 测试。
标准 uv 命令因构建依赖下载受网络限制未启动测试；直接使用现有环境。
首次直接运行在 macOS 原生无边框窗口测试处异常退出，改用 offscreen 后完整通过。
未运行全量回归、Windows、真实模型或游戏验收。
