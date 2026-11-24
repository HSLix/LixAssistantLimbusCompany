# 开发者指南

## 发布 LALC 框架

需要调整基础版本时，用 `uv version --bump patch --no-sync` 更新补丁版本，也可以用 `uv version 6.1.0 --no-sync` 指定版本。提交版本改动后，打开 GitHub 的 **Actions → Publish LALC → Run workflow**，选择分支和 `release` 模式。

- **`build-only`** 将构建结果留在当次运行的 Artifacts。
- **`beta`** 从所选分支构建，使用 Actions 运行编号生成标签，例如 `v6.0.0-beta.12`。工作流将两个 Windows ZIP 和 `SHA256SUMS` 上传到 GitHub Pre-release。测试者从 Releases 手动下载，应用内框架更新仅支持正式版。
- **`stable`** 从 `master` 构建并创建正式 Release 草稿，附上两个 Windows ZIP、供 5.x 迁移的 `lalc.zip` 和 `SHA256SUMS`。如果提交中已有审核过的 `packaging/default-resources.zip`，构建会将它打入安装包并附到草稿。否则，将本机导出并核对过的资源 ZIP 手动上传到草稿。检查附件后发布并标为最新正式版，用户首次安装后可以从首页下载资源。

发布完成后，检查 Windows 构建记录和 Release。两种发布都会从上一个正式版开始汇总贡献记录。

新代码首次合入 `master` 时，合并提交需要同时保留两边的历史，并以新版分支的文件树为基础。正式发版使用新版的 **Publish LALC** 工作流。

当前两条分支的历史独立。可以在准备好的新版分支上运行 `git merge -s ours --allow-unrelated-histories origin/master`，再将 `master` 快进到该合并提交。这个方向会保留旧版的提交与标签，并采用新版文件树。

### 在 Windows 随包打入默认资源

在存有正式资源的 Windows 机器上运行 `uv run --locked --all-extras python scripts/build_windows.py`。本地构建会从 `%LOCALAPPDATA%\LALC` 选取最新已发布 Workflow、全部 Assets、已安装扩展页面和 Skills，缺少的内置 Skill 使用程序随附版本。默认包还会自动导出镜牢页面已保存的饰品配置和主题包配置。首次安装时一并导入，已有用户可在分享导入预览中勾选镜牢默认配置，导入会保留镜牢页面内的其他字段。Agent 对话历史和其他页面配置留在本机。

用 `--default-resources 路径` 可指定另一数据目录或一份确认可随框架发布的分享 ZIP。GitHub Actions 可以从 `packaging/default-resources.zip` 取得已核对的默认包。Actions 执行机没有维护者 Windows 上的本地资源。

## 单独更新官方资源包

在 **通用设置 → 分享 → 导出** 选择要发布的工作流、素材、页面和 Skills，保留 `lalc-sharing-<时间戳>.zip` 文件名。核对内容后，把 ZIP 上传到待发布的正式 Release 草稿，或追加到 GitHub 上最新的正式框架 Release。首页按 GitHub 附件上传时间查找最新资源包，玩家可在应用内下载并预览。用于公开更新的包只包含上述资源类型，页面配置和 Agent 历史请留在本机。
