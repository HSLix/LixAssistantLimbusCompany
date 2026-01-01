# Changelog

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
