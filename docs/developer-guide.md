# 开发者指南

## 发布 LALC 框架

需要调整基础版本时，用 `uv version --bump patch --no-sync` 更新补丁版本，也可以用 `uv version 6.1.0 --no-sync` 指定版本。提交版本改动后，打开 GitHub 的 **Actions → Publish LALC → Run workflow**，选择分支和 `release` 模式。

- **`build-only`** 将构建结果留在当次运行的 Artifacts。
- **`beta`** 从所选分支构建，使用 Actions 运行编号生成标签，例如 `v6.0.0-beta.12`。提交中有默认资源 ZIP 时，构建会校验时间文件和 ZIP，将资源内置到两个 Windows ZIP，并把同一份资源按导出时间命名后附到 GitHub Pre-release。缺包时仍可发布，发布说明顶部会提示中英文用户另行获取资源。
- **`stable`** 从 `master` 的发版提交读取默认资源 ZIP 和时间文件，缺少文件或校验失败时停止。通过校验的 ZIP 会内置到两个 Windows 包，并按导出时间命名后附到正式 Release 草稿。草稿也包含供 5.x 迁移的 `lalc.zip`。维护者检查后手动发布并标为最新正式版。

发布完成后，检查 Windows 构建记录和 Release。两种发布都会从上一个正式版开始汇总贡献记录。

新代码首次合入 `master` 时，合并提交需要同时保留两边的历史，并以新版分支的文件树为基础。正式发版使用新版的 **Publish LALC** 工作流。

当前两条分支的历史独立。可以在准备好的新版分支上运行 `git merge -s ours --allow-unrelated-histories origin/master`，再将 `master` 快进到该合并提交。这个方向会保留旧版的提交与标签，并采用新版文件树。

### 在 Windows 准备默认资源

在存有正式资源的 Windows 机器上运行仓库根目录的 `prepare_default_resource.cmd`。脚本从 `%LOCALAPPDATA%\LALC` 导出默认包，校验通过后更新 `packaging/default-resources.zip` 和 `packaging/default-resources.txt`。文本第一行是精确到秒的 UTC 导出时间，例如 `20261125T103045Z`，第二行是同次导出 ZIP 的 SHA-256。把两个文件一起提交并推送。现有只有 ZIP 的提交需要重新导出才能用于新版发布流程。

默认包包括最新已发布 Workflow、Assets、已安装扩展页面和 Skills，以及镜牢已保存的饰品配置、星光强化和主题包配置。缺少的内置 Skill 使用程序随附版本。已有用户可在导入预览中分别勾选这三组，导入会保留该页面的其他字段。Agent 对话历史和其他页面配置留在本机。

需要在 Windows 本机构建时，运行 `uv run --locked --all-extras python scripts/build_windows.py`，可用 `--default-resources 路径` 指定数据目录或已核对的资源 ZIP。

## 单独更新官方资源包

导出并推送上述两个文件后，在 **Actions → Publish LALC Resources → Run workflow** 选择含有该提交的分支，填写 `target_release`，可以指定已发布的正式版或 Beta 标签。CI 会追加 `default-resources-20261125T103045Z.zip` 这类附件。同名且摘要一致时重跑成功，同名但摘要不一致时停止。目标 Release 必须允许追加附件。

所有客户端都只从最新已发布的正式 Release 检查资源。首页按资源导出时间选择新版附件，旧格式仍可按上传时间识别。Beta 的资源附件供手动下载。准备下一次正式框架发布时，确认发版提交包含最新已发布的正式资源。
