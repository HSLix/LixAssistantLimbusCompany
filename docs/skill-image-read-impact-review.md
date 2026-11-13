# Skill 图片读取与知识库错误提示影响审查

2026-11-13。依据本轮用户确认的两项要求，先完成只读审查，再实施；不改变读取权限、目录映射或大小限制。

## 设计变化

- 原指导要求 Skill 正文通过 `read` 按需读取、相对引用以 Skill 目录为基准；现明确正文及附图统一使用 `read` 和绝对路径，`knowledge_*` 仅访问外部知识库。
- `knowledge_read` 原来合并报告文件缺失与超过 2 MiB；现分别报告路径错误和大小超限。仍使用 ValueError，经工具分发返回原有错误结构。
- 不废弃工具或参数，不迁移数据，不扩大 Skill 或知识库权限；与现有 [Developer Skills](agent-skills.md) 及 [外部搜索](external-code-search.md) 边界一致，无需新增 ADR。

## 已确认的差距与影响

1. 分享日志 `objects/0/log/events.jsonl` 的当轮记录先成功读取 `skills/limbuscompany-knowledge/SKILL.md`，随后用 `knowledge_read` 请求 `limbuscompany-knowledge/mirror-select-ego-gift-page.png` 并失败。它引用的图片属于 Skill；失败调用未使用正确读取入口。
2. `agent_prompts.SKILL_GUIDANCE` 只明确正文读取，未明确附图入口及与 `knowledge_*` 的区别。`system_prompt()` 供 Construct／Repair 使用；`pi_probe.ts` 的 `read` 工具说明需要同步明确图片和绝对路径。现有 `checkedRead` 已将 Skill 绝对路径映射到本轮固定副本，不需要修改其验证或执行逻辑。
3. `RepairTools.knowledge_read → KnowledgeLibrary.read → path/source_path` 只解析知识库目录；`read` 在文件检查处将不存在和超限合并为同一错误，容易导致错误归因。拆开检查仍保留读取后字节数检查、哈希验证及图片格式校验。下游工具分发保留错误文本，没有需要迁移的错误码或结果字段。
4. 已检查 `tests/test_agent_prompts.py`、`tests/test_knowledge.py` 和既有 `test_skill_reference_image_survives_source_and_snapshot_cleanup`。前两者适合补充指导和错误分支回归；后者覆盖 pi 的 Skill 图片读取，但属于显式 Agent 集成测试，本次不将其存在视为执行通过。

## 潜在风险与实施顺序

- 分享包不保留未读取 Skill 的原始附图，无法确认 Windows 当轮原图是否存在或大小；本地同名图片大小不能证明远端状态。
- 提示明确后真实模型仍可能选错工具，需真实模型另行验收。既有用户 Skills 不自动覆盖；本次修改常驻 Prompt，无需迁移用户 Skills。
- 顺序：更新常驻提示与工具说明 → 拆分知识库检查并补充普通回归 → 同步两份使用文档 → 记录验证结果。不运行真实 pi／模型或游戏。

## 验证

已完成上述实现和文档同步。执行 `.venv/bin/python -m pytest -q tests/test_agent_prompts.py tests/test_knowledge.py`：42 passed（24.38s），覆盖 Construct／Repair 提示、缺失文件、目录误传、大小超限及既有知识库读取边界。`git diff --check` 通过。

未运行全量回归、显式 Agent 集成测试、真实模型、Windows 成品或游戏验收；工具说明文字经源码检查，未启动 pi。工作区已有的 `workflow-conventions/SKILL.md` 修改保持原样。
