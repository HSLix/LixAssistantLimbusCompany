# 项目架构简单介绍及开发建议
- 推荐在 VSCode 进行开发

- lalc_frontend，前端，目前用的版本是 `3.35.7`，初始化时用 `flutter create`，构建应用 `flutter run windows`。推荐下载插件 Flutter Intl 来方便国际化，这样一来只要编辑 arb 文件就能自动生成国际化配置代码。

- lalc_backend，后端，初始化时用 `uv sync` 来配置环境（uv 是一个 python 虚拟环境的工具，不了解的话请自行搜索下载使用）；由于涉及到平级目录互相调用，建议用 uv pip install -e . 来模块化项目。

- 项目整体的打包用根目录的 packup_release.bat 文件，打包环境为 windows

# Git commit message 建议
- fork 到自己仓库后，建议自己另建一个分支（branch）开发，完成后先把新分支 push 到自己仓库，然后前往 [pr](https://github.com/HSLix/LixAssistantLimbusCompany/compare) 来新建自己的 pr，把你的分支合进来。
- git commit 时，建议带上 feat: fix: chores: docs:，等前缀标明本次 commit 的类型，遵循 [conventionalcommits](https://www.conventionalcommits.org/en/v1.0.0/) 的规范要求来做的话，自动发版才会正常工作。以及在 message 的末尾，用 `Fixed #2` 可以关掉编号为 2 的 Issue，这样就不用在 pr 里面再次编辑了，下面引用其中一段：

> fix: 类型 为 fix 的提交表示在代码库中修复了一个 bug（这和语义化版本中的 PATCH 相对应）。

> feat: 类型 为 feat 的提交表示在代码库中新增了一个功能（这和语义化版本中的 MINOR 相对应）。

> BREAKING CHANGE: 在脚注中包含 BREAKING CHANGE: 或 <类型>(范围) 后面有一个 ! 的提交，表示引入了破坏性 API 变更（这和语义化版本中的 MAJOR 相对应）。 破坏性变更可以是任意 类型 提交的一部分。

> 除 fix: 和 feat: 之外，也可以使用其它提交 类型 ，例如 @commitlint/config-conventional（基于 Angular 约定）中推荐的 build:、chore:、 ci:、docs:、style:、refactor:、perf:、test:，等等。

> build: 用于修改项目构建系统，例如修改依赖库、外部接口或者升级 Node 版本等；

> chore: 用于对非业务性代码进行修改，例如修改构建流程或者工具配置等；

> ci: 用于修改持续集成流程，例如修改 Travis、Jenkins 等工作流配置；

> docs: 用于修改文档，例如修改 README 文件、API 文档等；

> style: 用于修改代码的样式，例如调整缩进、空格、空行等；

> refactor: 用于重构代码，例如修改代码结构、变量名、函数名等但不修改功能逻辑；

> perf: 用于优化性能，例如提升代码的性能、减少内存占用等；

> test: 用于修改测试用例，例如添加、删除、修改代码的测试用例等。
