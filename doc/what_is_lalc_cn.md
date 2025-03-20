# LixAssistantLimbusCompany
## 总评 3.0.0
- LALC 从没有上传 GitHub 的 0.3.2 开始，走到今天，见证了 Limbus 的镜牢从 1 走到 5，以后还有更多。
- 令人感慨，这个当初一气之下发起的项目，今天也有这么多人喜爱并使用着，感谢各位。
- 代码结构上，从一开始的全放主目录，到学会分出各种繁复的子目录，最后精简成现在这样，也是吃了不少堑（智感觉没长多少）
- 代码内容上，可拓展性也算大大增强（每个大版本的更新都是因为陆爻齐觉着之前的代码恶心得看不下去），至少 3.0.0 开始应该会好不少。

## 代码结构
- executor：负责鼠标、键盘的模拟以及识图，窗口获取的后端自动化功能，靠调用 config 的内容实现后端功能。算 LALC 的骨架。
- config：存储各种 json 文件，主要负责存储任务流程和本地数据备份，可以说这些 json 是 LALC 的肉。
- gui：负责图形用户界面的搭建，以及本地数据的存储，是 LALC 的皮。

## 流程结构
- 学习 [MaaFramework](https://github.com/MaaXYZ/MaaFramework)，通过 executor 的 control_unit 和 task 实现对 config 中 task.json 的转化和执行，本质上相当于电脑操作系统中 CPU 不断读取进程、执行，然后读取下一个进程的流程。
- 一次数据交互流程：Gui->Config->Task->ControlUnit->Gui。

## 打包
- 调用那个 spec 文件就行，记得改下绝对路径。