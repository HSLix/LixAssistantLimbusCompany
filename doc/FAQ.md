[English Version(translated by google)](https://github-com.translate.goog/HSLix/LixAssistantLimbusCompany/blob/master/doc/FAQ.md?_x_tr_sl=zh-CN&_x_tr_tl=en&_x_tr_hl=zh-CN&_x_tr_pto=wapp)

## 常见问题解答

### 1. 对电脑屏幕和缩放有什么要求？
电脑屏幕需要大于 1280x720，电脑的缩放在 100%-150% 都可运行，但 **150%** 是最稳定的，游戏窗口由程序设置，无需人工干预。

### 2. 游戏语言有什么要求？
游戏语言 **必须为英语**，如果游戏语言已经是英语但还有报错，请尝试重新运行。

### 3. 软件安装路径有什么要求？
放置 LALC 的路径上也需要 **全为英文**（或者普通的常见字符，如下划线等），因为中文等非英文字符可能会导致奇怪的异常。

### 4. 第一次安装后出现异常怎么办？
如果是 **第一次安装** 后发生的异常，且按照指示一步步做了也没效果，建议重启电脑试试。

### 5. 连接服务器失败怎么办？
对于图形化界面（前端）说"连接不上服务器"，或者黑框框（后端）说"服务器超时"，说明前后端有一边没有启动，请看 [教程](/doc/tutorial.md) 的第一条。如果关闭后，仍然没有效果，请尝试按下面步骤操作：先进入 lalc_frontend 文件夹，启动 lalc_frontend.exe，然后再尝试启动 LixAssistantLimbusCompany.exe。

### 6. 需要开启屏幕常亮吗？
由于现版本的交互不会被电脑视为活跃行为，需要 **开启屏幕常亮** 避免因息屏导致的运行异常。

### 7. 鼠标在游戏窗口内闪动是否正常？
运行过程中，鼠标在游戏窗口内会闪动的现象是正常的，因为鼠标在窗口内可能会挡住关键的部分，影响识图，所以会短暂地把鼠标移出窗口，截图完成再移回去，整个过程很快，所以就像是闪动。（交闪启动！）

### 8. 运行过程中可以做其他事情吗？
运行过程中，不需要游戏窗口置顶，可以做别的事，但建议是不需要你和键盘鼠标大量交互的事（比如打 FPS/RTS 游戏），LALC 会趁你没有使用键鼠的间隙来行动，注意 LALC 操控鼠标期间，你的键鼠会被屏蔽，虽然时间很短，但也有可能会影响平时的交互。

### 9. LALC无法处理某些邮件怎么办？
根据 [反馈](https://github.com/HSLix/LixAssistantLimbusCompany/issues/230)，现版本（v4.4.1）似乎无法处理某些特定邮件，如果发现卡在邮件领取，就需要人工处理特殊邮件。

### 10. LALC不行动是怎么回事？
当你正在使用鼠标或键盘，LALC 会等待你停止使用再占用鼠标，尽量规避因 LALC 占用鼠标就会屏蔽你的输入带来的负面体验。所以如果你正在疯狂打游戏然后发现 LALC 一动不动，不用担心，你一停下来它就会继续行动了。

### 11. 为什么LALC会选满罪人？
之所以选人会选满，是为了避免镜牢内人没选满，但战斗打不赢，卡在有人却不上的境地。

### 12. 程序启动报错 Dll load Failed，就像 [Issue #240](https://github.com/HSLix/LixAssistantLimbusCompany/issues/240) 一样
这是由于你的计算机上缺乏一些必要的运行组件，可以通过从 [微软的官网](https://learn.microsoft.com/zh-cn/cpp/windows/latest-supported-vc-redist?view=msvc-170) 按照自己的平台，下载对应的包进行安装。
> https://github.com/microsoft/onnxruntime/issues/16116#issuecomment-1768732885