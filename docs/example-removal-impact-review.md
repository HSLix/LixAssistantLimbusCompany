# 移除 example 目录的影响审查与实施

2026-11-15，用户明确决定不再需要仓库 example 目录，要求先审查再删除。

## 设计变化

由仓库提供可安装教学页面改为不维护教学目录；页面接口、生产加载能力及既有用户数据保持。此前 ADR 0026 允许新教学样例，但不要求永久保留；本次决定结束该样例的维护，不改变执行与权限契约。

## 已确认影响

- `example/pages/` 仅剩三个 Python 页面与 README；生产源码、构建配置无该目录依赖，setuptools 仅发现 src 下的包。
- `tests/test_gui_language.py` 两处依赖页面目录，覆盖双语导航、校验、旧页回退及子进程语言加载。三个页面移至 `tests/fixtures/language-pages/` 保留回归覆盖。
- `tests/test_user_pages.py::test_documented_minimal_page_loads_and_submits_empty_config` 解析 README 内代码，页面契约移至 `business-settings-pages.md` 并同步测试。
- `tests/gui_native_probe.py::main` 原先发布已不存在的 example/workflow；改用已有 user-pages Manifest 夹具，页面使用语言夹具。
- 当前教程、Sharing、语言规格、Agent 用法和 Windows 准备步骤仍指向旧目录；同步入口并删除失效的验收样例命令。历史 ADR、审查及实施记录保留其时点描述。

## 实施与验证

已删除整个 example 目录；不访问或修改应用数据目录中已安装的页面、Manifest 或用户配置。

执行 `QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest -q tests/test_gui_language.py tests/test_user_pages.py tests/test_windows_packaging.py`：63 passed、1 skipped、1 failed。失败为 test_single_editor_handoff_autosaves_and_restores_independent_selection，期待 user provider 保持 llama.cpp，实际为 deepseek；修改前后均以相同原因复现，不计通过。git diff --check 通过。

未运行原生 GUI 探针、全量回归、Agent、Windows 成品或真实游戏。仓库之外脚本若自行引用旧路径需调整，本次无法确认其存在与使用情况。
