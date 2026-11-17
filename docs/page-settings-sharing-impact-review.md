# 页面配置分享：决定、影响审查与验证

2026-11-17，用户确认后实施。

## 设计变更

既有 Sharing 只分享开发成果，排除私人配置。新增独立「页面配置」类别：按 PAGE_ID 选择已保存的业务配置，导入、导出均默认全不选；不包含任务次数、任务开关、页面启停、凭据，不自动附带页面包。页面源码和资源的安装继续保留配置，只有显式选择配置对象才写入配置。

相同配置跳过；已有不同配置展示新旧 JSON，并明确选择整页替换或跳过。整页替换移除旧页配置的多余字段，保留其他页面及 tasks。允许页面未安装时独立按原 PAGE_ID 保存，不执行页面代码，不保证业务字段兼容。页面是否安装只作静态提示，动态 ID 不作确定推断。

## 影响审查

- 已确认：`sharing.py` 的 KINDS、catalog、build_export、inspect_objects、import_selected 是新增类型的完整路径；固定快照、哈希、路径验证、活动锁及逐对象失败边界可复用。旧 ZIP 不变，旧版应用会拒绝含新增类型的包。
- 已确认：`sharing_gui.py` 的导出列表、导入分类、默认选择、冲突操作、重查、详情和提交结果需要同步扩展；中英文翻译需要更新。
- 已确认：`UserSettings.save` 原来复制内存中的整份设置，导入后旧 store 可能覆盖其他页面或任务；保存时应先读取最新文件，只替换明确的单项。
- 已确认：`UserWindow.submit_pages`、`start_plan`、`render_state` 以及 `GuiCoordinator.request_reload` 使用已加载页面；需要将实际导入的已加载页标记为待重载，禁止旧页保存、编辑和开始运行，重载时跳过其旧值。状态随共享 PageContext 保留，关闭再打开窗口也不得丢失保护。
- 潜在风险：业务配置虽是 JSON，仍可能包含用户手动填写的私人信息；持续隐私提示与默认全不选不可省略。页面字段兼容仅在实际加载／业务使用时才能确认。

## 实施与验证计划

先新增配置对象的结构校验、按页比较和提交前版本复核，再扩展现有弹窗；配置文件沿用原子保存。覆盖新配置、冲突替换／跳过、配置损坏、未选页面与任务保留、重查后变更、页面包独立性、默认全不选和旧界面保护。仅运行普通相关回归，不运行真实 pi／模型／游戏测试。

## 实施结果与验证

已完成独立 `page_settings` 对象（仅 `settings.json`）、导入／导出默认全不选、逐页新旧 JSON 审查、替换／跳过、提交前配置版本复核，以及共享 PageContext 的待重载保护。沿用现有 ZIP 格式版本及固定快照、锁和原子 JSON 保存；配置 ID 仅作为 JSON 键，不能被当作磁盘路径。更新中英文资源、Sharing 用法及领域词汇。

- `QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest -q tests/test_page_settings_sharing.py tests/test_sharing.py tests/test_sharing_gui.py tests/test_sharing_resources.py tests/test_sharing_progress.py tests/test_user_pages.py`：最终完整复跑 **105 passed, 1 skipped**。跳过项为本机 IPC 权限受限的真实进程重载检查，不计通过；页面冻结、重新打开窗口及重载前跳过旧值已有离屏测试覆盖。
- `QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest -q tests/test_gui_language.py`：**23 passed**，包括翻译清单及格式字段检查。
- `pyside6-lrelease`：589 条已完成翻译，0 条未完成；`git diff --check` 通过。
- 对四个修改的实现文件执行 Pyright（指定本项目 Python）：当前与 HEAD 基线均为 **32 errors**，按文件、诊断内容及规则对照 **无新增诊断**。完整类型检查仍未通过，未将其报告为通过，也未扩大范围清理原有问题。基线使用普通 WorkDirectory 副本，检查后清理。
- 最初一次合并测试在结束时退出码 139，分组串行复跑正常；修正新增测试中直接调用关闭回调的用法，改为正常关闭窗口后，最终同组完整运行正常退出。该次异常不算通过证据。

未运行真实 pi／模型／游戏测试，未做 Windows 成品现场验收；未证明未知页面版本的业务字段兼容。整页替换会删除该页原有但导入值未包含的字段，其他页面和任务设置保持。
