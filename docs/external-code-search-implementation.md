# 外部搜索与 Agent 进程复用：本地实施记录

2026-11-05。开发者已明确授权开始实现，并要求 hybrid 工具描述简要说明与 literal 的区别。依据 [ADR 0038](adr/0038-use-versioned-reference-search-and-reusable-agent-processes.md)、[16 项决定](external-code-search-decisions.md)与[影响审查](external-code-search-design-impact-review.md)。当前为本地实现与替身验证，不表示开发者验收、Windows 成品或真实环境验收。

## 实现

- `src/lalc/knowledge.py`：统一解析当前 A/B 版本，更新前磁盘预检，独立副本 fetch／reset／索引／查询验证后发布。成功才替换指针；不足、ENOSPC、取消或构建失败保留 A 并返回 update 错误、记日志。明确 fetch upstream refspec，远端删除分支不再沿用旧引用冒充最新。各仓库独立处理，同轮自动尝试一次；未变化的提交及内容复用索引。
- `src/lalc/codesearch.py`：固定基础版／MiniLM 资源检查、离线准备、受限 Git 工具路径、显式建索引和本机只读查询。索引前验证真实 Git 根，拒绝上溯父仓库或外部工作区。程序缺失／模型错误直接不可用，不下载。沿用 pi 的冻结 DLL 环境隔离。注册集合不变、进程仍存活则复用；已退出的服务在下次需要时重建。
- `src/lalc/pi_process.py`、`pi_probe.py/ts`：宿主保留进程，用读线程搬运协议事件，避免跨轮异步管道绑定已关闭的事件循环。每轮由固定配置文件重载根、历史、权限、额度与提示；密钥不写该文件。连接配置变化时重建。旧进程在准备本轮时失效可重启一次；本轮发送后中途退出不重放。取消／异常丢弃不安全进程；宿主关闭尝试回收两个进程，即使一方清理失败也会尝试另一方。
- `ApplicationService`／CLI：延迟持有 pi 和 codesearch，宿主退出／重载关闭，独立于 Developer GUI 是否存在；没有增加保活、轮询健康服务或通用管理框架。
- Python 策略、分发和 TypeScript 工具声明同步将 knowledge_search 改为 knowledge_search_literal，并新增 knowledge_search_hybrid。hybrid 描述明确“语义相关代码”与 literal 的“不区分大小写原文子串匹配”区别，建议英文 query。结果返回仓库、提交、哈希与 knowledge_read 参数；读取拒绝变化后的文件。历史记录不改写、不重放，CLI／Runtime 知识库权限不扩大。
- 列目录和页面资源复制沿用不 fetch 的约定，通过同一知识库路径解析读取当前可用版本。原 clone 是发现／初次准备入口，Agent 的默认文件来自知识库版本目录，具体路径含义见[用法](external-code-search.md)。
- `scripts/build_windows.py`：从同一应用主体产出 with-agent／without-agent，前者附完整 pi、codesearch 基础版、固定 MiniLM 和许可声明，后者可使用外部安装。检查程序 ZIP／模型哈希及两包公共内容；本轮准备了官方 Windows codesearch 1.7.9 ZIP 并核实摘要，但未在 macOS 构建 Windows 程序。

未新增运行依赖、MCP 通用客户端、符号分析工具、自动下载、外部仓库执行、云端检索、后台保活或跨仓库整体事务。

## 验证

按顺序串行执行，普通回归与显式 Agent 接入未并行。跳过项不计为通过。

| 检查 | 实际结果 |
| --- | --- |
| 普通全量 `QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest -q` | 877 passed，98 skipped，58.11s |
| 随后针对最终资源／根路径／版本／退出逻辑的普通测试：test_codesearch、test_knowledge、test_pi_startup、test_windows_packaging | 60 passed，14.88s |
| 显式 Agent：test_agent_repair_agent、test_developer_session_agent、test_external_search_agent | 83 passed，4 skipped，92.86s |
| 随后对最终进程重建／取消／真实搜索的显式检查：上述 external_search 测试及 cancel_reaps／cancel_waits 选择 | 8 passed，43 deselected，11.48s |
| scoped pyright：codesearch.py、pi_process.py、knowledge.py、scripts/build_windows.py | 0 errors，0 warnings |
| git diff --check | 通过 |

普通测试覆盖磁盘不足前置失败、构建 ENOSPC 后 A 保留、首次无索引的字面降级、缺模型不启动下载、Git 根上溯拒绝、远端分支删除、未变化时不重建索引、搜索后的文件哈希变化、嵌套／保留目录拒绝、旧进程准备时中断只重启一次、双包内容及模型／程序篡改、清理失败仍回收另一进程。

真实接入仅使用本机 HTTP 替身、临时本地 Git 数据及已准备的 codesearch／模型：覆盖不同事件循环跨轮复用 pi、连接配置改变后重建、实际进程中途死亡不重放、下轮重启、真实混合搜索及哈希读取、codesearch 重启和未变化时进程复用、现有完整 Session／图片／页面／工具循环回归。没有请求真实／付费对话模型或操作游戏。

扩大到 agent_repair.py／application.py 的类型检查仍有动态类型推断诊断，未作为全项目类型检查通过；上表仅报告所列四个核心文件。普通全量数字对应其实际执行时点，之后新增的边界断言由列出的定向检查覆盖，不把 deselected 计作通过。

## 未验收与保留

Windows 原生 PyInstaller 双成品、DLL／Git 路径兼容、进程树与 mmap 清理、断网首次加载、真实远端认证、真实双参考仓库／大仓库性能仍待开发者环境验证。磁盘预算是实际可用空间估算，不是空间预留；Git 新对象量不可精确预知，实际写入错误仍会失败保留 A。JSON 指针替换与正常进程中断有小样本证据，不宣称断电或损坏磁盘事务保证。

本轮保留此前验证代码、输入、资源与成功／失败结果：`tests/experiments/` 与 `.generated/external-search-validation/`。未按“验证通过”自动清理；等待开发者明确确认本次验证结束后再处理。生产版本目录的过期副本清理不触及这些证据。
