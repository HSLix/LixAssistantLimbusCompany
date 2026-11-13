# 外部知识库搜索与版本更新

2026-11-05 本地实现。设计依据 [ADR 0038](adr/0038-use-versioned-reference-search-and-reusable-agent-processes.md)；不代表 Windows 成品、真实远端／真实模型或大仓库验收。

## Agent 工具

`knowledge_*` 仅访问外部知识库。Skill 正文及附图使用 `read` 和 Skill 目录下的绝对路径，不能把 Skill 相对引用交给 `knowledge_read`。知识库读取分别报告“文件不存在或不是普通文件”（检查知识库相对路径）与“文件超过 2 MiB”（拆分资料），不再合并两种原因。

仅 Developer GUI Construct／Repair 获得知识库工具；CLI／Runtime 不因进程复用或历史恢复自动获权。

| 工具 | 用途 |
| --- | --- |
| knowledge_list | 列目录，不同步 |
| knowledge_search_literal | 不区分大小写的原文子串搜索；核对标识符、字符串、部分词，不需要语义索引 |
| knowledge_search_hybrid | 向量＋BM25 按相关性寻找参考代码，可查询全部允许仓库或 repositories 指定的子集；优先英文自然语言 query，标识符保留原文 |
| knowledge_read | UTF-8／原图读取；混合搜索命中返回 read_arguments，带 sha256 拒绝搜索后已变化的内容 |
| knowledge_git | 受控 fetch／show／log／diff；显式 fetch 触发完整版本更新 |

混合搜索用于找到相关代码，字面搜索用于核对原文；混合结果的得分不是概率，空结果不证明仓库不存在相应内容。混合工具描述中已直接说明两者区别。旧 knowledge_search 不再用于新调用，历史记录原样保留、不迁移、不重放。

## 参考仓库与 A/B 更新

开发者在 `data_root/knowledge/` 下准备独立普通 Git clone，配置明确 upstream 与非交互认证。知识库根、仓库根、`imported-agent-history/` 保留目录、嵌套仓库、指针型 .git、Git 元数据链接／junction 和外部对象目录不纳入受控仓库。普通资料中的符号链接／junction 只跳过该条目，不阻止其余文件构建版本；不跟随链接，不复制目标内容。普通文本／图片与导入历史不要求 Git 或索引。

原 clone 是发现及初次准备入口；Agent 默认读取的可用参考版本位于 `data_root/knowledge-versions/<仓库身份>/<版本>/`，由 active.json 选择。工具始终呈现知识库相对路径；文件管理器中原 clone 不会被替换为链接，也不会随工具版本指针自动移动。不要用原 clone 的 HEAD 判断 Agent 已读取的版本，应查看工具的 available_commit／commit。自写资料放普通目录，Git 资料副本不承诺保留本地修改。

每轮首次内容访问尝试一次更新，同轮不自动重试；显式 fetch 可再试。流程为：

1. 在真实目标盘预检副本及构建空间，保留当前 A。
2. 在独立 B 中复制、fetch、解析明确 upstream 提交并 reset；禁用内容转换器，不递归更新 submodule。
3. 显式构建固定模型索引并实际查询验证；文件和索引完整后替换版本指针。
4. 成功后读取／字面搜索／Git 查看／页面资源复制均解析可用版本；服务在注册集合未变时复用。提交及文件哈希均未变化则复用已有索引。

复制前和更新后均排除普通资料链接；Git 的 `120000` 文件模式用于识别 Windows 上检出为普通文本的链接。索引构建前移除副本中的这些条目，原 clone 不变；同步结果和版本记录的 `excluded_links` 列出仓库相对路径，复用版本时继续返回该列表。版本覆盖其余正常文件，不代表链接目标也已被读取或索引。因受控副本排除了已跟踪链接，Git status 可能显示这些路径被删除；这不表示原 clone 的文件被删除，Git 提交查看仍可返回链接本身的目标路径文本。

容量估算不能预知远端增长或并发磁盘占用。预检不足、无法查询容量、实际 ENOSPC、fetch／reset／索引失败均报告 update.ok=false 与脱敏原因并记日志，继续使用此前 A；不同仓库独立处理。没有可用旧索引时混合搜索不可用，但字面搜索和读取保留。失败不伪装为零命中或最新版本。

codesearch 版本探测与 Git 根路径探测捕获原始字节，在调用线程严格按 UTF-8 解码；索引元数据也按 UTF-8 读取，不依赖 Windows 系统代码页。非法编码按更新失败处理，不以替代字符构造路径，也不在子进程输出读取线程中解码而触发全局致命错误。

过期或未完成生产副本在成功更新后清理，清理失败记日志；这不清理 `.generated/external-search-validation/` 中按开发者要求保留的验证代码／资源／结果。

## codesearch 资源与进程

固定使用 codesearch **1.7.9 基础版**和量化 MiniLM，固定模型 revision `751bff37182d3f1213fa05d7196b954e230abad9`；不包含 SCIP 分析辅助程序。普通使用不自动下载安装。

Windows 外部安装可将基础版 `codesearch.exe` 与 `models/` 放在同一目录，把该目录加入系统 `Path`，重启应用即可，无需额外模型路径变量。源码开发也可将本机基础版放在 `codesearch_resources/codesearch`（Windows 为 codesearch.exe），模型缓存放在该目录的 models/。也可明确设置：

```text
LALC_CODESEARCH=<本机 codesearch 基础版绝对路径>
LALC_CODESEARCH_MODELS=<已准备的模型缓存根，内含 models--Xenova--all-MiniLM-L6-v2/>
```

没有资源目录中的程序时可从 PATH 找 codesearch。未显式配置模型路径时，依次寻找所选程序旁的 `models/`、随包资源的 `models/`、`data_root/codesearch/models/`；只跳过不存在的目录，已存在但缺文件或哈希不符直接报错。显式模型路径不存在时仍沿用数据目录缓存回退，不改选随包模型。应用检查固定模型文件哈希，再准备自己的缓存与单独基础版程序；不共享用户 repos.json。服务只监听本机临时端口，使用专用注册表、只读索引与受限 Git 工具路径，不开放符号分析或远端 federation。缺失资源或服务启动失败时向 Agent 反馈不可用，可改用字面搜索／读取。

pi 和 codesearch 首次需要时启动，跨轮次／Session 复用，由 ApplicationService 在宿主退出或重载时关闭；关闭 Developer GUI 本身不等于关闭整个应用。pi 每轮 new_session 并加载宿主轮次配置，权限、历史、根目录、额度和提示不继承旧轮；连接配置变化时重建进程。pi 中途退出结束本轮，不重跑工具，下轮再启动；取消或异常后丢弃无法安全复用的进程。不使用后台保活或周期探测。

Windows 双包的资源路径与构建输入见[打包说明](windows-packaging.md)。普通测试和显式 Agent 测试分开串行执行；本地实现证据与剩余限制见[实施记录](external-code-search-implementation.md)。
