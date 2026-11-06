# codesearch UTF-8 边界修复影响审查

2026-11-06；开发者已确认修复范围与方案。本文先记录源码审查结论，验证结果在实施后补充。

## 已确认方案

- codesearch 版本探测及 Git 根路径探测从依赖系统编码的文本管道，改为捕获原始字节，在调用线程严格按 UTF-8 解码；索引 metadata.json 显式按 UTF-8 读取。
- 路径和结构化数据不采用替代字符或 GBK 回退。非法 UTF-8 作为知识库更新失败处理，保留可用 A；首次失败仍可读取原资料。
- 延续 ADR 0038 的 A/B 切换、独立 Git 根检查、权限和进程生命周期。不修改全局线程致命错误策略，不扩大为全仓库编码改造。
- 这是既有失败边界的修复，没有新增领域术语或架构取舍，不新增 CONTEXT 条目或 ADR。

## 已确认问题与调用链

`repair_tools.knowledge_search_hybrid → KnowledgeLibrary.search_hybrid → synchronize → CodeSearch.build`。

1. `src/lalc/codesearch.py:CodeSearch.build` 使用 `subprocess.run(text=True)` 读取 Git 根路径，未指定编码。日志显示 Windows 读取线程按 GBK 解码失败；日志路径的 UTF-8 字节按 GBK 解码可复现相同的 `0x95 / position 17`。
2. Windows 子进程读取线程的异常进入 `src/lalc/lifecycle.py:run_application` 注册的 `threading.excepthook`，触发 `report_fatal`。调用线程不能捕获另一线程的异常，并继续因 stdout=None 产生 AttributeError，越过 `synchronize` 的预期错误处理。
3. `CodeSearch.prepare` 的版本探测同样使用隐式文本编码；`build` 读取索引元数据也依赖默认文件编码。这些边界一并修复。
4. `KnowledgeLibrary._run` 已使用二进制临时文件捕获 Git 输出；pi 的协议读取已有自己的边界，本次不改。`synchronize` 已捕获 ValueError，而 UnicodeDecodeError 属于 ValueError；在调用线程解码即可复用失败报告和保留 A 的逻辑。

## 影响与实施顺序

- `src/lalc/codesearch.py`：改两个短命令的输出捕获和解码，显式指定元数据编码。构建日志仅供诊断，继续允许替代非法字符；索引进程仍输出到二进制文件。
- `tests/test_codesearch.py`：同步替身为字节输出，检查版本探测采用二进制管道；覆盖中文真实 Git 根、父目录拒绝、无效 UTF-8 在调用线程抛出、中文元数据读取及进程回收。
- `tests/test_knowledge.py`：验证解码失败被记录为 update.ok=false、保留 A，以及首次失败可读取原资料。
- `docs/external-code-search.md`：说明 UTF-8 协议和局部失败行为；本记录补充执行证据。
- 无接口、配置、导出或数据格式迁移；已有版本与索引不需删除或重建。先运行相关普通测试，再串行运行默认回归；不因该修复启动真实 pi 或模型测试。

## 潜在风险与验收限制

本机中文 Git 路径检查不是 Windows 原生验收。需在 Windows GBK 默认环境、中文用户目录下验证真实 Git、codesearch 和模型的完整搜索；本次源码修复不能证明第三方程序内部的所有路径处理正确。全局线程致命错误策略保留，其它未捕获线程异常仍按既有规则处理。

## 实施与验证

上述改动已本地完成。解码仍严格执行，未增加新配置或依赖；UnicodeDecodeError 由既有 ValueError 分支记录，无需修改知识库错误策略。

- 定向：`.venv/bin/python -m pytest -q tests/test_codesearch.py tests/test_knowledge.py` → **42 passed**。真实本地 Git 验证中文目录，codesearch 索引使用替身；非法版本／路径输出在调用线程抛出，知识库替身验证解码失败保留 A 和首次失败可读取原资料。
- 默认回归：`QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest -q` → **887 passed, 98 skipped**；未开启 Agent 测试，跳过项不算通过。
- 首次定向执行因新测试把程序文件放到宿主保留的 codesearch 目录位置而失败，修正测试路径后通过。首次默认回归未设置 offscreen，在 macOS qframelesswindow 原生窗口初始化处段错误退出；使用项目既有 offscreen 设置后完成回归，不将前次中断计为通过。
- `git diff --check` 通过。未执行 Windows 原生、打包版、真实模型或游戏验收；未改全局异常钩子，未删除或迁移用户知识库。

## 后续复现与错误证据补充

开发者随后确认更新并完全重启后，混合搜索仍出现相同 GBK 读取线程异常。新提供的堆栈仅含 threading／subprocess 内部帧，没有具体命令或业务调用位置，不能据此认定仍由已经改为二进制管道的两个 codesearch 调用触发。当前源码检查中，codesearch 输出为字节／二进制文件，knowledge 的 Git 输出为二进制文件；pi 版本探测显式 UTF-8，另一个隐式文本调用仅用于 macOS vm_stat。这些检查不能证明 Windows 实际运行的所有依赖与动态页面均无其它文本管道。

为取得可归因证据，`ApplicationLifecycle.report_fatal` 对 UnicodeDecodeError 检查 traceback 中的真实 Popen 读取线程对象：补充程序文件名、PID、实际编码，并从正在等待同一个对象的 communicate 调用线程找回业务调用栈。该上下文同时写入日志和可复制详情，不转储 Popen 参数、输出、环境或其它线程，不吞掉异常，也不改变致命错误策略。调用线程已退出时只能提供程序与编码，不承诺重建所有已结束操作的历史。

通用 ErrorDialog 顶部增加“不用截图，请使用下方的‘复制错误详情’报告错误”；复制按钮更名并在浅／深主题中显示红色，翻译源码和编译资源一起更新。复制内容保持原摘要与完整详情，不混入操作提示。

补充定向测试 **102 passed**，包括模拟 Windows 读取线程、还原等待线程调用位置、命令参数不进入详情，以及普通／致命弹窗在两种主题下的文字颜色与复制行为；已查看无界面渲染截图。新的实际 Windows 触发来源仍需开发者用更新后的复制详情定位，不能将这次证据增强称为已修复再次出现的根因。

最终普通回归 `QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest -q` → **890 passed, 98 skipped**。过程中的旧按钮文字断言已同步；另一次页面导航选中状态断言失败，独立复跑该用例及相关弹窗／语言测试 **62 passed**，新主题测试改为恢复原主题后完成最终回归。跳过项不算通过，未开启 Agent 测试。附加生命周期类型检查仍报告原有线程钩子的 `exc_value` 可空参数问题；本次未扩展修改该接口。`git diff --check` 通过。
