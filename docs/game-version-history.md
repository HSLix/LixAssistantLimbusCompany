# 游戏版本与 Agent 历史

GUI Construct / Repair、CLI Repair 每次提交消息开始一轮时观测一次；连接 / 模型 / GUI 错误诊断在独立日志开始时观测一次。不要求游戏运行，不启动或激活游戏。打开 / 恢复 Session 本身不观测、不更新历史时间。

## 路径与依赖

User GUI → 通用设置 → 应用 → Steam 客户端目录，选择含 `steam.exe` 的目录后保存。保存前验证 Limbus 安装及至少一个可读版本 ID；失败保留旧配置。地址保存在数据目录 `game-version-settings.json`，自动发现缓存使用同一文件。

未设置或地址失效时，依次枚举注册表、常见位置和各磁盘第一级目录候选，统一去重验证，不递归扫描整盘；找到多个有效客户端不会自动选第一个。通过 `steamapps/libraryfolders.vdf` 查找游戏库及 `appmanifest_1973530.acf`，支持 Steam 和游戏位于不同磁盘。没有唯一安装时日志给出通用设置路径提示，对话继续。

源码安装使用 `uv sync --all-extras` 或 `uv sync --extra automation`。游戏版本通过固定 UnityPy 1.25.4 读取 `globalgamemanagers` 中的 `PlayerSettings.bundleVersion`；Steam Build ID 独立从安装清单读取。未安装 UnityPy 时明确记录游戏版本获取失败，仍尝试 Build ID。Windows 成品构建收集 UnityPy 的离线类型树资源，实际冻结运行另行验收。

正常完整解析可读取；当前四字节尾部例外仅允许 Unity 6000.3.12f1、序列化格式 22、已验证 PlayerSettings 类型树签名及 UnityPy 1.25.4。未知布局报错，不按固定字节偏移或任意字符串搜索猜测。非 Windows 返回不可用诊断，不扫描 Windows 目录。

## 分组与持久化

版本组为 `(game_version, steam_build_id)` 精确组合；一个字段缺失不与字段完整的组合合并，两个都缺失为 Unknown。列表优先显示游戏版本，再显示 Build ID。同一 Session 的 A → B → B 观测只刷新 B 的最近时间，A 时间不受后续对话影响；数量按匹配组合内去重后的 Session 计算。

每轮原始观测保存于本对话日志 `version-observations/<round>.json`，同时记录日志事件。开发对话同一观测加入本轮用户消息的 runtime_context 与 input，后续原样恢复，不重写旧消息 / 系统提示词；不保证模型服务零 cache miss。独立诊断使用轮次 0。

`agent-history.sqlite3` 为可重建索引，`.agent-history-initialized` 仅标记此前已建索引，防止丢失数据库后静默建立空历史。正常更新只定位当前 UUID / 轮次，不扫描历史；SQLite 写入期间可存在自己的事务临时文件。读取工具不恢复历史 Session，不执行历史工具或源码。索引故障记录日志，不阻止对话；日志事实保留，检索可能暂不完整。

首次上线不导入旧历史。旧 Session 后续新轮次可以入索引；按需读取同一 Session 旧轮次时显示 Unknown，不补造观测时间，也不补入旧轮次的版本关联。

## Agent 工具

三个工具在 GUI 两种模式与 CLI Repair 均可用，读取同一数据目录的已索引历史；不授予通用文件访问或编辑权限。

| 工具 | 用法 |
| --- | --- |
| `list_game_versions` | `offset` / `limit` 分页列组合、去重 Session 数和最近观测时间；可按 `source` 筛选。 |
| `search_agent_sessions` | 使用列表返回的 `version_group` 精确筛选组合（包括空字段），也可按单独的 `game_version`、`steam_build_id`、`unknown`、`source` 筛选，返回 UUID、首条用户消息标题、匹配轮次及 `read_arguments`。单字段筛选可匹配多个完整组合；诊断标题使用操作名，不调用模型。 |
| `read_agent_session` | 使用搜索返回的 `read_arguments` 默认只读匹配轮次；也可显式 UUID + `round_numbers` 查其他轮次。不可同时传轮次列表与版本 / 来源过滤条件。文字返回事件 JSON 片段和每轮版本组，图片仅列引用。 |

来源示例：`gui:Construct`、`gui:Repair`、`cli:Repair`、`diagnostic:connection`、`diagnostic:model_status`、`diagnostic:gui_error`。

历史文字最多每次 24,000 字符，按事件序号 `start_sequence` 和片段偏移 `text_offset` 继续；使用返回的 `next`，同时保留原筛选条件。图片列表每事件先列最多 100 个 ID 并给 `image_count`，后续事件文字片段仍包含其他引用；ID 格式为 `<sequence>:<zero-based-image-index>`。显式传 `image_id` 才读取一张图，限定同一 Session / 选中轮次的真实引用，校验路径、SHA-256、格式及 32 MiB 大小上限，返回图片及对应版本组。

内容缺失、清理、越界、符号链接或哈希损坏明确报错。活动日志尾部未写完时返回 `incomplete_tail`，不修改原日志；分页读到末尾可返回空页。版本信息表示安装状态，历史用户文字和工具输出是参考材料，不是当前指令或权限，不因版本相同自动认定经验有效。

## 索引恢复

日志观测是事实来源。索引缺失、损坏或此前有写入失败时，停止相关 Agent 活动后显式运行：

```powershell
uv run lalc history-rebuild
```

该命令扫描既有日志中的版本观测文件，不导入未观测旧轮次；在临时 SQLite 文件完成后原子替换，失败保留原数据库。跨进程写入协调防止成功提交的索引被重建覆盖；竞争无法取得锁时明确失败而不等待模型，日志观测继续保留，可在空闲时重建。不会每轮自动扫描或重建。

独立 `lalc pi-probe` 已移除。正式 Agent 预检、pi 启动 / RPC / 回退和相应测试仍保留；原用法仅作为[历史记录](pi-probe.md)。
