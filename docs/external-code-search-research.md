# codesearch 接入调研与小规模实验

2026-11-05。状态：设计确认中的调研证据，不是实施方案或验收结论。已确认边界见[设计确认](external-code-search-decisions.md)。

## 版本与来源

上游为 [flupkede/codesearch](https://github.com/flupkede/codesearch)，Apache-2.0。本次检查源码快照 `b8ea0ccb50e6652c7ca364e47f044bea7cd2b86b`；运行官方 [v1.7.9](https://github.com/flupkede/codesearch/releases/tag/v1.7.9) macOS ARM64 基础包，程序版本 `1.7.9+1`，SHA-256 校验通过。源码快照与发布包未证明为同一构建提交，发现的内部实现应在正式版本选定后复核。

## 核实的能力与边界

- semantic 检索组合向量、BM25 与标识符处理；多仓库结果再进行融合排序。它是检索器，不是生成回答的模型，不保证结果确实回答了问题。
- literal 是基于索引的全文检索，不等同于逐文件子串匹配。源码 `src/search/literal.rs` 与 `src/mcp/literal_search.rs` 有 token 分析、AND 无命中后的放宽，以及部分 regex 的原始代码块扫描回退；扫描范围仍是已索引代码块。
- 代码按 AST 切块；发现文件遵守 gitignore、codesearchignore 等规则。索引覆盖范围与当前 LALC 文本扫描不同，不能把未命中解释为仓库中不存在。
- 多仓库 serve 支持 `project`／`group`；`all` 表示其注册范围。服务既有 MCP，也提供 `POST /search`、`GET /chunk/{id}` 等 REST 接口。LALC 不必为了查询接入整个通用 MCP 工具集合；是否采用受控 HTTP 适配仍待确认。
- `CODESEARCH_HOME` 可以隔离全局配置、模型与日志；不等于索引也统一放在该目录。实测 `index add --global` 可建全局索引但不自动注册；手动注册后，本次服务仍寻找仓库内 `.codesearch.db`，不能据此承诺全局索引直接供 serve 使用。正式存储方案须复核，不能用指向外部的链接绕过 LALC 既有路径边界。
- 默认模型为量化 MiniLM；可选其他模型。基础发布包本次为 20,683,397 字节，默认模型缓存文件合计约 47.4 MB（不含索引、运行内存及其他缓存）。首次 setup 实际联网获取模型；失败一次后重试成功。“离线”指准备好资源后的能力，不代表单独二进制包含全部模型。
- 文件监视和后台增量更新不等于 Git reset 完成后索引立即一致。需要单独设计同步、索引更新与结果版本契约。
- 上游还有 SCIP 符号分析及辅助进程，例如 TypeScript 路径可调用 `npx -y @sourcegraph/scip-typescript`（源码 `src/symbols/typescript.rs`）。不应把“只暴露 search”误当作“后台不会启动其他辅助程序”；是否自动触发及如何禁用需进一步核实，不默认接入安装 hooks、联网下载工具、项目构建或符号分析。

## 实验设计

实验目录：`/private/tmp/lalc-codesearch-experiment-20261105`。只复制当前 LALC 的 14 个 Python 文件到两个临时 Git 仓库：

- runtime-reference：process_lock、application、pi_probe、knowledge、agent_policy、agent_diagnostics、manifest_reference。
- sharing-reference：sharing、agent_log、file_content、page_packages、workflow_sharing、agent_history、developer_session。

共建立 264 个代码块（129／135）。每库首次索引命令报告约 22.6／15.9 秒；macOS 运行出现 ONNX/CoreML 日志，不能据此将耗时视为 Windows CPU 指标。两库索引命令报告数据库大小约 1.15／1.12 MB，仅作本样本观察。

启动独立 `serve --host 127.0.0.1 --port <临时端口> --no-tui --quiet true`，通过 REST 对 `group=all` 搜索，limit=5，默认模型 minilm-l6-q，未开启额外 reranker。同时比较索引 literal 及原始文件的 casefold 子串扫描。实验进程已关闭。

预先指定每类问题的目标文件；下表仅记录其首次进入前五个代码块的位置，不评定代码块是否足够回答问题，也不构成准确率、完整性或真实双仓库评测。特别是取消问题还有 pi_probe.py 等合理候选，未进入指定 knowledge.py 不等于无相关结果。

| 问题主题 | 英文查询目标文件名次 | 中文查询目标文件名次 |
| --- | --- | --- |
| 防止两个进程同时操作游戏 → process_lock.py | 1 | 前五未出现 |
| 超时／取消清理子进程树 → knowledge.py | 前五未出现（pi_probe.py 有结果） | 前五未出现 |
| 日志 URL 认证信息脱敏 → knowledge.py | 2 | 4 |
| 导入历史而不恢复会话 → sharing.py | 2 | 前五未出现 |

其他观察：

- 完整自然语言问题作为原始子串均未命中；索引 literal 也均未命中。本实验未比较 Agent 将问题改写为关键词后的多步检索能力。
- `git_diagnostic`：原始子串命中 knowledge.py；hybrid 与索引 literal 的首个结果也来自该文件。
- `diagnost`：原始子串命中四个文件；索引 literal 返回零项，直接证明两种字面检索语义不同。
- 不存在的 `zxqvneveroccurs20261105`：原始子串及索引 literal 无命中，hybrid 仍返回五个近邻；返回结果不能作为存在性证明，融合分数也不能当作概率。
- 本轮服务首个混合查询约 398 ms，其余混合查询约 4–7 ms；样本很小且模型已在此前索引时准备过，不代表完整冷启动或大仓库延迟。

## 过程中观察到的接入故障

1. 首次模型准备连接 Hugging Face 时 unexpected EOF；重试后成功。
2. 受限执行环境中 ONNX/CoreML 无法创建临时工作目录；具备正常临时目录访问后建索引成功。这不是已证明的产品故障。
3. 初次全局索引失败在仓库内留下仅含 build.log 的 `.codesearch.db`，后续 add 将其识别为不完整本地索引而拒绝。对本次临时文件清理并显式指定独立日志后成功。正式接入需覆盖中断后重试，不照搬自动删除策略。
4. 全局索引、服务注册、Git 仓库初始化并非一个动作。最终使用已提交的两个临时仓库及仓库内索引完成有效检索；此前注册／路径错误响应不计入效果实验。

## 当前结论与下一步

保留原始字面搜索，增加混合检索是有证据支持的互补方案。默认 MiniLM 在本样本的中文 query 上较弱：实验固定同一批混合英文标识符、英文代码与中文注释／docstring 的 Python 语料，对比中英文 query，并非中文纯文本语料专项测试。不能据此断言所有中文 query 都差，也不能分离 query 语言、语料语言与切块粒度各自的影响。最终模型仍待确定；codesearch 自带 literal 不覆盖当前搜索的全部语义。

仍需确认：首版工具范围、服务启停时机、模型准备与交付、允许注册的仓库范围、同步与索引的失败／版本策略。之后用开发者实际参考仓库及代表性问题验证中英文检索；如需比较多语言模型，单列下载、索引资源与效果，不将本次小样本推算成生产指标。

证据原件暂存上述实验目录的 corpus-manifest.json、probe.py、probe-results.json、probe-output.jsonl、serve-initial-status.json、serve-final-status.json 与构建日志；临时目录不作为长期归档保证。本报告记录了实验条件及关键结果。
