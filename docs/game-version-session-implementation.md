# 游戏版本与 Agent 历史关联：实施记录

2026-11-01。开发者已整体确认[设计决定](game-version-session-decisions.md)及[影响审查](game-version-session-impact-review.md)，并授权实施。规范取舍见 [ADR 0035](adr/0035-associate-agent-history-with-per-round-game-observations.md)，当前用法见[游戏版本历史](game-version-history.md)。以下本地实施不等同于开发者 Windows 成品 / 真实模型 / 游戏验收。

## 已实现

- `game_version.py`：Steam 客户端设置 / 缓存、多库 VDF 定位、无递归自动发现、有效路径优先与歧义拒绝；Build ID 和游戏版本独立读取，失败有诊断且不阻断对话。非 Windows 明确不可用，不探测本机其他游戏环境。
- UnityPy 1.25.4 加入 automation，更新 uv.lock。游戏版本按 PlayerSettings.bundleVersion 读取；已验证四字节兼容例外绑定引擎、文件格式和类型树签名，不使用字节偏移 / 字符串搜索。
- `agent_history.py`：每轮观测日志文件及事件、自包含日志事实、SQLite 增量索引、UTC 时间规范化、当前组合独立最近时间、明确缺失 / 损坏报错和显式 history-rebuild。索引锁竞争 / 写入失败保留日志事实并诊断，空闲重建可恢复。
- 开发对话在 GUI / CLI 共用的轮次入口采集，保存到用户 runtime_context 和 input；预检 / 格式纠正共享本轮观测，不新增观测。恢复保留原始上下文，不修改旧轮次。GUI 连接 / 模型 / 独立设置错误诊断开始时同样留证。
- 三个工具同步接入 Python 入口权限、宿主分派和 TypeScript Schema：list_game_versions、search_agent_sessions、read_agent_session。完整 / 部分缺失的组合可精确筛选；单独版本字段可跨组合查询；历史旧轮次可显式读取并显示 Unknown，不补索引。
- 历史内容按完整事件序号和字符片段有界返回，图片先列引用，显式请求后才读取并校验；沿用路径 / 哈希 / 脱敏边界，不通过恢复 Session 读取。自读活跃日志不争用 Candidate 锁，未写完尾部只报告、不修复原文件。
- User GUI 通用设置增加 Steam 客户端目录选择 / 保存及中英翻译；验证失败不覆盖既有地址，设置与发现缓存共用数据文件。标题规则移入不依赖 Qt 的共享模块，GUI 与 CLI 索引共用。
- 删除独立 pi-probe 命令、专用循环及测试；共享 pi_probe.py / pi_probe.ts、启动回退 / RPC / 证书逻辑和正式预检保留。HTTP 服务替身从被删除测试提取到 agent_test_server.py，正式集成测试继续使用；普通测试补充个人配置隔离参数检查。
- Windows 冻结配置收集 UnityPy 离线类型树资源及递归依赖元数据 / 许可，组包检查 lzma.tpk 存在；更新第三方说明。未在 macOS 执行 Windows 构建。

## 本地验证

- 普通串行回归：`QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest -q` → **694 passed，63 skipped**，33.26 秒。默认跳过 Agent 测试；跳过不计通过。
- 指定 Agent 串行回归：`tests/test_developer_session_agent.py` 与 `tests/test_agent_repair_agent.py`，显式 `--run-agent-tests`，仅选新增历史工具、Session 图片恢复、多文件权限、SOP / 工具概览、传输错误无重试、逐轮额度及取消 → **13 passed，46 deselected**。实际 pi 对本机 HTTP 替身，不调用真实模型。
- 最终工具 Schema 增加精确版本组（包括 null 字段）后，再选三个新增工具往返用例：**3 passed，11 deselected**，覆盖 GUI Construct、GUI Repair、CLI Repair 及空字段组合；与前项有重叠，不相加计数。
- 新增模块及直接共享契约定向类型检查：`game_version.py`、`agent_history.py`、`agent_log.py`、`agent_prompts.py`、`agent_policy.py` → **0 errors，0 warnings**。未将其报告为整个项目类型检查通过。
- 用户附件实际读取 `1.118.0`；临时副本将版本字符串替换为同长度 `1.119.0` 后，实际字段解析返回新值。原附件未修改，未将游戏文件加入仓库。UnityPy 离线 lzma.tpk 资源实测可读，207,720 字节。
- 日志去重 / 引用、Unknown / 部分组合、A→B→B 时间、重复写、索引失败留证、丢失 / 损坏重建、重建失败保护原数据库、并发成功写入、过滤 / 长文本续页、图片延迟读取 / 哈希 / 轮次校验、路径越界、手工 Steam 保存及 CLI 删除入口均有本地测试覆盖。
- Qt 中文翻译重新生成；源码编译与本次文档本地链接检查通过，差异空白检查通过。

验证中曾将普通回归与 Agent 回归并行启动，因项目全局游戏锁争用造成失败；随后改为串行，得到上述通过结果。未为避免争用而弱化生产锁或测试锁。

## 未验证与保留限制

- 未进行 Windows 注册表 / 磁盘真实发现、真实多库迁移、冻结成品执行或 Windows 原生 GUI 专项验收。
- 未调用真实模型或执行真实游戏操作；用户此前 PowerShell 实测属于原验证脚本，不冒充本次完整产品验收。
- 未验证其他 Unity / 游戏版本；四字节尾部具体含义仍未知。未知布局可能让游戏版本获取失败，此时 Build ID 独立继续。
- 客户端版本与 Build ID 不覆盖所有游戏内热更新或服务器变化，不自动判定历史经验有效性。
- 不导入旧历史，不提供语义搜索、摘要或人工历史浏览页；Runtime 接入仍留 Stage 6。
- 未提交 Git、发布 issue、关闭 issue 或覆盖工作区已有其他改动。
