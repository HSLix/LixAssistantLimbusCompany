# -*- coding: utf-8 -*-
'''
* Author: LuYaoQi
* Time  : 2023/9/18 17:48
* File  : classMir.py   
* Project   :LixAssistantLimbusCompany
* Function  :将镜牢相关函数包装为类          
'''


from src.script.classTask import _task, checkAndExit, beginAndFinishLog
from src.common.myTime import mySleep
from src.error.myError import unexpectNumError,noSavedPresetsError, mirrorInProgressError, previousClaimRewardError
from src.common.mouseScroll import littleUpScroll
from src.log.myLog import myLog
import globalVar
from os import walk
from src.script.classScript import _script
from src.common.picLocate import getSinCenXY

notFullFlag = 0


class _Mirror(_script):
    __slots__ = ("mirrorSwitch", "mirrorCount", "mirrorFinishCount")

    def __init__(self,mirrorSwitch, mirrorCount):
        '''初始化镜牢选择变量'''
        self.mirrorSwitch = mirrorSwitch
        self.mirrorCount = mirrorCount
        self.mirrorFinishCount = 0


    def start(self):
        '''根据选择变量，选择具体镜牢执行任务'''
        if(self.mirrorSwitch == 1):
            self.ScriptTaskMirror1()
        elif(self.mirrorSwitch == 2):
            self.ScriptTaskMirror2Normal()
        elif(self.mirrorSwitch == 3):
            self.ScriptTaskMirror3Normal()
        elif(self.mirrorSwitch == 4):
            self.ScriptTaskMirror4Normal()
        else:
            raise unexpectNumError("镜牢选择数字未设置")


    def getMirrorFinishCount(self):
        '''返回镜牢完成次数'''
        return self.mirrorFinishCount
    

    @checkAndExit
    @beginAndFinishLog
    def ScriptTaskMirror4Normal(self):
        '''镜牢4一次流程'''
        mir = _MirrorOfTheWuthering()
        loopCount = 0
        while(self.mirrorFinishCount < self.mirrorCount):
            self.errorRetry()
            # print("mirror LoopCount :" + str(loopCount))
            if not mir.mirror4():
                loopCount += 1
                if loopCount == 2:
                    mir.mirror4Leave()
                    self.ScriptBackToInitMenu()
            else:
                loopCount = 0

            if(mir.mirror4Prize()):
                loopCount = 0
                self.mirrorFinishCount += 1
                msg = "mirror4 Success "  + str(self.mirrorFinishCount) + " Times!"
                globalVar.exeResult["MirrorFinishCount"] += 1
                myLog("info", msg)
                self.ScriptBackToInitMenu()
                continue

            if loopCount > 4:
                myLog("warning","Hard to continue! Next Mission!")
                #离开进入函数
                self.mirrorCount = 0

            msg = "mirror4 Loop " + str(loopCount) + " Times!"
            myLog("info", msg) 


    
    @checkAndExit
    @beginAndFinishLog
    def ScriptTaskMirror3Normal(self):
        '''镜牢3一次流程'''
        mir = _MirrorOfTheLake()
        loopCount = 0
        while(self.mirrorFinishCount < self.mirrorCount):
            self.errorRetry()
            # print("mirror LoopCount :" + str(loopCount))
            if not mir.mirror3():
                loopCount += 1
                if loopCount == 2:
                    mir.mirror3Leave()
                    self.ScriptBackToInitMenu()
            else:
                loopCount = 0

            if(mir.mirror3Prize()):
                loopCount = 0
                self.mirrorFinishCount += 1
                msg = "mirror3 Success "  + str(self.mirrorFinishCount) + " Times!"
                globalVar.exeResult["MirrorFinishCount"] += 1
                myLog("info", msg)
                self.ScriptBackToInitMenu()
                continue

            if loopCount > 4:
                myLog("warning","Hard to continue! Next Mission!")
                #离开进入函数
                self.mirrorCount = 0

            msg = "mirror3 Loop " + str(loopCount) + " Times!"
            myLog("info", msg) 


    @checkAndExit
    @beginAndFinishLog
    def ScriptTaskMirror2Normal(self):
        '''镜牢2一次流程'''
        mir = _MirrorOfMirrors()
        loopCount = 0
        while(self.mirrorFinishCount < self.mirrorCount):
            
            self.errorRetry()
            # print("mirror LoopCount :" + str(loopCount))
            if not mir.Mirror2():
                loopCount += 1
                if loopCount == 2 and not mir.noWayFlag:
                    mir.noWayFlag = False
                    mir.mirror2Leave()
                    self.ScriptBackToInitMenu()
            else:
                loopCount = 0

            if(mir.mirror2Prize()):
                loopCount = 0
                self.mirrorFinishCount += 1
                msg = "Mirror2 Success "  + str(self.mirrorFinishCount) + " Times!"
                globalVar.exeResult["MirrorFinishCount"] += 1
                myLog("info", msg)
                self.ScriptBackToInitMenu()
                self.convertPai()
                continue

            if loopCount > 4:
                myLog("warning","Hard to continue! Next Mission!")
                #离开进入函数
                self.mirrorCount = 0

            msg = "Mirror2 Loop " + str(loopCount) + " Times!"
            myLog("info", msg) 
            # mySleep(1)
    

    @checkAndExit
    @beginAndFinishLog
    def ScriptTaskMirror1(self):
        '''镜牢1一次流程'''
        mir = _MirrorOfTheBeginning()
        loopCount = 0
        while(self.mirrorFinishCount < self.mirrorCount):
            
            self.errorRetry()
            # print("mirror LoopCount :" + str(loopCount))
            if not mir.Mirror1():
                loopCount += 1
                if loopCount == 2 and not mir.noWayFlag:
                    mir.noWayFlag = False
                    mir.mirror1Leave()
                    self.ScriptBackToInitMenu()
            else:
                loopCount = 0

            if(mir.mirror1Prize()):
                loopCount = 0
                self.mirrorFinishCount += 1
                globalVar.exeResult["MirrorFinishCount"] += 1
                msg = "Mirror1 Success "  + str(self.mirrorFinishCount) + " Times!"
                myLog("info", msg)
                self.ScriptBackToInitMenu()
                self.convertPai()
                continue

            if loopCount > 4:
                myLog("warning","Hard to continue! Next Mission!")
                #离开进入函数
                self.mirrorCount = 0
            
            msg = "Mirror1 Loop " + str(loopCount) + " Times!"
            myLog("info", msg) 
            # mySleep(2)


class _MirrorOfTheWuthering(_script):
    '''镜牢4的相关函数'''
    __slots__ = {"noWayFlag"}

    def mirror4(self):
        '''镜牢4进入、寻路、处理交互的集合'''
        result = False
        self.noWayFlag = False
        self.mirror4Entry()
        #有地图标识才寻路，否则仅作事件处理
        self.cap_win()
        if(self.is_find("./pic/mirror/mirror4/way/mirror4MapSign.png", "mirror4MapSign") and\
            self.is_find("./pic/mirror/mirror4/way/Self.png", "Self", 0.8)):
            self.noWayFlag = self.mirror4SinCoreFindWay()

        result = self.mirror4Cope()
        
        return result


    def mirror4PurchaseEGO(self):
        '''镜牢4购买EGO的流程'''
        #windll.user32.SetCursorPos(930,350)
        #windll.user32.SetCursorPos(1130,350)
        #windll.user32.SetCursorPos(780,450)
        loc_x = [930, 1130, 780, 930, 1130]
        loc_y = [350, 350, 450, 450, 450]
        for x, y in zip(loc_x, loc_y):
            log_str = "PurchaseEGO at ({}, {})".format(x, y)
            self.click_locate(x, y, str(log_str))
            self.cap_win()
            if self.single_target_click("./pic/mirror/mirror4/ProductCatalogue/ConfirmPurchase.png", "ConfirmPurchase", 0, 0, 1):
                self.cap_win()
                self.single_target_click("./pic/mirror/mirror4/way/Confirm.png", "confirmEGOGift")

        # 对bus/chair的出口第一时间反应
        self.cap_win()
        if(self.single_target_click("./pic/event/Leave.png", "Leave")):
            self.cap_win()
            self.single_target_click("./pic/mirror/mirror2/whiteConfirm.png", "Confirm")
    
    def mirror4Prize(self):
        '''镜牢4获取奖励的流程'''
        result = False
        self.cap_win()
        self.single_target_click("./pic/battle/confirm.png", "Final_Fight")
        self.cap_win()
        if self.is_find("./pic/mirror/mirror4/ClaimRewards.png","ClaimRewards"):
            self.press_key('enter', 0.3, 5)
            result = True

        '''self.single_target_click("./pic/mirror/mirror4/ClaimRewards.png","ClaimRewards")
        self.cap_win()
        self.single_target_click("./pic/mirror/mirror4/Receive.png","Receive")
        self.cap_win()
        if self.single_target_click("./pic/mirror/mirror4/whiteConfirm.png","FirstConfirm"):
            self.cap_win()
            if self.single_target_click("./pic/mirror/mirror4/way/Confirm.png","SecondConfirm"):
                result = True'''
        return result


    @checkAndExit
    @beginAndFinishLog
    def mirror4Leave(self):
        '''镜牢4离开时处理notFullFlag'''
        global notFullFlag 
        notFullFlag = 0

    
    def mirror4HaltAndEnter(self):
        self.press_key("esc", 1)
        self.cap_win()
        self.single_target_click("./pic/mirror/mirror4/mirror4Normal.png", "mirror4Normal", 0, 0, 2)
        self.cap_win()
        self.single_target_click("./pic/mirror/mirror4/HaltExploration.png", "HaltExploration", 0, 0, 1, 1, 0.6)
        self.press_key("enter", 1)
        self.cap_win()
        self.single_target_click("./pic/mirror/mirror4/GiveUpRewards.png", "GiveUpRewards")
        self.press_key("enter")

    @checkAndExit
    @beginAndFinishLog
    def mirror4GetStartGift(self):
        '''刷取饰品'''
        gift_flag = 0
        while not gift_flag:
            self.cap_win()
            self.single_target_click("./pic/mirror/mirror4/gift/Poise/Poise.png", "Poise", 0, 0, 2, 1, 0.9)
            self.cap_win()
            if self.single_target_click("./pic/mirror/mirror4/gift/Poise/Mebulizer.png", "Mebulizer", 0, 0, 1):
                gift_flag = 1
                if self.single_target_click("./pic/mirror/mirror4/gift/Poise/CigaretteHolder.png", "CigaretteHolder", 0, 0, 1):
                    pass
                if self.single_target_click("./pic/mirror/mirror4/gift/Poise/OrnamentalHorseshoe.png", "OrnamentalHorseshoe", 0, 0, 1):
                    pass
            
            # 卡住来测试该函数的
            # gift_flag = 0
            if not gift_flag:
                self.mirror4HaltAndEnter()
                self.cap_win()
                self.single_target_click("./pic/mirror/mirror4/mirror4Normal.png", "mirror4Normal")
                self.press_key("enter")
                self.cap_win()
                self.single_target_click("./pic/mirror/mirror4/firstWishConfirm.png", "firstWishConfirm", 0, 0, 1)      
    

    def getGiftSwitch(self):
        f = open("gift_switch.txt")
        line = f.readline().strip()
        line = int(line)
        globalVar.gift_switch = line
        f.close()



    @checkAndExit
    @beginAndFinishLog
    def mirror4Entry(self):
        '''进入镜牢4流程'''
        if(self.is_find("./pic/mirror/mirror4/way/mirror4MapSign.png", "mirror4MapSign")):
            return
        self.cap_win()
        self.single_target_click("./pic/initMenu/drive.png", "Drive")
        self.cap_win()
        self.single_target_click("./pic/mirror/mirror4/MirrorDungeons.png", "MirrorDungeons", 0, 0, 1, 1, 0.9)
        self.cap_win()
        if(self.is_find("./pic/mirror/previousClaimReward.png", "previousClaimReward")):
            raise previousClaimRewardError("有上周的镜牢奖励未领取")
        self.single_target_click("./pic/mirror/mirror4/mirror4Normal.png", "mirror4Normal")
        self.cap_win()
        if(self.is_find("./pic/mirror/MirrorInProgress.png", "MirrorInProgress")):
            raise mirrorInProgressError("有其他镜牢未结束")
        if (self.single_target_click("./pic/mirror/mirror4/Enter.png", "Enter", 0, 0, 2) or
            self.single_target_click("./pic/mirror/mirror4/Resume.png", "Resume", 0, 0, 5)):
            self.cap_win()
            self.single_target_click("./pic/mirror/mirror4/firstWishConfirm.png", "firstWishConfirm", 0, 0, 1.5)
            self.cap_win()
            self.getGiftSwitch()
            if globalVar.gift_switch:
                self.mirror4GetStartGift()
            else:
                # self.single_target_click("./pic/mirror/mirror4/ego/RandomEGOGift.png", "egoGift")
                self.single_target_click("./pic/mirror/mirror4/ego/PoiseEGOGift.png", "egoGift")
                self.cap_win()
                self.multiple_target_click("./pic/mirror/mirror4/ego/confirmRandomEGOGift.png", "EGOGift")
            self.cap_win()
            if (self.single_target_click("./pic/mirror/mirror4/ego/SelectEGOGift.png", "SelectEGOGift", 0, 0, 5)):
                self.press_key('enter', 0.4, 3) # confirm the ego
                self.press_key('enter', 3) # enter
            self.cap_win()
            
        if(self.is_find("./pic/team/Announcer.png", "Member")
           and self.is_find("./pic/mirror/mirror4/firstTeamConfirm.png", "firstTeamConfirm", 0.5)):
            self.press_key('enter')
        if(self.is_find("./pic/Wait.png", "Wait Sign")):
            self.myWait()
        

    def mirror4SelectEncounterRewardCard(self):
        self.cap_win()
        if (self.single_target_click("./pic/mirror/mirror4/way/RewardCard/EGOGiftCard.png", "EGOGiftCard")):
            mySleep(1)
            self.press_key('enter', 1)
            self.cap_win()
            self.single_target_click("./pic/mirror/mirror4/way/Confirm.png", "confirm ego gift", 0, 0, 0.4, 3)
        elif (self.single_target_click("./pic/mirror/mirror4/way/RewardCard/CostCard.png", "CostCard")):
            mySleep(1)
            self.press_key('enter', 1)
        elif (self.single_target_click("./pic/mirror/mirror4/way/RewardCard/StarlightCard.png", "StarlightCard")):
            mySleep(1)
            self.press_key('enter', 1)
        elif (self.single_target_click("./pic/mirror/mirror4/way/RewardCard/EGOResourceCard.png", "EGOResourceCard")):
            mySleep(1)
            self.press_key('enter', 1)
        else:
            self.press_key('enter', 1)
            self.single_target_click("./pic/mirror/mirror4/way/Confirm.png", "confirm ego gift", 0, 0, 0.4, 3)

        mySleep(5)

    
    def mirror4ChooseThemePack(self):
        # 先默认拉第一个好了，之后再搞选择
        self.cap_win()
        theme_selected = 0
        reset_flag = 0
        mySleep(2)
        while not theme_selected:
            # You Can Change Event_Theme.png depend on Event New Theme If you want to avoid Event Theme Pack Then Copy Any Theme And Rename It to Event_Theme.png
            if(self.is_find("./pic/mirror/mirror4/theme/EventTheme.png", "Event_Theme")):
                self.click_locate_and_drag_to("./pic/mirror/mirror4/theme/EventTheme.png", "Event_Theme")
                theme_selected = 1
            # ThemeSelectedByOrderPriorityFrom1
            elif(self.is_find("./pic/mirror/mirror4/theme/1.png", "theme_1")):
                self.click_locate_and_drag_to("./pic/mirror/mirror4/theme/1.png", "theme_1")
                theme_selected = 1
            elif(self.is_find("./pic/mirror/mirror4/theme/2.png", "theme_2")):
                self.click_locate_and_drag_to("./pic/mirror/mirror4/theme/2.png", "theme_2")
                theme_selected = 1
            elif(self.is_find("./pic/mirror/mirror4/theme/3.png", "theme_3")):
                self.click_locate_and_drag_to("./pic/mirror/mirror4/theme/3.png", "theme_3")
                theme_selected = 1
            elif(self.is_find("./pic/mirror/mirror4/theme/4.png", "theme_4")):
                self.click_locate_and_drag_to("./pic/mirror/mirror4/theme/4.png", "theme_4")
                theme_selected = 1
            elif(self.is_find("./pic/mirror/mirror4/theme/5.png", "theme_5")):
                self.click_locate_and_drag_to("./pic/mirror/mirror4/theme/5.png", "theme_5")
                theme_selected = 1
            elif(self.is_find("./pic/mirror/mirror4/theme/6.png", "theme_6")):
                self.click_locate_and_drag_to("./pic/mirror/mirror4/theme/6.png", "theme_6")
                theme_selected = 1
            elif(self.is_find("./pic/mirror/mirror4/theme/7.png", "theme_7")):
                self.click_locate_and_drag_to("./pic/mirror/mirror4/theme/7.png", "theme_7")
                theme_selected = 1
            elif(self.is_find("./pic/mirror/mirror4/theme/8.png", "theme_8")):
                self.click_locate_and_drag_to("./pic/mirror/mirror4/theme/8.png", "theme_8")
                theme_selected = 1
            elif(self.is_find("./pic/mirror/mirror4/theme/9.png", "theme_9")):
                self.click_locate_and_drag_to("./pic/mirror/mirror4/theme/9.png", "theme_9")
                theme_selected = 1
            elif(self.is_find("./pic/mirror/mirror4/theme/10.png", "theme_10")):
                self.click_locate_and_drag_to("./pic/mirror/mirror4/theme/10.png", "theme_10")
                theme_selected = 1
            elif(self.is_find("./pic/mirror/mirror4/theme/11.png", "theme_11")):
                self.click_locate_and_drag_to("./pic/mirror/mirror4/theme/11.png", "theme_11")
                theme_selected = 1
            elif(self.is_find("./pic/mirror/mirror4/theme/12.png", "theme_12")):
                self.click_locate_and_drag_to("./pic/mirror/mirror4/theme/12.png", "theme_12")
                theme_selected = 1
            elif(self.is_find("./pic/mirror/mirror4/theme/13.png", "theme_13")):
                self.click_locate_and_drag_to("./pic/mirror/mirror4/theme/13.png", "theme_13")
                theme_selected = 1
            elif(self.is_find("./pic/mirror/mirror4/theme/14.png", "theme_14")):
                self.click_locate_and_drag_to("./pic/mirror/mirror4/theme/14.png", "theme_14")
                theme_selected = 1
            elif(self.is_find("./pic/mirror/mirror4/theme/15.png", "theme_15")):
                self.click_locate_and_drag_to("./pic/mirror/mirror4/theme/15.png", "theme_15")
                theme_selected = 1
            elif(self.is_find("./pic/mirror/mirror4/theme/16.png", "theme_16")):
                self.click_locate_and_drag_to("./pic/mirror/mirror4/theme/16.png", "theme_16")
                theme_selected = 1
            elif(self.is_find("./pic/mirror/mirror4/theme/17.png", "theme_17")):
                self.click_locate_and_drag_to("./pic/mirror/mirror4/theme/17.png", "theme_17")
                theme_selected = 1
            elif(self.is_find("./pic/mirror/mirror4/theme/18.png", "theme_18")):
                self.click_locate_and_drag_to("./pic/mirror/mirror4/theme/18.png", "theme_18")
                theme_selected = 1
            elif(self.is_find("./pic/mirror/mirror4/theme/19.png", "theme_19")):
                self.click_locate_and_drag_to("./pic/mirror/mirror4/theme/19.png", "theme_19")
                theme_selected = 1
            elif(self.is_find("./pic/mirror/mirror4/theme/20.png", "theme_20")):
                self.click_locate_and_drag_to("./pic/mirror/mirror4/theme/20.png", "theme_20")
                theme_selected = 1
            elif(self.is_find("./pic/mirror/mirror4/theme/21.png", "theme_21")):
                self.click_locate_and_drag_to("./pic/mirror/mirror4/theme/21.png", "theme_21")
                theme_selected = 1
            elif(self.is_find("./pic/mirror/mirror4/theme/22.png", "theme_22")):
                self.click_locate_and_drag_to("./pic/mirror/mirror4/theme/22.png", "theme_22")
                theme_selected = 1
            elif(self.is_find("./pic/mirror/mirror4/theme/23.png", "theme_23")):
                self.click_locate_and_drag_to("./pic/mirror/mirror4/theme/23.png", "theme_23")
                theme_selected = 1
            elif(self.is_find("./pic/mirror/mirror4/theme/24.png", "theme_24")):
                self.click_locate_and_drag_to("./pic/mirror/mirror4/theme/24.png", "theme_24")
                theme_selected = 1
            elif(self.is_find("./pic/mirror/mirror4/theme/25.png", "theme_25")):
                self.click_locate_and_drag_to("./pic/mirror/mirror4/theme/25.png", "theme_25")
                theme_selected = 1
            elif(self.is_find("./pic/mirror/mirror4/theme/26.png", "theme_26")):
                self.click_locate_and_drag_to("./pic/mirror/mirror4/theme/26.png", "theme_26")
                theme_selected = 1
            elif(self.is_find("./pic/mirror/mirror4/theme/27.png", "theme_27")):
                self.click_locate_and_drag_to("./pic/mirror/mirror4/theme/27.png", "theme_27")
                theme_selected = 1
            elif(self.is_find("./pic/mirror/mirror4/theme/28.png", "theme_28")):
                self.click_locate_and_drag_to("./pic/mirror/mirror4/theme/28.png", "theme_28")
                theme_selected = 1
            elif(self.is_find("./pic/mirror/mirror4/theme/29.png", "theme_29")):
                self.click_locate_and_drag_to("./pic/mirror/mirror4/theme/29.png", "theme_29")
                theme_selected = 1
            elif(self.is_find("./pic/mirror/mirror4/theme/30.png", "theme_30")):
                self.click_locate_and_drag_to("./pic/mirror/mirror4/theme/30.png", "theme_30")
                theme_selected = 1
            elif(self.is_find("./pic/mirror/mirror4/theme/31.png", "theme_31")):
                self.click_locate_and_drag_to("./pic/mirror/mirror4/theme/31.png", "theme_31")
                theme_selected = 1
            elif(self.is_find("./pic/mirror/mirror4/theme/32.png", "theme_32")):
                self.click_locate_and_drag_to("./pic/mirror/mirror4/theme/32.png", "theme_32")
                theme_selected = 1
            elif(self.is_find("./pic/mirror/mirror4/theme/33.png", "theme_33")):
                self.click_locate_and_drag_to("./pic/mirror/mirror4/theme/33.png", "theme_33")
                theme_selected = 1
            elif(self.is_find("./pic/mirror/mirror4/theme/34.png", "theme_34")):
                self.click_locate_and_drag_to("./pic/mirror/mirror4/theme/34.png", "theme_34")
                theme_selected = 1
            elif(self.is_find("./pic/mirror/mirror4/theme/35.png", "theme_35")):
                self.click_locate_and_drag_to("./pic/mirror/mirror4/theme/35.png", "theme_35")
                theme_selected = 1
            elif(self.is_find("./pic/mirror/mirror4/theme/36.png", "theme_36")):
                self.click_locate_and_drag_to("./pic/mirror/mirror4/theme/36.png", "theme_36")
                theme_selected = 1
            elif(self.is_find("./pic/mirror/mirror4/theme/37.png", "theme_37")):
                self.click_locate_and_drag_to("./pic/mirror/mirror4/theme/37.png", "theme_37")
                theme_selected = 1
            elif(self.is_find("./pic/mirror/mirror4/theme/38.png", "theme_38")):
                self.click_locate_and_drag_to("./pic/mirror/mirror4/theme/38.png", "theme_38")
                theme_selected = 1
            elif(self.is_find("./pic/mirror/mirror4/theme/39.png", "theme_39")):
                self.click_locate_and_drag_to("./pic/mirror/mirror4/theme/39.png", "theme_39")
                theme_selected = 1
            elif(self.is_find("./pic/mirror/mirror4/theme/40.png", "theme_40")):
                self.click_locate_and_drag_to("./pic/mirror/mirror4/theme/40.png", "theme_40")
                theme_selected = 1
            elif(self.is_find("./pic/mirror/mirror4/theme/41.png", "theme_41")):
                self.click_locate_and_drag_to("./pic/mirror/mirror4/theme/41.png", "theme_41")
                theme_selected = 1
            elif reset_flag == 1:
                self.single_target_click("./pic/mirror/mirror4/theme/LBIcon.png", "randomTheme")
                theme_selected = 1
            # ResetIfNoFoundPreferedTheme
            elif self.is_find("./pic/mirror/mirror4/theme/refresh.png", "refresh") and reset_flag == 0:
                self.single_target_click("./pic/mirror/mirror4/theme/refresh.png", "refresh")
                reset_flag = 1
                mySleep(2)
        mySleep(6)

    def mirror4Chair(self):
        self.single_target_click("./pic/mirror/mirror4/ProductCatalogue/ChairHealSinner.png", "Heal Sinner")
        self.cap_win()
        self.single_target_click("./pic/mirror/mirror4/ProductCatalogue/AllSinnerRest.png", "AllSinnerRest")
        self.cap_win()
        self.single_target_click("./pic/event/Skip.png", "Skip", 0, 0, 0.3, 2)
        self.cap_win()
        if (not self.single_target_click("./pic/event/Continue.png", "Continue")):
            # For the situation that sinner all healthy
            self.single_target_click("./pic/mirror/mirror4/ProductCatalogue/DontPurchase.png", "NoSinnerNeedRestSign")
        # 对bus/chair的出口第一时间反应
        self.cap_win()
        if(self.single_target_click("./pic/event/Leave.png", "Leave")):
            self.cap_win()
            self.single_target_click("./pic/mirror/mirror2/whiteConfirm.png", "Confirm")

    def mirror4Cope(self): 
        '''处理镜牢4交互的各种情况'''
        result = False
        self.cap_win()
        # 确保能显现各种事件的正体
        if self.single_target_click("./pic/event/Skip.png", "Skip", 0, 0, 0.4, 3):
            self.cap_win()

        if(self.is_find("./pic/team/Announcer.png", "Announcer")):
            self.mirror4PrepareBattle()
            self.mirror4BattlePart()
            result = True
        elif(self.is_find("./pic/battle/WinRate.png", "battleSign")):
            self.mirror4BattlePart()
            result = True
        elif(self.is_find("./pic/mirror/mirror4/ProductCatalogue/ProductCatalogue.png", "ProductCatalogue")
             and self.single_target_click("./pic/event/Skip.png", "Skip", 0, 0, 0.4, 3)):
            if (self.is_find("./pic/mirror/mirror4/ProductCatalogue/FuseGifts.png", "ChairSign")):
                self.mirror4Chair()
            elif (self.is_find("./pic/mirror/mirror4/ProductCatalogue/PurchaseEGO.png", "PurchaseEGOSign")):
                self.mirror4PurchaseEGO()
            result = True
        elif(self.is_find("./pic/event/Skip.png", "Skip")):
            self.eventPart()
            result = True
        elif(self.is_find("./pic/mirror/mirror4/way/RewardCard/RewardCardSign.png", "RewardCardSign")):
            mySleep(3)
            self.mirror4SelectEncounterRewardCard()
            result = True
        elif(self.is_find("./pic/mirror/mirror4/way/Confirm.png", "EGOGift")):
            #self.single_target_click("./pic/mirror/mirror4/way/Confirm.png", "confirmEGOGift")
            self.press_key('enter')
            result = True
        elif(self.single_target_click("./pic/mirror/mirror4/ego/egoGift.png", "ChooseEgoGift")):
            self.cap_win()
            self.single_target_click("./pic/mirror/mirror4/ego/SelectEGOGift.png", "SelectEGOGift")
            self.press_key('enter')
            result = True
        elif(self.single_target_click("./pic/mirror/mirror4/way/Enter.png", "Enter", 0, 0, 2)):
            result = True
        elif(self.is_find("./pic/mirror/mirror4/way/ThemePack/SelectFloor.png", "SelectFloor")
             and self.is_find("./pic/mirror/mirror4/way/ThemePack/ThemePack.png", "ThemePack")):
            self.mirror4ChooseThemePack()
            result = True
        elif(self.is_find("./pic/Wait.png", "Wait Sign")):
            self.myWait()
            result = True
            
        return result


    @checkAndExit
    @beginAndFinishLog
    def mirror4PrepareBattle(self):
        '''镜牢4准备战斗的流程'''
        self.prepareBattle()

    @checkAndExit
    @beginAndFinishLog
    def mirror4BattlePart(self):
        self.allWinRateBattle()
        


    @checkAndExit
    @beginAndFinishLog
    def mirror4SinCoreFindWay(self):
        '''镜牢4单进程寻路流程'''

        '''
        # 滚动滑轮以保持视图大小不变
        littleUpScroll()

        self.single_target_click("./pic/mirror/mirror4/way/Self.png", "Self", 0, 0, 0.8, 1, 0.7)
        self.cap_win()
        if self.is_find("./pic/mirror/mirror4/way/Enter.png", "Enter"):
            self.press_key('enter')
            return True
        
        base_path = "./pic/mirror/mirror4/way/"
        for target in globalVar.enemyList:
            path = base_path + target
            for root,dirs,files in walk(path):
                for i in range(len(files)):
                    if(files[i][-3:] == 'png'):
                        file_path = root + '/' + files[i]
                        if self.single_target_click(file_path, target + files[i][-6:-4], 0, -10):
                            self.cap_win()
                            if self.is_find("./pic/mirror/mirror4/way/Enter.png", "Enter"):
                                self.press_key('enter', 2)
                                return True
                            
        self.click_drag_to("./pic/mirror/mirror4/way/Self.png", "DragSelf", globalVar.winLeft + 638, globalVar.winTop + 370, -100, 100, 0.9, 0.7)
        '''
        self.single_target_click("./pic/mirror/mirror4/way/Self.png", "Self")
        self.cap_win()
        if self.is_find("./pic/mirror/mirror4/way/Enter.png", "Enter"):
            self.press_key('enter')
            return True

        self.click_locate(740, 340, "Middle way")
        self.cap_win()
        if self.is_find("./pic/mirror/mirror4/way/Enter.png", "Enter"):
            self.press_key('enter', 2)
            return True

        self.click_locate(740, 125, "High way")
        self.cap_win()
        if self.is_find("./pic/mirror/mirror4/way/Enter.png", "Enter"):
            self.press_key('enter', 2)
            return True
        
        self.click_locate(740, 550, "Low way")
        self.cap_win()
        if self.is_find("./pic/mirror/mirror4/way/Enter.png", "Enter"):
            self.press_key('enter', 2)
            return True
        
        
        return False



class _MirrorOfTheLake(_script):
    '''镜牢3的相关函数'''
    __slots__ = {"noWayFlag"}

    def mirror3(self):
        '''镜牢3进入、寻路、处理交互的集合'''
        result = False
        self.noWayFlag = False
        self.mirror3Entry()
        #有地图标识才寻路，否则仅作事件处理
        self.cap_win()
        if(self.is_find("./pic/mirror/mirror3/way/mirror3MapSign.png", "mirror3MapSign") and\
            (self.is_find("./pic/mirror/mirror3/way/BigSelf.png", "BigSelf", 0.8) or\
            self.is_find("./pic/mirror/mirror3/way/Self.png", "Self", 0.8))):
            self.noWayFlag = self.mirror3SinCoreFindWay()

        result = self.mirror3Cope()
        
        return result


    
    def mirror3Prize(self):
        '''镜牢3获取奖励的流程'''
        result = False
        self.cap_win()
        self.single_target_click("./pic/battle/confirm.png", "Final_Fight")
        self.cap_win()
        if self.is_find("./pic/mirror/mirror3/ClaimRewards.png","ClaimRewards"):
            self.press_key('enter', 0.3, 5)
            result = True

        '''self.single_target_click("./pic/mirror/mirror3/ClaimRewards.png","ClaimRewards")
        self.cap_win()
        self.single_target_click("./pic/mirror/mirror3/Receive.png","Receive")
        self.cap_win()
        if self.single_target_click("./pic/mirror/mirror3/whiteConfirm.png","FirstConfirm"):
            self.cap_win()
            if self.single_target_click("./pic/mirror/mirror3/way/Confirm.png","SecondConfirm"):
                result = True'''
        return result


    @checkAndExit
    @beginAndFinishLog
    def mirror3Leave(self):
        '''镜牢3离开时处理notFullFlag'''
        global notFullFlag 
        notFullFlag = 0

    
    def mirror3HaltAndEnter(self):
        self.press_key("esc", 1)
        self.cap_win()
        self.single_target_click("./pic/mirror/mirror3/mirror3Normal.png", "mirror3Normal", 0, 0, 2)
        self.cap_win()
        self.single_target_click("./pic/mirror/mirror3/HaltExploration.png", "HaltExploration", 0, 0, 1, 1, 0.6)
        self.press_key("enter", 1)
        self.cap_win()
        self.single_target_click("./pic/mirror/mirror3/GiveUpRewards.png", "GiveUpRewards")
        self.press_key("enter")

    @checkAndExit
    @beginAndFinishLog
    def mirror3GetStartGift(self):
        '''刷取饰品'''
        gift_flag = 0
        while not gift_flag:
            self.cap_win()
            self.single_target_click("./pic/mirror/mirror3/gift/Poise/Poise.png", "Poise", 0, 0, 2, 1, 0.9)
            self.cap_win()
            if self.single_target_click("./pic/mirror/mirror3/gift/Poise/Mebulizer.png", "Mebulizer", 0, 0, 1):
                gift_flag = 1
                if self.single_target_click("./pic/mirror/mirror3/gift/Poise/CigaretteHolder.png", "CigaretteHolder", 0, 0, 1):
                    pass
                if self.single_target_click("./pic/mirror/mirror3/gift/Poise/OrnamentalHorseshoe.png", "OrnamentalHorseshoe", 0, 0, 1):
                    pass
            
            # 卡住来测试该函数的
            # gift_flag = 0
            if not gift_flag:
                self.mirror3HaltAndEnter()
                self.cap_win()
                self.single_target_click("./pic/mirror/mirror3/mirror3Normal.png", "mirror3Normal")
                self.press_key("enter")
                self.cap_win()
                self.single_target_click("./pic/mirror/mirror3/firstWishConfirm.png", "firstWishConfirm", 0, 0, 1)

            
    

    def getGiftSwitch(self):
        f = open("gift_switch.txt")
        line = f.readline().strip()
        line = int(line)
        globalVar.gift_switch = line
        f.close()



    @checkAndExit
    @beginAndFinishLog
    def mirror3Entry(self):
        '''进入镜牢3流程'''
        if(self.is_find("./pic/mirror/mirror3/way/mirror3MapSign.png", "mirror3MapSign")):
            return
        self.cap_win()
        self.single_target_click("./pic/initMenu/drive.png", "Drive")
        self.cap_win()
        self.single_target_click("./pic/mirror/mirror3/MirrorDungeons.png", "MirrorDungeons", 0, 0, 1, 1, 0.9)
        self.cap_win()
        if(self.is_find("./pic/mirror/previousClaimReward.png", "previousClaimReward")):
            raise previousClaimRewardError("有上周的镜牢奖励未领取")
        self.single_target_click("./pic/mirror/mirror3/mirror3Normal.png", "mirror3Normal")
        self.cap_win()
        if(self.is_find("./pic/mirror/MirrorInProgress.png", "MirrorInProgress")):
            raise mirrorInProgressError("有其他镜牢未结束")
        if(self.single_target_click("./pic/mirror/mirror3/Enter.png", "Enter", 0, 0, 2)):
            self.cap_win()
            self.single_target_click("./pic/mirror/mirror3/firstWishConfirm.png", "firstWishConfirm", 0, 0, 1.5)
            self.cap_win()
            self.getGiftSwitch()
            if globalVar.gift_switch:
                self.mirror3GetStartGift()
            else:
                self.single_target_click("./pic/mirror/mirror3/ego/RandomEGOGift.png", "egoGift")
                self.cap_win()
                self.multiple_target_click("./pic/mirror/mirror3/ego/confirmRandomEGOGift.png", "EGOGift")
            self.cap_win()
            self.single_target_click("./pic/mirror/mirror3/ego/SelectEGOGift.png", "SelectEGOGift", 0, 0, 5)
            self.press_key('enter', 0.4, 3) # confirm the ego
            self.press_key('enter', 3) # enter
            self.cap_win()
        else:
            self.single_target_click("./pic/mirror/mirror3/Resume.png", "Resume", 0, 0, 5)
        if(self.is_find("./pic/Wait.png", "Wait Sign")):
            self.myWait()
        



    def mirror3Cope(self): 
        '''处理镜牢3交互的各种情况'''
        result = False
        self.cap_win()
        if(self.is_find("./pic/team/Announcer.png", "Announcer")):
            self.mirror3PrepareBattle()
            self.mirror3BattlePart()
            result = True
        elif(self.is_find("./pic/battle/WinRate.png", "battleSign")):
            self.mirror3BattlePart()
            result = True
        elif(self.is_find("./pic/event/Skip.png", "Skip")):
            self.eventPart()
            result = True
        elif(self.is_find("./pic/mirror/mirror3/way/Confirm.png", "EGOGift")):
            self.single_target_click("./pic/mirror/mirror3/way/Confirm.png", "confirmEGOGift", 0, 0, 1, 2)
            result = True
        elif(self.single_target_click("./pic/mirror/mirror3/ego/egoGift.png", "ChooseEgoGift")):
            self.cap_win()
            self.single_target_click("./pic/mirror/mirror3/ego/SelectEGOGift.png", "SelectEGOGift", 0, 0, 6)
            result = True
        elif(self.single_target_click("./pic/mirror/mirror3/way/Enter.png", "Enter", 0, 0, 2)):
            result = True
        elif(self.is_find("./pic/Wait.png", "Wait Sign")):
            self.myWait()
            result = True
            
        return result


    @checkAndExit
    @beginAndFinishLog
    def mirror3PrepareBattle(self):
        '''镜牢3准备战斗的流程'''
        self.prepareBattle()

    @checkAndExit
    @beginAndFinishLog
    def mirror3BattlePart(self):
        self.allWinRateBattle()
        


    @checkAndExit
    @beginAndFinishLog
    def mirror3SinCoreFindWay(self):
        '''镜牢3单进程寻路流程'''
        # 滚动滑轮以保持视图大小不变
        littleUpScroll()

        self.single_target_click("./pic/mirror/mirror3/way/Self.png", "Self", 0, 0, 0.8, 1, 0.7)
        self.cap_win()
        if self.is_find("./pic/mirror/mirror3/way/Enter.png", "Enter"):
            self.press_key('enter')
            return True
        
        base_path = "./pic/mirror/mirror3/way/"
        for target in globalVar.enemyList:
            path = base_path + target
            for root,dirs,files in walk(path):
                for i in range(len(files)):
                    if(files[i][-3:] == 'png'):
                        file_path = root + '/' + files[i]
                        if self.single_target_click(file_path, target + files[i][-6:-4], 0, -10):
                            self.cap_win()
                            if self.is_find("./pic/mirror/mirror3/way/Enter.png", "Enter"):
                                self.press_key('enter', 2)
                                return True
                            
        self.click_drag_to("./pic/mirror/mirror3/way/Self.png", "DragSelf", globalVar.winLeft + 638, globalVar.winTop + 370, -100, 100, 0.9, 0.7)
        
        return False





class _MirrorOfMirrors(_script):
    '''镜牢2相关函数集合类'''
    __slots__ = ("noWayFlag")

    def __init__(self):
        self.noWayFlag = False
        pass

    
    def Mirror2(self):
        '''镜牢2进入、寻路、处理交互的集合'''
        result = False
        self.noWayFlag = False
        self.mirror2Entry()
        #有地图标识才寻路，否则仅作事件处理
        self.cap_win()
        if(self.is_find("./pic/mirror/mirror2/way/mirror2MapSign.png", "mirror2MapSign") and\
            (self.is_find("./pic/mirror/mirror2/way/BigSelf.png", "BigSelf", 0.8) or\
            self.is_find("./pic/mirror/mirror2/way/Self.png", "Self", 0.8))):
            self.noWayFlag = self.mirror2SinCoreFindWay()

        result = self.mirror2Cope()
        
        return result


    
    def mirror2Prize(self):
        '''镜牢2获取奖励的流程'''
        result = False
        self.cap_win()
        self.single_target_click("./pic/battle/confirm.png", "Final_Victory")
        self.cap_win()
        self.single_target_click("./pic/mirror/mirror2/ClaimRewards.png","ClaimRewards", 0, 0, 0.7, 1, 0.7)
        self.cap_win()
        self.single_target_click("./pic/mirror/mirror2/Receive.png","Receive")
        self.cap_win()
        if self.single_target_click("./pic/mirror/mirror2/whiteConfirm.png","FirstConfirm"):
            self.cap_win()
            if self.single_target_click("./pic/mirror/mirror2/way/Confirm.png","SecondConfirm"):
                result = True
        return result


    @checkAndExit
    @beginAndFinishLog
    def mirror2Leave(self):
        '''镜牢2离开时处理notFullFlag'''
        global notFullFlag 
        notFullFlag = 0
        


    @checkAndExit
    @beginAndFinishLog
    def mirror2Entry(self):
        '''进入镜牢2流程'''
        if(self.is_find("./pic/mirror/mirror2/way/mirror2MapSign.png", "mirror2MapSign")):
            return
        self.cap_win()
        self.single_target_click("./pic/initMenu/drive.png", "Drive")
        self.cap_win()
        self.single_target_click("./pic/mirror/mirror2/MirrorDungeons.png", "MirrorDungeons", 0, 0, 1, 1, 0.9)
        self.cap_win()
        if(self.is_find("./pic/mirror/previousClaimReward.png", "previousClaimReward")):
            raise previousClaimRewardError("有上周的镜牢奖励未领取")
        self.single_target_click("./pic/mirror/mirror2/Mirror2Normal.png", "Mirror2Normal")
        self.cap_win()
        if(self.is_find("./pic/mirror/MirrorInProgress.png", "MirrorInProgress")):
            raise mirrorInProgressError("有其他镜牢未结束")
        if(self.single_target_click("./pic/mirror/mirror2/Enter.png", "Enter", 0, 0, 5) or\
            self.single_target_click("./pic/mirror/mirror2/Resume.png", "Resume", 0, 0, 5)):
            self.cap_win()
            self.single_target_click("./pic/mirror/mirror2/ego/egoGift.png", "egoGift")
            self.cap_win()
            self.single_target_click("./pic/mirror/mirror2/ego/SelectEGOGift.png", "SelectEGOGift")
            self.cap_win()
            if self.single_target_click("./pic/mirror/mirror2/Preset.png", "Preset"):
                self.cap_win()
                if(self.is_find("./pic/error/noSavedPreset.png", "noPreset")):
                    raise noSavedPresetsError("没有预选队伍")
                self.mirror2ChoosePreset()
            self.single_target_click("./pic/mirror/mirror2/blackConfirm.png", "Confirm", 0, 0, 3)
            self.cap_win()
            self.single_target_click("./pic/mirror/mirror2/BuyCoin.png", "BuyCoin", 0, 0, 8)
        if(self.is_find("./pic/Wait.png", "Wait Sign")):
            self.myWait()


    def mirror2ChoosePreset(self):
        '''镜牢2预选人的流程'''
        i = 1
        countFlag = 0
        while(not self.is_find("./pic/team/FullTeam77.png", "7/7PresetFullSign")):
            #i的归零
            if(i > 12):
                i = 1
                countFlag += 1
                if(countFlag > 1):
                    myLog("warning","Preset Fail")
                    break
            self.cap_win()
            if(i < 7):
                addX = i * 140
                addY = 0
            else:
                addX = (i - 6) * 140
                addY = 200

            self.single_target_click("./pic/team/Announcer.png", "Member", addX, addY + 100, 0.2)
            self.cap_win()
            i += 1

        self.single_target_click("./pic/team/Announcer.png", "Confirm", 1000, 400, 3)
        



    def mirror2Cope(self): 
        '''处理镜牢2交互的各种情况'''
        result = False
        self.cap_win()
        if(self.is_find("./pic/team/Announcer.png", "Announcer")):
            self.mirror2PrepareBattle()
            self.mirror2BattlePart()
            result = True
        elif(self.is_find("./pic/battle/WinRate.png", "battleSign")):
            self.mirror2BattlePart()
            result = True
        elif(self.is_find("./pic/event/Skip.png", "Skip")):
            self.eventPart()
            result = True
        elif(self.is_find("./pic/mirror/mirror2/way/Confirm.png", "EGOGift")):
            self.single_target_click("./pic/mirror/mirror2/way/Confirm.png", "EGOGift", 0, 0, 1, 2)
            result = True
        elif(self.single_target_click("./pic/mirror/mirror2/ego/egoGift.png", "ChooseEgoGift")):
            self.cap_win()
            self.single_target_click("./pic/mirror/mirror2/ego/SelectEGOGift.png", "SelectEGOGift", 0, 0, 6)
            result = True
        elif(self.single_target_click("./pic/mirror/mirror2/way/Enter.png", "Enter", 0, 0, 2)):
            result = True
        elif(self.is_find("./pic/Wait.png", "Wait Sign")):
            self.myWait()
            result = True
            
        return result
            

    #根据已选人数和队伍可容纳人数做情况分类
    #检测5/5；6/6；7/7最好就一个标准，能省不少时间
    def mirror2JudTeamCondition(self):
        '''判断当前队伍状况'''
        resultCondition = -1
        if(self.is_find("./pic/team/FullTeam77.png", "FullTeam7/7", 0.94) or\
            self.is_find("./pic/team/FullTeam66.png", "FullTeam6/6", 0.94) or\
            self.is_find("./pic/team/FullTeam55.png", "FullTeam5/5", 0.94)):
            resultCondition = 0
        elif(self.is_find("./pic/team/EmptyTeam05.png", "EmptyTeam0/5", 0.94)):
            resultCondition = 1
        elif(self.is_find("./pic/team/EmptyTeam06.png", "EmptyTeam0/6", 0.94) or\
        self.is_find("./pic/team/NotFullTeam56.png", "NotFullTeam5/6", 0.94)):
            resultCondition = 2
        elif(self.is_find("./pic/team/EmptyTeam07.png", "EmptyTeam0/7", 0.94) or\
        self.is_find("./pic/team/NotFullTeam67.png", "NotFullTeam6/7", 0.94)):
            resultCondition = 3
        return resultCondition


    #满队标准
    def mirror2JudFullTeam(self,condition):
        '''判断队伍是否人满'''
        result = False
        if(condition == 0):
            result = True
        elif(condition == 1):
            if(self.is_find("./pic/team/FullTeam55.png", "FullTeam5/5", 0.94)):
                result = True
        elif(condition == 2):
            if(self.is_find("./pic/team/FullTeam66.png", "FullTeam6/6", 0.94)):
                result = True
        elif(condition == 3):
            if(self.is_find("./pic/team/FullTeam77.png", "FullTeam7/7", 0.94)):
                result = True
        else:
            if(self.is_find("./pic/team/FullTeam77.png", "FullTeam7/7", 0.94) or\
                self.is_find("./pic/team/FullTeam66.png", "FullTeam6/6", 0.94) or\
                self.is_find("./pic/team/FullTeam55.png", "FullTeam5/5", 0.94)):
                result = True
        return result


    @checkAndExit
    @beginAndFinishLog
    def mirror2PrepareBattle(self):
        '''镜牢2准备战斗的流程'''
        i = 1
        global notFullFlag 
        countFlag = 0
        condition = self.mirror2JudTeamCondition()
        while(not self.mirror2JudFullTeam(condition) and (notFullFlag == 0)):
            #i的归零
            if(i > 12):
                i = 1
                countFlag += 1
                if(countFlag > 1):
                    myLog("warning","Can't make team full")
                    notFullFlag = 1
                    break
            self.cap_win()
            if(i < 7):
                addX = i * 140
                addY = 0
            else:
                addX = (i - 6) * 140
                addY = 200

            self.single_target_click("./pic/team/Announcer.png", "Member", addX, addY + 100, 0.2)
            self.cap_win()
            i += 1

        #即使选不到满人，也要尽可能多选人
        if(notFullFlag == 1 and\
        (self.is_find("./pic/team/EmptyTeam05.png", "EmptyTeam0/5", 0.94)or\
            self.is_find("./pic/team/EmptyTeam06.png", "EmptyTeam0/6", 0.94)or\
            self.is_find("./pic/team/EmptyTeam07.png", "EmptyTeam0/7", 0.94)or\
            self.is_find("./pic/team/NotFullTeam15.png", "NotFullTeam1/5", 0.94)or\
            self.is_find("./pic/team/NotFullTeam16.png", "NotFullTeam1/6", 0.94)or\
            self.is_find("./pic/team/NotFullTeam17.png", "NotFullTeam1/7", 0.94))
            ):
            for i in range(1,13):
                self.cap_win()
                if(i < 7):
                    addX = i * 140
                    addY = 0
                else:
                    addX = (i - 6) * 140
                    addY = 200

                self.single_target_click("./pic/team/Announcer.png", "Member", addX, addY + 100, 0.2)



        self.single_target_click("./pic/team/Announcer.png", "ToBattle", 1000, 400, 5)
        self.cap_win()
        if(self.is_find("./pic/Wait.png", "Wait Sign")):
                self.myWait()


    @checkAndExit
    @beginAndFinishLog
    def mirror2BattlePart(self):
        '''镜牢战斗处理'''
        '''self.cap_win()
        loopCount = 0
        while(True):
            self.cap_win()
            condition = False
            if (self.is_find("./pic/battle/WinRate.png", "WinRate")):
                self.cap_win()
                if (self.is_find("./pic/battle/Start.png", "StartBattle")):
                    condition = True
            elif(self.is_find("./pic/battle/battlePause.png", "Fighting Sign")):
                mySleep(2)
                condition = True
            elif(self.single_target_click("./pic/battle/trianglePause.png", "Continue Fight!")):
                condition = True    
            elif(self.is_find("./pic/event/Skip.png", "Skip")):
                self.eventPart()
                condition = True
            elif(self.is_find("./pic/Wait.png", "Wait Sign")):
                self.myWait()
                condition = True
            if(not condition):
                loopCount += 1
                if(loopCount > 2):
                    break
            else:
                loopCount = 0
            mySleep(0.9)'''
        self.allWinRateBattle()
        


    @checkAndExit
    @beginAndFinishLog
    def mirror2SinCoreFindWay(self):
        '''镜牢2单进程寻路流程'''
        result = False

        # 滚动滑轮以保持视图大小不变
        littleUpScroll()

        self.single_target_click("./pic/mirror/mirror2/way/Self.png", "Self")
        self.cap_win()
        if(self.single_target_click("./pic/mirror/mirror2/way/Enter.png", "Enter", 0, 0, 2)):
            result = True
            return result
        self.mirror2SinCoreQuesionMark()
        if(self.single_target_click("./pic/mirror/mirror2/way/Enter.png", "Enter", 0, 0, 2)):
            result = True
            return result
        self.mirror2SinCoreChair()
        if(self.single_target_click("./pic/mirror/mirror2/way/Enter.png", "Enter", 0, 0, 2)):
            result = True
            return result
        self.mirror2SinCoreBus()
        if(self.single_target_click("./pic/mirror/mirror2/way/Enter.png", "Enter", 0, 0, 2)):
            result = True
            return result
        self.mirror2SinCoreFight()
        if(self.single_target_click("./pic/mirror/mirror2/way/Enter.png", "Enter", 0, 0, 2)):
            result = True
            return result
        self.mirror2SinCoreBoss()
        if(self.single_target_click("./pic/mirror/mirror2/way/Enter.png", "Enter", 0, 0, 2)):
            result = True
            return result
        self.mirror2SinCoreBattle()
        if(self.single_target_click("./pic/mirror/mirror2/way/Enter.png", "Enter", 0, 0, 2)):
            result = True
            return result
        self.mirror2SinCoreEncounter()
        if(self.single_target_click("./pic/mirror/mirror2/way/Enter.png", "Enter", 0, 0, 2)):
            result = True
            return result
        
        
        return result


    #椅子部分
    def mirror2SinCoreChair(self):
        '''镜牢2单进程找椅子'''
        if self.single_target_click("./pic/mirror/mirror2/way/Chair/ChairM.png", "ChairMiddle"):
            self.cap_win()
            if self.is_find("./pic/mirror/mirror2/way/Enter.png", "Enter"):
                return
        

        if self.single_target_click("./pic/mirror/mirror2/way/Chair/ChairRH.png", "ChairRightHigh"):
            self.cap_win()
            if self.is_find("./pic/mirror/mirror2/way/Enter.png", "Enter"):
                return

        if self.single_target_click("./pic/mirror/mirror2/way/Chair/ChairRM.png", "ChairRightMiddle"):
            self.cap_win()
            if self.is_find("./pic/mirror/mirror2/way/Enter.png", "Enter"):
                return
        
        if self.single_target_click("./pic/mirror/mirror2/way/Chair/ChairRL.png", "ChairRightLow", 0, -10):
            self.cap_win()
            if self.is_find("./pic/mirror/mirror2/way/Enter.png", "Enter"):
                return
        
        if self.single_target_click("./pic/mirror/mirror2/way/Chair/ChairLH.png", "ChairLeftHigh"):
            self.cap_win()
            if self.is_find("./pic/mirror/mirror2/way/Enter.png", "Enter"):
                return

        if self.single_target_click("./pic/mirror/mirror2/way/Chair/ChairLM.png", "ChairLeftMiddle"):
            self.cap_win()
            if self.is_find("./pic/mirror/mirror2/way/Enter.png", "Enter"):
                return

        if self.single_target_click("./pic/mirror/mirror2/way/Chair/ChairLL.png", "ChairLeftLow", 0, -10):
            self.cap_win()
            if self.is_find("./pic/mirror/mirror2/way/Enter.png", "Enter"):
                return

    #异想体部分
    def mirror2SinCoreEncounter(self):
        '''镜牢2单进程找异想体'''
        if self.single_target_click("./pic/mirror/mirror2/way/Encounter/EncounterM.png", "EncounterMiddle"):
            self.cap_win()
            if self.is_find("./pic/mirror/mirror2/way/Enter.png", "Enter"):
                return
        
        if self.single_target_click("./pic/mirror/mirror2/way/Encounter/EncounterRH.png", "EncounterRightHigh"):
            self.cap_win()
            if self.is_find("./pic/mirror/mirror2/way/Enter.png", "Enter"):
                return

        if self.single_target_click("./pic/mirror/mirror2/way/Encounter/EncounterRM.png", "EncounterRightMiddle"):
            self.cap_win()
            if self.is_find("./pic/mirror/mirror2/way/Enter.png", "Enter"):
                return

        if self.single_target_click("./pic/mirror/mirror2/way/Encounter/EncounterRL.png", "EncounterRightLow", 0, -10):
            self.cap_win()
            if self.is_find("./pic/mirror/mirror2/way/Enter.png", "Enter"):
                return

        if self.single_target_click("./pic/mirror/mirror2/way/Encounter/EncounterLH.png", "EncounterLeftHigh"):
            self.cap_win()
            if self.is_find("./pic/mirror/mirror2/way/Enter.png", "Enter"):
                return
        

        if self.single_target_click("./pic/mirror/mirror2/way/Encounter/EncounterLM.png", "EncounterLeftMiddle"):
            self.cap_win()
            if self.is_find("./pic/mirror/mirror2/way/Enter.png", "Enter"):
                return
        
        
        if self.single_target_click("./pic/mirror/mirror2/way/Encounter/EncounterLL.png", "EncounterLeftLow", 0, -10):
            self.cap_win()
            if self.is_find("./pic/mirror/mirror2/way/Enter.png", "Enter"):
                return


    #巴士部分
    def mirror2SinCoreBus(self):
        '''镜牢2单进程找巴士'''
        if self.single_target_click("./pic/mirror/mirror2/way/Bus/BusM.png", "BusMiddle"):
            self.cap_win()
            if self.is_find("./pic/mirror/mirror2/way/Enter.png", "Enter"):
                return
        if self.is_find("./pic/mirror/mirror2/way/Enter.png", "Enter"):
            return

        if self.single_target_click("./pic/mirror/mirror2/way/Bus/BusRH.png", "BusRightHigh"):
            self.cap_win()
            if self.is_find("./pic/mirror/mirror2/way/Enter.png", "Enter"):
                return

        if self.single_target_click("./pic/mirror/mirror2/way/Bus/BusRM.png", "BusRightMiddle"):
            self.cap_win()
            if self.is_find("./pic/mirror/mirror2/way/Enter.png", "Enter"):
                return
        
        if self.single_target_click("./pic/mirror/mirror2/way/Bus/BusRL.png", "BusRightLow", 0, -10):
            self.cap_win()
            if self.is_find("./pic/mirror/mirror2/way/Enter.png", "Enter"):
                return

        
        if self.single_target_click("./pic/mirror/mirror2/way/Bus/BusLH.png", "BusLeftHigh"):
            self.cap_win()
            if self.is_find("./pic/mirror/mirror2/way/Enter.png", "Enter"):
                return
        

        if self.single_target_click("./pic/mirror/mirror2/way/Bus/BusLM.png", "BusLeftMiddle"):
            self.cap_win()
            if self.is_find("./pic/mirror/mirror2/way/Enter.png", "Enter"):
                return
        
        if self.single_target_click("./pic/mirror/mirror2/way/Bus/BusLL.png", "BusLeftLow", 0, -10):
            self.cap_win()
            if self.is_find("./pic/mirror/mirror2/way/Enter.png", "Enter"):
                return
            


    #困难战斗部分
    def mirror2SinCoreBattle(self):
        '''镜牢2单进程找困难战斗'''
        if self.single_target_click("./pic/mirror/mirror2/way/Battle/BattleM.png", "BattleMiddle"):
            self.cap_win()
            if self.is_find("./pic/mirror/mirror2/way/Enter.png", "Enter"):
                return

        if self.single_target_click("./pic/mirror/mirror2/way/Battle/BattleRH.png", "BattleRightHigh"):
            self.cap_win()
            if self.is_find("./pic/mirror/mirror2/way/Enter.png", "Enter"):
                return
        
        if self.single_target_click("./pic/mirror/mirror2/way/Battle/BattleRM.png", "BattleRightMiddle"):
            self.cap_win()
            if self.is_find("./pic/mirror/mirror2/way/Enter.png", "Enter"):
                return
        
        if self.single_target_click("./pic/mirror/mirror2/way/Battle/BattleRL.png", "BattleRightLow", 0, -10):
            self.cap_win()
            if self.is_find("./pic/mirror/mirror2/way/Enter.png", "Enter"):
                return
        
        if self.single_target_click("./pic/mirror/mirror2/way/Battle/BattleLH.png", "BattleLeftHigh"):
            self.cap_win()
            if self.is_find("./pic/mirror/mirror2/way/Enter.png", "Enter"):
                return
        
        if self.single_target_click("./pic/mirror/mirror2/way/Battle/BattleLM.png", "BattleLeftMiddle"):
            self.cap_win()
            if self.is_find("./pic/mirror/mirror2/way/Enter.png", "Enter"):
                return
            
        if self.single_target_click("./pic/mirror/mirror2/way/Battle/BattleLL.png", "BattleLeftLow", 0, -10):
            self.cap_win()
            if self.is_find("./pic/mirror/mirror2/way/Enter.png", "Enter"):
                return

        

    #首领部分
    def mirror2SinCoreBoss(self):
        '''镜牢2单进程找首领'''
        if self.single_target_click("./pic/mirror/mirror2/way/Boss/BossM.png", "BossMiddle"):
            self.cap_win()
            if self.is_find("./pic/mirror/mirror2/way/Enter.png", "Enter"):
                return


        if self.single_target_click("./pic/mirror/mirror2/way/Boss/BossRH.png", "BossRightHigh"):
            self.cap_win()
            if self.is_find("./pic/mirror/mirror2/way/Enter.png", "Enter"):
                return

        if self.single_target_click("./pic/mirror/mirror2/way/Boss/BossRM.png", "BossRightMiddle"):
            self.cap_win()
            if self.is_find("./pic/mirror/mirror2/way/Enter.png", "Enter"):
                return

        if self.single_target_click("./pic/mirror/mirror2/way/Boss/BossRL.png", "BossRightLow", 0, -10):
            self.cap_win()
            if self.is_find("./pic/mirror/mirror2/way/Enter.png", "Enter"):
                return


        if self.single_target_click("./pic/mirror/mirror2/way/Boss/BossLH.png", "BossLeftHigh"):
            self.cap_win()
            if self.is_find("./pic/mirror/mirror2/way/Enter.png", "Enter"):
                return

        if self.single_target_click("./pic/mirror/mirror2/way/Boss/BossLM.png", "BossLeftMiddle"):
            self.cap_win()
            if self.is_find("./pic/mirror/mirror2/way/Enter.png", "Enter"):
                return
        
        if self.single_target_click("./pic/mirror/mirror2/way/Boss/BossLL.png", "BossLeftLow", 0, -10):
            self.cap_win()
            if self.is_find("./pic/mirror/mirror2/way/Enter.png", "Enter"):
                return

        

    #问号事件部分
    def mirror2SinCoreQuesionMark(self):
        '''镜牢2单进程找问号'''
        if self.single_target_click("./pic/mirror/mirror2/way/QuesionMark/QuesionMarkM.png", "QuesionMarkMiddle"):
            self.cap_win()
            if self.is_find("./pic/mirror/mirror2/way/Enter.png", "Enter"):
                return
        
        if self.single_target_click("./pic/mirror/mirror2/way/QuesionMark/QuesionMarkRH.png", "QuesionMarkRightHigh"):
            self.cap_win()
            if self.is_find("./pic/mirror/mirror2/way/Enter.png", "Enter"):
                return

        if self.single_target_click("./pic/mirror/mirror2/way/QuesionMark/QuesionMarkRM.png", "QuesionMarkRightMiddle"):
            self.cap_win()
            if self.is_find("./pic/mirror/mirror2/way/Enter.png", "Enter"):
                return

        if self.single_target_click("./pic/mirror/mirror2/way/QuesionMark/QuesionMarkRL.png", "QuesionMarkRightLow", 0, -10):
            self.cap_win()
            if self.is_find("./pic/mirror/mirror2/way/Enter.png", "Enter"):
                return

        if self.single_target_click("./pic/mirror/mirror2/way/QuesionMark/QuesionMarkLH.png", "QuesionMarkLeftHigh"):
            self.cap_win()
            if self.is_find("./pic/mirror/mirror2/way/Enter.png", "Enter"):
                return

        if self.single_target_click("./pic/mirror/mirror2/way/QuesionMark/QuesionMarkLM.png", "QuesionMarkLeftMiddle"):
            self.cap_win()
            if self.is_find("./pic/mirror/mirror2/way/Enter.png", "Enter"):
                return

        if self.single_target_click("./pic/mirror/mirror2/way/QuesionMark/QuesionMarkLL.png", "QuesionMarkLeftLow", 0, -10):
            self.cap_win()
            if self.is_find("./pic/mirror/mirror2/way/Enter.png", "Enter"):
                return


    #战斗部分
    def mirror2SinCoreFight(self):
        '''镜牢2单进程找普通战斗'''
        if self.single_target_click("./pic/mirror/mirror2/way/Fight/FightM.png", "FightMiddle"):
            self.cap_win()
            if self.is_find("./pic/mirror/mirror2/way/Enter.png", "Enter"):
                return

        if self.single_target_click("./pic/mirror/mirror2/way/Fight/FightRH.png", "FightRightHigh"):
            self.cap_win()
            if self.is_find("./pic/mirror/mirror2/way/Enter.png", "Enter"):
                return

        if self.single_target_click("./pic/mirror/mirror2/way/Fight/FightRM.png", "FightRightMiddle"):
            self.cap_win()
            if self.is_find("./pic/mirror/mirror2/way/Enter.png", "Enter"):
                return

        if self.single_target_click("./pic/mirror/mirror2/way/Fight/FightRL.png", "FightRightLow", 0, -10):
            self.cap_win()
            if self.is_find("./pic/mirror/mirror2/way/Enter.png", "Enter"):
                return

        if self.single_target_click("./pic/mirror/mirror2/way/Fight/FightLH.png", "FightLeftHigh"):
            self.cap_win()
            if self.is_find("./pic/mirror/mirror2/way/Enter.png", "Enter"):
                return

        if self.single_target_click("./pic/mirror/mirror2/way/Fight/FightLM.png", "FightLeftMiddle"):
            self.cap_win()
            if self.is_find("./pic/mirror/mirror2/way/Enter.png", "Enter"):
                return

        if self.single_target_click("./pic/mirror/mirror2/way/Fight/FightLL.png", "FightLeftLow", 0, -10):
            self.cap_win()
            if self.is_find("./pic/mirror/mirror2/way/Enter.png", "Enter"):
                return
        



class _MirrorOfTheBeginning(_script):
    '''镜牢1相关函数集合类'''
    __slots__ = ("noWayFlag")

    def __init__(self):
        self.noWayFlag = False
        pass

    def Mirror1(self):
        '''镜牢1进入、寻路、处理交互的集合'''
        result = False
        self.noWayFlag = False
        self.mirror1Entry()
        #有地图标识才寻路，否则仅作事件处理
        self.cap_win()
        if(self.is_find("./pic/mirror/mirror1/way/mirror1MapSign.png", "mirror1MapSign") and\
            (self.is_find("./pic/mirror/mirror1/way/BigSelf.png", "BigSelf", 0.8) or\
            self.is_find("./pic/mirror/mirror1/way/Self.png", "Self", 0.8))):
            self.noWayFlag = self.mirror1SinCoreFindWay()

        result = self.mirror1Cope()
        
        return result
    

    
    @checkAndExit
    @beginAndFinishLog
    def mirror1Entry(self):
        '''进入镜牢1流程'''
        if(self.is_find("./pic/mirror/mirror1/way/mirror1MapSign.png", "mirror1MapSign")):
            return
        self.cap_win()
        self.single_target_click("./pic/initMenu/drive.png", "Drive")
        self.cap_win()
        self.single_target_click("./pic/mirror/mirror1/MirrorDungeons.png", "MirrorDungeons", 0, 0, 1, 1, 0.9)
        self.cap_win()
        if(self.is_find("./pic/mirror/previousClaimReward.png", "previousClaimReward")):
            raise previousClaimRewardError("有上周的镜牢奖励未领取")
        self.single_target_click("./pic/mirror/mirror1/Mirror1Normal.png", "Mirror1Normal")
        self.cap_win()
        if(self.is_find("./pic/mirror/MirrorInProgress.png", "MirrorInProgress")):
            raise mirrorInProgressError("有其他镜牢未结束")
        if(self.single_target_click("./pic/mirror/mirror1/Enter.png", "Enter", 0, 0, 5) or\
            self.single_target_click("./pic/mirror/mirror1/Resume.png", "Resume", 0, 0, 5)):
            self.cap_win()
            self.single_target_click("./pic/mirror/mirror1/ego/egoGift.png", "egoGift")
            self.cap_win()
            self.single_target_click("./pic/mirror/mirror1/ego/SelectEGOGift.png", "SelectEGOGift")
            self.cap_win()
            if self.single_target_click("./pic/mirror/mirror1/Preset.png", "Preset"):
                self.cap_win()
                if(self.is_find("./pic/error/noSavedPreset.png", "noPreset")):
                    raise noSavedPresetsError("没有预选队伍")
                self.mirror1ChoosePreset()
            self.single_target_click("./pic/mirror/mirror1/blackConfirm.png", "blackConfirm", 0, 0, 3)
            self.cap_win()
            self.single_target_click("./pic/mirror/mirror1/BuyCoin.png", "BuyCoin", 0, 0, 8)
        if(self.is_find("./pic/Wait.png", "Wait Sign")):
            self.myWait()

    
    def mirror1ChoosePreset(self):
        '''镜牢1预选人的流程'''
        i = 1
        countFlag = 0
        while(not self.is_find("./pic/team/FullTeam55.png", "5/5PresetFullSign")):
            #i的归零
            if(i > 12):
                i = 1
                countFlag += 1
                if(countFlag > 1):
                    myLog("warning","Preset Fail")
                    break
            self.cap_win()
            if(i < 7):
                addX = i * 140
                addY = 0
            else:
                addX = (i - 6) * 140
                addY = 200

            self.single_target_click("./pic/team/Announcer.png", "Member", addX, addY + 100, 0.2)
            self.cap_win()
            i += 1

        self.single_target_click("./pic/team/Announcer.png", "Confirm", 1000, 400, 3)


    @checkAndExit
    @beginAndFinishLog
    def mirror1Leave(self):
        '''镜牢1离开时处理notFullFlag'''
        global notFullFlag 
        notFullFlag = 0


    def mirror1Prize(self):
        '''镜牢1获取奖励的流程'''
        result = False
        self.cap_win()
        self.single_target_click("./pic/battle/confirm.png", "Final_Victory")
        self.cap_win()
        self.single_target_click("./pic/mirror/mirror1/ClaimRewards.png","ClaimRewards", 0, 0, 0.7, 1, 0.7)
        self.cap_win()
        self.single_target_click("./pic/mirror/mirror1/Receive.png","Receive")
        self.cap_win()
        if self.single_target_click("./pic/mirror/mirror1/whiteConfirm.png","FirstConfirm"):
            self.cap_win()
            if self.single_target_click("./pic/mirror/mirror1/way/Confirm.png","SecondConfirm"):
                result = True
        return result




    def mirror1Cope(self): 
        '''处理镜牢1交互的各种情况'''
        result = False
        self.cap_win()
        if(self.is_find("./pic/team/Announcer.png", "Announcer")):
            self.mirror1PrepareBattle()
            self.mirror1BattlePart()
            result = True
        elif(self.is_find("./pic/battle/WinRate.png", "battleSign")):
            self.mirror1BattlePart()
            result = True
        elif(self.is_find("./pic/event/Skip.png", "Skip")):
            self.eventPart()
            result = True
        elif(self.is_find("./pic/mirror/mirror1/way/Confirm.png", "EGOGift")):
            self.single_target_click("./pic/mirror/mirror1/way/Confirm.png", "EGOGift", 0, 0, 1, 2)
            result = True
        elif(self.single_target_click("./pic/mirror/mirror1/ego/egoGift.png", "ChooseEgoGift")):
            self.cap_win()
            self.single_target_click("./pic/mirror/mirror1/ego/SelectEGOGift.png", "SelectEGOGift", 0, 0, 6)
            result = True
        elif(self.single_target_click("./pic/mirror/mirror1/way/Enter.png", "Enter", 0, 0, 2)):
            result = True
        elif(self.is_find("./pic/Wait.png", "Wait Sign")):
            self.myWait()
            result = True
        
            
        return result


    #根据已选人数和队伍可容纳人数做情况分类
    #检测3/3；4/4；5/5最好就一个标准，能省不少时间
    def mirror1JudTeamCondition(self):
        resultCondition = -1
        if(self.is_find("./pic/team/FullTeam55.png", "FullTeam5/5", 0.94) or\
            self.is_find("./pic/team/FullTeam44.png", "FullTeam4/4", 0.94) or\
            self.is_find("./pic/team/FullTeam33.png", "FullTeam3/3", 0.94)):
            resultCondition = 0
        elif(self.is_find("./pic/team/EmptyTeam03.png", "EmptyTeam0/3", 0.94)):
            resultCondition = 1
        elif(self.is_find("./pic/team/EmptyTeam04.png", "EmptyTeam0/4", 0.94) or\
        self.is_find("./pic/team/NotFullTeam34.png", "NotFullTeam3/4", 0.94)):
            resultCondition = 2
        elif(self.is_find("./pic/team/EmptyTeam05.png", "EmptyTeam0/5", 0.94) or\
        self.is_find("./pic/team/NotFullTeam45.png", "NotFullTeam4/5", 0.94)):
            resultCondition = 3
        return resultCondition


    #满队标准
    def mirror1JudFullTeam(self,condition):
        result = False
        if(condition == 0):
            result = True
        elif(condition == 1):
            if(self.is_find("./pic/team/FullTeam33.png", "FullTeam3/3", 0.94)):
                result = True
        elif(condition == 2):
            if(self.is_find("./pic/team/FullTeam44.png", "FullTeam4/4", 0.94)):
                result = True
        elif(condition == 3):
            if(self.is_find("./pic/team/FullTeam55.png", "FullTeam5/5", 0.94)):
                result = True
        else:
            if(self.is_find("./pic/team/FullTeam55.png", "FullTeam5/5", 0.94) or\
                self.is_find("./pic/team/FullTeam44.png", "FullTeam4/4", 0.94) or\
                self.is_find("./pic/team/FullTeam33.png", "FullTeam3/3", 0.94)):
                result = True
        return result




    @checkAndExit
    @beginAndFinishLog
    def mirror1PrepareBattle(self):
        '''镜牢1在战斗前的组队操作'''
        i = 1
        global notFullFlag 
        countFlag = 0
        condition = self.mirror1JudTeamCondition()
        while(not self.mirror1JudFullTeam(condition) and (notFullFlag == 0)):
            #i的归零
            if(i > 12):
                i = 1
                countFlag += 1
                if(countFlag > 1):
                    myLog("warning","Can't make team full")
                    notFullFlag = 1
                    break
            self.cap_win()
            if(i < 7):
                addX = i * 140
                addY = 0
            else:
                addX = (i - 6) * 140
                addY = 200

            self.single_target_click("./pic/team/Announcer.png", "Member", addX, addY + 100, 0.2)
            self.cap_win()
            i += 1

        #即使选不到满人，也要尽可能多选人
        if(notFullFlag == 1 and\
        (self.is_find("./pic/team/EmptyTeam03.png", "EmptyTeam0/3", 0.94)or\
            self.is_find("./pic/team/EmptyTeam04.png", "EmptyTeam0/4", 0.94)or\
            self.is_find("./pic/team/EmptyTeam05.png", "EmptyTeam0/5", 0.94)or\
            self.is_find("./pic/team/NotFullTeam15.png", "NotFullTeam1/5", 0.94))
            ):
            for i in range(1,13):
                self.cap_win()
                if(i < 7):
                    addX = i * 140
                    addY = 0
                else:
                    addX = (i - 6) * 140
                    addY = 200

                self.single_target_click("./pic/team/Announcer.png", "Member", addX, addY, 0.2)



        self.single_target_click("./pic/team/Announcer.png", "ToBattle", 1000, 400, 5)
        self.cap_win()
        if(self.is_find("./pic/Wait.png", "Wait Sign")):
                self.myWait()


    @checkAndExit
    @beginAndFinishLog
    def mirror1BattlePart(self):
        '''镜牢战斗处理'''
        '''self.cap_win()
        loopCount = 0
        while(True):
            self.cap_win()
            condition = False
            if (self.is_find("./pic/battle/WinRate.png", "WinRate")):
                self.cap_win()
                if (self.is_find("./pic/battle/Start.png", "StartBattle")):
                    condition = True
            elif(self.is_find("./pic/battle/battlePause.png", "Fighting Sign")):
                mySleep(2)
                condition = True
            elif(self.single_target_click("./pic/battle/trianglePause.png", "Continue Fight!")):
                condition = True    
            elif(self.is_find("./pic/event/Skip.png", "Skip")):
                self.eventPart()
                condition = True
            elif(self.is_find("./pic/Wait.png", "Wait Sign")):
                self.myWait()
                condition = True
            if(not condition):
                loopCount += 1
                if(loopCount > 2):
                    break
                elif(loopCount > 0):
                    if (self.is_find("./pic/battle/Gear.png", "FinishingBattle")):
                        condition = True
                        loopCount = 0
            else:
                loopCount = 0
            mySleep(0.9)'''
        self.allWinRateBattle()




    @checkAndExit
    @beginAndFinishLog
    def mirror1SinCoreFindWay(self):
        '''镜牢1单进程寻路'''
        
        result = False

        # 滚动滑轮以保持视图大小不变
        littleUpScroll()

        self.single_target_click("./pic/mirror/mirror1/way/Self.png", "Self")
        self.cap_win()
        if(self.single_target_click("./pic/mirror/mirror1/way/Enter.png", "Enter", 0, 0, 2)):
            result = True
            return result
        self.mirror1SinCoreQuesionMark()
        if(self.single_target_click("./pic/mirror/mirror1/way/Enter.png", "Enter", 0, 0, 2)):
            result = True
            return result
        self.mirror1SinCoreChair()
        if(self.single_target_click("./pic/mirror/mirror1/way/Enter.png", "Enter", 0, 0, 2)):
            result = True
            return result
        self.mirror1SinCoreBus()
        if(self.single_target_click("./pic/mirror/mirror1/way/Enter.png", "Enter", 0, 0, 2)):
            result = True
            return result
        self.mirror1SinCoreFight()
        if(self.single_target_click("./pic/mirror/mirror1/way/Enter.png", "Enter", 0, 0, 2)):
            result = True
            return result
        self.mirror1SinCoreBoss()
        if(self.single_target_click("./pic/mirror/mirror1/way/Enter.png", "Enter", 0, 0, 2)):
            result = True
            return result
        self.mirror1SinCoreBattle()
        if(self.single_target_click("./pic/mirror/mirror1/way/Enter.png", "Enter", 0, 0, 2)):
            result = True
            return result
        self.mirror1SinCoreEncounter()
        if(self.single_target_click("./pic/mirror/mirror1/way/Enter.png", "Enter", 0, 0, 2)):
            result = True
            return result
        
        
        return result





    #巴士部分
    def mirror1SinCoreBus(self):
        '''镜牢1单进程找巴士'''
        if self.single_target_click("./pic/mirror/mirror1/way/Bus/BusM.png", "BusMiddle"):
            self.cap_win()
            if self.is_find("./pic/mirror/mirror1/way/Enter.png", "Enter"):
                return
        if self.is_find("./pic/mirror/mirror1/way/Enter.png", "Enter"):
            return

        if self.single_target_click("./pic/mirror/mirror1/way/Bus/BusRH.png", "BusRightHigh"):
            self.cap_win()
            if self.is_find("./pic/mirror/mirror1/way/Enter.png", "Enter"):
                return

        if self.single_target_click("./pic/mirror/mirror1/way/Bus/BusRM.png", "BusRightMiddle"):
            self.cap_win()
            if self.is_find("./pic/mirror/mirror1/way/Enter.png", "Enter"):
                return
        
        if self.single_target_click("./pic/mirror/mirror1/way/Bus/BusRL.png", "BusRightLow", 0, -10):
            self.cap_win()
            if self.is_find("./pic/mirror/mirror1/way/Enter.png", "Enter"):
                return

        
        if self.single_target_click("./pic/mirror/mirror1/way/Bus/BusLH.png", "BusLeftHigh"):
            self.cap_win()
            if self.is_find("./pic/mirror/mirror1/way/Enter.png", "Enter"):
                return
        

        if self.single_target_click("./pic/mirror/mirror1/way/Bus/BusLM.png", "BusLeftMiddle"):
            self.cap_win()
            if self.is_find("./pic/mirror/mirror1/way/Enter.png", "Enter"):
                return
        
        if self.single_target_click("./pic/mirror/mirror1/way/Bus/BusLL.png", "BusLeftLow", 0, -10):
            self.cap_win()
            if self.is_find("./pic/mirror/mirror1/way/Enter.png", "Enter"):
                return
            


    #椅子部分
    def mirror1SinCoreChair(self):
        '''镜牢1单进程找椅子'''
        if self.single_target_click("./pic/mirror/mirror1/way/Chair/ChairM.png", "ChairMiddle"):
            self.cap_win()
            if self.is_find("./pic/mirror/mirror1/way/Enter.png", "Enter"):
                return
        

        if self.single_target_click("./pic/mirror/mirror1/way/Chair/ChairRH.png", "ChairRightHigh"):
            self.cap_win()
            if self.is_find("./pic/mirror/mirror1/way/Enter.png", "Enter"):
                return

        if self.single_target_click("./pic/mirror/mirror1/way/Chair/ChairRM.png", "ChairRightMiddle"):
            self.cap_win()
            if self.is_find("./pic/mirror/mirror1/way/Enter.png", "Enter"):
                return
        
        if self.single_target_click("./pic/mirror/mirror1/way/Chair/ChairRL.png", "ChairRightLow", 0, -10):
            self.cap_win()
            if self.is_find("./pic/mirror/mirror1/way/Enter.png", "Enter"):
                return
        
        if self.single_target_click("./pic/mirror/mirror1/way/Chair/ChairLH.png", "ChairLeftHigh"):
            self.cap_win()
            if self.is_find("./pic/mirror/mirror1/way/Enter.png", "Enter"):
                return

        if self.single_target_click("./pic/mirror/mirror1/way/Chair/ChairLM.png", "ChairLeftMiddle"):
            self.cap_win()
            if self.is_find("./pic/mirror/mirror1/way/Enter.png", "Enter"):
                return

        if self.single_target_click("./pic/mirror/mirror1/way/Chair/ChairLL.png", "ChairLeftLow", 0, -10):
            self.cap_win()
            if self.is_find("./pic/mirror/mirror1/way/Enter.png", "Enter"):
                return


    #异想体部分
    def mirror1SinCoreEncounter(self):
        '''镜牢1单进程找异想体'''
        if self.single_target_click("./pic/mirror/mirror1/way/Encounter/EncounterM.png", "EncounterMiddle"):
            self.cap_win()
            if self.is_find("./pic/mirror/mirror1/way/Enter.png", "Enter"):
                return
        
        if self.single_target_click("./pic/mirror/mirror1/way/Encounter/EncounterRH.png", "EncounterRightHigh"):
            self.cap_win()
            if self.is_find("./pic/mirror/mirror1/way/Enter.png", "Enter"):
                return

        if self.single_target_click("./pic/mirror/mirror1/way/Encounter/EncounterRM.png", "EncounterRightMiddle"):
            self.cap_win()
            if self.is_find("./pic/mirror/mirror1/way/Enter.png", "Enter"):
                return

        if self.single_target_click("./pic/mirror/mirror1/way/Encounter/EncounterRL.png", "EncounterRightLow", 0, -10):
            self.cap_win()
            if self.is_find("./pic/mirror/mirror1/way/Enter.png", "Enter"):
                return

        if self.single_target_click("./pic/mirror/mirror1/way/Encounter/EncounterLH.png", "EncounterLeftHigh"):
            self.cap_win()
            if self.is_find("./pic/mirror/mirror1/way/Enter.png", "Enter"):
                return
        

        if self.single_target_click("./pic/mirror/mirror1/way/Encounter/EncounterLM.png", "EncounterLeftMiddle"):
            self.cap_win()
            if self.is_find("./pic/mirror/mirror1/way/Enter.png", "Enter"):
                return
        
        
        if self.single_target_click("./pic/mirror/mirror1/way/Encounter/EncounterLL.png", "EncounterLeftLow", 0, -10):
            self.cap_win()
            if self.is_find("./pic/mirror/mirror1/way/Enter.png", "Enter"):
                return


    #困难战斗部分
    def mirror1SinCoreBattle(self):
        '''镜牢1单进程找困难战斗'''
        if self.single_target_click("./pic/mirror/mirror1/way/Battle/BattleM.png", "BattleMiddle"):
            self.cap_win()
            if self.is_find("./pic/mirror/mirror1/way/Enter.png", "Enter"):
                return

        if self.single_target_click("./pic/mirror/mirror1/way/Battle/BattleRH.png", "BattleRightHigh"):
            self.cap_win()
            if self.is_find("./pic/mirror/mirror1/way/Enter.png", "Enter"):
                return
        
        if self.single_target_click("./pic/mirror/mirror1/way/Battle/BattleRM.png", "BattleRightMiddle"):
            self.cap_win()
            if self.is_find("./pic/mirror/mirror1/way/Enter.png", "Enter"):
                return
        
        if self.single_target_click("./pic/mirror/mirror1/way/Battle/BattleRL.png", "BattleRightLow", 0, -10):
            self.cap_win()
            if self.is_find("./pic/mirror/mirror1/way/Enter.png", "Enter"):
                return
        
        if self.single_target_click("./pic/mirror/mirror1/way/Battle/BattleLH.png", "BattleLeftHigh"):
            self.cap_win()
            if self.is_find("./pic/mirror/mirror1/way/Enter.png", "Enter"):
                return
        
        if self.single_target_click("./pic/mirror/mirror1/way/Battle/BattleLM.png", "BattleLeftMiddle"):
            self.cap_win()
            if self.is_find("./pic/mirror/mirror1/way/Enter.png", "Enter"):
                return
            
        if self.single_target_click("./pic/mirror/mirror1/way/Battle/BattleLL.png", "BattleLeftLow", 0, -10):
            self.cap_win()
            if self.is_find("./pic/mirror/mirror1/way/Enter.png", "Enter"):
                return

        

    #首领部分
    def mirror1SinCoreBoss(self):
        '''镜牢1单进程找首领'''
        if self.single_target_click("./pic/mirror/mirror1/way/Boss/BossM.png", "BossMiddle"):
            self.cap_win()
            if self.is_find("./pic/mirror/mirror1/way/Enter.png", "Enter"):
                return


        if self.single_target_click("./pic/mirror/mirror1/way/Boss/BossRH.png", "BossRightHigh"):
            self.cap_win()
            if self.is_find("./pic/mirror/mirror1/way/Enter.png", "Enter"):
                return

        if self.single_target_click("./pic/mirror/mirror1/way/Boss/BossRM.png", "BossRightMiddle"):
            self.cap_win()
            if self.is_find("./pic/mirror/mirror1/way/Enter.png", "Enter"):
                return

        if self.single_target_click("./pic/mirror/mirror1/way/Boss/BossRL.png", "BossRightLow", 0, -10):
            self.cap_win()
            if self.is_find("./pic/mirror/mirror1/way/Enter.png", "Enter"):
                return


        if self.single_target_click("./pic/mirror/mirror1/way/Boss/BossLH.png", "BossLeftHigh"):
            self.cap_win()
            if self.is_find("./pic/mirror/mirror1/way/Enter.png", "Enter"):
                return

        if self.single_target_click("./pic/mirror/mirror1/way/Boss/BossLM.png", "BossLeftMiddle"):
            self.cap_win()
            if self.is_find("./pic/mirror/mirror1/way/Enter.png", "Enter"):
                return
        
        if self.single_target_click("./pic/mirror/mirror1/way/Boss/BossLL.png", "BossLeftLow", 0, -10):
            self.cap_win()
            if self.is_find("./pic/mirror/mirror1/way/Enter.png", "Enter"):
                return

        

    #问号事件部分
    def mirror1SinCoreQuesionMark(self):
        '''镜牢1单进程找问号'''
        if self.single_target_click("./pic/mirror/mirror1/way/QuesionMark/QuesionMarkM.png", "QuesionMarkMiddle"):
            self.cap_win()
            if self.is_find("./pic/mirror/mirror1/way/Enter.png", "Enter"):
                return
        
        if self.single_target_click("./pic/mirror/mirror1/way/QuesionMark/QuesionMarkRH.png", "QuesionMarkRightHigh"):
            self.cap_win()
            if self.is_find("./pic/mirror/mirror1/way/Enter.png", "Enter"):
                return

        if self.single_target_click("./pic/mirror/mirror1/way/QuesionMark/QuesionMarkRM.png", "QuesionMarkRightMiddle"):
            self.cap_win()
            if self.is_find("./pic/mirror/mirror1/way/Enter.png", "Enter"):
                return

        if self.single_target_click("./pic/mirror/mirror1/way/QuesionMark/QuesionMarkRL.png", "QuesionMarkRightLow", 0, -10):
            self.cap_win()
            if self.is_find("./pic/mirror/mirror1/way/Enter.png", "Enter"):
                return

        if self.single_target_click("./pic/mirror/mirror1/way/QuesionMark/QuesionMarkLH.png", "QuesionMarkLeftHigh"):
            self.cap_win()
            if self.is_find("./pic/mirror/mirror1/way/Enter.png", "Enter"):
                return

        if self.single_target_click("./pic/mirror/mirror1/way/QuesionMark/QuesionMarkLM.png", "QuesionMarkLeftMiddle"):
            self.cap_win()
            if self.is_find("./pic/mirror/mirror1/way/Enter.png", "Enter"):
                return

        if self.single_target_click("./pic/mirror/mirror1/way/QuesionMark/QuesionMarkLL.png", "QuesionMarkLeftLow", 0, -10):
            self.cap_win()
            if self.is_find("./pic/mirror/mirror1/way/Enter.png", "Enter"):
                return


    #战斗部分
    def mirror1SinCoreFight(self):
        '''镜牢1单进程找普通战斗'''
        if self.single_target_click("./pic/mirror/mirror1/way/Fight/FightM.png", "FightMiddle"):
            self.cap_win()
            if self.is_find("./pic/mirror/mirror1/way/Enter.png", "Enter"):
                return

        if self.single_target_click("./pic/mirror/mirror1/way/Fight/FightRH.png", "FightRightHigh"):
            self.cap_win()
            if self.is_find("./pic/mirror/mirror1/way/Enter.png", "Enter"):
                return

        if self.single_target_click("./pic/mirror/mirror1/way/Fight/FightRM.png", "FightRightMiddle"):
            self.cap_win()
            if self.is_find("./pic/mirror/mirror1/way/Enter.png", "Enter"):
                return

        if self.single_target_click("./pic/mirror/mirror1/way/Fight/FightRL.png", "FightRightLow", 0, -10):
            self.cap_win()
            if self.is_find("./pic/mirror/mirror1/way/Enter.png", "Enter"):
                return

        if self.single_target_click("./pic/mirror/mirror1/way/Fight/FightLH.png", "FightLeftHigh"):
            self.cap_win()
            if self.is_find("./pic/mirror/mirror1/way/Enter.png", "Enter"):
                return

        if self.single_target_click("./pic/mirror/mirror1/way/Fight/FightLM.png", "FightLeftMiddle"):
            self.cap_win()
            if self.is_find("./pic/mirror/mirror1/way/Enter.png", "Enter"):
                return

        if self.single_target_click("./pic/mirror/mirror1/way/Fight/FightLL.png", "FightLeftLow", 0, -10):
            self.cap_win()
            if self.is_find("./pic/mirror/mirror1/way/Enter.png", "Enter"):
                return
        
