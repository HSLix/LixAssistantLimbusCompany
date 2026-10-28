# Stage 2 收尾与 #317 延期说明

更新：2026-10-22。本文替代原邮箱验收指导；原“邮箱通过才结束 Stage 2”的规则已由开发者明确修订，见 [ADR 0026](adr/0026-close-stage-2-without-a-real-game-workflow.md)。

## 已确认的阶段边界

Stage 2 按确定性执行与基础交互能力完成，不再以邮箱业务端到端为门槛。沿用 Manifest/Component、Step Recovery、完整 Working Manifest、Plan/Trace/Ledger、前台观察、控制接管及 Asset 的既有要求与验收；补齐 crop 产物登记、新工作台库文件名和三层教学样例。

新入口：

- [可运行的三层 Workflow 与全部 Trusted Actions](../example/workflow/README.md)
- [开发者命令及 Candidate 工作台](developer-workflow-tutorial.md)
- [Stage 2 实施切片与修订后完成规则](stage-2-implementation-slices.md)

[ADR 0027](adr/0027-resolve-assets-independently-with-optional-priority-tags.md) 已取代旧专属 Asset Library：Candidate 和发布物不再需要素材映射文件。完整逻辑名对应目录，图片仅以完整哈希命名，asset-tag.json 保存可选标签；缺标签的图片也参与匹配。旧素材数据废弃，清理后重新裁剪，不做迁移或兼容。

crop/tag-asset 只处理共享目录内的图片、标签与来源，无需 publish 或重新 set-default。标签列表整体覆盖，省略或传空列表时写 []、清空旧标签。每次匹配按优先组→剩余组读取当前目录，素材更新在同一 Run 的下一次匹配生效。

## 验证与证据边界

本轮自动化验证覆盖：Manifest 无素材依赖；crop 离线标签配置与整体覆盖、空标签、缺标签候选；优先组短路与回退、跨模板排序/NMS、同 Run 更新可见；外部图片、缺来源、哈希/解码错误；旧发布库及 Default 保留；新样例校验发布、三层应用服务调用、全部七个生产动作、裁剪→设置标签→直接匹配、Trace/Ledger 与证据保存。

```bash
QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest -q
git diff --check
```

其中新测试为 `tests/test_developer_assets.py` 和 `tests/test_example_workflow.py`。示例测试仅替换 Windows 平台，使用生产动作注册。既有 #310/#311 对应 `tests/test_recovery.py`，#313 对应 `tests/test_plan.py`，全套回归覆盖其当前实现。

此前 Windows 单项截图、控制/接管和 Asset 实验仍按各自实际范围保留；自动化替身与 macOS 打包探针不证明当前 Windows 业务集成。具体本轮通过数量见 #307 收尾记录。

## #317 保留的延期工作

[#317](https://github.com/HSLix/LixAssistantLimbusCompany/issues/317) 不按“邮箱已验收”关闭。待 GUI 开发工具支持坐标显示、区域选择等工作后，重新核对支持入口、转换、可观察停滞、已完成状态和最终业务检查，再实施真实 mailbox Task Workflow。

独立保留 #321 移交的验收：

- Windows 游戏新格式裁剪→配置/设置标签→优先匹配与回退，证明无需再次 publish，旧图片及 Component Manifest 不变。
- 当前真实 Workflow 从 Run 启动开始监听，验证物理接管、输入释放、无重放、显式 Resume、新观察和 Stop。
- Windows onedir 在无系统 Python、无旧 runtime 的环境执行正式用户路径；验证统一动作注册与 NumPy/OpenCV。当前 `console=False` 对 CLI 确认/恢复交互的影响仍须实机检查。

上述延期内容不再阻塞 Stage 2，也不被声明为已经通过。Stage 3 独立 Component 修复与 Stage 3.5 Runtime Agent 维持各自范围。
