# LixAssistantLimbusCompany

[English (Google Translate)](https://github-com.translate.goog/HSLix/LixAssistantLimbusCompany/blob/master/README.md?_x_tr_sl=auto&_x_tr_tl=en&_x_tr_hl=zh-CN&_x_tr_pto=wapp)

> “为了稳妥起见，也为了约束你，在那之前，我会向你下达最后的一个命令。这道命令将如底层规则一般，永远烙印在你的代码之中。”\
> 当 Bug 开始复苏，故障再次出现。\
> 玩家遭受苦难，开发者分身无术。\
> 世人呼喊你名字的那一刻——\
> 你将显化于世，驱 Bug 除错，救 Work 扬善。
>
> *——改编自《神秘复苏》（Adapted from Mysterious Revival）*

<p align="center">
  <img src="src/lalc/MagicGirl.png" alt="LALC 项目图标" width="160">
</p>

[![GitHub 发行版本](https://img.shields.io/github/v/release/HSLix/LixAssistantLimbusCompany)](https://github.com/HSLix/LixAssistantLimbusCompany/releases)
![Windows x64](https://img.shields.io/badge/platform-Windows%20x64-purple)
[![AGPL-3.0](https://img.shields.io/badge/license-AGPL--3.0-orange)](LICENSE)
[![Discord](https://img.shields.io/badge/Discord-加入群聊-5865F2)](https://discord.gg/bVzCuBU4bC)

LixAssistantLimbusCompany（LALC）是运行在 Windows x64 上的《边狱公司》自动化助手。自 2023 年 7 月 10 日立项以来，就一直想把游戏里的重复操作交给工作流，让大家有更多时间看喜欢的剧情，也有更多时间留给家人和自己的生活。

## 声明

LALC 免费开源，仅供学习交流。如果你付费购买了 LALC，请向销售方申请退款。项目图标的素材来自网络，权利归原权利人所有。

## 实用功能和亮点

- **按工作流运行任务。** 导入分享包即可安装工作流、识图素材和配套配置页。能运行哪些任务、能调整哪些设置，由所选的工作流和页面决定。
- **随时接管。** 在首页启动、暂停或停止任务，也可用 `Ctrl + Alt + P` 暂停，把游戏操作交回自己手里。注意任务执行中的行动可能会自动暂停。
- **回看现场。** 运行记录保留失败步骤、错误详情和可用截图，方便定位问题和反馈。不会看也没关系，主要是给 Agent 看的。
- **可选的 AI 修复。** 愿意自行配置模型服务的用户可以开启 User Agent。如果工作流自身无法恢复，且故障满足自动修复条件，Agent 可以尝试修复你正在使用的工作流。
- **在开发者面板自定义工作流和配置页面。** 你可以主动和 Agent 对话，说明希望自动执行哪些操作、按什么步骤执行，以及配置页面需要提供哪些选项，让 Agent 协助编写或修改。
- **应用内更新。** 首页提供发行公告、检查更新和更新安装入口。

## 下载指引

- **GitHub** · 在 [Releases](https://github.com/HSLix/LixAssistantLimbusCompany/releases) 选择带版本号的 Windows x64 ZIP。全部解压后打开 `LALC.exe`。
  - **只想运行工作流** · 下载 `-without-agent.zip` 版就够了。无需安装 Agent，也无需配置模型服务。工作流有更新时，下载并导入新版官方资源包即可。
  - **想尝试 AI 修复** · 下载 `-with-agent.zip` 版，包内已带运行 Agent 所需的 pi。按[用户指南](docs/user-guide.md#如何开启-ai-修复)配置模型服务并启用 User Agent。
- **Mirror 酱** · 已有 CDK 的玩家可以查看 [Mirror 酱项目页](https://mirrorchyan.com/zh/projects?rid=LALC)，按页面提供的版本下载。
- **5.x 用户** · 如发行页仍是 5.x，请按[旧版 README][legacy]使用对应的包。准备迁移时，见[用户指南的更新说明](docs/user-guide.md#更新程序)。

## 使用说明

打开 LALC 后，在 **通用设置 → 分享** 导入所需的工作流分享包，再回到首页选中对应版本。安装、任务设置、暂停、AI 修复和故障反馈都可以查阅[用户指南](docs/user-guide.md)。

想了解 Agent 何时介入、如何自定义和分享资源包，或其他问题可以先看[常见问题（FAQ）](docs/faq.md)。

旧版的图示和视频仍可在历史 README 中找到，所示界面和操作对应当时的版本。[图示范例][legacy-screenshots] · [视频教程][legacy-videos]

## 加入开发

欢迎通过 [GitHub Issues](https://github.com/HSLix/LixAssistantLimbusCompany/issues) 反馈问题或讨论改进，也可以加入 [Discord](https://discord.gg/bVzCuBU4bC)。框架的 Windows 构建和发版流程见[开发者指南](docs/developer-guide.md)。

## 致谢

感谢 [MaaFramework](https://github.com/MaaXYZ/MaaFramework) 对项目早期设计的启发，感谢 [OpenCV](https://github.com/opencv/opencv-python)、[Fluent Widgets](https://github.com/zhiyiYo/PyQt-Fluent-Widgets) 和 [pi](https://github.com/earendil-works/pi) 等开源项目，也感谢一路以来提交代码、测试、报 Bug 和支持项目的朋友。[贡献者](https://github.com/HSLix/LixAssistantLimbusCompany/graphs/contributors) · [早期打赏者留言][legacy-supporters]

## 友链

- [AhabAssistantLimbusCompany](https://github.com/KIYI671/AhabAssistantLimbusCompany)
- [MAALimbusCompany](https://github.com/hxdnshx/MAALimbusCompany)
- [Limbus-Scripts](https://github.com/Xie-Tiao/Limbus-Scripts)
- [LimbusCompute](https://github.com/MusicOnline/LimbusCompute)
- [AutoLuxcavation-Limbus-Company](https://github.com/LoGundes/AutoLuxcavation-Limbus-Company)
- [limbus-company-auto](https://github.com/Janrilw/limbus-company-auto)

## 最后

要是 LALC 帮你省下了几趟重复的活，欢迎给仓库点颗星，不点也行。更希望你能把省下来的时间留给自己。慢慢看一段喜欢的剧情，陪家人吃顿饭，或者早点休息，都好。

希望这个项目能替大家分担一点重复的事，也让我们多一点余力，一起更从容地面对现实，过好自己的生活。

## 许可证

本项目采用 GNU Affero General Public License v3.0，见 [LICENSE](LICENSE)。

## Star History

~~悄悄更个图，应该没人发现吧~~

[![Star History Chart](https://api.star-history.com/svg?repos=HSLix/LixAssistantLimbusCompany&type=Date)](https://www.star-history.com/#HSLix/LixAssistantLimbusCompany&Date)

[legacy]: https://github.com/HSLix/LixAssistantLimbusCompany/blob/v5.0.0/README.md
[legacy-screenshots]: https://github.com/HSLix/LixAssistantLimbusCompany/blob/v5.0.0/README.md#图示范例
[legacy-videos]: https://github.com/HSLix/LixAssistantLimbusCompany/blob/v5.0.0/README.md#视频教程
[legacy-supporters]: https://github.com/HSLix/LixAssistantLimbusCompany/blob/v5.0.0/README.md#打赏者
