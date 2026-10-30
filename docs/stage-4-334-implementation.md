# #334 本地实施与待完成的 Windows 成品验收

2026-10-30：开发者确认[影响评审](stage-4-334-design-impact-review.md)后授权继续实施，并指定源码根目录 `pi_resources/` 放置 pi 原始归档。已完成以下本地实现及验证；尚未提交本轮 Git 变更，尚未在 Windows 生成／运行成品。#334 保持开放，开发者确认验收后才关闭。

## 已实现

- `scripts/build_windows.py` 在 Windows x64 使用独立、非 editable 的构建环境和现有锁文件；默认读取忽略目录 `pi_resources/pi-windows-x64.zip`，支持 `--pi-zip`。校验固定官方 1.4.0 归档摘要、版本与解压路径，再从一次应用构建组装含／不含 pi 两个 ZIP，核对公共文件一致并输出 SHA256SUMS。记录实际源码文件摘要（含未提交源码）、commit、锁文件、Python／已安装依赖版本及 pi 来源。
- 保留完整上游 pi 运行目录并补带 MIT 许可；没有把 `pi_resources/` 整目录、业务数据、用户配置、草稿或示例加入应用 ZIP。用户提供的文件已经在该目录，未搬移或删除 Downloads 原文件。已读取其内容核实版本与 SHA-256，与接受的官方发布记录一致。
- 默认 pi 随包优先，再查环境；保留显式 `--pi`。版本探测、启动或 ready 前退出可在清理后回退一次；缺随包时记录原因并直接选环境。版本不符只警告。路径／版本／回退原因进入日志，密钥不进入命令参数或记录。
- 同一轮 PiStartup 贯穿模型预检和正式修复。发送第一个模型 prompt 前关闭回退，部分写入失败也不重发；预检后进程启动失败、模型错误、超时、协议／工具集错误、取消及清理错误均不触发回退。版本探测有明确等待上限。冻结进程为 pi 隔离自身库路径，并恢复宿主 DLL 目录；恢复失败时回收已建立的子进程，不尝试另一 pi。
- 成品 Candidate、元数据与 GUI／CLI 锁统一按数据目录计算；源码仍在当前项目使用 Candidate，显式宿主注入保留，不自动迁移旧数据。
- PyInstaller 显式收集宿主 pi_probe.ts，保留已有应用／Qt／Fluent 翻译；增加使用同一 main 的 `LALC-console.exe` 以保留 CLI 输入输出。User 默认使用无终端 `LALC.exe`，Developer.cmd 转交同一 GUI 实现，仍由原有单实例及活动门控裁决。
- `example/acceptance` 复用既有 exp／mirror 外置页配置和正式 Plan→Task→Step 调用，提供三次成功、成功→普通失败→成功、Plan 中断并保留既有结果的演示；五秒协作等待用于人工暂停／接管／Stop。只用于独立测试数据，不在首次启动时生成，不发送示例点击或按键。
- 使用与现场记录说明见 [Windows 构建和验收](windows-packaging.md)。Stage 4 规格、路线图、ADR 0032、domain 指南、术语及开发教程已同步分发／路径边界；历史验证记录保留。

## 已执行验证

| 检查 | 结果与范围 |
| --- | --- |
| 最终普通回归：`QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest -q` | **555 passed，53 skipped**；未加 Agent 开关，跳过项不算通过 |
| 定向源码检查：pi 启动、冻结路径、双包内容、Agent 设置和错误诊断 | **76 passed，1 skipped**；模拟进程／Windows 标志，不启动真实模型，包含清理失败后不回退及回收已启动进程 |
| 显式 Agent 回归：`tests/test_pi_probe.py tests/test_agent_repair_agent.py -k 'not real_model'`，加 `--run-agent-tests` | **45 passed，4 deselected**；真实本机 pi + 本地 HTTP 替身，覆盖工具循环、保存版本试运行、取消／清理等，全部真实模型用例被排除 |
| 最终启动清理细化后的 pi smoke：`tests/test_pi_probe.py -k 'image_and_restricted_read or provider_error'`，加 `--run-agent-tests` | **3 passed，5 deselected**；再次验证图片／受限读取与服务错误无重试；仍仅本地 HTTP 替身 |
| 提供的 `pi_resources/pi-windows-x64.zip` | 固定 SHA-256、包内 1.4.0 元数据、237 条归档条目路径检查通过；未执行 Windows pi |
| `LALC.spec` 语法、`git diff --check` | 通过；不等于 Windows 构建成功 |

HTTP 替身测试首次因当前执行限制不能监听 127.0.0.1 而出现 fixture 错误；允许本地监听后以上选定用例通过。该环境失败未计作功能通过，也未调用真实模型解决它。

## 仍需 Windows／开发者确认

- 尚未实际生成本票 Windows 双 ZIP；本地只验证构建辅助逻辑、归档组装及源码行为，不能将 macOS 平台替身报告成 Windows 成品通过。
- Windows 上按说明验证实际依赖收集、两个 EXE 和启动文件、翻译、外置导入、CLI 输入输出、无系统 Python、中文／空格路径、语言重启／窗口恢复、原生 DPAPI、模态／缩放、焦点／接管、互斥与清理。
- 通用成品功能只验一个包；pi 的随包选择、环境选择、限定故障回退及缺失行为分别覆盖两个包。运行资源完整性及上游运行依赖的原始许可附件仍须随实际发布包核对；当前保留完整官方归档内容并补根 MIT，不声称已对二进制中全部上游依赖逐一审计。
- 不调用真实模型完成回归，Windows 真实模型验证不属于本票；本地 HTTP 替身不替代 Windows 原生证据。完整游戏业务、Runtime Agent、数据导出／导入、Actions、安装器、单文件和自动更新没有加入。
- 完成现场记录并由开发者确认后，才能将 #334 标记完成／关闭。
