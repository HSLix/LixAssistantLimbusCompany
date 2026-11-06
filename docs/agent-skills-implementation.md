# Developer Skills 实施记录

2026-11-06，按[已确认设计](agent-skills-decisions.md)和[影响评审](agent-skills-impact-review.md)实施。当前 SOP 正文及 Core／Mode 详细指导先迁入七个默认 Skills，随后删除旧 sop.md、XML 解析和旧资源引用；不提供双轨加载或任意旧安装 SOP 自动迁移。

## 实现

- `src/lalc/skills/` 提供 Workflow 开发、故障修复、共用编写规范、素材、页面、验证与试运行、人工反馈七个原生 SKILL.md。保留原指导中的外部知识库适配、完整匹配与歧义、OCR／语言限制、素材少文字建议、页面配置兼容、Plan 接线和审批／证据边界；共用规范只维护一份。
- `agent_prompts.py` 精简角色、模式及安全原则，最终 JSON／格式纠正契约保持；指定领域句在宿主 Prompt 后部独立展示。Skill 使用规则明确本轮使用前重新读取、相对引用以 Skill 所在目录为基准、知识不授予权限。
- `agent_skills.py` 只在数据目录缺少 skills/ 时准备完整默认目录并提交；已有目录不补齐或覆盖。初始化复用跨进程锁，失败不留下已命名的半成品默认目录。开发者直接维护文件，Agent 没有写入工具。
- 每轮在后台线程流式固定正文和附带资料，复用现有 FileContent／copy_content 及容量检查；复制期间文件变化明确失败。根目录必须是普通目录，子级链接和特殊文件排除并诊断。临时副本在交给 pi 发现前已经限制可见范围，避免原生发现跟随链接；不将全部内容常驻内存。
- 快照由本轮 async context 持有。准备取消时通知线程、等待退出再删除；轮次正常、错误或取消后释放。清理失败保存明确错误、用户历史和结果，不跳过轮次留存。
- `pi_probe.ts` 调用 pi 1.5 的 loadSkills／formatSkillsForPrompt，使用显式本轮目录及 includeDefaults=false；保留个人配置、扩展、模板和 Skill 自动发现的隔离。Skill 元数据实际拼入最终系统消息，不被现有宿主 Prompt 覆盖。
- `read` 把目录中稳定的 Skill 绝对路径映射到本轮固定副本，不直接读取源文件；固定副本的路径同样检查，Candidate 的既有读取仍可用；edit 的 Candidate／授权文件检查保持。接回 pi 原生图片检测，以便 Skill 参考图片按图片返回，读取前同样检查路径。
- `pi_process.py` 将 Skill 路径加入既有 round.json 轮次传递，不把变化的临时路径加入命令签名；pi 仍可跨轮／Session 按原契约复用。工具权限、额度、格式纠正、历史重放过滤及中途退出不重放行为不变。
- 为保持内容未变时的跨轮系统消息前缀，目录展示数据目录下的稳定逻辑路径；实际读取仍限本轮副本。初次完整 Agent 回归暴露了随机临时路径导致的前缀变化，已通过此映射修正。
- 原生诊断和路径排除诊断作为 skill_warning 保存，并在 Workbench 对话和 CLI 显示。原生无效文件／重名规则不另写解析器：有效项继续使用，空目录可以正常工作。
- input.json 保存本轮目录，实际 read 文本／图片及模型请求复用现有无损日志。只保存元数据而非未读正文；临时工作副本不留在长期日志和 Sharing 中。旧历史不改写，旧路径不作为当前访问授权。

## 资源与文档

wheel 递归收集 `lalc/skills/`；PyInstaller 收集整目录，Windows 组装检查七个必需 SKILL.md。默认资源仅供初始化；应用更新不覆盖数据目录中的既有内容。`docs/agent-repair.md`、Windows 构建说明和当前状态入口同步到 [Developer Skills 用法](agent-skills.md)。历史 SOP 评审／实现及 pi 升级记录保留旧证据，通过后续链接说明替代关系。

最终当前文档链接、默认 Skill 间引用及 `git diff --check` 检查通过。

构建检查发现旧 `build/lib/lalc/sop.md` 可混入直接复用构建目录的 wheel；已清除该过期生成文件。使用标准 `uv build` 先生成 sdist，再从干净 sdist 构建 wheel，实际归档包含七个 Skills 且不含旧 SOP；独立离开源码目录初始化验证通过。

## 验证证据

所有 Agent 检查使用全局 pi 1.5.0 和本机 HTTP 替身，不访问真实模型或操作游戏；普通回归与 Agent 回归分开串行。

1. 首轮文件／Prompt／组包检查：

   ```sh
   QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest -q \
     tests/test_agent_skills.py tests/test_agent_prompts.py tests/test_windows_packaging.py
   ```

   22 passed。后续补充初始化竞争、错误清理及 UI 警告检查，见下列针对性结果。

2. 默认回归：

   ```sh
   QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest -q
   ```

   941 passed、106 skipped、3 failed，进程退出码 1，不能报告全量通过。两个 `test_example_workflow.py::test_exp_mirror_pages_feed_plan_and_shared_actions` 参数化用例仍期待已删除的 exp.py／exp Task 调度，与本次迁移无关。另一个 `test_user_gui.py::test_empty_navigation_groups_expand_and_compact_without_extra_pages` 在 offscreen 导航展开高度断言失败；单独复测通过，本轮未修改该 GUI 行为，不能把单独通过视为整个套件无问题。

3. 新增／修改边界及上述 GUI 项针对性复测：

   ```sh
   QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest -q \
     tests/test_agent_skills.py tests/test_agent_prompts.py tests/test_windows_packaging.py \
     tests/test_developer_gui.py::test_gui_warning_stays_visible_after_progress_events \
     tests/test_user_gui.py::test_empty_navigation_groups_expand_and_compact_without_extra_pages
   ```

   28 passed。覆盖空目录与自定义内容保护、复制失败回滚、初始化排他／人工新建目录、取消等待线程清理、源文件变更拒绝、失败结果留存、警告可见、Prompt 以及七个资源的组包要求。

4. 新增 Skill 真实 pi 检查：5 passed；首次图片用例失败，发现自定义 read operations 未接原生图片检测，补齐后该文件全部通过。覆盖三个开发入口、目录不含正文、正文及引用轮内固定、跨轮增改删和 PID 复用、只读范围与 Candidate 权限、诊断／空目录、日志独立还原和图片留存。

5. 完整相关 Agent 回归：

   ```sh
   QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest --run-agent-tests -q \
     tests/test_agent_skills_agent.py tests/test_agent_repair_agent.py \
     tests/test_developer_session_agent.py tests/test_external_search_agent.py \
     -k 'not real_model and not windows_saved and not windows_real and not real_codesearch'
   ```

   首次结果为 86 passed、5 failed、5 deselected；五项失败均为旧有跨轮前缀检查（额度通知及四种 DeepSeek 配置），发现随机工作副本路径会改变系统消息。保留原断言并修正实现：目录展示稳定路径，read 映射本轮副本。针对性复测 10 passed、40 deselected；随后完整相关集合重新运行，最终 **91 passed、5 deselected**，退出码 0。五个显式排除的真实模型／Windows／codesearch 用例不计通过。

6. 资源实际构建：

   ```sh
   UV_CACHE_DIR=.generated/uv-cache uv build --offline --out-dir /private/tmp/lalc-skills-dist
   ```

   sdist／wheel 构建通过。检查 wheel 的七个 SKILL.md 和旧 SOP 缺席，并以独立 Python 进程从临时解包的 wheel 导入、初始化全部默认 Skills，通过。未在主环境安装该 wheel，也未构建 Windows 程序。

## 剩余验收与限制

- 未调用真实模型、运行 Windows 原生成品或游戏；未测量上下文成本、速度、磁盘大目录性能或真实模型选 Skill／重读的可靠性。
- Windows junction／实际权限与冻结资源初始化需原生验收；macOS 的替身和归档检查不能替代该证据。
- 当前提供 pi 原生格式和发现，不新增完整 `/skill:name` 命令界面、包管理器或 allowed-tools 授权。disable-model-invocation 项按原生规则不进入自动选择目录。
- 默认回归仍有上述未解决项，既有示例及 offscreen GUI 的整套执行稳定性不属于此次迁移修复范围。
