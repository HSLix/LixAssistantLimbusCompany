# Skills Sharing 与 Asset 树调整

2026-11-09 用户确认后实施。

## 接受的变化

- Sharing 增加 Skills，按顶层目录名识别完整 Skill（SKILL.md 和所有普通附属文件）。导出默认不选，导入默认全不选；相同完整内容跳过，不同内容沿用 Asset 的显式覆盖／跳过。覆盖整目录，旧版多余文件移除。
- Asset 树取消“图片和标签”叶项，直接选择逻辑名，目录选择联动子项；默认仅展开顶层。Developer GUI 模板匹配树同样仅默认展开顶层，刷新保留人工展开状态。

## 影响与证据

实施前确认：`sharing.KINDS/catalog/build_export/inspect_objects/import_selected` 仅接入四类对象；`sharing_gui.asset_tree` 额外生成图片和标签叶项并展开两层；`TemplateMatchPage.update_catalog` 首次展开所有目录。

实施后：Sharing 增加 skills kind，沿用 ZIP 成员、路径、哈希、磁盘和活动互斥边界。Skill 快照复用 `agent_skills.skill_files`，拒绝链接和特殊文件；整目录同盘准备、版本复核、替换失败回滚，恢复失败保留旧副本。导入页增加独立选择、冲突动作及状态／文件详情；Asset 和 Skill 冲突操作互不影响。

Developer Skill 术语和权限没有变化，不需要新增 ADR 或修改术语表。现行使用规格见 sharing.md；历史四类对象记录保留原时点。

## 兼容性与风险

仍使用 Sharing v1 的对象 kind 扩展；旧应用会拒绝含 Skills 的包，应使用新版导入。既有四类包继续读取。未创建本地 skills 目录时导出列表为空，不为分享隐式安装默认 Skills。已开始的 Agent 轮次使用固定副本，下轮才读取变更。普通异常回滚不等于断电恢复；人工并发改文件不受应用活动锁控制，提交时重新比对目标版本。

## 验证

针对 Sharing、GUI、资源检查及模板匹配运行本地测试；新增覆盖完整目录往返、相同跳过、冲突必选、覆盖／跳过、过期目标拒绝、普通提交失败回滚、链接拒绝、默认不选和树展开／刷新行为。本地 68 项通过，另有 Qt 退出时的既有 GC ResourceWarning；`git diff --check` 通过。未运行真实 Agent、Windows 成品或游戏验收。
