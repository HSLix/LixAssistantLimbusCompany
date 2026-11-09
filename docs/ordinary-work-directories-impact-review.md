# 普通工作目录与直接导出：决定和影响审查

2026-11-09：开发者确认下述边界并授权实施。审查基于当前工作区源码；已有 pi 协议处理改动不属于本次设计。

## 接受的替代决定

- 产品及脚本不再通过 tempfile 创建目录；工作目录和待提交文件采用普通创建方式，继承父目录权限。默认工作区位于应用数据目录的 `work/`，需要同盘提交的工作区仍位于目标父目录。
- 普通工作目录仍按生命周期清理；保留固定快照引用、Worker 退出等待、活动锁、启动遗留清理、原子提交、失败回滚及恢复失败时保留唯一旧副本。
- 无明确且记录在案的理由，不允许引入临时目录。pytest `tmp_path` 等测试隔离设施保留；手写测试探针和构建脚本也使用普通工作目录。
- 分享导出选择完成后直接选择 ZIP 保存位置，取消第二步文件清单审查；仍冻结并校验实际导出内容。保留选择页的隐私提示，Agent History 默认不选。
- 导入页面 Review、来源确认、路径和哈希验证及权限边界不变。

## 实施前已确认的差距

- `run_log_gui.export_zip`、`run_log_sharing.export_log/import_log` 使用 TemporaryDirectory；日志导入将目录重命名为持久副本。`runtime.staging_directory` 和 `manifest.checkout` 已记录 Windows 受限 DACL 随重命名保留的问题，其他路径尚未统一。
- `sharing.save_package` 使用 NamedTemporaryFile 后重命名最终 ZIP；只更换目录不足以覆盖此权限传播路径。Asset、Component、日志内容、页面源码和导入 Manifest 的 mkstemp/NamedTemporaryFile 同样需迁移。
- `page_packages`、`sharing`、`agent_skills`、`developer`、`agent_history`、`pi_probe`、`pi_process` 及 Windows 构建脚本创建临时目录；快照 owner 的 name/cleanup 和自动释放语义必须保留。页面、Asset 替换必须保留恢复失败时的备份。
- `sharing.staging_root` 与 SharingPackage 显式指定 0700，需改为普通 mkdir；活动实例锁及遗留清理不能删除。
- `ExportDialog.advance` 首次点击冻结并进入第二页，第二次才保存；测试 `test_export_defaults_and_frozen_second_step` 和现行 Sharing 规格要求同步改为一次点击保存。
- codesearch/knowledge 的匿名输出文件不是目录，也不发布为产物；仍统一为普通文件并保持结束清理。ProcessLock 的系统共享锁路径仅用于跨实例互斥，不是工作目录，保留以免新旧进程失去互斥。

## 实施顺序与验证

复用现有 UUID + mkdir 的权限继承模式，统一工作目录生命周期和普通待提交文件创建；迁移所有直接目录创建点及产物文件；简化导出界面并同步中文翻译；更新边界与现行规格；检查所有调用点并执行相关普通测试。pytest 自带隔离目录不迁移，也不添加依赖或新配置。

潜在风险：普通创建继承的是父目录现有权限，不能修复既有父目录的 ACL；Windows ZIP 解压失败的具体现场尚未复现。新实现的本机权限和回滚检查不等于 Windows 成品验收，不批量修改用户已有文件权限。


## 实施与验证结果

- 新增 `src/lalc/work_files.py`，采用 UUID 唯一路径和普通 mkdir／排他文件创建；WorkDirectory 支持作用域清理、快照引用释放清理及目录已提交后的安全退出。复用既有 runtime.staging_directory 入口，迁移全部产品及脚本 tempfile 创建调用、手写测试探针和构建目录；pytest 隔离工作区不写真实应用数据。
- 导出选择页直接显示“保存 ZIP”，取消系统保存对话框不冻结副本；取消导出文件清单页和返回导航，保留原选择默认值、隐私提示、校验与 Worker 进度取消。导入 Review 保持。
- AGENTS.md、domain 指南、Sharing 现行规格、ADR 0036／0037 与当前状态已同步；中文 TS／QM 已更新。
- 普通相关回归：25 个文件，**462 passed, 1 skipped**。覆盖工作目录生命周期、普通权限与最终 ZIP 权限、取消保存、日志往返、恶意包拒绝、页面／Asset 回滚、日志内容提交、Manifest、Skills、索引、构建归档及 GUI。跳过项不计为通过。
- Agent 接入与普通回归分开串行执行：`tests/test_agent_repair_agent.py::test_text_only_and_context_retained` 和 `::test_cancel_reaps_process_and_keeps_candidate_and_log`，显式 `--run-agent-tests`，**2 passed**；使用真实 pi + 本机 HTTP 替身，不是真实模型验收。初次受本机端口绑定权限限制，放行本地测试运行后通过。
- `test_run_ui_updates.py` 单独运行 **3 passed**。两次单进程全量普通回归分别在该文件与 `test_user_gui.py` 的 Qt 事件处理中段错误退出（exit 139），不能报告完整回归通过；未在本次范围内定位或修复该崩溃。相关回归正常退出时仍有 Qt 对象回收 ResourceWarning。
- 源码边界扫描通过：产品和脚本无 tempfile 目录／文件创建调用；剩余 gettempdir 仅为约定保留的共享进程锁，测试中另有跨进程探针文件。compileall、中文翻译编译与 git diff --check 通过。

未运行 Windows 成品构建、Windows ACL／解压实机或真实模型／游戏验收；未修复已有受限父目录及旧产物权限。工作目录保留正常生命周期清理，不新增崩溃后通用工作区恢复机制；Sharing 的活动锁与专用遗留清理继续保留。原有 pi 协议处理及相应文档／测试的未提交改动已保留。
