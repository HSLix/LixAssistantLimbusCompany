# Developer Skills

2026-11-21：GUI Agent 和 Runtime 调用 `validate_and_publish` 必须提交非空 `summary`，只记录本次实际变更和要点。宿主在校验前用它覆盖 Candidate 的 `AdditionalMessage`。用户明确要求不写附加信息时，传入字符串 `"None"`。CLI Repair 仍直接更新 Candidate 的说明。已有 `skills/` 可按下文合并 `workflow-development`、`workflow-repair` 和 `publish-and-trial`。

2026-11-19：Workflow 开发、修复及验证指导要求每次 Publish 前更新 `AdditionalMessage`，概括本版主要改动。Developer 编辑 Candidate 的 `manifest.json`，Runtime 继续提供发布工具的 `summary`。已初始化的 Skills 手动合并这三个随包文件。

2026-11-17：`workflow-development` 与 `validation-and-trial` 明确 Developer 可在任务授权范围内自行编写点击坐标、模板中心点击或键盘操作的 Step，校验发布后指定 Manifest ID 和 Step 逻辑名进行独立试运行，把现场推进到后续开发需要的状态；试运行不限于代码验证。操作后重新观察，现有现场保护及 Runtime 无独立试运行的边界保持。已有 `skills/` 需手动合并这两个随包文件，不自动覆盖用户内容。

2026-11-16：Workflow 指导已按[修订决定](agent-skills-revision-discussion.md)改为局部目标 Step、显式交回和有界循环分派；正常过渡集中等待，验证按变更范围并珍惜现场。替代此前“不能跨状态”“普通超时一律失败”“重试统一 3 次”“稳定后强制完整实跑”的指导；执行器、RunState 及工具权限不变，已有 Manifest 不自动迁移。影响及验证见[专项记录](agent-skills-revision-impact-review.md)。

2026-11-11 Stage 6 已接入 Runtime 只读 Skills；随包指导已更新 RunState、非必要不改调用约定、发布问题简述及当前入口 Recheck。已有用户 `skills/` 仍不自动覆盖，需手动合并随包变更；程序组织的 Runtime 提示始终包含新接口及权限边界。见 [Stage 6 实施记录](stage-6-implementation.md)。

开发 Agent 使用 pi 原生格式的 Skill 按需获取流程指导和只读参考资料；Skill 不授予权限，不执行附带脚本。GUI Construct、GUI Repair 和 CLI Repair 展示同一份目录，实际操作仍取决于本轮工具权限。Runtime 同样可只读加载 Skills，其可操作工具由 Runtime 白名单决定。

## 文件与维护

Skill 位于应用实际数据目录的 `skills/`：默认 Windows 为 `%LOCALAPPDATA%\LALC\skills`，其他平台为 `~/.local/share/LALC/skills`；指定自定义数据目录时随之变化。在开始一轮开发 Agent 消息时按需准备，也可通过 Developer GUI 的 Session “+”→工作区与页面→“打开 Skills 文件夹”初始化并打开持久化源目录，不需要模型请求。

- `skills/` 不存在：创建并复制随程序发布的全部 Skills；检查必需入口存在，不限制额外 Skill 数量。
- `skills/` 已存在：不补齐、不覆盖、不更新，空目录也保持为空。默认内容后续改进由开发者手动合入。
- 开发者直接编辑、新增或移除目录中的文件；没有 GUI 编辑器，Agent 只能读取。若整个目录被删除，下轮会按“目录不存在”重新初始化。
- 同名普通文件或根目录链接会报告错误，不覆盖。目录内链接／特殊文件排除并显示诊断，避免 pi 在发现阶段读到目录外资料。

设置页 Sharing 支持按完整 Skill 目录导出和导入，导入默认不选；同名相同内容跳过，不同内容显式覆盖或跳过。详见 [Sharing](sharing.md)。

每个 Skill 使用 `技能名/SKILL.md`，例如 `skills/my-guide/SKILL.md`：

```markdown
---
name: my-guide
description: 说明流程的用途、何时使用，以及需要哪些已启用工具。
---
# 自定义指导

具体步骤写在这里。需要时先读 references/example.md，再执行当前工具允许的操作。
```

Skill 名遵循 pi 格式，用小写字母、数字和连字符；参考资料和图片可放同目录或子目录。Skill 正文及附图统一使用 `read` 和绝对路径；引用相对路径以 `SKILL.md` 所在目录为基准，解析为稳定绝对路径后再读取。`knowledge_*` 仅访问外部知识库，不用于读取 Skill 正文或附图。这些路径对应数据目录中的 Skill 位置，但由 LALC 映射到本轮固定副本，不直接读取正在编辑的源文件；旧轮临时路径不代表当前访问授权。pi 会处理命名警告、缺 description、重名等诊断；有警告不一定不加载，实际规则沿用 pi。没有 description 的文件不会加载，重名保留先发现的项。

当前复用 pi 的格式、发现及目录生成，不提供完整 pi 终端命令界面、`/skill:name` 或包安装／更新管理。`disable-model-invocation: true` 仍按 pi 规则从自动选择目录隐藏；不要为需要自动使用的自定义 Skill 设置它。`allowed-tools` 元数据不授予 LALC 工具权限。

## 默认指导

| Skill | 内容 |
| --- | --- |
| workflow-development | Workflow 开发流程，按需引用共用规范和验证流程 |
| workflow-repair | 故障定位及最小修复 |
| workflow-conventions | 调用层级、Step 职责、完成证据、Plan 成败日志及源码约定 |
| asset-management | 素材、截图、OCR、预览保存及归档 |
| page-development | 页面整包、配置兼容、Plan 接线和人工安装 |
| publish-and-trial | Validate／Publish／显式版本运行及证据边界 |
| human-feedback | 人工信息／操作请求、Confirm／Skip 含义和后续处理 |

共用规范的 `references/dispatch-and-wait.md`、`references/recovery-rules.md` 分别在修改分派／等待和恢复规则时读取；它们是随 Skill 一起初始化、固定和分发的普通参考文件，不新增默认 Skill 入口。

内置内容保留在 `src/lalc/skills/`，随 wheel 和 Windows 两种包完整发布，仅用于缺失目录的初始化。旧 `sop.md` 已在内容承接后删除；不再解析 XML、不叠加旧 SOP、不自动迁移任意旧安装中自行修改过的 SOP。

## 合并本次指导到已有安装

- 对照应用实际数据目录 `skills/`，合并本次更新的 workflow-conventions、workflow-development、workflow-repair、publish-and-trial、asset-management、page-development，以及后续补充的 human-feedback；workflow-conventions 的两个 references 文件也要复制。保留用户定制条款，消解与新指导冲突的旧规则，不以整目录重置代替合并。
- 保留自建 limbuscompany-knowledge、图片及其他自定义 Skill；本次不需要删除整个 skills 目录，也不自动覆盖已有安装。
- 内置 Agent 下一条用户消息刷新 Skill 副本；远程 MCP 使用接手时固定副本，当前控制会话空闲释放后重新接手才读取新合并内容。不要为刷新中断正在运行的任务。
- 合并指导不等于迁移已发布 Workflow。按实际任务检查受影响调用方、Step 返回、Workflow 分派及过渡等待，再校验发布；不要将旧 None 返回批量认作未达成。

## 生效、权限与日志

每条用户消息开始时刷新目录，并准备本轮独立临时副本；目录、正文和参考资料轮内固定。复制期间内容发生变化或空间不足会明确失败，不把半成品作为可用默认目录。编辑、添加或删除在下一条消息生效，不需要新聊天或应用重载。目录对模型展示稳定路径，内容未变时不会因临时副本换名而改变系统提示词。准备和取消等待复制线程退出后释放临时内容；pi 进程仍可跨轮复用。

系统提示词只包含名称、description 和路径，正文不预先全文注入。模型根据任务按需使用 `read`，使用前必须读取本轮版本，即使历史已读过；一个任务可以使用多个 Skill。此要求由提示指导，接入测试不证明真实模型一定遵循。

`read` 允许当前 Candidate，并把目录中的 Skill 路径映射到本轮固定内容；`edit` 仍只允许当前 Candidate 的授权文件。读到页面或人工反馈指导不代表获得对应工具，Skill 和参考内容不能覆盖系统契约。不执行 Skill 脚本，不新增通用终端权限。

加载警告在当前对话／CLI 及日志中显示；无效项按 pi 规则诊断，其余有效项继续使用，空目录可正常对话。`round-N/input.json` 保留本轮目录，实际模型请求及 read 工具结果保留当时文本／图片，复用现有无损日志。未读取的正文不额外长期归档，临时副本不进入 Sharing。历史 Skill／旧 SOP 消息保持不变，不重放旧操作，也不把历史路径作为当前访问授权。

设计依据见[讨论](agent-skills-decisions.md)和[影响评审](agent-skills-impact-review.md)；实施证据和限制见[实施记录](agent-skills-implementation.md)。

2026-11-08 内置 page-development 已同步 TASKS 多任务声明、逐任务次数开关及专用人工确认启停。已有数据目录的自定义 Skill 仍不自动覆盖；如已有该文件，需人工对照内置版本同步。Agent 工具声明同时包含新契约，旧页面级声明会被拒绝。
