'''
* Author: LuYaoQi
* Time  : 2023/9/16 9:25
* File  : myGUI.py        
* Project   :LixAssistantLimbusCompany
* Function  :图形化交互界面            
'''
import tkinter as tk
from tkinter import ttk
import tkinter.messagebox as msgbox
from threading import Thread, Lock
from src.common.listenAndExit import listenAndExit
from os import _exit
from ctypes import windll
from src.script.classScript import _mainScript
from time import sleep

exeCount = {"EXPCount" : 0, "ThreadCount" : 0, "MirrorCount":0, "setWinSwitch":0, "setPrizeSwitch":0, "MirrorSwitch":0, "ActivityCount":0}

version = "V2.1.2_Realease"



class myGUI:
    #限制变量
    __slots__ = ("root", "aboutPageFrame", "aboutText", "leftMainPageFrame", "rightMainPageFrame",
                 "buttonFrame", "SetWin", "SetPrize", "descriptionText", "startButton",
                 "taskFrame", "EXPCount", "ThreadCount", "MirrorCount", "script", "buttonThread", 
                 "EXPSpin", "ThreadSpin", "MirrorSpin","ActivitySpin", "SetMirror", "ActivityCount")


    # 构造函数
    def __init__(self):
        # 排除缩放干扰
        windll.user32.SetProcessDPIAware()

        self.root = tk.Tk()

        titleName = "LALC_LixAssistantLimbusCompany_" + version
        self.root.title(titleName)
        self.root.iconbitmap('./pic/GUITitlePic.ico')

        #设置主题
        self.root.tk.call("source", "./azure.tcl")
        self.root.tk.call("set_theme", "dark")

        #禁止窗口拉伸
        self.root.resizable(0,0)

        #窗口置顶
        self.root.attributes('-alpha', 1)

        #设置窗口在屏幕中心出现
        screenWidth = self.root.winfo_screenwidth()
        screenHeight = self.root.winfo_screenheight()
        width = 800  # 设定窗口宽度
        height = 600  # 设定窗口高度
        left = (screenWidth - width) / 2
        top = (screenHeight - height) / 2
        #设置窗口大小和位置
        self.root.geometry("%dx%d+%d+%d" % (width, height, left, top))

        #关闭设置
        self.root.protocol('WM_DELETE_WINDOW', self.offCommand)

        #多线程监听键盘ESC
        listenAndExit()


            
    def offCommand(self):
        '''设置关闭按钮'''
        self.root.destroy()
        # 全部程序退出
        _exit(0)

        
    # 设置关于界面框架
    def showAboutPageFrame(self):
        '''设置关于界面的框架'''
        self.aboutPageFrame = tk.LabelFrame(self.root, padx = 5, pady = 5)
        self.aboutPageFrame.place(width = 700, height = 550,x = 1024, y = 10)
        self.aboutText = tk.Text(self.aboutPageFrame)
        self.aboutText.place(width = 686, height = 540,x = 3, y = 0)
        self.aboutText.insert("end", "* 关于本软件\n\n")
        self.aboutText.insert("end", "* 软件图标素材来源网图，不属于GPL协议开源的内容，如有侵权，请及时联系作者删除\n")
        self.aboutText.insert("end", "* GitHub地址\n")
        self.aboutText.insert("end", "* https://github.com/HSLix/LixAssistantLimbusCompany.git\n\n")
        self.aboutText.insert("end", "* 致谢\n")
        self.aboutText.insert("end", "* 直接或间接参与到本软件开发的所有人员\n")
        self.aboutText.insert("end", "* 包括在网络上分享各种教程的大佬们\n\n")
        self.aboutText.insert("end", "* 声明\n")
        self.aboutText.insert("end", "* 本软件开源、免费，仅供学习交流使用。\n")
        self.aboutText.insert("end", "* 若您遇到商家使用本软件进行代练并收费，可能是设备与时间等费用，产生的问题及后果与本软件无关。\n")
        self.aboutText.insert("end", "* 获取管理员权限是为了确保运行顺利\n")
        self.aboutText.insert("end", "* 该版本离线，只能到github自助更新\n\n")

        


        self.aboutText.configure(state="disabled", font=("微软雅黑", 12))
        


    #界面切换函数
    def switchPage(self, pageNum):
        '''界面切换，根据pagenum切换两个框架的坐标'''
        if pageNum == 1:
            self.leftMainPageFrame.place(x = 0)
            self.rightMainPageFrame.place(x = 280)
            self.aboutPageFrame.place(x = 1024)
        elif pageNum == 2:
            self.leftMainPageFrame.place(x = 1024)
            self.rightMainPageFrame.place(x = 1024)
            self.aboutPageFrame.place(x = 50)


    
    def showMenu(self):
        """展示菜单栏"""
        menubar = tk.Menu(self.root)
        menubar.add_command(label = "开始", command=lambda :self.switchPage(1))
        menubar.add_command(label = "关于", command=lambda :self.switchPage(2))
        self.root["menu"] = menubar


    def showMainPageFrame(self):
        """设置并展示主页面"""
        self.setMainPageLeftFrame()
        self.setMainPageRightFrame()
        


    def setMainPageLeftFrame(self):
        """左边布局"""
        self.leftMainPageFrame = tk.Frame(self.root)
        self.leftMainPageFrame.place(width = 250, height = 600, x = 0, y = 0)

        """左边布局 窗口初始化与奖励领取"""
        self.taskFrame = tk.LabelFrame(self.leftMainPageFrame, text = "任务内容", padx = 5, pady = 5)
        self.taskFrame.place(width = 230, height = 550, x = 10, y = 5)

        

    def setMainPageRightFrame(self):
        """右边布局"""
        self.rightMainPageFrame = tk.Frame(self.root)
        self.rightMainPageFrame.place(width = 500, height = 600,x = 280, y = 0)
        infoFrame = tk.LabelFrame(self.rightMainPageFrame, text = "必读须知", padx = 5, pady = 5)
        infoFrame.place(width = 500, height = 450,x = 0, y = 5)

        
        '''解释框架的文本框'''
        self.descriptionText = tk.Text(infoFrame)
        self.descriptionText.place(width = 493, height = 415,x = 0, y = 0)
        
        
        self.descriptionText.insert("end", "* 点击下方\"Start\"按钮即可启动软件\nClick the Start Button\n")
        self.descriptionText.insert("end", "* 点击下方\"Stop\"按钮即可停止软件\n并获取软件运行情况\n")
        self.descriptionText.insert("end", "* 为确保稳定性，该停止按钮不会立即生效\n")
        self.descriptionText.insert("end", "* 但可按ESC键立即停止\nPress ESC can interrupt the program immediately\n\n")
        self.descriptionText.insert("end", "* 为了确保软件运行顺利\n")
        self.descriptionText.insert("end", "* 请在64位Windows系统下运行本软件\n")
        self.descriptionText.insert("end", "* 不要关闭此窗口\nDon't turn this window off\n")
        self.descriptionText.insert("end", "* 将游戏语言设置为英语\nSet Game Language English\n")
        self.descriptionText.insert("end", "* 请勿遮挡游戏画面\nKeep The Screen Clear\n")
        self.descriptionText.insert("end", "* 尽量不要在运行过程中使用鼠标\nHad Better not use Mouse\n")
        self.descriptionText.insert("end", "* 游戏窗口大小设置为 1280*720\n\n")
        self.descriptionText.insert("end", "* 游戏窗口位置默认设置为 左上角(0,0)\n")
        self.descriptionText.insert("end", "* 默认将脑啡肽转成绿饼和购买第一次体力\n\n")
        self.descriptionText.insert("end", "* 如遇到软件运行异常\nWhen error occur\n")
        self.descriptionText.insert("end", "* 请点击\"Stop\"按钮获取软件运行情况\nClick the Stop Button\n")
        self.descriptionText.insert("end", "* 保存好文件夹log内的日志文件\nSave the logs\n")
        self.descriptionText.insert("end", "* 自行查看常见Q&A，如仍没能解决\nCheck Q&A\n")
        self.descriptionText.insert("end", "* 请在GitHub的Issue里提交问题\nPlease send the Problem to the Issue in GitHub\n\n")
        self.descriptionText.insert("end", "* 希望能减少游戏中有时间压力的部分\nHope you can have fun\n")
        self.descriptionText.insert("end", "* 祝使用愉快 (-▽-)\nGood Luck~\n")
        
        self.descriptionText.configure(state="disabled", font=("微软雅黑", 10))

        """右边布局 按钮交互"""
        self.buttonFrame = tk.Frame(self.rightMainPageFrame, padx = 5, pady = 5)
        self.buttonFrame.place(width = 400, height = 100, x = 0, y = 470)




    def showTasks(self):
        '''展示主页左侧的任务栏'''
        self.showInitWin()
        self.showInitPrize()
        self.showLCATasks()
        


    def showLCATasks(self):
        '''展示具体任务'''
        '''展示EXP关相关选项'''
        def checkInputIsInt(content):
            if (str.isdigit(content) or content == '') and len(content) < 4:
                return True
            else:
                return False
            
        vcmd = (self.root.register(checkInputIsInt), "%P")


        self.EXPCount = tk.StringVar()
        self.ThreadCount = tk.StringVar()
        self.MirrorCount = tk.StringVar()
        self.ActivityCount = tk.StringVar()

        maxCount = 999

        tk.Label(self.taskFrame, text="经验本EXP",
                          font=("微软雅黑", 10),
                          justify="left",
                          anchor="w").place(width = 180, height = 20,x = 0, y = 170)
        self.EXPSpin = tk.Spinbox(self.taskFrame, from_=0, to=maxCount, width=10,textvariable=self.EXPCount,
                          validate="key", 
                          validatecommand=vcmd)
        self.EXPSpin.place(x = 5, y = 200)

        tk.Label(self.taskFrame, text="纽本Thread",
                          font=("微软雅黑", 10),
                          justify="left",
                          anchor="w").place(width = 180, height = 20,x = 0, y = 245)
        self.ThreadSpin = tk.Spinbox(self.taskFrame, from_=0, to=maxCount, width=10,textvariable=self.ThreadCount,
                          validate="key", 
                          validatecommand=vcmd)
        self.ThreadSpin.place(x = 5, y = 270)

        tk.Label(self.taskFrame, text="镜牢Mirror",
                          font=("微软雅黑", 10),
                          justify="left",
                          anchor="w").place(width = 180, height = 20,x = 0, y = 320)
        
        self.SetMirror = ttk.Combobox(self.taskFrame)
        self.SetMirror['values'] = ["镜牢1", "镜牢2Normal"]
        self.SetMirror.configure(state="readonly")
        self.SetMirror.current(1)
        self.SetMirror.place(width = 180, height = 40,x = 0, y = 345)

        self.MirrorSpin = tk.Spinbox(self.taskFrame, from_=0, to=maxCount, width=10,textvariable=self.MirrorCount,
                          validate="key", 
                          validatecommand=vcmd)
        self.MirrorSpin.place(x = 5, y = 390)

        tk.Label(self.taskFrame, text="活动Activity 待更新 ",
                          font=("微软雅黑", 10),
                          justify="left",
                          anchor="w").place(width = 180, height = 20,x = 0, y = 440)
        self.ActivitySpin = tk.Spinbox(self.taskFrame, from_=0, to=maxCount, width=10,textvariable=self.ActivityCount,
                          validate="key", 
                          validatecommand=vcmd)
        self.ActivitySpin.place(x = 5, y = 470)

        

    def showInitWin(self):
        '''展示任务栏中窗口的设置'''
        tk.Label(self.taskFrame, text="窗口初始化",
                          font=("微软雅黑", 10),
                          justify="left",
                          anchor="w").place(width = 150, height = 20,x = 0, y = 0)
        self.SetWin = ttk.Combobox(self.taskFrame)
        self.SetWin['values'] = ["位置+大小", "大小", "位置", "无"]
        self.SetWin.configure(state="readonly")
        self.SetWin.current(0)
        self.SetWin.place(width = 180, height = 40,x = 0, y = 30)


    def showInitPrize(self):
        '''展示任务栏中奖励领取的设置'''
        tk.Label(self.taskFrame, text="奖励领取",
                          font=("微软雅黑", 10),
                          justify="left",
                          anchor="w").place(width = 100, height = 20, x = 0, y = 80)
        self.SetPrize = ttk.Combobox(self.taskFrame)
        self.SetPrize['values'] = ["邮件+日/周常", "日/周常", "邮件", "无"]
        self.SetPrize.configure(state="readonly")
        self.SetPrize.current(0)
        self.SetPrize.place(width = 180, height = 40, x = 0, y = 110)



    def showButton(self):
        '''设置启动按钮的格式和位置'''
        self.startButton = tk.Button(self.buttonFrame, 
                           text="Start",
                           font=("微软雅黑", 30), 
                           command= self.startAndStopMsg)
        self.startButton.place(width = 300,height = 80, x = 0, y = 0)
        

    def startAndStopMsg(self):
        '''点击按钮后，启动和停止两种互动，并停止其它按钮的交互'''
        if(self.startButton["text"] == "Start"):
            self.startButton["text"] = "Stop"
            self.SetPrize.config(state=tk.DISABLED)
            self.SetWin.config(state=tk.DISABLED)
            self.SetMirror.config(state=tk.DISABLED)
            self.EXPSpin.config(state=tk.DISABLED)
            self.ThreadSpin.config(state=tk.DISABLED)
            self.MirrorSpin.config(state=tk.DISABLED)
            self.ActivitySpin.config(state=tk.DISABLED)
            msgbox.showinfo("提示", "脚本即将开始！\nBegin NOW!\n")
            self.outputList()
            self.createAndStartScript()
            self.buttonThread = Thread(None,self.waitScriptEndAndCheck)
            self.buttonThread.setDaemon(True)
            self.buttonThread.start()

            
            
        elif(self.startButton["text"] == "Stop"):
            self.startButton["text"] = "Stopping"
            self.startButton.config(state=tk.DISABLED)
            self.stopThreadScript()


    def waitScriptEndAndCheck(self):
        '''等待脚本线程结束并处理其它按钮恢复交互'''
        while self.script.is_alive():
                sleep(1)
                continue
        self.checkScriptExitCode(self.script.getExitCode())
        self.SetPrize.configure(state="readonly")
        self.SetWin.configure(state="readonly")
        self.SetMirror.configure(state="readonly")
        
        self.EXPSpin.config(state=tk.NORMAL)
        self.ThreadSpin.config(state=tk.NORMAL)
        self.MirrorSpin.config(state=tk.NORMAL)
        self.ActivitySpin.config(state=tk.NORMAL)
        self.startButton.config(state=tk.NORMAL)
        self.startButton["text"] = "Start"
    

    def createAndStartScript(self):
        '''启动脚本线程'''
        self.script = _mainScript(exeCount["EXPCount"], exeCount["ThreadCount"], exeCount["MirrorCount"], exeCount["setWinSwitch"], exeCount["setPrizeSwitch"], exeCount["MirrorSwitch"], exeCount["ActivityCount"])
        self.script.setDaemon(True)
        self.script.start()
        


    def stopThreadScript(self):
        '''设置脚本类里的变量使得该线程尽早自行停止'''
        with Lock():
            self.script.kill()
        msgbox.showinfo("提示", "请稍等，程序马上结束")
        

        
    def checkScriptExitCode(self, ExitCode):
        '''根据ExitCode给出窗口提示程序运行情况和任务完成情况'''
        if(ExitCode == -1):
            msg = "程序被手动终止"
        elif(ExitCode == 0):
            msg = "程序正常结束"
        elif(ExitCode == 1):
            msg = "程序出现未知错误"
        elif(ExitCode == 2):
            msg = "没有管理员权限，程序不能稳定运行"
        elif(ExitCode == 3):
            msg = "无法读取图片，请检查图片文件和主程序位置"
        elif(ExitCode == 4):
            msg = "下载时间较长，程序提前终止"
        elif(ExitCode == 5):
            msg = "游戏窗口不存在，请打开游戏后再运行本程序"
        elif(ExitCode == 6):
            msg = "当前界面无法返回到初始主界面，无法继续任务"
        elif(ExitCode == 7):
            msg = "网络连接不稳，请重启游戏，修复网络，重新开始"
        elif(ExitCode == 8):
            msg = "网络多次重连失败，请重启游戏，修复网络，重新开始"
        elif(ExitCode == 9):
            msg = "内部出现未知选择情况，请另存日志文件并提交Issue"
        elif(ExitCode == 10):
            msg = "请自己选好人后再启动程序，往后会自动选上一次的队伍"
        elif(ExitCode == 11):
            msg = "请自行结束其它镜牢再启动程序，本程序不能自作主张"
        else:
            msg = "未知情况错误，请另存日志文件并提交Issue"



        msg += "\nEXP:{} Thread:{} Mirror:{} Activity:{}".format(self.script.EXPFinishCount ,self.script.ThreadFinishCount,self.script.MirrorFinishCount,self.script.ActivityFinishCount)
        
        msgbox.showinfo("本次程序运行情况", msg)
        


    def outputList(self):
        '''将GUI接受的变量传到exeCount的字典里给脚本类调用'''
        exeCount["EXPCount"] = self.EXPCount.get()
        exeCount["ThreadCount"] = self.ThreadCount.get()
        exeCount["MirrorCount"] = self.MirrorCount.get()
        exeCount["ActivityCount"] = self.ActivityCount.get()
        #防止传空值
        if exeCount["EXPCount"] == "":
            exeCount["EXPCount"] = 0
        else:
            exeCount["EXPCount"] = int(exeCount["EXPCount"])

        if exeCount["ThreadCount"] == "":
            exeCount["ThreadCount"] = 0
        else:
            exeCount["ThreadCount"] = int(exeCount["ThreadCount"])

        if exeCount["MirrorCount"] == "":
            exeCount["MirrorCount"] = 0
        else:
            exeCount["MirrorCount"] = int(exeCount["MirrorCount"])

        if exeCount["ActivityCount"] == "":
            exeCount["ActivityCount"] = 0
        else:
            exeCount["ActivityCount"] = int(exeCount["ActivityCount"])

        #根据窗口和奖励选择传值
        strSetWin = self.SetWin.get()
        strSetPrize = self.SetPrize.get()
        strSetMirror = self.SetMirror.get()

        if(strSetWin == "位置+大小"):
            exeCount["setWinSwitch"] = 0
        elif(strSetWin == "大小"):
            exeCount["setWinSwitch"] = 1
        elif(strSetWin == "位置"):
            exeCount["setWinSwitch"] = 2
        elif(strSetWin == "无"):
            exeCount["setWinSwitch"] = 3

        if(strSetPrize == "邮件+日/周常"):
            exeCount["setWinSwitch"] = 0
        elif(strSetPrize == "日/周常"):
            exeCount["setWinSwitch"] = 1
        elif(strSetPrize == "邮件"):
            exeCount["setWinSwitch"] = 2
        elif(strSetPrize == "无"):
            exeCount["setWinSwitch"] = 3

        if(strSetMirror == "镜牢1"):
            exeCount["MirrorSwitch"] = 1
        elif(strSetMirror == "镜牢2Normal"):
            exeCount["MirrorSwitch"] = 2
        

        #print(exeCount["setWinSwitch"] + exeCount["setWinSwitch"])
        

    def showWin(self):
        """展示窗口"""
        self.showMenu()
        self.showMainPageFrame()
        self.showTasks()
        self.showButton()
        self.showAboutPageFrame()
        self.root.mainloop()


