# Construct / Repair Prompt 重构实施记录

日期：2026-11-01。决定与影响范围见 [影响审查](agent-prompt-impact-review.md)，操作说明见 [Agent 指南](agent-repair.md#prompt-与-sop)。

## 当前行为

- `src/lalc/agent_prompts.py` 集中维护 Core、Construct / Repair Mode、严格 JSON 输出语义、三个典型结果示例和精简纠错提示。严格解析器及工具权限实现保持不变。
- `src/lalc/sop.md` 是唯一 SOP 资源，附开发者填写说明。三个正文区为空；每轮开始执行时校验文件并读取当前模式 + Asset，轮内冻结，下一轮读取新内容。缺失、重复或嵌套错误在发出模型请求前明确报告，不静默用空默认值替代。
- `agent_repair.py` 在用户消息中分别组织 Runtime Context 和 User Request，包含模式、入口、Candidate 相对根、来源 Manifest（空白 Construct 为 null）、已有可编辑文件和 Manifest 参考附件。历史不迁移，不自动重放。GUI 标题及历史显示兼容新旧包装，保留用户正文中的标签。
- `pi_probe.ts` 从 `getAllTools()` 获取实际注册名称和描述，按 `getActiveTools()` 过滤，追加工具概览；参数 Schema 不重复注入。预检和格式纠正工具概览为空。预检由扩展使用专用连接 / 图片检查指令，不要求开发结果 JSON；不修改 pi 启动 / 回退路径。独立 `run_probe()` 仍为只读诊断命令。
- `input.json` 保留所选 SOP 正文及宿主 Prompt；每次完整实际请求继续落入 `request-*.json`，含扩展追加内容。动态额度通知仍是 user 消息，系统消息保留停止规则。相关旧文档已纠正。
- wheel、Windows `LALC.spec` 和 ZIP 组装资源检查均包含 `sop.md`；缺失时拒绝组装，已有 ZIP 不受影响。Windows 成品编辑位置为 `_internal/lalc/sop.md`，升级前自行保留填写内容。

## 验证与边界

普通全量回归：

```sh
QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest -q -x
```

结果：**624 passed, 66 skipped**。跳过项未计为通过。覆盖 SOP 合法空正文 / 缺失 / 重复 / 嵌套、请求前失败、消息原文提取、GUI 历史与标题、已有 Session 行为、包装资源缺失及旧 ZIP 保留等。

Agent 接入回归使用真实本地 pi 1.4.0 + 本机 HTTP 替身，不调用真实模型：

```sh
QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest -q -x --run-agent-tests \
  tests/test_agent_repair_agent.py tests/test_pi_probe.py tests/test_developer_session_agent.py \
  -k 'not real_model and not fixed_pure_case'
```

结果：**58 passed, 4 deselected**，4 项真实模型用例明确排除。覆盖实际请求中的工具概览与 Schema 名称集合一致、Construct / Repair 隔离、SOP 轮内冻结及跨轮重读、预检不带开发 JSON 契约、纠正禁用工具、额度、会话恢复及受限工具拒绝。

已实际构建 wheel 并检查 `lalc/sop.md` 和 `lalc/pi_probe.ts` 的字节与源码一致；不将本地构建视为 Windows 成品验收。相关测试共用游戏活动锁，须串行执行；本次早期重叠运行导致的锁冲突结果不计为最终回归结论。

未运行真实模型、`lalc pi-probe` 的真实服务检查、Windows 成品或真实游戏验收；不能据此宣称 Prompt 改进提升了模型成功率。未填写业务 SOP、增加工具权限、迁移历史、加入编辑界面或新增第三方依赖。
