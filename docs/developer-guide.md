# 开发者指南

## 发布 LALC 框架

1. 用 `uv version --bump patch --no-sync` 更新补丁版本，也可以用 `uv version 6.1.0 --no-sync` 指定版本。提交版本改动并合入 `master`。Windows EXE、ZIP 和发布标签都从同一个项目版本号生成。
2. 打开 GitHub 的 **Actions → Publish LALC → Run workflow**。验证构建时留空 `publish`。正式发布时选择 `master` 并勾选 `publish`。
3. 检查 Windows 构建记录和 Release。工作流会按上一版以来的提交生成贡献者更新记录，并上传两个 Windows 包、供 5.x 使用的 `lalc.zip` 和 `SHA256SUMS`。验证构建可以从该次运行的 Artifacts 下载。

新代码首次合入 `master` 时，合并提交需要同时保留两边的历史，并以新版分支的文件树为基础。正式发版使用新版的 **Publish LALC** 工作流。

当前两条分支的历史独立。可以在准备好的新版分支上运行 `git merge -s ours --allow-unrelated-histories origin/master`，再将 `master` 快进到该合并提交。这个方向会保留旧版的提交与标签，并采用新版文件树。

### 在 Windows 随包打入默认资源

在存有正式资源的 Windows 机器上运行 `uv run --locked --all-extras python scripts/build_windows.py`。本地构建会从 `%LOCALAPPDATA%\LALC` 选取最新已发布 Workflow、全部 Assets、已安装扩展页面和 Skills，缺少的内置 Skill 使用程序随附版本。默认包排除 Agent 对话历史和页面配置。

用 `--default-resources 路径` 可指定另一数据目录或一份确认可随框架发布的分享 ZIP。GitHub Actions 可以从 `packaging/default-resources.zip` 取得已核对的默认包。Actions 执行机没有维护者 Windows 上的本地资源。
