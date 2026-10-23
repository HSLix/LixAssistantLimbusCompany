---
status: accepted
---

# Resolve Assets independently with optional priority tags

开发者于 2026-10-23 确认：Asset 不再隶属于 Manifest，Manifest 专注 Component 与 Recovery Rule。移除 Candidate 和已发布 Manifest 的专属 Asset Library 映射；素材查找按完整逻辑名直接进入共享库对应目录。代价是相同 Manifest 的后续匹配可随素材变化，不再凭 Manifest ID 固定素材；收益是新图片无需 publish 或切换 Manifest 即可使用，尤其适合未来 Agent 新增素材后继续当前 Run。

## Storage and metadata

- 逻辑名所有段都对应文件夹，例如 `assets/ui/mail/claim/`。图片名为完整 SHA-256 加 `.png`，不包含语言或其他 tag；保留完整哈希校验、已有图片不覆盖及裁剪来源记录。
- 每个逻辑名目录维护自己的 `asset-tag.json`，内容为 `hash → tag 列表`。语言只是普通可选 tag，不具有固定位置或特殊筛选规则；不自动根据游戏语言添加优先条件。
- 目录内所有有效模板图片都是候选，tag 文件不是登记白名单。查不到对应哈希的标签记录时按 `[]` 处理，图片仍参与匹配；`tag-asset` 等配置入口未提供 tag 时也明确写入 `[]`。它们不再修改 Developer Candidate，也不要求发布素材映射。
- 2026-10-23 后续修订：命令命名为 `tag-asset`。已有哈希配置 tag 时，用新列表整体覆盖旧列表，不追加、不合并、不去重，输入顺序与重复项原样保留。未提供 tag 或传空列表时写入 `[]`，可以清空旧标签。裁剪相同图片时也遵循同一覆盖规则，图片字节仍不覆盖。

## Matching and update visibility

匹配调用接受可选 `priority_tags`，默认 `None`；`None` 或空列表都表示无优先条件。与任一优先 tag 有交集的模板组成优先组，该组全部参与匹配。只要优先组有达标结果，就只返回该批结果，不匹配其余模板；若优先组无结果，则匹配剩余所有模板，包括无标签模板。保留可配置 NMS，在选定批次内统一处理重复命中，最终按分数降序、同分按确定顺序返回；不再只选一张最高分模板的结果。

每次匹配重新读取对应逻辑名目录和 tag 信息，并固定本次使用的候选与标签，过程中不重新读取。新增图片或修改 tag 从下一次匹配生效，包括同一个 Run 内；不建立跨调用的目录/tag 快照或缓存。图片内容仍按哈希验证，不因允许更新元数据而允许覆盖图片。Trace 与 Usage Index 必须能说明实际使用的图片哈希、标签、优先条件及结果，以保留运行事实。

## Scope and implementation status

本决定取代 ADR 0024 的每 Manifest 专属库、语言单图选择和随发布冻结素材的规则，也修订 ADR 0026 中相关工作台库名及登记步骤；Stage 2 的既定收尾范围不重新打开。本决定本身不授予 Agent 写入权限；后续 ADR 0028 已允许 Stage 3 通过专用现场裁剪工具新增 Asset，并要求同名同哈希复用原图与原标签，不能覆盖旧标签。开发者工具的标签整体替换规则不变。

开发者明确选择重新准备素材：旧 Asset 图片布局、旧 Candidate `asset-library.json` 及已发布专属库废弃，清理后重新裁剪、配置，不提供数据迁移、旧格式回退或长期兼容路径。该清理范围只涉及旧 Asset 及其专属库数据，不因此删除 Component 源码、Manifest、Default 选择或运行历史。历史记录保留事实引用，不保证清理后的旧图片仍可打开。

**2026-10-23 已在当前工作区实现。** Manifest/Run 已移除 Asset 映射，裁剪和 tag-asset 改用独立目录及 tag 整体覆盖，匹配支持优先批次短路/回退、跨模板 NMS、同 Run 更新可见；Trace/Usage Index、动作结果注解、测试、样例和使用指导已同步。全套回归 186 passed，变更文档链接与 git diff --check 通过。本轮没有 Windows 真机或包内验收。

清理核对：已删除样例及四组测试夹具的五份旧 asset-library.json；当前工作台为空，仓库根目录及本机默认数据目录未发现旧运行素材、专属库或旧 Asset Usage Index，本机默认运行目录本身不存在。没有删除 Component、Manifest、Default 或运行历史。其他机器的旧数据不在本次本地清理范围，使用新布局前需明确移除旧素材布局及专属库后重新准备，不自动迁移。
