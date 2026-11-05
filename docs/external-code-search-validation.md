# pi 复用与外部代码搜索：设计验证结果

2026-11-05。本轮只增加验证代码与文档，没有修改生产实现。验证代码、资源与失败／成功证据均保留；开发者明确确认本次验证结束前不清理。已确认目标见[设计记录](external-code-search-decisions.md)，首次检索小实验见[调研记录](external-code-search-research.md)。

## 运行与证据

- 入口：[验证套件](../tests/experiments/test_external_search_validation.py)、[pi 扩展原型](../tests/experiments/reusable_pi_extension.ts)、[复跑说明](../tests/experiments/README.md)。
- 使用 macOS ARM64、实际 pi 及官方 codesearch v1.7.9 基础包；pi 请求只连接已有本机 HTTP 替身，不调用真实／付费模型或游戏。
- 显式命令：`QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest --run-agent-tests -q -s tests/experiments/test_external_search_validation.py`。
- 最后一次整套运行 **6 passed in 7.22s**。随后检查发现第六项两个失败注入目录尚未初始化为独立 Git 仓库，codesearch 自动上溯到主项目执行文件发现；模型失败／强杀发生在生成主项目索引之前，检查主项目没有 `.codesearch.db`。已修正样本、增加实际数据库路径与文件数断言，单独重跑第六项：**1 passed, 5 deselected in 0.76s**。第六项仅采信修正后的结果，先前整套通过不证明原失败样本隔离正确。
- 前五项有效证据分别为 `.generated/external-search-validation/run-008w_m4q/`、`run-dbt3idcm/`、`run-_cp6rhej/`、`run-u7eg_jv7/`、`run-d_xsk9yr/`；修正后的第六项为 `run-f1tqz5k0/`。初轮错误假设和原型失败结果保留在更早的 run 目录，不计为通过证据。
- 可复用依赖保留在 `.generated/external-search-validation/resources/`，含二进制版本／哈希来源 manifest；首次实验脚本与输出另存 `initial-probe/`，不依赖仅有临时目录中的验证脚本。

## 已验证结果

| 验证项 | 结果与边界 |
| --- | --- |
| 原生产扩展在一个 pi 进程内执行 new_session | 两次请求均可完成：new_session 会重新初始化扩展、重置额度；但宿主改变原 env 字典不会改变存活子进程的启动根目录。不能简单把旧进程留着并继续按原来方式配置 |
| pi 同进程换轮 | 原型在同一 PID 内切换文件根、宿主历史、系统提示、工具集合、模型 ID 和独立请求额度。第二轮只声明读工具，读取 B 的内容，未混入 A 的消息／提示 |
| pi 取消与中途退出 | abort 后仍可在同 PID 开始新轮；执行中主动 exit(7) 后 RPC 明确 EOF，不自动重放；下一次显式启动获得新 PID，重新配置后可以完成新轮 |
| codesearch A/B 内容与索引 | 在两个独立目录分别 reset 到确定提交并建索引，以一个小 JSON 指针发布可用版本。未发布 B 不改变 A，发布 B 后搜索和读块同时对应 B；只读服务拒绝 reindex，样本数据文件哈希未变 |
| 真实建索引失败／强杀 | 缺少模型且模型端点不可达时明确失败；另一个 B 构建在 Phase 2 被 SIGKILL。重开服务后保留 A 的文件和索引仍可搜索和读块；没有声称上游的原地增量更新能自行回滚 |
| 模型缓存加载 | 两个样本索引与查询在 `HF_ENDPOINT=http://127.0.0.1:9`、已准备缓存条件下成功，不需要可访问的 Hugging Face 端点。这不是操作系统级全网络流量审计，也不是 Windows 离线验收 |

pi 原型验证的是 SDK 能力，不是正式 GUI／CLI 已完成复用。当前 GUI 每个 Operation 使用独立 `asyncio.Runner`（`developer_gui.py:Operation.run`），CLI 循环每轮调用 `asyncio.run`（`agent_repair.py:run_repair`）。异步进程管道不能直接挂到下一轮新建的事件循环；正式接入必须给持久进程一个稳定的传输／事件循环所有者，再接入现有取消和退出路径。尚未对 Qt 跨线程接线、图片、完整工具集、不同服务地址／密钥切换做验证。

## 已确认的上游隐含行为

### 只读配置不等于禁止符号辅助程序

在带 tsconfig.json 的仓库上，`repo_read_only=true` 仍实际调用了指定的 TypeScript 辅助程序。探针仅写标记并退出，没有安装或运行真实 SCIP 分析器。证据为第四项的 helper-invoked.json 与 helper-observation.json。

同一服务使用 macOS 系统工具 PATH（`/usr/bin:/bin`），并移除显式 SCIP 路径覆盖后，状态显示 `ts_helper=false`、`csharp_helper=false`。这证明本机可用小范围子进程环境限制避免自动符号分析，但还不能证明 Windows Git／系统工具路径兼容或所有辅助程序都被禁用。生产不得仅因不暴露 find_impact 就宣称不执行辅助程序。

### get_chunk 的陈旧提示不是哈希校验

保留源码原 mtime 后替换内容，get_chunk 仍返回旧索引内容且没有 note。证据为第五项的 staleness-results.json。因此不应以 note 缺失证明索引与文件相同；结果需绑定可用版本，并通过现有文件哈希／版本验证读取。直接请求附加 context_lines 还涉及读取实时文件，不能在无校验时把其与旧索引正文拼成同一版本。

### index 会自动上溯 Git 根目录

失败注入样本最初只建了普通子目录，codesearch 将其提升到父级主项目根进行文件发现。本次修正为独立 Git 仓库，并固定数据库路径断言。正式注册与构建前必须验证 Git 顶层路径就是允许的仓库根，不能只检查传入目录位于 knowledge 内。不能把普通文档目录误当作 Git 参考仓库注册。

## 方案建议，不自动视为新决定

1. pi 使用稳定的进程／传输所有者；每轮通过固定配置文件与受控命令／new_session 重建轮次状态。扩展切换后旧 ctx／pi API 会失效，必须在新一代回调中配置；首次原型违反此边界得到明确 stale ctx 错误，修正后通过。不要手写一套逐字段重置聊天状态的复杂框架。
2. 为满足失败保留 A，优先保留已完成的 A 文件＋索引，在独立 B 中构建，通过一个可恢复的版本指针发布；读工具统一解析当前可用版本。这个机制需额外磁盘空间，属于实现前需确认的成本，而不是已经批准的存储设计。测试只覆盖指针替换前构建失败及成功替换，没有覆盖写指针过程中断电、磁盘损坏或 Windows 文件占用。
3. codesearch 的 serve 作为只读查询进程，索引构建由宿主显式启动，避免后台监视破坏 A/B 发布边界；同时限制符号工具发现，不能只设置 repo_read_only。
4. 搜索返回仓库、可用提交／索引身份、相对文件与位置；正文读取优先复用带哈希校验的 knowledge_read。是否还暴露专用读块接口留影响审查比较，当前不增加多余工具。
5. 启动前检查模型文件已准备好；资源缺失直接报告混合搜索不可用。不能依赖上游在初始化失败前自行遵守“不下载”的产品规则。

## 资源许可与未验证项

codesearch 源码标注 Apache-2.0；本次实际模型缓存为 Xenova/all-MiniLM-L6-v2，模型卡与原始 sentence-transformers/all-MiniLM-L6-v2 均标注 Apache-2.0，来源：[ONNX 模型卡](https://huggingface.co/Xenova/all-MiniLM-L6-v2)、[原模型卡](https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2)。正式打包仍须固定文件哈希、保留适用的许可／声明并核对二进制依赖资源；这不是完整依赖许可审计。

未验证 Windows 成品与进程树回收、真实双参考仓库／大仓库、真实模型、GUI 全链路、首次网络安装、全局断电恢复及完整冷启动基准。先前自然语言检索小样本不计为这些项目的验收。
