# 开发者指南

## 发布 LALC 框架

需要调整基础版本时，用 `uv version --bump patch --no-sync` 更新补丁版本，也可以用 `uv version 6.1.0 --no-sync` 指定版本。提交版本改动后，打开 GitHub 的 **Actions → Publish LALC → Run workflow**，选择分支和 `release` 模式。

- **`build-only`** 将构建结果留在当次运行的 Artifacts。
- **`beta`** 从所选分支构建，使用 Actions 运行编号生成标签，例如 `v6.0.0-beta.12`。如果该提交包含 `packaging/default-resources.zip`，构建会校验并内置它。缺包时仍可发布，发布说明顶部会提示中英文用户另行获取资源。工作流将两个 Windows ZIP 和 `SHA256SUMS` 上传到 GitHub Pre-release，测试者从 Releases 手动下载。
- **`stable`** 从 `master` 的发版提交读取 `packaging/default-resources.zip`，缺包或校验失败会停止。通过校验的 ZIP 会内置到 Windows 包，并随两个 Windows ZIP、供 5.x 迁移的 `lalc.zip` 和 `SHA256SUMS` 一起附到正式 Release 草稿。维护者检查附件后手动发布并标为最新正式版。应用只从已发布的正式 Release 检查更新。

发布完成后，检查 Windows 构建记录和 Release。两种发布都会从上一个正式版开始汇总贡献记录。

新代码首次合入 `master` 时，合并提交需要同时保留两边的历史，并以新版分支的文件树为基础。正式发版使用新版的 **Publish LALC** 工作流。

当前两条分支的历史独立。可以在准备好的新版分支上运行 `git merge -s ours --allow-unrelated-histories origin/master`，再将 `master` 快进到该合并提交。这个方向会保留旧版的提交与标签，并采用新版文件树。

### 在 Windows 准备默认资源

在存有正式资源的 Windows 机器上运行仓库根目录的 `prepare_default_resource.cmd`。脚本从 `%LOCALAPPDATA%\LALC` 导出默认包，校验通过后更新当前工作目录里的 `packaging/default-resources.zip`。核对内容后，由开发者按正常流程提交和推送 ZIP。发版工作流使用所选提交中的文件。

默认包包括最新已发布 Workflow、Assets、已安装扩展页面和 Skills，以及镜牢已保存的饰品配置、星光强化和主题包配置。缺少的内置 Skill 使用程序随附版本。已有用户可在导入预览中分别勾选这三组，导入会保留该页面的其他字段。Agent 对话历史和其他页面配置留在本机。

需要在 Windows 本机构建时，运行 `uv run --locked --all-extras python scripts/build_windows.py`，可用 `--default-resources 路径` 指定数据目录或已核对的资源 ZIP。

## 单独更新官方资源包

在 **通用设置 → 分享 → 导出** 选择要发布的工作流、素材、页面和 Skills，保留 `lalc-sharing-<时间戳>.zip` 文件名。核对内容后，把 ZIP 上传到待发布的正式 Release 草稿，或追加到 GitHub 上最新的正式框架 Release。首页按 GitHub 附件上传时间查找最新资源包，玩家可在应用内下载并预览。用于公开更新的包只包含上述资源类型，页面配置和 Agent 历史请留在本机。
