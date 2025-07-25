# 教程
[EnglishVersion](manual_en.md)
## 电脑环境要求
- 请最好在 **64** 位 Windows 系统下运行本软件
- 屏幕缩放最好定为 **150%**,否则可能会导致软件运行异常
- 游戏内语言要求必须为英文 **English**
- 要求电脑屏幕分辨率在 **1600x900 以上**，否则需要通过虚拟机等手段使得游戏环境能达到这个分辨率。如果电脑分辨率不大于1600x900，可以参考[该回答](https://github.com/HSLix/LixAssistantLimbusCompany/issues/126#issuecomment-2799048129)
- 可以的情况下，在**游戏设置选择“高”**的图像画面设置，否则识图可能不能正常工作。
- 请确保 LALC 的**目录路径全部都是英文**，否则启动时会报错提示。
- 需要在游戏设置中，选择**窗口化**。LALC 将会把游戏窗口的分辨率自动调整为 1600x900（设置显示数值），**无需手动调整游戏窗口大小**。
- 为了避免被 Windows 防火墙误杀，请自行**关闭 Windows 的防火墙（Defender）**，否则程序可能会被自动删除。
- 如果你的显示器支持 HDR 模式，请**关闭 HDR 模式**，参考[该回答](https://github.com/HSLix/LixAssistantLimbusCompany/issues/189#issuecomment-2992538140)，这将会避免图片截取时的过曝。
## 简要教程
- 在主界面，点击下方按钮即可启动软件。
- 在工作界面，点击下方暂停和停止按钮，分别可以暂停和停止运行。
- 为确保稳定性，暂停和停止按钮不会立即生效。
- 队伍编辑是队伍轮换的子按钮，队伍的顺序需要点击保存顺序才行，否则只会按上次的保存结果。
- 支持**自定义任务**，具体可查看[指导说明](json_guide_cn.md)
- 支持**自定义主题卡包选择**，编辑 `config` 中的 theme_pack.json 即
## 异常处理教程
- 游戏内更改语言设置后，须重启游戏才能使设置生效
- 如有点击异常现象，请尝试自行“用管理员模式运行”尝试修复
- 根据反馈，零协的汉化很可能需要彻底卸载并重启游戏，才能免除其影响
- 如遇到软件运行异常，请保存当日的日志文件和录像文件（分别可以在设置界面打开文件夹），然后在 GitHub 的 Issue 处反馈 Bug。
## 快捷键
- 全自动任务开始：Ctrl+Enter+F
- 半自动任务开始：Ctrl+Enter+S
- 暂停/恢复：Ctrl+P
- 停止：Ctrl+Q