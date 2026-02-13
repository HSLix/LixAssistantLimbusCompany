# Changelog

## [4.11.0](https://github.com/HSLix/LixAssistantLimbusCompany/compare/v4.10.1...v4.11.0) (2026-02-13)


### Features

* 增加字体切换功能，兼容霞鹭文楷 | add font setting Fixed [#256](https://github.com/HSLix/LixAssistantLimbusCompany/issues/256) ([99eb8cb](https://github.com/HSLix/LixAssistantLimbusCompany/commit/99eb8cb0330c925ab81c071888b930178cfd8528))


### Bug Fixes

* 修复了导入默认配置导致队伍风格倾向失效 | fix the default config make the error of team style ([e0dd741](https://github.com/HSLix/LixAssistantLimbusCompany/commit/e0dd741a634b76f098bdce1f067b3c67b1e615bc))
* 修复了战斗过程中可能卡在事件的问题 | fix the bug that battle may stuck at the event ([22211c1](https://github.com/HSLix/LixAssistantLimbusCompany/commit/22211c1e19867306bfc8cebee4083db0e361d174))
* 更新默认配置 | update default config ([e371b43](https://github.com/HSLix/LixAssistantLimbusCompany/commit/e371b431732e94f5bb3d929339ef41d18dc11faf))
* 通过处理重试后，返回主界面，避免因各种情况下错误导致流程中断无法推进的 bug | fix the bug that lalc will stuck after deal with the retry popup by going back to the main page ([bc60201](https://github.com/HSLix/LixAssistantLimbusCompany/commit/bc6020126e97b7b2d6a140c6d4dbfe9a4eb66ead))

## [4.10.1](https://github.com/HSLix/LixAssistantLimbusCompany/compare/v4.10.0...v4.10.1) (2026-02-06)


### Bug Fixes

* 修复了开发环境和生产环境没有彻底同步导致的启动异常 | fix the problem of the release environment is not complete Fixed [#258](https://github.com/HSLix/LixAssistantLimbusCompany/issues/258) ([fa2837c](https://github.com/HSLix/LixAssistantLimbusCompany/commit/fa2837ca8257acc03127eda1c017b2191e44c0dc))

## [4.10.0](https://github.com/HSLix/LixAssistantLimbusCompany/compare/v4.9.1...v4.10.0) (2026-02-05)


### Features

* 增加前端对于节点权重和 ego 启用开关的设置 | add the config for legend weight and the switch of E.G.O ([042c7f3](https://github.com/HSLix/LixAssistantLimbusCompany/commit/042c7f30980124a3dcf625db6016ef8a382bd7f9))
* 增加流程对 ai 模型的适配 ([13c299b](https://github.com/HSLix/LixAssistantLimbusCompany/commit/13c299b08f03042836c677b329baa34e31bac0a3))
* 增加识别拼点状态的 ai 模型 | add the ai model for skill icon ([8e93c48](https://github.com/HSLix/LixAssistantLimbusCompany/commit/8e93c481a046c9089bbd060825ebcabe7d903b06))
* 增加识别镜牢寻路的 ai 模型 | add the ai model for mirror path ([63c0d4e](https://github.com/HSLix/LixAssistantLimbusCompany/commit/63c0d4e9187e77f4bb07f6abdb6b30364a821793))
* 增加识别镜牢节点的 ai 模型 | add the ai model for mirror legend ([5e90504](https://github.com/HSLix/LixAssistantLimbusCompany/commit/5e9050442d837a23762ab7b46e26ace57e6d506d))


### Bug Fixes

* 修复了人数过少会卡在战斗的问题 | fix the stuck when the number of sinner in battle is too low ([6bc1ee8](https://github.com/HSLix/LixAssistantLimbusCompany/commit/6bc1ee8c93cb7053f407933891e8a6b77d887aeb))
* 修复了在处理事件过程中，由于弹窗透明度过高，卡在无法识别和处理错误的时候 | fix the stuck when network error occur and the skip still be seen by program ([eaefdcd](https://github.com/HSLix/LixAssistantLimbusCompany/commit/eaefdcde3a955414d58f88e44b6f039a5263d867))
* 修复了金额设置过低导致卡在商店的问题 | fix the low stopPurchaseGiftMoney Fixed [#254](https://github.com/HSLix/LixAssistantLimbusCompany/issues/254) ([b7713d0](https://github.com/HSLix/LixAssistantLimbusCompany/commit/b7713d0be2fc250d392cef9cb32bb293b1fde978))
* 修复了镜牢返回主页不稳定可能卡住的问题 | fix the bug that may stuck when lalc wants to go back the home page ([52a52e8](https://github.com/HSLix/LixAssistantLimbusCompany/commit/52a52e8e39487a2cf34f750f0628580b23f73781))
* 修复技能选择错位和卡在技能选择的问题 | fix the problem when choosing ego ([8db1a9f](https://github.com/HSLix/LixAssistantLimbusCompany/commit/8db1a9f01784703d4cde05ed9ac5c807160e0516))
* 提升队伍选择的稳定性 | make the team choose more stable ([322cd99](https://github.com/HSLix/LixAssistantLimbusCompany/commit/322cd99e7392e875771c050f038ec0fe447f5f5f))
* 提高了镜牢进入的稳定性 | make the mirror enter more stable ([aa98004](https://github.com/HSLix/LixAssistantLimbusCompany/commit/aa980042da079170bc437c519d469ccbe51d8ea0))
* 添加对事件 buff 的互动处理 | deal with the select event effect [#253](https://github.com/HSLix/LixAssistantLimbusCompany/issues/253) ([8cf6fd2](https://github.com/HSLix/LixAssistantLimbusCompany/commit/8cf6fd28ab225df2b1c11d81464dc8e254392235))
* 补充性能分析的平均模块 | add the avg of performace analyse ([9280fba](https://github.com/HSLix/LixAssistantLimbusCompany/commit/9280fbac6f355fc1f44fef48b86576a7886a2190))

## [4.9.1](https://github.com/HSLix/LixAssistantLimbusCompany/compare/v4.9.0...v4.9.1) (2026-01-17)


### Bug Fixes

* 修复了任务结束的结束通知没有发出来的问题 | fix the missing of finish task notification ([083b47e](https://github.com/HSLix/LixAssistantLimbusCompany/commit/083b47e382b673e575f04ff095e57feacaf8948d))

## [4.9.0](https://github.com/HSLix/LixAssistantLimbusCompany/compare/v4.8.3...v4.9.0) (2026-01-15)


### Features

* 增加了对于客户端没有升级的提醒 | add the remind of client is not up to date ([89a573d](https://github.com/HSLix/LixAssistantLimbusCompany/commit/89a573daa8b45cd122e54c95042fbedb82d2f21c))


### Bug Fixes

* 修复了日志调用容易混淆 | make the log more easy to use in backend ([4c64dcb](https://github.com/HSLix/LixAssistantLimbusCompany/commit/4c64dcbd4ff4271a256d86e3f7f68d16f97b608d))
* 修复了暂停接停止会导致下次开始不了的bug | fix the bug that pause ([afa9355](https://github.com/HSLix/LixAssistantLimbusCompany/commit/afa9355d31c9e79ab2c3e888465e0fa88dfc3057))
* 修复了更新的时候前端和后端没有相继关闭的bug | fix the bug that frontend and backend can not close as expected ([f697c2e](https://github.com/HSLix/LixAssistantLimbusCompany/commit/f697c2e02c6a3e277ff95bd1dcc9126094a95e9f))
* 修复了没有正确获取版本号的问题 | fix the bug that get wrong version number ([7e25ec2](https://github.com/HSLix/LixAssistantLimbusCompany/commit/7e25ec2278d940691e077d557965a5c06d59ea37))
* 减少日志图片占用，并将日志部分图片记录替换成识别结果 | reduce the size of log's images and replace some of them with the ressult of recognition ([9e76427](https://github.com/HSLix/LixAssistantLimbusCompany/commit/9e764278d847d235aa349d37515de7935d6beaac))
* 后端识别兼容纽本 | make recognize can see the thread lv60 ([5b69138](https://github.com/HSLix/LixAssistantLimbusCompany/commit/5b6913860ccfa5cdf3ced0643e761cb15ccef3f3))
* 增添并丰富 star 和 discord 界面 | add and enrich star page and discord page ([80492e2](https://github.com/HSLix/LixAssistantLimbusCompany/commit/80492e2f03c7bb1109644c16626595733241d7b6))
* 提升饰品合成的稳定性 | make the task of fuse gift more stable ([f36b7e9](https://github.com/HSLix/LixAssistantLimbusCompany/commit/f36b7e9e6d20f4d17a9f870e036e6100c13433f7))

## [4.8.3](https://github.com/HSLix/LixAssistantLimbusCompany/compare/v4.8.2...v4.8.3) (2026-01-14)


### Bug Fixes

* 调整通用延迟实现加速 | make the common delay shorter ([c7e4e8c](https://github.com/HSLix/LixAssistantLimbusCompany/commit/c7e4e8cba19d7a610ba6c5455e3e509d071c6c03))

## [4.8.2](https://github.com/HSLix/LixAssistantLimbusCompany/compare/v4.8.1...v4.8.2) (2026-01-13)


### Bug Fixes

* 为解决卡在饰品选择的情况，增加饰品选择标识物 | to avoid stuck when acquire ego gift, lalc add other sign to know time to acquire ego gift ([f52009f](https://github.com/HSLix/LixAssistantLimbusCompany/commit/f52009f0fae7f61a9b8779dc30b6efec9fd2b7e6))
* 修复了可能卡在中途加入镜牢的bug | fix the bug that can stuck when enter the mirror ([dd7cf87](https://github.com/HSLix/LixAssistantLimbusCompany/commit/dd7cf8741955232aa851c09b39e6ecc560a35286))
* 修复了有时镜牢只刷了一次就停止的错误 | fix the bug that mirror only run single turn and stop no matter what config is ([571834b](https://github.com/HSLix/LixAssistantLimbusCompany/commit/571834b2773caabe31476d0f8519cb157e926bfb))
* 补充奖励获取的带图日志 | add the log with image in get reward ([7144e64](https://github.com/HSLix/LixAssistantLimbusCompany/commit/7144e64290d34540187006552a545732a7012d47))

## [4.8.1](https://github.com/HSLix/LixAssistantLimbusCompany/compare/v4.8.0...v4.8.1) (2026-01-13)


### Bug Fixes

* 优化镜牢进入的流程 | make the enter mirror dungeon better ([b5bbeb8](https://github.com/HSLix/LixAssistantLimbusCompany/commit/b5bbeb81f72b41dcca892693d63645e65eace186))
* 修缮流程，提高镜牢流程的稳定性 | make the mirror task running more stable ([0d93264](https://github.com/HSLix/LixAssistantLimbusCompany/commit/0d93264faa6df39194dcf5b8360e73b779890e31))
* 增加对于 SSL 报错的提醒 | add the remind of the ssl error of github download ([c48aeb1](https://github.com/HSLix/LixAssistantLimbusCompany/commit/c48aeb12f8e6e0effc25c3669ff2c7becc2d9cf9))
* 补上所有的困难主题包 | add the rest of themepacks of hard more ([47ca3e2](https://github.com/HSLix/LixAssistantLimbusCompany/commit/47ca3e26bd28f89c224340e787c2ca683ee9ce23))

## [4.8.0](https://github.com/HSLix/LixAssistantLimbusCompany/compare/v4.7.1...v4.8.0) (2026-01-12)


### Features

* 增加对于网络不稳定的自动重启 | add the automatically reboot for the unstable network ([9ef9a7e](https://github.com/HSLix/LixAssistantLimbusCompany/commit/9ef9a7e9eff8ba179168bb1449eaa8f9a7379dbd))


### Bug Fixes

* 尝试修复在个别设备点击效果不稳定的问题 | try making the click more stable by double the duration between press and release ([5122869](https://github.com/HSLix/LixAssistantLimbusCompany/commit/51228699d59c9350e67917821027a25baf4a0ec2))
* 更改截图的鼠标移动不归位，提升效率并且避免因为鼠标多次移动导致实际坐标紊乱 | get rid of  the reset of mouse to make it more stable ([11be629](https://github.com/HSLix/LixAssistantLimbusCompany/commit/11be629bc5e4ba2f02bebab3965819ab0ad4f12a))

## [4.7.1](https://github.com/HSLix/LixAssistantLimbusCompany/compare/v4.7.0...v4.7.1) (2026-01-11)


### Bug Fixes

* 修复了主题包自更新可能引发的配置不统一问题 | fix the bug that configs are different between backend and frontend ([f23045a](https://github.com/HSLix/LixAssistantLimbusCompany/commit/f23045aa354d79af0bd67517202577d2d604f345))
* 修复了全是 very low 无法选择的 bug | fix the stuck in the event pass ([16fc547](https://github.com/HSLix/LixAssistantLimbusCompany/commit/16fc547f3d9ce070f20d71e5f28e1bf3a100a78c))
* 修复了后端对于主题包更新后残留的处理 | add the remove of the outdated theme pack data ([e1e5bfe](https://github.com/HSLix/LixAssistantLimbusCompany/commit/e1e5bfe4f96d22d45c2998f66bdc4391f533e464))
* 修复了执行次数没有归零的错误 | fix the bug that execute count can not reset ([5afb14c](https://github.com/HSLix/LixAssistantLimbusCompany/commit/5afb14cee8aef6c883f6858b6a2da1cb5c5bb49f))
* 修复楼层末选饰品重复点击的问题 | fix the bug that duplicate click of floor ego gift ([f1d64d6](https://github.com/HSLix/LixAssistantLimbusCompany/commit/f1d64d66ef773033d795e31787a1574db383acd8))

## [4.7.0](https://github.com/HSLix/LixAssistantLimbusCompany/compare/v4.6.0...v4.7.0) (2026-01-10)


### Features

* 增加结算奖励自定义 | add the choice of accept the reward or not ([ea55925](https://github.com/HSLix/LixAssistantLimbusCompany/commit/ea559256f95266c1cfcb81a5a96c4fef7dcdcf13))


### Bug Fixes

* 修复了对于还没执行过的日志的导入错误问题 | fix the error the import the log of never execute the task ([cb93ef7](https://github.com/HSLix/LixAssistantLimbusCompany/commit/cb93ef757896d46980b452e3d1f254d8c3724f84))
* 尝试修复关底饰品选择不了 | try fixing the error of select floor ego gift [#236](https://github.com/HSLix/LixAssistantLimbusCompany/issues/236) ([c7a98c7](https://github.com/HSLix/LixAssistantLimbusCompany/commit/c7a98c7e765e3f3f82ba35d58ccaa576eb7bdd4b))

## [4.6.0](https://github.com/HSLix/LixAssistantLimbusCompany/compare/v4.5.1...v4.6.0) (2026-01-09)


### Features

* 增加经验采光09 | add exp 09 ([45234ea](https://github.com/HSLix/LixAssistantLimbusCompany/commit/45234ea93bcdae63f4ca663065469d815abd7a40))
* 给主题页动态刷新功能 | add fresh button on theme pack page ([f2137de](https://github.com/HSLix/LixAssistantLimbusCompany/commit/f2137de438e65487fdb4b1e385e6dcf2e087441e))


### Bug Fixes

* 修复最后的界面无法打开 | fix the At last slide window ([6d2316e](https://github.com/HSLix/LixAssistantLimbusCompany/commit/6d2316e596bb30be46482aed8b30678a5d6a9d1d))
* 修复因错误识别战斗标识导致卡死 | fix the stuck due to recognize the winrate in the wrong place ([f18f963](https://github.com/HSLix/LixAssistantLimbusCompany/commit/f18f963fc4bf89d804cdb5b54efd131e5aeefcba))
* 修复自动更新只下载不更新的问题，且修复自动更新会卡顿的问题 | fix the bug that update will not execute correctly and will not stuck again ([95dfe48](https://github.com/HSLix/LixAssistantLimbusCompany/commit/95dfe48f0d2ca0e4d746dec22329848306e089e0))
* 修复跳过普通异常的问题 | fix the skip battle of exp and thread ([7edcd58](https://github.com/HSLix/LixAssistantLimbusCompany/commit/7edcd58ea7b2105eead10df1c0be1b465fe2bdd3))
* 统一前后端图片来源 | make frontend and backend share with the same images ([8ed10b8](https://github.com/HSLix/LixAssistantLimbusCompany/commit/8ed10b84a02e95c97c89946f0068828d17b7d910))
* 补充任务预览内容 | add the preview of task ([2aeb3fd](https://github.com/HSLix/LixAssistantLimbusCompany/commit/2aeb3fdf5c3b59cec07ae6027a5a5a7bb0e06917))

## [4.5.1](https://github.com/HSLix/LixAssistantLimbusCompany/compare/v4.5.0...v4.5.1) (2026-01-08)


### Bug Fixes

* 更换cdk加密解密为更通用的方法，注意此前保存的cdk失效，需要重新保存 | use a better method to save cdk, and the cdk you save now needs to be saved again Fixed [#232](https://github.com/HSLix/LixAssistantLimbusCompany/issues/232) ([b9341b6](https://github.com/HSLix/LixAssistantLimbusCompany/commit/b9341b6d63cc11d59cf0d99147839d5b1967a2d6))

## [4.5.0](https://github.com/HSLix/LixAssistantLimbusCompany/compare/v4.4.1...v4.5.0) (2026-01-07)


### Features

* 初步适配困难模式 | suit a part of hard mode ([e07a741](https://github.com/HSLix/LixAssistantLimbusCompany/commit/e07a741774d6317cd14cb27304476655bcccb027))
* 增加半自动模式（纯P） | add semi auto mode(just p) ([7c02e3f](https://github.com/HSLix/LixAssistantLimbusCompany/commit/7c02e3f1f365c8420cb2c8be96e192c82ef6eda1))
* 增加性能监测 | add the monitor of actions ([49e762d](https://github.com/HSLix/LixAssistantLimbusCompany/commit/49e762da4e422664dbb2a2dd2b89cd4d26deba8f))
* 增加运行结果通知 | add the notification of a single run ([acfa18b](https://github.com/HSLix/LixAssistantLimbusCompany/commit/acfa18b1827ac2dacaceaf9857ae19a875ed6c45))
* 增加镜像地牢商店的自定义选项 | add the custom choice for mirror shop ([6a47331](https://github.com/HSLix/LixAssistantLimbusCompany/commit/6a4733123e8a3e28333c6d183b745e1ed6fcf2a1))
* 增加队伍自动轮换更新 | add the auto rotate team ([3c27e72](https://github.com/HSLix/LixAssistantLimbusCompany/commit/3c27e72668fd33dbc3f9dda71524b6d1208c42e3))


### Bug Fixes

* 修复了以前不会选满人的bug | fix the bug that previous version can not select as more sinner as possible ([0ed9a7e](https://github.com/HSLix/LixAssistantLimbusCompany/commit/0ed9a7ebd297a50d532949bcdd592eb68667b5b1))
* 修复了任务执行次数无法正确统计的问题 | fix the bug the can not report the count of task execution correctly ([a21a561](https://github.com/HSLix/LixAssistantLimbusCompany/commit/a21a561397f80e0bfb72ed8d8ad1846913f0e96f))
* 修复了任务页队伍流派国际化缺漏，以及队伍配置页国际化不规范的问题 | fix the missing of l10n for team style in task page and hte problem of l10n in team config page ([836b310](https://github.com/HSLix/LixAssistantLimbusCompany/commit/836b310ae787a4e17072226f1c7e60c5cc92ea5c))
* 修复了前端刚启动时没有连接的问题 | fix the error that frontend do not connect to websocket at the beginning ([958043d](https://github.com/HSLix/LixAssistantLimbusCompany/commit/958043dd548a6aab69fef0f52314162926a10b24))
* 修复了队伍轮换没有正常启动的问题 | fix the bug that team rotate error ([a5d9d38](https://github.com/HSLix/LixAssistantLimbusCompany/commit/a5d9d38bc46d9cc1770516f1665895b3f8872f64))
* 修复了鼠标活动时，仍可能抢占的bug | fix the bug that it will take the control of your mouse even if you are using it ([ceb7a26](https://github.com/HSLix/LixAssistantLimbusCompany/commit/ceb7a260665093538ca7a605d69e1561baf56bcb))
* 修复任务页国际化不完全的问题 | fix the l10n of taskpage ([f61597b](https://github.com/HSLix/LixAssistantLimbusCompany/commit/f61597bed9cace1184fcd3755c00a566dcd5f80d))
* 增加镜牢商店结束后的延迟，避免因为错位识别导致卡住 | add the delay after finish the mirror shop ([18992cb](https://github.com/HSLix/LixAssistantLimbusCompany/commit/18992cb17fe231acd0860886dd3ec593d61464f5))

## [4.4.1](https://github.com/HSLix/LixAssistantLimbusCompany/compare/v4.4.0...v4.4.1) (2026-01-03)


### Bug Fixes

* 修复了前端出现多个网关发送和接收信息的问题 | remove the useless gateway ([08345cc](https://github.com/HSLix/LixAssistantLimbusCompany/commit/08345ccb42933722035a60684fa3479e1954443c))
* 尝试修复主程序无法启动前端的问题 | try to fix can not launch front end [#229](https://github.com/HSLix/LixAssistantLimbusCompany/issues/229) ([be3f0f8](https://github.com/HSLix/LixAssistantLimbusCompany/commit/be3f0f859071311a01b6f1683525885dc9941710))

## [4.4.0](https://github.com/HSLix/LixAssistantLimbusCompany/compare/v4.3.0...v4.4.0) (2026-01-02)


### Features

* 增加对空饰品倾向的提醒，添加队伍倾向时也会添加到饰品倾向，去除时也会同步去除 | add the remind of empty gift style list, the gift sytle will add sytle when change team style list ([694cad2](https://github.com/HSLix/LixAssistantLimbusCompany/commit/694cad24a81843b92697fd9043f134c78fd17d77))


### Bug Fixes

* 修复了启动程序报错无法延迟 | fix the bug that start programme can not sleep Fixed [#227](https://github.com/HSLix/LixAssistantLimbusCompany/issues/227) ([7921c7c](https://github.com/HSLix/LixAssistantLimbusCompany/commit/7921c7cd15ed9077fff86f76ee33f016696bc5ac))
* 修复了日志对于长段内容没能完全展示的错误 | fix the error of not display the whole content of log dialog ([78aa54a](https://github.com/HSLix/LixAssistantLimbusCompany/commit/78aa54adb504c22b3f944899f67270b4484c209f))
* 增加队伍是否为空的检查，也算解决了卡在队伍选择的问题 | add the check of no team for tasks, avoid stucking when choosing the team ([ed70c07](https://github.com/HSLix/LixAssistantLimbusCompany/commit/ed70c0790cb18d1abf6da3809798513e5696c790))

## [4.3.0](https://github.com/HSLix/LixAssistantLimbusCompany/compare/v4.2.0...v4.3.0) (2026-01-02)


### Features

* 增加了新版本更新的提醒 | add the notification of the new version ([764cca0](https://github.com/HSLix/LixAssistantLimbusCompany/commit/764cca0476133438d92d136d1f4bcb08e52175e6))


### Bug Fixes

* 修复了主程序启动时莫名闪退没有报错提示的问题 | fix the missing the message box for the error in main programme ([576b11b](https://github.com/HSLix/LixAssistantLimbusCompany/commit/576b11b76e3b4acd030f982e3c5dc2559763b326))
* 修复了因为各种中间窗口，无法获取鼠标坐标，导致程序中断 | fix the intterupt for the error of aucquiring cursor position ([8d5d1cf](https://github.com/HSLix/LixAssistantLimbusCompany/commit/8d5d1cf3ad21b3382b110b9fd539820f175d9d10))

## [4.2.0](https://github.com/HSLix/LixAssistantLimbusCompany/compare/v4.1.0...v4.2.0) (2026-01-01)


### Features

* 增加自动回归初始界面的代码 | can back to the init page automatically ([f348be2](https://github.com/HSLix/LixAssistantLimbusCompany/commit/f348be2c00b15e112a420e94c6225f037b5b9230))


### Bug Fixes

* 修复了选人时，取消选择中间顺序成员而已选成员顺序没有更新的bug | fix theerror of do not update the selected member when cancel the middle order sinner ([f42effa](https://github.com/HSLix/LixAssistantLimbusCompany/commit/f42effaadf327d7ebb0ec119e16679dcc790e08b))
* 前端打开失败，事件图片识别不良，固定镜牢难度，避免没有选择倾向饰品卡住 | fail to launch frontend, fail to recognize event pass, fix the normal of mirror, fail to stuck when choose prefer gift style ([4d3ff88](https://github.com/HSLix/LixAssistantLimbusCompany/commit/4d3ff881c1a98907e267b251c9c27dad63269928))

## [4.1.0](https://github.com/HSLix/LixAssistantLimbusCompany/compare/v4.0.0...v4.1.0) (2025-12-31)


### Features

* 让游戏窗口保持规定大小 | keep the game window size in curtain shape ([06b4c8e](https://github.com/HSLix/LixAssistantLimbusCompany/commit/06b4c8eb268901a9ddcc787efacd28ad74b35768))


### Bug Fixes

* 修复了教程没有正常显示的问题 | fix the bug of show the tutorial ([dadf1c7](https://github.com/HSLix/LixAssistantLimbusCompany/commit/dadf1c7921fd82a76dc72a8237fdd29d12894b6a))
* 修复事件判定模板因更新失效的问题 | fix the error that lalc wold stuck at the event pass due to the change of pass words ([3dc08cb](https://github.com/HSLix/LixAssistantLimbusCompany/commit/3dc08cb6add0cda5c8685d91064b905fdc70b634))
* 更换获取 UUID 的方式，避免个别设备没有 wmic 这个工具 | get rid of wmic to get the uuid ([daa88d7](https://github.com/HSLix/LixAssistantLimbusCompany/commit/daa88d776e16d2827508d31d3a8a538cc8965695))
* 让英文路径报错时，能输出当前路径辅助调试 | add the detail of the english path error to show current path ([db08f5f](https://github.com/HSLix/LixAssistantLimbusCompany/commit/db08f5f9e86c14e9a02e833d560443f8a3f7e30b))

## [4.0.0](https://github.com/HSLix/LixAssistantLimbusCompany/compare/v1.0.0...v4.0.0) (2025-12-30)


### Bug Fixes

* 修复版本号的问题，完成重构 | the error of version, finish rebuilding ([6de7d21](https://github.com/HSLix/LixAssistantLimbusCompany/commit/6de7d21730f381c6b02f6d7bcd0fdc5e51e52a9c))

## 1.0.0 (2025-12-30)


### Features

* 1. add team6; 2. suit enter mirror6; ([cfc540b](https://github.com/HSLix/LixAssistantLimbusCompany/commit/cfc540b419c3eecd7894e7a5748c1452cfa6c14a))
* accelerate skip event ([0432a54](https://github.com/HSLix/LixAssistantLimbusCompany/commit/0432a54ab3b8af37fcb9ffa3c26f11149174e038))
* accept reward when fail in mirror ([dea6a64](https://github.com/HSLix/LixAssistantLimbusCompany/commit/dea6a64e85a9b6e3f0200822e28473298b88a61f))
* add exit action ([73f61c5](https://github.com/HSLix/LixAssistantLimbusCompany/commit/73f61c5302aa43f6ea6b7305816f96a210763b7a))
* add team edit assistance ([4d26c4c](https://github.com/HSLix/LixAssistantLimbusCompany/commit/4d26c4c74301a9d77b526c56c3dd8805efdea49b))
* add the translation of three new trend for chinese ([39237d7](https://github.com/HSLix/LixAssistantLimbusCompany/commit/39237d77ec1757b0cfad47530fe1c245ef7ee8bd))
* custom mirror starlight ([4782598](https://github.com/HSLix/LixAssistantLimbusCompany/commit/4782598ea5986819af6df792a67b539570ac114f))
* make sure screen scale is 150% ([8b16c7f](https://github.com/HSLix/LixAssistantLimbusCompany/commit/8b16c7fdf2c9a7564617ddf168ed955235c592c6))
* rebuild checkpoint ([b468c5f](https://github.com/HSLix/LixAssistantLimbusCompany/commit/b468c5fd4df326db668ad9e5455f2fb7a8bef1bf))
* set process name lalc ([781fe4f](https://github.com/HSLix/LixAssistantLimbusCompany/commit/781fe4fde0be16362c44c6607764c8fd4bab5ee1))
* suit mirror6 ([69b72fc](https://github.com/HSLix/LixAssistantLimbusCompany/commit/69b72fc87cbc06f8c4a2124735cfdaaca61ca125))
* 重构整个应用 | Rebuild the whole application ([0d7c6bd](https://github.com/HSLix/LixAssistantLimbusCompany/commit/0d7c6bd1b116846ca2fd530a3e76913951699752))


### Bug Fixes

* 1. stuck when init the team for the team on the left vague; 2. can not recognize the team 12 and 10 correct ([bdacd22](https://github.com/HSLix/LixAssistantLimbusCompany/commit/bdacd2278824ced8aba89ad4d25f788eb3d95951))
* 3.2.8 miss change task name ([eece06d](https://github.com/HSLix/LixAssistantLimbusCompany/commit/eece06dae62a569be4eee3f14cbbe86a3767969b))
* avoid being stuck by the gift search ([af628f7](https://github.com/HSLix/LixAssistantLimbusCompany/commit/af628f77d00406eb76f1e92518aee3ce1a99327b))
* can not ready battle ([450a665](https://github.com/HSLix/LixAssistantLimbusCompany/commit/450a665f58a956533c1757807f90e2b955330d1b))
* can not set first team and change team correctly ([dd2515b](https://github.com/HSLix/LixAssistantLimbusCompany/commit/dd2515bc7740168844f57c6b1e3820801548aa79))
* choose the wrong team ([be7d7cb](https://github.com/HSLix/LixAssistantLimbusCompany/commit/be7d7cbbdea7594a5b247d61b21c77efd645de84))
* execute time error ([3d76e0b](https://github.com/HSLix/LixAssistantLimbusCompany/commit/3d76e0b5be3e4228cb5398773db3cbfeeb654708))
* fail to init team ([d1a40d8](https://github.com/HSLix/LixAssistantLimbusCompany/commit/d1a40d81ed4ce17ba30f839df7127e81244935c8))
* may stuck after select the reward card ([1b8a2db](https://github.com/HSLix/LixAssistantLimbusCompany/commit/1b8a2dbcef301e631cd9ade2d18e5eba49633711))
* mirror init change recognization sign, add team select delay ([931f116](https://github.com/HSLix/LixAssistantLimbusCompany/commit/931f1161a758c598e4ffc0d0a409d435cc434390))
* remove 150% force and add warning ([d36b7a8](https://github.com/HSLix/LixAssistantLimbusCompany/commit/d36b7a819b7bb0f49adc2124e1cd606eea5dedef))
* remove starlight 2 ([ba0b13b](https://github.com/HSLix/LixAssistantLimbusCompany/commit/ba0b13b6e8230a0fa22571b61af650ab9a78d3a6))
* stuck for the new ui before entering mirror ([f1fe3ff](https://github.com/HSLix/LixAssistantLimbusCompany/commit/f1fe3ff217c765ac9e54a826f4cc6f57f742e364))
* stuck when choosing the theme pack ([ada3f7a](https://github.com/HSLix/LixAssistantLimbusCompany/commit/ada3f7aebf5903592d83f17d6d32f181761cf3cc))
* tagName error in ci ([cd7368d](https://github.com/HSLix/LixAssistantLimbusCompany/commit/cd7368de612dd7ef35c503d24a14a5460cdc0be2))
* tagName error in ci ([1d8898e](https://github.com/HSLix/LixAssistantLimbusCompany/commit/1d8898e3e1f91063fca271912e608e748b9d4b31))
* the bug of auto release content error ([5b58138](https://github.com/HSLix/LixAssistantLimbusCompany/commit/5b581381dd2f213f17e87e675977f553d31b200a))
* the bug of automatic release content ([f2b2761](https://github.com/HSLix/LixAssistantLimbusCompany/commit/f2b27619433258cb64b9945242d3860091b7772a))
* the bug of error replace the token name of chyan ([7ec0318](https://github.com/HSLix/LixAssistantLimbusCompany/commit/7ec0318513ff93080b697e9d184e7c0f0f493b7d))
* the bug of error replace the token name of chyan ([14c0a0a](https://github.com/HSLix/LixAssistantLimbusCompany/commit/14c0a0afbd6ac2570c89010655b0419ba14e8a19))
* the bug of token of mirror chyan ([d213734](https://github.com/HSLix/LixAssistantLimbusCompany/commit/d213734c00f3a55256ec88d2ef14d535efcafcb1))
* the bug that can not recognize - as a normal signal ([f40d2e7](https://github.com/HSLix/LixAssistantLimbusCompany/commit/f40d2e79b4ac12159b2fd901aef8538e7b557454))
* the bug that can not wait connecting in the shop ([21b56d7](https://github.com/HSLix/LixAssistantLimbusCompany/commit/21b56d7c1b23dab0b14d0bd0af2bf29a9e7b8700))
* the version compare error and execute time ([41d126f](https://github.com/HSLix/LixAssistantLimbusCompany/commit/41d126fb62673a26848889d5efd5dbe64fc2d149))
* upload token in mirror release and upload ([36025c2](https://github.com/HSLix/LixAssistantLimbusCompany/commit/36025c22eb6ed784040b07311ae185a8fc4bb6e6))
* 自动构建的分支错误 | Error of the wrong branch name of build release ([46ac1da](https://github.com/HSLix/LixAssistantLimbusCompany/commit/46ac1da9f8469b7cc1de498da752eb215cab358a))
