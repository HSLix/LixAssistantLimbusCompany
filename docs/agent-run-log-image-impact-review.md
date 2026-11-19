# Agent 读取运行日志标注图

2026-11-19，已确认用 Run ID 和事件序号定位标注图。`evidence_id` 标识已保存的观察，同一张截图可被多个动作引用。匹配框、OCR 文字框和点击十字线属于各自的动作日志；标注图是按需生成的预览。原有按证据 ID 读取截图的用法继续有效。

## 影响审查

- **已确认的说明偏差。** `pi_probe.ts` 仍称 OCR 自动保存；`Runtime.trusted_action` 和 `ApplicationService._observation_evidence` 显示 OCR、模板匹配及特征匹配只引用当前已保存的观察。点击有缓存帧时保存或复用该帧。同步 pi 工具说明与 Agent 使用文档。
- **已确认的接口差距。** `RepairTools.read_run_log` 只按 `evidence_id` 返回 JPEG。日志页用 `image_annotations.action_annotations` 从具体事件提取标注。新增 `render_sequence` 精确选中动作结束事件，并对该事件引用的截图复用同一套标注数据。无命中时预览不画框；事件缺失、动作不适用或截图不可用时给出明确错误，不借用其他事件的截图。
- **受影响的入口。** pi 显式声明 Schema，远程 MCP 从 Python 签名生成 Schema 并单独映射参数类型。两处均需将 `render_sequence` 声明为整数。工具结果沿用现有图片日志与传输机制；无须修改权限、Trace、证据存储或迁移旧日志。
- **待验证的风险。** CLI 的 `gui` 依赖可省略，Qt 的文字绘制不能作为统一入口。沿用 Pillow 预览，在缩放后的图像按原图坐标绘制，检查同图不同事件、OCR 文字、点击坐标缩放、旧 PNG 和新 AVIF。另检查 pi 真实工具声明及远程 MCP Schema；底图留存、字体覆盖和成品兼容性分别验证。

## 实施验证

- 122 项普通回归通过，包含同一底图的匹配、OCR、点击和未命中预览、尺寸与坐标缩放、原图字节保留、无证据与越界拒绝，以及远程 MCP 工具声明。覆盖 AVIF 和旧 PNG。
- 随后串行运行真实 pi 与本地 HTTP 替身的定向测试，1 项通过。验证 `render_sequence` 声明为整数，调用后模型请求包含 JPEG。
- OCR 标签字形取决于系统可用字体。未在 Windows 成品、真实模型或真实游戏中验证。
