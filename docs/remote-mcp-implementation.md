# 远程 MCP V1 实施与验证

2026-11-15。设计与授权见[逐项记录](remote-mcp-decisions.md)、[ADR 0042](adr/0042-add-an-exclusive-remote-mcp-workbench.md)，实施前的结论见[影响审查](remote-mcp-impact-review.md)。基线提交 `fd3406f`；当前改动尚未提交。本地实施不表示 Windows、真实 Codex 或游戏已经验收。

## 实施范围

- `remote_mcp.py`：独立 Construct 能力白名单、连接令牌校验哈希、本地授权、独占控制凭据、单个持久工作台、固定 Skills 副本、异步操作及本地审批桥接。网络断开不取消、不放权；撤销及 Stop 复用协作取消，启动前再检查撤销／取消，防止检查后启动的竞态。
- `mcp_server.py`：官方 MCP Python SDK 2.x 的 Streamable HTTP；回环监听、Bearer 认证、明确 Host／Origin 范围、工具发现及结构化文本／图片返回。外部没有启停服务、暂停／恢复或 Runtime Recheck 工具。
- `application.py`：同一服务强制远程控制边界，原 Runner 的远程 Developer Trial、Run 启动操作关联、包含 Debug 的五条有界日志缓存；原普通运行和 pi 工具契约保留。
- `manifest.py`：允许受信任内部调用预分配发布 UUID；普通调用仍自行生成 UUID，不改变内容哈希、校验和 Default 规则。操作结果可依据发布提交点及 Run Trace 恢复，无法证明的标未知，不重放。
- `remote_mcp_gui.py`／`gui.py`：Developer GUI 独立“远程 MCP”页；服务、地址、令牌、授权、来源选择、上次使用时间、运行状态与近期操作。本地只读匹配继续可用，现场截图／保存须空闲串行；不为远程 trial 打开阻断调试页的模态运行窗口。
- `page_drafts.py`／`page_preview.py`：明确允许 mcp Construct 入口复用页面服务，保留实际快照审批；本地批准后重启会先撤销远程控制并等清理，不保留旧授权。内置 pi Session 恢复逻辑未复用为外部对话。
- `__main__.py`：CLI 相关写入及开发入口检查远程控制锁。锁范围仍为当前系统用户，不扩大为跨用户或操作系统沙箱。
- 可选 `mcp` 依赖及锁文件、Windows 打包元数据／许可证、中文翻译资源、领域术语及文档入口已更新。暂存继续使用普通 `work_files`，Skills 固定副本使用应用工作目录，同盘提交阶段在目标父目录。

实现时采用的保守口径：素材归档始终本地确认；重置令牌一并撤销；更换来源只替换 Candidate／基线，保留页面草稿；接手时固定既有全局历史／知识库／Manifest 查询开关。内置模型配置与请求额度不进入 MCP。

## 执行验证

最终相关默认回归（未使用 `--run-agent-tests`）：

```sh
QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest -q \
  tests/test_remote_mcp.py tests/test_remote_mcp_gui.py \
  tests/test_developer_policy.py tests/test_developer_gui.py tests/test_user_gui.py \
  tests/test_gui_language.py tests/test_template_match_lab.py tests/test_page_package_tools.py \
  tests/test_process_lock.py tests/test_developer_session.py tests/test_windows_packaging.py
```

结果：**179 passed, 1 skipped**。跳过项不算通过。真实回环 HTTP 测试在允许本地监听的环境执行；它通过协议读取、修改、发布、试运行、查询及释放，游戏执行使用替身，不启动 pi 或调用模型。

新增测试还覆盖：另一控制会话拒绝、凭据不落日志、重置撤销、最新版本与 Default 区别、Candidate／路径保护、相同操作编号去重及参数冲突、审批取消及迟到答复、发布证据恢复、崩溃未知不重放、运行中五条 Debug、撤销与启动竞态、本地辅助调试门控、HTTP 认证／Origin、本地页面批准实际安装、用户配置冻结及释放恢复。

静态检查：

```sh
.venv/bin/pyright --pythonpath .venv/bin/python \
  src/lalc/remote_mcp.py src/lalc/mcp_server.py src/lalc/remote_mcp_gui.py
```

结果：0 errors、0 warnings。`git diff --check` 通过；中文 QM 已重新生成，并以离屏截图检查新页布局，不能替代 Windows 原生显示验收。

## 广泛回归的已知限制

单进程默认全量回归在约六成进度发生 Qt 原生段错误，未完成；不能报告全量通过。随后按 87 个测试文件串行隔离巡检，当时汇总为 1437 passed、132 skipped、9 failed，`test_user_pages.py` 进程结束时仍出现原生崩溃。末轮新增的撤销竞态、隐私开关和审计恢复测试另包含在上面的最终相关回归中。

对巡检中的每项失败使用 `git archive HEAD` 导出的未修改 `fd3406f` 源码作隔离对照，均复现：

| 测试 | 已复现的基线问题 |
| --- | --- |
| `test_agent_skills::test_defaults_initialized_once_and_empty_directory_stays_empty` | 实际默认资源另含 `limbuscompany-knowledge`，测试断言只列旧集合。 |
| `test_input_activity::test_evidence_path_follows_refreshed_observation_after_focus_wait` | 测试仍要求 `.png`，当前日志证据为 `.avif`。 |
| `test_manifest_transition::test_production_action_registration_is_shared_and_not_manifest_owned` | 预期 Action 集合未包含 `control.scroll`。 |
| `test_page_availability::test_source_label_fixed_session_and_new_selection` | 测试预期空来源，当前新对话默认选择最新 Manifest。 |
| `test_user_gui_p0` 的其他 provider 配置及两项 API key 对话框检查 | 原源码同样存在 provider 预期／密钥索引不一致。 |
| `test_user_pages::test_single_editor_handoff_autosaves_and_restores_independent_selection` | 原源码同样返回 deepseek，而测试要求 llama.cpp。 |
| `test_user_pages::test_reload_through_real_process_restores_both_windows_and_rescans` | 在相同本地 IPC 权限下单独对照原源码，均未生成 ready 标记。 |

基线 `test_user_pages.py` 也出现退出信号 11。未扩大本次范围修复这些问题；原生崩溃原因未定。上述对照不代表本次所有行为均已证明无回归。

## 尚未完成的验收

- Windows 成品构建、SDK／HTTP 依赖在两种包中的实际启动。
- 两台设备的 Tailscale HTTPS、转发头、真实断网／休眠／重连。
- Mac Codex 桌面应用的配置、令牌可见性、工具图片显示和控制凭据续接。
- 真实游戏的构建 → 发布 → 试运行 → 修复闭环及输入接管。

任意不合作的 Python 代码仍不能保证立即停止；致命清理错误不自动恢复本地执行权。真实跨设备验收按[接入指南](remote-mcp.md)进行，不能用替身测试代替。
