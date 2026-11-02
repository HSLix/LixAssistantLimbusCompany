# #336 — 聊天交互重构实施记录

依据开发者完整 UI 要求、[已确认决定](stage-5-336-chat-ui-decisions.md)和[专项影响检查](stage-5-336-chat-ui-impact-review.md)实施。当前为本地实现及自动检查，不等同于开发者试用或 Windows 原生验收；#336 保持开放。

## 当前操作

- 左侧历史默认展开，可用聊天区左上按钮折叠；窄窗口自动收起以保留输入区。New Chat 创建新的准备状态，清空旧来源选择。小型刷新按钮在历史栏标题旁，不再占底部整行。
- 历史以首条实际用户消息的第一句为标题，超长省略，悬停可读完整内容及 UUID；下一行自然显示 🛠 Construct / 🔧 Repair。旧 Session 也可本地读取标题，不写回 / 迁移元数据，不调用模型；正被其他入口使用的会话使用已有缓存或明确的忙提示。
- 首次发送前，顶部是带滑动背景的 Construct / Repair 分段选择。来源参数通过右上“聊天上下文”打开；Construct 可空白，Repair 必须明确选择已发布版本。开始后隐藏可交互选择，标题旁显示只读模式，来源 / Prompt / 工具权限及 Candidate 仍按原 Session 固定。
- 底部圆角容器集成输入、附件、More 和一个发送 / 停止按钮。输入随换行及自动折行增高，有高度上限；更多文本在输入内部滚动。Enter 发送，Shift / Ctrl+Enter 换行，组合输入和提交候选后的同周期 Return 不发送，长按 Return 不重复提交。
- 运行时同位置切换停止图标；取消请求后显示“正在取消…”并拒绝重复取消，直到后台作业实际退出后才恢复发送。取消不删除 Session 或 Candidate。其他开发作业只禁用发送，不冒充可取消的 Agent 轮次。
- More 按工作区与页面、日志与诊断、开发与验证分组，复用原目录 / 错误详情 / 复制 / Diff / Validate / Publish 调用链。历史错误可逐条选择；无错误时显示不可用入口。无 Session 草稿或忙时不能发布；最终仍执行宿主活动 / 锁及完整校验，不因菜单启用而绕过边界。
- 聊天和工具摘要占主体，参数 / 结果按需展开；完整诊断面板与文件路径不再常驻。轮次请求信息保留在发送按钮提示，运行 / 取消 / 结果在会话内紧凑显示。Developer 窗口底部 Current activity 状态栏已删除；User GUI、最左导航及其他开发页保留。

不恢复人工 Manifest 运行或“应用到 User GUI”入口，Agent trial_run 能力保持；未改变 Agent Loop、Session 存储协议、原图处理或模式白名单，未增加依赖、模型命名、后台服务、自动记忆或 MCP。

## 主要影响与兼容处理

- 新 `chat_input.py` 只处理文本输入 / 输入法 / 高度；`developer_gui.py:RepairPage` 重排布局及菜单，`repair_chat.py:chat_title` 负责本地标题。
- `gui.py:MainWindow.launch` 对快速取消导致的 CancelledError 不再错误地交给结果回调或当作普通失败。UserWindow 借用同一关闭处理，新的会话内退出提示仅在 Developer 存在工作台时写入，保留 User 的关闭 / 清理边界。
- 诊断对象仍保留错误关联和脱敏，仅隐藏常驻显示；菜单每次打开根据当前状态刷新，并释放重建的错误菜单项。标题读取遵守已有 Candidate 锁，不恢复或重放运行。
- 更新中英翻译，以及依赖旧模式下拉、按钮、布局和状态栏的测试；新聊天不借用上一会话的隐藏来源。

## 验证与限制

- 新增 `tests/test_chat_ui.py` 覆盖 Construct / Repair 首次提交和恢复、旧会话标题与元数据不变、IME 组合 / 提交、三种快捷键、长按 Enter、输入增高 / 收缩、取消请求去重和真实清理、快速取消、菜单目录 / 历史错误 / Validate / Publish / Diff、忙状态、折叠及窄窗口控件可见性。
- 真实 pi + 本机 HTTP 替身的针对性检查：`QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest --run-agent-tests -q -x -ra tests/test_developer_session_agent.py::test_gui_send_uses_actual_pi_events_and_cli_can_continue tests/test_agent_repair_agent.py::test_trial_stop_or_round_cancel_waits_for_cleanup`，**3 passed**；不调用真实模型。
- 已生成并查看宽窗口、窄窗口和新聊天的 offscreen 截图，确认聊天占主体、模式动画控件、底部输入以及折叠 / 收起后的布局；实际 Windows 视觉、跨 DPI 及原生中文输入法仍需开发者实机检查。
- 普通全量：`QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest -q -x -ra`，**612 passed，63 skipped**。跳过的 Agent / Windows / 原生焦点 / 环境受限 IPC 检查不计通过；本轮未提交 Git，未关闭 issue。

文档检查：65 个本地链接目标存在，git diff --check 通过。另以 QT_SCALE_FACTOR=1.5 渲染并断言输入、发送和来源控件边界，不将 Qt 缩放模拟等同于 Windows 跨 DPI 验收。

## 本地试用反馈：设置底色与 JSON 纠正显示

- Developer Settings 的 QScrollArea / viewport 及内容页不再独立填充系统底色，改为透明继承，与 Capture 使用同一页面背景。通过整窗合成截图像素对比验证，避免将透明控件单独 grab 的像素当作最终颜色。
- 对应本机会话日志显示同一轮实际发生两次格式失败及两次自动纠正；保存的初始 Prompt 已有 JSON 契约及禁止 Markdown 的说明。不是宿主没有重试，也不是一次重试被执行两遍。
- 保持严格 JSON 解析及额度内自动重试，不自动剥除围栏后假称模型回答合格。加强初始 Prompt 和纠正反馈：保留实际业务回答到 message，只修正包装 / 字段类型，不把重新提示或去掉 Markdown 的工作交给用户。额度耗尽、取消和服务错误仍按原规则停止。
- 历史重建不再把 LALC_FINAL_FORMAT_CORRECTION 内部指令显示成用户消息；每轮使用一条系统摘要累计实际自动重试次数。失败事件与重试通知不再把同一次错误重复加入诊断；最终额度耗尽信息合并到对应诊断。内部消息、原始错误及模型上下文完整保留，未改写旧日志。
- 普通全量：`QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest -q -x -ra`，**615 passed，64 skipped**。相关 pi / 本机 HTTP 替身测试 **7 passed**，覆盖围栏 / 非 JSON / 字段类型错误、连续两次不合格后成功、额度耗尽及原图留存；未调用真实模型。
- 新增普通检查覆盖设置页与 Capture 的合成背景一致、旧历史中隐藏内部指令 / 原始证据保留、同轮系统摘要合并，以及实时诊断与回合预算失败去重。

需整应用重载 / 重启以加载改动。Windows 原生界面及真实模型遵从性尚未复测，本轮未提交 Git，#336 继续等待开发者确认。

### 三个反引号的明确说明

根据实际 raw_text，再将初始 Prompt、解析失败 hint 及自动纠正请求明确为：回复外层不要出现三个反引号 ```，也不要用 ```json 开头或 ``` 结尾；正文直接以 { 开始、以 } 结束。message 字符串内部仍允许 Markdown / 代码块。未改变解析器、自动纠正次数或额度。纯解析及相关检查 26 项通过；本次 pi 针对性检查首次被其他进程持有的游戏活动锁拒绝，未发送模型请求，不计为通过。
