# 开发者指南

## 发布 LALC 框架

1. 用 `uv version --bump patch --no-sync` 更新补丁版本，也可以用 `uv version 6.1.0 --no-sync` 指定版本。提交版本改动并合入 `master`。Windows EXE、ZIP 和发布标签都从同一个项目版本号生成。
2. 打开 GitHub 的 **Actions → Publish LALC → Run workflow**。验证构建时留空 `publish`。正式发布时选择 `master` 并勾选 `publish`。
3. 检查 Windows 构建记录和 Release。工作流会按上一版以来的提交生成贡献者更新记录，并上传两个 Windows 包、供 5.x 使用的 `lalc.zip` 和 `SHA256SUMS`。验证构建可以从该次运行的 Artifacts 下载。

新代码首次合入 `master` 时，合并提交需要同时保留两边的历史，并以新版分支的文件树为基础。检查合并后的 `.github/workflows`，只启用新版的发布和镜像同步工作流。

当前两条分支的历史独立。可以在准备好的新版分支上运行 `git merge -s ours --allow-unrelated-histories origin/master`，再将 `master` 快进到该合并提交。这个方向会保留旧版的提交与标签，并采用新版文件树。

### Mirror酱

向 Mirror酱确认了新版 `with-agent` 资源 ID 和平台后，在仓库设置配置 `LALC_MIRROR_RID`、`LALC_MIRROR_OS`、`LALC_MIRROR_ARCH` 变量。后两项按对方提供的参数填写，通用包留空。上传 Token 保存为 Actions secret `MIRRORCHYANUPLOADTOKEN`。

如果对方确认旧资源可以继续分发迁移包，设置 `LALC_LEGACY_MIRROR_RID`。旧资源需要另外的上传 Token 时使用 `LALC_LEGACY_MIRROR_UPLOAD_TOKEN`。GitHub 发布完成后会同步已配置的资源。同步失败时，从 **Sync LALC to MirrorChyan** 按 Release 标签重试。
