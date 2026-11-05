# Sharing 资源处理修订：影响审查

2026-11-04。开发者明确同意：Sharing 导入／导出及 Agent 页面资源取消固定数量、容量、源码和像素上限，改用本机资源检查、流式处理和按需预览。附件中的流程正文作为需求输入，粘贴的 Mermaid 样式不属于实现指令。本审查基于当前工作区源码；未运行真实模型或 Windows 成品。

## 设计变化

旧固定 1,000 对象／20,000 文件／128–512 MiB 等阈值 → 声明大小预估磁盘需求、实际大小和哈希最终校验。页入口、标签、Workflow 及 Agent 页资源的 2 MiB／16 MiB、36 MP 拒绝条件撤销。分页长度、传输块大小、缩略图尺寸仍是处理单位，不是文件准入上限。路径合法性、链接／别名拒绝及注册／权限规则保持。

## 已确认的影响

- `sharing.py:SharingPackage` 当前在 GUI 线程创建并立即解压；虽分块校验，未检查磁盘、无进度／取消，`verify()` 仍依赖原 ZIP。应拆成索引／空间预检、Worker 暂存、复用受控暂存内容三阶段；最终提交不需要原 ZIP。
- `sharing.py:read_file/tree_files/build_export/files`、`page_packages.py:PageSnapshot/snapshot_page` 当前把全部资源存为字节；仅删常量会把资源压力转移到内存。改用受控文件快照与分块哈希／复制，导出冻结版仍须保留到保存或取消。
- `sharing_gui.py` 的检查、重检、保存／提交及 Asset 图片构造会阻塞事件循环；移入可取消后台任务，实际执行页面的 Review 保持 GUI 主线程。资源图片按需缩略预览，不能因无固定像素上限就直接解码任意尺寸。
- `page_drafts.py:file_bytes/read/write_resource`、`repair_tools.py:page_read/page_resource/page_preview` 及日志快照当前读写整包字节；需同步文件复制、文本分页、图片缩略输出、完整原始资源证据和工具描述。
- 历史读取引用可放大：当前 `MAX_TOTAL` 同时限制 ZIP 与日志展开。撤销业务容量阈值后仍须检查实际可用内存／磁盘，避免无限递归、重复图片解码；保留完整原始资料，不能为减少资源消耗丢失证据。
- `docs/sharing.md`、页面示例、Prompt／pi 工具描述、双语文案和以旧常量为断言的测试必须同步。ZIP 格式不变，不需要迁移已有分享包或 Session。

## 实施与验证顺序

先加入资源检查／文件内容流式操作，接页面包和 Agent 工具；再改 ZIP 索引、暂存生命周期和磁盘估算；最后接 GUI Worker／取消与清理、按需预览，更新文档。验证无旧限额、空间不足／未知、不同磁盘、声明不符、取消／故障清理、暂存篡改、删除原 ZIP 后导入、整包版本和既有逐对象失败行为。

资源估算是预检，不是预留：其他程序可消耗空间，最终写入仍必须安全失败。ZIP 索引、JSON／Python 语法树仍需内存，应按当时可用资源判断并明确报错，不能宣称无限资源。启动遗留清理只能触及应用管理的暂存目录，且必须确认对应活动锁未被持有，不能删除另一实例正在审查的包。

## 实施收尾

已按上述顺序完成文件流、页面工具、后台 ZIP 暂存和界面接入，最终规则见 [Sharing](sharing.md)、架构决定见 [ADR 0037](adr/0037-budget-sharing-against-available-resources.md)。普通全量 865 passed／88 skipped，随后源码内存预检相关 46 passed；另串行 pi 接入 6 passed。详细命令、时点及未验证环境见[实施记录](sharing-implementation-progress.md#资源规则修订实现与验证)。
