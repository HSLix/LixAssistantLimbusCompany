## Parent

Spec #323；原 Stage 3 跟踪 #312。已确认步骤 2/6。

## What to build

开发者通过独立修复 CLI 指定一个现有 Component，提供问题、异常和截图；LALC 从 Default 重建 Developer Candidate，真实模型只修改目标源码，调用现有 Validator 迭代，最终输出源码、Diff、校验结果与完整日志。

## Acceptance criteria

- [ ] 来源和目标检查先于候选清空；没有有效 Default、加载失败、目标缺失不启动 Agent、不破坏旧草稿、不改选历史 Manifest。
- [ ] 有效启动替换已有 Developer Candidate，可读全部候选文件但只写指定 Component；拒绝任意路径、其他源码及候选 Manifest 写入，不自动 Publish 或改变 Default。
- [ ] 源码读取与修改复用 pi 的 read/edit，通过扩展或文件操作接口实施权限检查，不重写文本替换或编辑引擎；不把工作目录当作隔离，不开放通用 write 或终端工具。
- [ ] 接收初始截图/异常/问题描述和 LALC 编写约束；不引入游戏模拟或候选自动运行。
- [ ] Validator 反馈实际回到模型；结束时重新校验最终源码，输出实际 Diff，不把校验通过称为行为修复成功。
- [ ] 默认 20 次请求并支持本次设置；超限、模型错误和取消停止并保留产物，信息不足时最终回答说明缺少什么并结束。
- [ ] 完整日志和原始/最终产物在数据目录留存，后续重建候选不会抹掉前次记录；错误、取消与校验失败也有明确结束原因。

## Blocked by

- #324
