# -*- coding: utf-8 -*-
'''
* Author: LuYaoQi
* Time  : 2023/9/18 17:48
* File  : classMir.py   
* Project   :LixAssistantLimbusCompany
* Function  :将镜牢相关函数包装为类          
'''



from src.common import getPic, autoFindOrClick as afc
from src.script.myWait import myWait
from src.script.event import eventPart
from src.script.classScript import _mainScript,checkAndExit
from src.log.myLog import myLog, beginAndFinishLog
from src.common.myTime import myTimeSleep
from src.error.myError import unexpectNumError,noSavedPresetsError, mirrorInProgressError, previousClaimRewardError
from src.common.mouseScroll import littleUpScroll

notFullFlag = 0


class _Mirror(_mainScript):
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
        else:
            raise unexpectNumError("镜牢选择数字未设置")


    def getMirrorFinishCount(self):
        '''返回镜牢完成次数'''
        return self.mirrorFinishCount


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
            # myTimeSleep(1)
    

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
            # myTimeSleep(2)





class _MirrorOfMirrors():
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
        getPic.winCap()
        if(afc.autoFind("./pic/mirror/mirror2/way/mirror2MapSign.png", "mirror2MapSign") and\
            (afc.autoFind("./pic/mirror/mirror2/way/BigSelf.png", "BigSelf", 0.8) or\
            afc.autoFind("./pic/mirror/mirror2/way/Self.png", "Self", 0.8))):
            self.noWayFlag = self.mirror2SinCoreFindWay()

        result = self.mirror2Cope()
        
        return result


    
    def mirror2Prize(self):
        '''镜牢2获取奖励的流程'''
        result = False
        getPic.winCap()
        afc.autoSinClick("./pic/battle/confirm.png", "Final_Victory")
        getPic.winCap()
        afc.autoSinClick("./pic/mirror/mirror2/ClaimRewards.png","ClaimRewards", 0, 0, 0.7, 1, 0.7)
        getPic.winCap()
        afc.autoSinClick("./pic/mirror/mirror2/Receive.png","Receive")
        getPic.winCap()
        if afc.autoSinClick("./pic/mirror/mirror2/whiteConfirm.png","FirstConfirm"):
            getPic.winCap()
            if afc.autoSinClick("./pic/mirror/mirror2/way/Confirm.png","SecondConfirm"):
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
        if(afc.autoFind("./pic/mirror/mirror2/way/mirror2MapSign.png", "mirror2MapSign")):
            return
        getPic.winCap()
        afc.autoSinClick("./pic/initMenu/drive.png", "Drive")
        getPic.winCap()
        afc.autoSinClick("./pic/mirror/mirror2/MirrorDungeons.png", "MirrorDungeons", 0, 0, 1, 1, 0.9)
        getPic.winCap()
        if(afc.autoFind("./pic/mirror/previousClaimReward.png", "previousClaimReward")):
            raise previousClaimRewardError("有上周的镜牢奖励未领取")
        afc.autoSinClick("./pic/mirror/mirror2/Mirror2Normal.png", "Mirror2Normal")
        getPic.winCap()
        if(afc.autoFind("./pic/mirror/MirrorInProgress.png", "MirrorInProgress")):
            raise mirrorInProgressError("有其他镜牢未结束")
        if(afc.autoSinClick("./pic/mirror/mirror2/Enter.png", "Enter", 0, 0, 5) or\
            afc.autoSinClick("./pic/mirror/mirror2/Resume.png", "Resume", 0, 0, 5)):
            getPic.winCap()
            afc.autoSinClick("./pic/mirror/mirror2/ego/egoGift.png", "egoGift")
            getPic.winCap()
            afc.autoSinClick("./pic/mirror/mirror2/ego/SelectEGOGift.png", "SelectEGOGift")
            getPic.winCap()
            if afc.autoSinClick("./pic/mirror/mirror2/Preset.png", "Preset"):
                getPic.winCap()
                if(afc.autoFind("./pic/error/noSavedPreset.png", "noPreset")):
                    raise noSavedPresetsError("没有预选队伍")
                self.mirror2ChoosePreset()
            afc.autoSinClick("./pic/mirror/mirror2/blackConfirm.png", "Confirm", 0, 0, 3)
            getPic.winCap()
            afc.autoSinClick("./pic/mirror/mirror2/BuyCoin.png", "BuyCoin", 0, 0, 8)
        if(afc.autoFind("./pic/Wait.png", "Wait Sign")):
            myWait()


    def mirror2ChoosePreset(self):
        '''镜牢2预选人的流程'''
        i = 1
        countFlag = 0
        while(not afc.autoFind("./pic/team/FullTeam77.png", "7/7PresetFullSign")):
            #i的归零
            if(i > 12):
                i = 1
                countFlag += 1
                if(countFlag > 1):
                    from src.log.myLog import myLog
                    myLog("warning","Preset Fail")
                    break
            getPic.winCap()
            if(i < 7):
                addX = i * 140
                addY = 0
            else:
                addX = (i - 6) * 140
                addY = 200

            afc.autoSinClick("./pic/team/Announcer.png", "Member", addX, addY + 100, 0.2)
            getPic.winCap()
            i += 1

        afc.autoSinClick("./pic/team/Announcer.png", "Confirm", 1000, 400, 3)
        



    def mirror2Cope(self): 
        '''处理镜牢2交互的各种情况'''
        result = False
        getPic.winCap()
        if(afc.autoFind("./pic/team/Announcer.png", "Announcer")):
            self.mirror2PrepareBattle()
            self.mirror2BattlePart()
            result = True
        elif(afc.autoFind("./pic/battle/WinRate.png", "battleSign")):
            self.mirror2BattlePart()
            result = True
        elif(afc.autoFind("./pic/event/Skip.png", "Skip")):
            eventPart()
            result = True
        elif(afc.autoFind("./pic/mirror/mirror2/way/Confirm.png", "EGOGift")):
            afc.autoSinClick("./pic/mirror/mirror2/way/Confirm.png", "EGOGift", 0, 0, 1, 2)
            result = True
        elif(afc.autoSinClick("./pic/mirror/mirror2/ego/egoGift.png", "ChooseEgoGift")):
            getPic.winCap()
            afc.autoSinClick("./pic/mirror/mirror2/ego/SelectEGOGift.png", "SelectEGOGift", 0, 0, 6)
            result = True
        elif(afc.autoSinClick("./pic/mirror/mirror2/way/Enter.png", "Enter", 0, 0, 2)):
            result = True
        elif(afc.autoFind("./pic/Wait.png", "Wait Sign")):
            myWait()
            result = True
            
        return result
            

    #根据已选人数和队伍可容纳人数做情况分类
    #检测5/5；6/6；7/7最好就一个标准，能省不少时间
    def mirror2JudTeamCondition(self):
        '''判断当前队伍状况'''
        resultCondition = -1
        if(afc.autoFind("./pic/team/FullTeam77.png", "FullTeam7/7", 0.94) or\
            afc.autoFind("./pic/team/FullTeam66.png", "FullTeam6/6", 0.94) or\
            afc.autoFind("./pic/team/FullTeam55.png", "FullTeam5/5", 0.94)):
            resultCondition = 0
        elif(afc.autoFind("./pic/team/EmptyTeam05.png", "EmptyTeam0/5", 0.94)):
            resultCondition = 1
        elif(afc.autoFind("./pic/team/EmptyTeam06.png", "EmptyTeam0/6", 0.94) or\
        afc.autoFind("./pic/team/NotFullTeam56.png", "NotFullTeam5/6", 0.94)):
            resultCondition = 2
        elif(afc.autoFind("./pic/team/EmptyTeam07.png", "EmptyTeam0/7", 0.94) or\
        afc.autoFind("./pic/team/NotFullTeam67.png", "NotFullTeam6/7", 0.94)):
            resultCondition = 3
        return resultCondition


    #满队标准
    def mirror2JudFullTeam(self,condition):
        '''判断队伍是否人满'''
        result = False
        if(condition == 0):
            result = True
        elif(condition == 1):
            if(afc.autoFind("./pic/team/FullTeam55.png", "FullTeam5/5", 0.94)):
                result = True
        elif(condition == 2):
            if(afc.autoFind("./pic/team/FullTeam66.png", "FullTeam6/6", 0.94)):
                result = True
        elif(condition == 3):
            if(afc.autoFind("./pic/team/FullTeam77.png", "FullTeam7/7", 0.94)):
                result = True
        else:
            if(afc.autoFind("./pic/team/FullTeam77.png", "FullTeam7/7", 0.94) or\
                afc.autoFind("./pic/team/FullTeam66.png", "FullTeam6/6", 0.94) or\
                afc.autoFind("./pic/team/FullTeam55.png", "FullTeam5/5", 0.94)):
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
                    from src.log.myLog import beginAndFinishLog, myLog
                    myLog("warning","Can't make team full")
                    notFullFlag = 1
                    break
            getPic.winCap()
            if(i < 7):
                addX = i * 140
                addY = 0
            else:
                addX = (i - 6) * 140
                addY = 200

            afc.autoSinClick("./pic/team/Announcer.png", "Member", addX, addY + 100, 0.2)
            getPic.winCap()
            i += 1

        #即使选不到满人，也要尽可能多选人
        if(notFullFlag == 1 and\
        (afc.autoFind("./pic/team/EmptyTeam05.png", "EmptyTeam0/5", 0.94)or\
            afc.autoFind("./pic/team/EmptyTeam06.png", "EmptyTeam0/6", 0.94)or\
            afc.autoFind("./pic/team/EmptyTeam07.png", "EmptyTeam0/7", 0.94)or\
            afc.autoFind("./pic/team/NotFullTeam15.png", "NotFullTeam1/5", 0.94)or\
            afc.autoFind("./pic/team/NotFullTeam16.png", "NotFullTeam1/6", 0.94)or\
            afc.autoFind("./pic/team/NotFullTeam17.png", "NotFullTeam1/7", 0.94))
            ):
            for i in range(1,13):
                getPic.winCap()
                if(i < 7):
                    addX = i * 140
                    addY = 0
                else:
                    addX = (i - 6) * 140
                    addY = 200

                afc.autoSinClick("./pic/team/Announcer.png", "Member", addX, addY + 100, 0.2)



        afc.autoSinClick("./pic/team/Announcer.png", "ToBattle", 1000, 400, 5)
        getPic.winCap()
        if(afc.autoFind("./pic/Wait.png", "Wait Sign")):
                myWait()


    @checkAndExit
    @beginAndFinishLog
    def mirror2BattlePart(self):
        '''镜牢战斗处理'''
        getPic.winCap()
        loopCount = 0
        while(True):
            getPic.winCap()
            condition = False
            if (afc.autoSinClick("./pic/battle/WinRate.png", "WinRate")):
                getPic.winCap()
                if (afc.autoSinClick("./pic/battle/Start.png", "Start")):
                    condition = True
            elif(afc.autoFind("./pic/battle/battlePause.png", "Fighting Sign")):
                myTimeSleep(2)
                condition = True
            elif(afc.autoSinClick("./pic/battle/trianglePause.png", "Continue Fight!")):
                condition = True    
            elif(afc.autoFind("./pic/event/Skip.png", "Skip")):
                eventPart()
                condition = True
            elif(afc.autoFind("./pic/Wait.png", "Wait Sign")):
                myWait()
                condition = True
            if(not condition):
                loopCount += 1
                if(loopCount > 2):
                    break
                elif(loopCount > 0):
                    if (afc.autoFind("./pic/battle/Gear.png", "FinishingBattle")):
                        condition = True
                        loopCount = 0
            else:
                loopCount = 0
            myTimeSleep(0.9)


    @checkAndExit
    @beginAndFinishLog
    def mirror2SinCoreFindWay(self):
        '''镜牢2单进程寻路流程'''
        result = False

        # 滚动滑轮以保持视图大小不变
        littleUpScroll()

        afc.autoSinClick("./pic/mirror/mirror2/way/Self.png", "Self")
        getPic.winCap()
        if(afc.autoSinClick("./pic/mirror/mirror2/way/Enter.png", "Enter", 0, 0, 2)):
            result = True
            return result
        self.mirror2SinCoreQuesionMark()
        if(afc.autoSinClick("./pic/mirror/mirror2/way/Enter.png", "Enter", 0, 0, 2)):
            result = True
            return result
        self.mirror2SinCoreChair()
        if(afc.autoSinClick("./pic/mirror/mirror2/way/Enter.png", "Enter", 0, 0, 2)):
            result = True
            return result
        self.mirror2SinCoreBus()
        if(afc.autoSinClick("./pic/mirror/mirror2/way/Enter.png", "Enter", 0, 0, 2)):
            result = True
            return result
        self.mirror2SinCoreFight()
        if(afc.autoSinClick("./pic/mirror/mirror2/way/Enter.png", "Enter", 0, 0, 2)):
            result = True
            return result
        self.mirror2SinCoreBoss()
        if(afc.autoSinClick("./pic/mirror/mirror2/way/Enter.png", "Enter", 0, 0, 2)):
            result = True
            return result
        self.mirror2SinCoreBattle()
        if(afc.autoSinClick("./pic/mirror/mirror2/way/Enter.png", "Enter", 0, 0, 2)):
            result = True
            return result
        self.mirror2SinCoreEncounter()
        if(afc.autoSinClick("./pic/mirror/mirror2/way/Enter.png", "Enter", 0, 0, 2)):
            result = True
            return result
        
        
        return result


    #椅子部分
    def mirror2SinCoreChair(self):
        '''镜牢2单进程找椅子'''
        if afc.autoSinClick("./pic/mirror/mirror2/way/Chair/ChairM.png", "ChairMiddle"):
            getPic.winCap()
            if afc.autoFind("./pic/mirror/mirror2/way/Enter.png", "Enter"):
                return
        

        if afc.autoSinClick("./pic/mirror/mirror2/way/Chair/ChairRH.png", "ChairRightHigh"):
            getPic.winCap()
            if afc.autoFind("./pic/mirror/mirror2/way/Enter.png", "Enter"):
                return

        if afc.autoSinClick("./pic/mirror/mirror2/way/Chair/ChairRM.png", "ChairRightMiddle"):
            getPic.winCap()
            if afc.autoFind("./pic/mirror/mirror2/way/Enter.png", "Enter"):
                return
        
        if afc.autoSinClick("./pic/mirror/mirror2/way/Chair/ChairRL.png", "ChairRightLow"):
            getPic.winCap()
            if afc.autoFind("./pic/mirror/mirror2/way/Enter.png", "Enter"):
                return
        
        if afc.autoSinClick("./pic/mirror/mirror2/way/Chair/ChairLH.png", "ChairLeftHigh"):
            getPic.winCap()
            if afc.autoFind("./pic/mirror/mirror2/way/Enter.png", "Enter"):
                return

        if afc.autoSinClick("./pic/mirror/mirror2/way/Chair/ChairLM.png", "ChairLeftMiddle"):
            getPic.winCap()
            if afc.autoFind("./pic/mirror/mirror2/way/Enter.png", "Enter"):
                return

        if afc.autoSinClick("./pic/mirror/mirror2/way/Chair/ChairLL.png", "ChairLeftLow"):
            getPic.winCap()
            if afc.autoFind("./pic/mirror/mirror2/way/Enter.png", "Enter"):
                return

    #异想体部分
    def mirror2SinCoreEncounter(self):
        '''镜牢2单进程找异想体'''
        if afc.autoSinClick("./pic/mirror/mirror2/way/Encounter/EncounterM.png", "EncounterMiddle"):
            getPic.winCap()
            if afc.autoFind("./pic/mirror/mirror2/way/Enter.png", "Enter"):
                return
        
        if afc.autoSinClick("./pic/mirror/mirror2/way/Encounter/EncounterRH.png", "EncounterRightHigh"):
            getPic.winCap()
            if afc.autoFind("./pic/mirror/mirror2/way/Enter.png", "Enter"):
                return

        if afc.autoSinClick("./pic/mirror/mirror2/way/Encounter/EncounterRM.png", "EncounterRightMiddle"):
            getPic.winCap()
            if afc.autoFind("./pic/mirror/mirror2/way/Enter.png", "Enter"):
                return

        if afc.autoSinClick("./pic/mirror/mirror2/way/Encounter/EncounterRL.png", "EncounterRightLow"):
            getPic.winCap()
            if afc.autoFind("./pic/mirror/mirror2/way/Enter.png", "Enter"):
                return

        if afc.autoSinClick("./pic/mirror/mirror2/way/Encounter/EncounterLH.png", "EncounterLeftHigh"):
            getPic.winCap()
            if afc.autoFind("./pic/mirror/mirror2/way/Enter.png", "Enter"):
                return
        

        if afc.autoSinClick("./pic/mirror/mirror2/way/Encounter/EncounterLM.png", "EncounterLeftMiddle"):
            getPic.winCap()
            if afc.autoFind("./pic/mirror/mirror2/way/Enter.png", "Enter"):
                return
        
        
        if afc.autoSinClick("./pic/mirror/mirror2/way/Encounter/EncounterLL.png", "EncounterLeftLow"):
            getPic.winCap()
            if afc.autoFind("./pic/mirror/mirror2/way/Enter.png", "Enter"):
                return


    #巴士部分
    def mirror2SinCoreBus(self):
        '''镜牢2单进程找巴士'''
        if afc.autoSinClick("./pic/mirror/mirror2/way/Bus/BusM.png", "BusMiddle"):
            getPic.winCap()
            if afc.autoFind("./pic/mirror/mirror2/way/Enter.png", "Enter"):
                return
        if afc.autoFind("./pic/mirror/mirror2/way/Enter.png", "Enter"):
            return

        if afc.autoSinClick("./pic/mirror/mirror2/way/Bus/BusRH.png", "BusRightHigh"):
            getPic.winCap()
            if afc.autoFind("./pic/mirror/mirror2/way/Enter.png", "Enter"):
                return

        if afc.autoSinClick("./pic/mirror/mirror2/way/Bus/BusRM.png", "BusRightMiddle"):
            getPic.winCap()
            if afc.autoFind("./pic/mirror/mirror2/way/Enter.png", "Enter"):
                return
        
        if afc.autoSinClick("./pic/mirror/mirror2/way/Bus/BusRL.png", "BusRightLow"):
            getPic.winCap()
            if afc.autoFind("./pic/mirror/mirror2/way/Enter.png", "Enter"):
                return

        
        if afc.autoSinClick("./pic/mirror/mirror2/way/Bus/BusLH.png", "BusLeftHigh"):
            getPic.winCap()
            if afc.autoFind("./pic/mirror/mirror2/way/Enter.png", "Enter"):
                return
        

        if afc.autoSinClick("./pic/mirror/mirror2/way/Bus/BusLM.png", "BusLeftMiddle"):
            getPic.winCap()
            if afc.autoFind("./pic/mirror/mirror2/way/Enter.png", "Enter"):
                return
        
        if afc.autoSinClick("./pic/mirror/mirror2/way/Bus/BusLL.png", "BusLeftLow"):
            getPic.winCap()
            if afc.autoFind("./pic/mirror/mirror2/way/Enter.png", "Enter"):
                return
            


    #困难战斗部分
    def mirror2SinCoreBattle(self):
        '''镜牢2单进程找困难战斗'''
        if afc.autoSinClick("./pic/mirror/mirror2/way/Battle/BattleM.png", "BattleMiddle"):
            getPic.winCap()
            if afc.autoFind("./pic/mirror/mirror2/way/Enter.png", "Enter"):
                return

        if afc.autoSinClick("./pic/mirror/mirror2/way/Battle/BattleRH.png", "BattleRightHigh"):
            getPic.winCap()
            if afc.autoFind("./pic/mirror/mirror2/way/Enter.png", "Enter"):
                return
        
        if afc.autoSinClick("./pic/mirror/mirror2/way/Battle/BattleRM.png", "BattleRightMiddle"):
            getPic.winCap()
            if afc.autoFind("./pic/mirror/mirror2/way/Enter.png", "Enter"):
                return
        
        if afc.autoSinClick("./pic/mirror/mirror2/way/Battle/BattleRL.png", "BattleRightLow"):
            getPic.winCap()
            if afc.autoFind("./pic/mirror/mirror2/way/Enter.png", "Enter"):
                return
        
        if afc.autoSinClick("./pic/mirror/mirror2/way/Battle/BattleLH.png", "BattleLeftHigh"):
            getPic.winCap()
            if afc.autoFind("./pic/mirror/mirror2/way/Enter.png", "Enter"):
                return
        
        if afc.autoSinClick("./pic/mirror/mirror2/way/Battle/BattleLM.png", "BattleLeftMiddle"):
            getPic.winCap()
            if afc.autoFind("./pic/mirror/mirror2/way/Enter.png", "Enter"):
                return
            
        if afc.autoSinClick("./pic/mirror/mirror2/way/Battle/BattleLL.png", "BattleLeftLow"):
            getPic.winCap()
            if afc.autoFind("./pic/mirror/mirror2/way/Enter.png", "Enter"):
                return

        

    #首领部分
    def mirror2SinCoreBoss(self):
        '''镜牢2单进程找首领'''
        if afc.autoSinClick("./pic/mirror/mirror2/way/Boss/BossM.png", "BossMiddle"):
            getPic.winCap()
            if afc.autoFind("./pic/mirror/mirror2/way/Enter.png", "Enter"):
                return


        if afc.autoSinClick("./pic/mirror/mirror2/way/Boss/BossRH.png", "BossRightHigh"):
            getPic.winCap()
            if afc.autoFind("./pic/mirror/mirror2/way/Enter.png", "Enter"):
                return

        if afc.autoSinClick("./pic/mirror/mirror2/way/Boss/BossRM.png", "BossRightMiddle"):
            getPic.winCap()
            if afc.autoFind("./pic/mirror/mirror2/way/Enter.png", "Enter"):
                return

        if afc.autoSinClick("./pic/mirror/mirror2/way/Boss/BossRL.png", "BossRightLow"):
            getPic.winCap()
            if afc.autoFind("./pic/mirror/mirror2/way/Enter.png", "Enter"):
                return


        if afc.autoSinClick("./pic/mirror/mirror2/way/Boss/BossLH.png", "BossLeftHigh"):
            getPic.winCap()
            if afc.autoFind("./pic/mirror/mirror2/way/Enter.png", "Enter"):
                return

        if afc.autoSinClick("./pic/mirror/mirror2/way/Boss/BossLM.png", "BossLeftMiddle"):
            getPic.winCap()
            if afc.autoFind("./pic/mirror/mirror2/way/Enter.png", "Enter"):
                return
        
        if afc.autoSinClick("./pic/mirror/mirror2/way/Boss/BossLL.png", "BossLeftLow"):
            getPic.winCap()
            if afc.autoFind("./pic/mirror/mirror2/way/Enter.png", "Enter"):
                return

        

    #问号事件部分
    def mirror2SinCoreQuesionMark(self):
        '''镜牢2单进程找问号'''
        if afc.autoSinClick("./pic/mirror/mirror2/way/QuesionMark/QuesionMarkM.png", "QuesionMarkMiddle"):
            getPic.winCap()
            if afc.autoFind("./pic/mirror/mirror2/way/Enter.png", "Enter"):
                return
        
        if afc.autoSinClick("./pic/mirror/mirror2/way/QuesionMark/QuesionMarkRH.png", "QuesionMarkRightHigh"):
            getPic.winCap()
            if afc.autoFind("./pic/mirror/mirror2/way/Enter.png", "Enter"):
                return

        if afc.autoSinClick("./pic/mirror/mirror2/way/QuesionMark/QuesionMarkRM.png", "QuesionMarkRightMiddle"):
            getPic.winCap()
            if afc.autoFind("./pic/mirror/mirror2/way/Enter.png", "Enter"):
                return

        if afc.autoSinClick("./pic/mirror/mirror2/way/QuesionMark/QuesionMarkRL.png", "QuesionMarkRightLow"):
            getPic.winCap()
            if afc.autoFind("./pic/mirror/mirror2/way/Enter.png", "Enter"):
                return

        if afc.autoSinClick("./pic/mirror/mirror2/way/QuesionMark/QuesionMarkLH.png", "QuesionMarkLeftHigh"):
            getPic.winCap()
            if afc.autoFind("./pic/mirror/mirror2/way/Enter.png", "Enter"):
                return

        if afc.autoSinClick("./pic/mirror/mirror2/way/QuesionMark/QuesionMarkLM.png", "QuesionMarkLeftMiddle"):
            getPic.winCap()
            if afc.autoFind("./pic/mirror/mirror2/way/Enter.png", "Enter"):
                return

        if afc.autoSinClick("./pic/mirror/mirror2/way/QuesionMark/QuesionMarkLL.png", "QuesionMarkLeftLow"):
            getPic.winCap()
            if afc.autoFind("./pic/mirror/mirror2/way/Enter.png", "Enter"):
                return


    #战斗部分
    def mirror2SinCoreFight(self):
        '''镜牢2单进程找普通战斗'''
        if afc.autoSinClick("./pic/mirror/mirror2/way/Fight/FightM.png", "FightMiddle"):
            getPic.winCap()
            if afc.autoFind("./pic/mirror/mirror2/way/Enter.png", "Enter"):
                return

        if afc.autoSinClick("./pic/mirror/mirror2/way/Fight/FightRH.png", "FightRightHigh"):
            getPic.winCap()
            if afc.autoFind("./pic/mirror/mirror2/way/Enter.png", "Enter"):
                return

        if afc.autoSinClick("./pic/mirror/mirror2/way/Fight/FightRM.png", "FightRightMiddle"):
            getPic.winCap()
            if afc.autoFind("./pic/mirror/mirror2/way/Enter.png", "Enter"):
                return

        if afc.autoSinClick("./pic/mirror/mirror2/way/Fight/FightRL.png", "FightRightLow"):
            getPic.winCap()
            if afc.autoFind("./pic/mirror/mirror2/way/Enter.png", "Enter"):
                return

        if afc.autoSinClick("./pic/mirror/mirror2/way/Fight/FightLH.png", "FightLeftHigh"):
            getPic.winCap()
            if afc.autoFind("./pic/mirror/mirror2/way/Enter.png", "Enter"):
                return

        if afc.autoSinClick("./pic/mirror/mirror2/way/Fight/FightLM.png", "FightLeftMiddle"):
            getPic.winCap()
            if afc.autoFind("./pic/mirror/mirror2/way/Enter.png", "Enter"):
                return

        if afc.autoSinClick("./pic/mirror/mirror2/way/Fight/FightLL.png", "FightLeftLow"):
            getPic.winCap()
            if afc.autoFind("./pic/mirror/mirror2/way/Enter.png", "Enter"):
                return
        



class _MirrorOfTheBeginning():
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
        getPic.winCap()
        if(afc.autoFind("./pic/mirror/mirror1/way/mirror1MapSign.png", "mirror1MapSign") and\
            (afc.autoFind("./pic/mirror/mirror1/way/BigSelf.png", "BigSelf", 0.8) or\
            afc.autoFind("./pic/mirror/mirror1/way/Self.png", "Self", 0.8))):
            self.noWayFlag = self.mirror1SinCoreFindWay()

        result = self.mirror1Cope()
        
        return result
    

    
    @checkAndExit
    @beginAndFinishLog
    def mirror1Entry(self):
        '''进入镜牢1流程'''
        if(afc.autoFind("./pic/mirror/mirror1/way/mirror1MapSign.png", "mirror1MapSign")):
            return
        getPic.winCap()
        afc.autoSinClick("./pic/initMenu/drive.png", "Drive")
        getPic.winCap()
        afc.autoSinClick("./pic/mirror/mirror1/MirrorDungeons.png", "MirrorDungeons", 0, 0, 1, 1, 0.9)
        getPic.winCap()
        if(afc.autoFind("./pic/mirror/previousClaimReward.png", "previousClaimReward")):
            raise previousClaimRewardError("有上周的镜牢奖励未领取")
        afc.autoSinClick("./pic/mirror/mirror1/Mirror1Normal.png", "Mirror1Normal")
        getPic.winCap()
        if(afc.autoFind("./pic/mirror/MirrorInProgress.png", "MirrorInProgress")):
            raise mirrorInProgressError("有其他镜牢未结束")
        if(afc.autoSinClick("./pic/mirror/mirror1/Enter.png", "Enter", 0, 0, 5) or\
            afc.autoSinClick("./pic/mirror/mirror1/Resume.png", "Resume", 0, 0, 5)):
            getPic.winCap()
            afc.autoSinClick("./pic/mirror/mirror1/ego/egoGift.png", "egoGift")
            getPic.winCap()
            afc.autoSinClick("./pic/mirror/mirror1/ego/SelectEGOGift.png", "SelectEGOGift")
            getPic.winCap()
            if afc.autoSinClick("./pic/mirror/mirror1/Preset.png", "Preset"):
                getPic.winCap()
                if(afc.autoFind("./pic/error/noSavedPreset.png", "noPreset")):
                    raise noSavedPresetsError("没有预选队伍")
                self.mirror1ChoosePreset()
            afc.autoSinClick("./pic/mirror/mirror1/blackConfirm.png", "blackConfirm", 0, 0, 3)
            getPic.winCap()
            afc.autoSinClick("./pic/mirror/mirror1/BuyCoin.png", "BuyCoin", 0, 0, 8)
        if(afc.autoFind("./pic/Wait.png", "Wait Sign")):
            myWait()

    
    def mirror1ChoosePreset(self):
        '''镜牢1预选人的流程'''
        i = 1
        countFlag = 0
        while(not afc.autoFind("./pic/team/FullTeam55.png", "5/5PresetFullSign")):
            #i的归零
            if(i > 12):
                i = 1
                countFlag += 1
                if(countFlag > 1):
                    from src.log.myLog import myLog
                    myLog("warning","Preset Fail")
                    break
            getPic.winCap()
            if(i < 7):
                addX = i * 140
                addY = 0
            else:
                addX = (i - 6) * 140
                addY = 200

            afc.autoSinClick("./pic/team/Announcer.png", "Member", addX, addY + 100, 0.2)
            getPic.winCap()
            i += 1

        afc.autoSinClick("./pic/team/Announcer.png", "Confirm", 1000, 400, 3)


    @checkAndExit
    @beginAndFinishLog
    def mirror1Leave(self):
        '''镜牢1离开时处理notFullFlag'''
        global notFullFlag 
        notFullFlag = 0


    def mirror1Prize(self):
        '''镜牢1获取奖励的流程'''
        result = False
        getPic.winCap()
        afc.autoSinClick("./pic/battle/confirm.png", "Final_Victory")
        getPic.winCap()
        afc.autoSinClick("./pic/mirror/mirror1/ClaimRewards.png","ClaimRewards", 0, 0, 0.7, 1, 0.7)
        getPic.winCap()
        afc.autoSinClick("./pic/mirror/mirror1/Receive.png","Receive")
        getPic.winCap()
        if afc.autoSinClick("./pic/mirror/mirror1/whiteConfirm.png","FirstConfirm"):
            getPic.winCap()
            if afc.autoSinClick("./pic/mirror/mirror1/way/Confirm.png","SecondConfirm"):
                result = True
        return result




    def mirror1Cope(self): 
        '''处理镜牢1交互的各种情况'''
        result = False
        getPic.winCap()
        if(afc.autoFind("./pic/team/Announcer.png", "Announcer")):
            self.mirror1PrepareBattle()
            self.mirror1BattlePart()
            result = True
        elif(afc.autoFind("./pic/battle/WinRate.png", "battleSign")):
            self.mirror1BattlePart()
            result = True
        elif(afc.autoFind("./pic/event/Skip.png", "Skip")):
            eventPart()
            result = True
        elif(afc.autoFind("./pic/mirror/mirror1/way/Confirm.png", "EGOGift")):
            afc.autoSinClick("./pic/mirror/mirror1/way/Confirm.png", "EGOGift", 0, 0, 1, 2)
            result = True
        elif(afc.autoSinClick("./pic/mirror/mirror1/ego/egoGift.png", "ChooseEgoGift")):
            getPic.winCap()
            afc.autoSinClick("./pic/mirror/mirror1/ego/SelectEGOGift.png", "SelectEGOGift", 0, 0, 6)
            result = True
        elif(afc.autoSinClick("./pic/mirror/mirror1/way/Enter.png", "Enter", 0, 0, 2)):
            result = True
        elif(afc.autoFind("./pic/Wait.png", "Wait Sign")):
            myWait()
            result = True
        
            
        return result


    #根据已选人数和队伍可容纳人数做情况分类
    #检测3/3；4/4；5/5最好就一个标准，能省不少时间
    def mirror1JudTeamCondition(self):
        resultCondition = -1
        if(afc.autoFind("./pic/team/FullTeam55.png", "FullTeam5/5", 0.94) or\
            afc.autoFind("./pic/team/FullTeam44.png", "FullTeam4/4", 0.94) or\
            afc.autoFind("./pic/team/FullTeam33.png", "FullTeam3/3", 0.94)):
            resultCondition = 0
        elif(afc.autoFind("./pic/team/EmptyTeam03.png", "EmptyTeam0/3", 0.94)):
            resultCondition = 1
        elif(afc.autoFind("./pic/team/EmptyTeam04.png", "EmptyTeam0/4", 0.94) or\
        afc.autoFind("./pic/team/NotFullTeam34.png", "NotFullTeam3/4", 0.94)):
            resultCondition = 2
        elif(afc.autoFind("./pic/team/EmptyTeam05.png", "EmptyTeam0/5", 0.94) or\
        afc.autoFind("./pic/team/NotFullTeam45.png", "NotFullTeam4/5", 0.94)):
            resultCondition = 3
        return resultCondition


    #满队标准
    def mirror1JudFullTeam(self,condition):
        result = False
        if(condition == 0):
            result = True
        elif(condition == 1):
            if(afc.autoFind("./pic/team/FullTeam33.png", "FullTeam3/3", 0.94)):
                result = True
        elif(condition == 2):
            if(afc.autoFind("./pic/team/FullTeam44.png", "FullTeam4/4", 0.94)):
                result = True
        elif(condition == 3):
            if(afc.autoFind("./pic/team/FullTeam55.png", "FullTeam5/5", 0.94)):
                result = True
        else:
            if(afc.autoFind("./pic/team/FullTeam55.png", "FullTeam5/5", 0.94) or\
                afc.autoFind("./pic/team/FullTeam44.png", "FullTeam4/4", 0.94) or\
                afc.autoFind("./pic/team/FullTeam33.png", "FullTeam3/3", 0.94)):
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
                    from src.log.myLog import beginAndFinishLog, myLog
                    myLog("warning","Can't make team full")
                    notFullFlag = 1
                    break
            getPic.winCap()
            if(i < 7):
                addX = i * 140
                addY = 0
            else:
                addX = (i - 6) * 140
                addY = 200

            afc.autoSinClick("./pic/team/Announcer.png", "Member", addX, addY + 100, 0.2)
            getPic.winCap()
            i += 1

        #即使选不到满人，也要尽可能多选人
        if(notFullFlag == 1 and\
        (afc.autoFind("./pic/team/EmptyTeam03.png", "EmptyTeam0/3", 0.94)or\
            afc.autoFind("./pic/team/EmptyTeam04.png", "EmptyTeam0/4", 0.94)or\
            afc.autoFind("./pic/team/EmptyTeam05.png", "EmptyTeam0/5", 0.94)or\
            afc.autoFind("./pic/team/NotFullTeam15.png", "NotFullTeam1/5", 0.94))
            ):
            for i in range(1,13):
                getPic.winCap()
                if(i < 7):
                    addX = i * 140
                    addY = 0
                else:
                    addX = (i - 6) * 140
                    addY = 200

                afc.autoSinClick("./pic/team/Announcer.png", "Member", addX, addY, 0.2)



        afc.autoSinClick("./pic/team/Announcer.png", "ToBattle", 1000, 400, 5)
        getPic.winCap()
        if(afc.autoFind("./pic/Wait.png", "Wait Sign")):
                myWait()


    @checkAndExit
    @beginAndFinishLog
    def mirror1BattlePart(self):
        '''镜牢战斗处理'''
        getPic.winCap()
        loopCount = 0
        while(True):
            getPic.winCap()
            condition = False
            if (afc.autoSinClick("./pic/battle/WinRate.png", "WinRate")):
                getPic.winCap()
                if (afc.autoSinClick("./pic/battle/Start.png", "Start")):
                    condition = True
            elif(afc.autoFind("./pic/battle/battlePause.png", "Fighting Sign")):
                myTimeSleep(2)
                condition = True
            elif(afc.autoSinClick("./pic/battle/trianglePause.png", "Continue Fight!")):
                condition = True    
            elif(afc.autoFind("./pic/event/Skip.png", "Skip")):
                eventPart()
                condition = True
            elif(afc.autoFind("./pic/Wait.png", "Wait Sign")):
                myWait()
                condition = True
            if(not condition):
                loopCount += 1
                if(loopCount > 2):
                    break
                elif(loopCount > 0):
                    if (afc.autoFind("./pic/battle/Gear.png", "FinishingBattle")):
                        condition = True
                        loopCount = 0
            else:
                loopCount = 0
            myTimeSleep(0.9)




    @checkAndExit
    @beginAndFinishLog
    def mirror1SinCoreFindWay(self):
        '''镜牢1单进程寻路'''
        
        result = False

        # 滚动滑轮以保持视图大小不变
        littleUpScroll()

        afc.autoSinClick("./pic/mirror/mirror1/way/Self.png", "Self")
        getPic.winCap()
        if(afc.autoSinClick("./pic/mirror/mirror1/way/Enter.png", "Enter", 0, 0, 2)):
            result = True
            return result
        self.mirror1SinCoreQuesionMark()
        if(afc.autoSinClick("./pic/mirror/mirror1/way/Enter.png", "Enter", 0, 0, 2)):
            result = True
            return result
        self.mirror1SinCoreChair()
        if(afc.autoSinClick("./pic/mirror/mirror1/way/Enter.png", "Enter", 0, 0, 2)):
            result = True
            return result
        self.mirror1SinCoreBus()
        if(afc.autoSinClick("./pic/mirror/mirror1/way/Enter.png", "Enter", 0, 0, 2)):
            result = True
            return result
        self.mirror1SinCoreFight()
        if(afc.autoSinClick("./pic/mirror/mirror1/way/Enter.png", "Enter", 0, 0, 2)):
            result = True
            return result
        self.mirror1SinCoreBoss()
        if(afc.autoSinClick("./pic/mirror/mirror1/way/Enter.png", "Enter", 0, 0, 2)):
            result = True
            return result
        self.mirror1SinCoreBattle()
        if(afc.autoSinClick("./pic/mirror/mirror1/way/Enter.png", "Enter", 0, 0, 2)):
            result = True
            return result
        self.mirror1SinCoreEncounter()
        if(afc.autoSinClick("./pic/mirror/mirror1/way/Enter.png", "Enter", 0, 0, 2)):
            result = True
            return result
        
        
        return result





    #巴士部分
    def mirror1SinCoreBus(self):
        '''镜牢1单进程找巴士'''
        if afc.autoSinClick("./pic/mirror/mirror1/way/Bus/BusM.png", "BusMiddle"):
            getPic.winCap()
            if afc.autoFind("./pic/mirror/mirror1/way/Enter.png", "Enter"):
                return
        if afc.autoFind("./pic/mirror/mirror1/way/Enter.png", "Enter"):
            return

        if afc.autoSinClick("./pic/mirror/mirror1/way/Bus/BusRH.png", "BusRightHigh"):
            getPic.winCap()
            if afc.autoFind("./pic/mirror/mirror1/way/Enter.png", "Enter"):
                return

        if afc.autoSinClick("./pic/mirror/mirror1/way/Bus/BusRM.png", "BusRightMiddle"):
            getPic.winCap()
            if afc.autoFind("./pic/mirror/mirror1/way/Enter.png", "Enter"):
                return
        
        if afc.autoSinClick("./pic/mirror/mirror1/way/Bus/BusRL.png", "BusRightLow"):
            getPic.winCap()
            if afc.autoFind("./pic/mirror/mirror1/way/Enter.png", "Enter"):
                return

        
        if afc.autoSinClick("./pic/mirror/mirror1/way/Bus/BusLH.png", "BusLeftHigh"):
            getPic.winCap()
            if afc.autoFind("./pic/mirror/mirror1/way/Enter.png", "Enter"):
                return
        

        if afc.autoSinClick("./pic/mirror/mirror1/way/Bus/BusLM.png", "BusLeftMiddle"):
            getPic.winCap()
            if afc.autoFind("./pic/mirror/mirror1/way/Enter.png", "Enter"):
                return
        
        if afc.autoSinClick("./pic/mirror/mirror1/way/Bus/BusLL.png", "BusLeftLow"):
            getPic.winCap()
            if afc.autoFind("./pic/mirror/mirror1/way/Enter.png", "Enter"):
                return
            


    #椅子部分
    def mirror1SinCoreChair(self):
        '''镜牢1单进程找椅子'''
        if afc.autoSinClick("./pic/mirror/mirror1/way/Chair/ChairM.png", "ChairMiddle"):
            getPic.winCap()
            if afc.autoFind("./pic/mirror/mirror1/way/Enter.png", "Enter"):
                return
        

        if afc.autoSinClick("./pic/mirror/mirror1/way/Chair/ChairRH.png", "ChairRightHigh"):
            getPic.winCap()
            if afc.autoFind("./pic/mirror/mirror1/way/Enter.png", "Enter"):
                return

        if afc.autoSinClick("./pic/mirror/mirror1/way/Chair/ChairRM.png", "ChairRightMiddle"):
            getPic.winCap()
            if afc.autoFind("./pic/mirror/mirror1/way/Enter.png", "Enter"):
                return
        
        if afc.autoSinClick("./pic/mirror/mirror1/way/Chair/ChairRL.png", "ChairRightLow"):
            getPic.winCap()
            if afc.autoFind("./pic/mirror/mirror1/way/Enter.png", "Enter"):
                return
        
        if afc.autoSinClick("./pic/mirror/mirror1/way/Chair/ChairLH.png", "ChairLeftHigh"):
            getPic.winCap()
            if afc.autoFind("./pic/mirror/mirror1/way/Enter.png", "Enter"):
                return

        if afc.autoSinClick("./pic/mirror/mirror1/way/Chair/ChairLM.png", "ChairLeftMiddle"):
            getPic.winCap()
            if afc.autoFind("./pic/mirror/mirror1/way/Enter.png", "Enter"):
                return

        if afc.autoSinClick("./pic/mirror/mirror1/way/Chair/ChairLL.png", "ChairLeftLow"):
            getPic.winCap()
            if afc.autoFind("./pic/mirror/mirror1/way/Enter.png", "Enter"):
                return


    #异想体部分
    def mirror1SinCoreEncounter(self):
        '''镜牢1单进程找异想体'''
        if afc.autoSinClick("./pic/mirror/mirror1/way/Encounter/EncounterM.png", "EncounterMiddle"):
            getPic.winCap()
            if afc.autoFind("./pic/mirror/mirror1/way/Enter.png", "Enter"):
                return
        
        if afc.autoSinClick("./pic/mirror/mirror1/way/Encounter/EncounterRH.png", "EncounterRightHigh"):
            getPic.winCap()
            if afc.autoFind("./pic/mirror/mirror1/way/Enter.png", "Enter"):
                return

        if afc.autoSinClick("./pic/mirror/mirror1/way/Encounter/EncounterRM.png", "EncounterRightMiddle"):
            getPic.winCap()
            if afc.autoFind("./pic/mirror/mirror1/way/Enter.png", "Enter"):
                return

        if afc.autoSinClick("./pic/mirror/mirror1/way/Encounter/EncounterRL.png", "EncounterRightLow"):
            getPic.winCap()
            if afc.autoFind("./pic/mirror/mirror1/way/Enter.png", "Enter"):
                return

        if afc.autoSinClick("./pic/mirror/mirror1/way/Encounter/EncounterLH.png", "EncounterLeftHigh"):
            getPic.winCap()
            if afc.autoFind("./pic/mirror/mirror1/way/Enter.png", "Enter"):
                return
        

        if afc.autoSinClick("./pic/mirror/mirror1/way/Encounter/EncounterLM.png", "EncounterLeftMiddle"):
            getPic.winCap()
            if afc.autoFind("./pic/mirror/mirror1/way/Enter.png", "Enter"):
                return
        
        
        if afc.autoSinClick("./pic/mirror/mirror1/way/Encounter/EncounterLL.png", "EncounterLeftLow"):
            getPic.winCap()
            if afc.autoFind("./pic/mirror/mirror1/way/Enter.png", "Enter"):
                return


    #困难战斗部分
    def mirror1SinCoreBattle(self):
        '''镜牢1单进程找困难战斗'''
        if afc.autoSinClick("./pic/mirror/mirror1/way/Battle/BattleM.png", "BattleMiddle"):
            getPic.winCap()
            if afc.autoFind("./pic/mirror/mirror1/way/Enter.png", "Enter"):
                return

        if afc.autoSinClick("./pic/mirror/mirror1/way/Battle/BattleRH.png", "BattleRightHigh"):
            getPic.winCap()
            if afc.autoFind("./pic/mirror/mirror1/way/Enter.png", "Enter"):
                return
        
        if afc.autoSinClick("./pic/mirror/mirror1/way/Battle/BattleRM.png", "BattleRightMiddle"):
            getPic.winCap()
            if afc.autoFind("./pic/mirror/mirror1/way/Enter.png", "Enter"):
                return
        
        if afc.autoSinClick("./pic/mirror/mirror1/way/Battle/BattleRL.png", "BattleRightLow"):
            getPic.winCap()
            if afc.autoFind("./pic/mirror/mirror1/way/Enter.png", "Enter"):
                return
        
        if afc.autoSinClick("./pic/mirror/mirror1/way/Battle/BattleLH.png", "BattleLeftHigh"):
            getPic.winCap()
            if afc.autoFind("./pic/mirror/mirror1/way/Enter.png", "Enter"):
                return
        
        if afc.autoSinClick("./pic/mirror/mirror1/way/Battle/BattleLM.png", "BattleLeftMiddle"):
            getPic.winCap()
            if afc.autoFind("./pic/mirror/mirror1/way/Enter.png", "Enter"):
                return
            
        if afc.autoSinClick("./pic/mirror/mirror1/way/Battle/BattleLL.png", "BattleLeftLow"):
            getPic.winCap()
            if afc.autoFind("./pic/mirror/mirror1/way/Enter.png", "Enter"):
                return

        

    #首领部分
    def mirror1SinCoreBoss(self):
        '''镜牢1单进程找首领'''
        if afc.autoSinClick("./pic/mirror/mirror1/way/Boss/BossM.png", "BossMiddle"):
            getPic.winCap()
            if afc.autoFind("./pic/mirror/mirror1/way/Enter.png", "Enter"):
                return


        if afc.autoSinClick("./pic/mirror/mirror1/way/Boss/BossRH.png", "BossRightHigh"):
            getPic.winCap()
            if afc.autoFind("./pic/mirror/mirror1/way/Enter.png", "Enter"):
                return

        if afc.autoSinClick("./pic/mirror/mirror1/way/Boss/BossRM.png", "BossRightMiddle"):
            getPic.winCap()
            if afc.autoFind("./pic/mirror/mirror1/way/Enter.png", "Enter"):
                return

        if afc.autoSinClick("./pic/mirror/mirror1/way/Boss/BossRL.png", "BossRightLow"):
            getPic.winCap()
            if afc.autoFind("./pic/mirror/mirror1/way/Enter.png", "Enter"):
                return


        if afc.autoSinClick("./pic/mirror/mirror1/way/Boss/BossLH.png", "BossLeftHigh"):
            getPic.winCap()
            if afc.autoFind("./pic/mirror/mirror1/way/Enter.png", "Enter"):
                return

        if afc.autoSinClick("./pic/mirror/mirror1/way/Boss/BossLM.png", "BossLeftMiddle"):
            getPic.winCap()
            if afc.autoFind("./pic/mirror/mirror1/way/Enter.png", "Enter"):
                return
        
        if afc.autoSinClick("./pic/mirror/mirror1/way/Boss/BossLL.png", "BossLeftLow"):
            getPic.winCap()
            if afc.autoFind("./pic/mirror/mirror1/way/Enter.png", "Enter"):
                return

        

    #问号事件部分
    def mirror1SinCoreQuesionMark(self):
        '''镜牢1单进程找问号'''
        if afc.autoSinClick("./pic/mirror/mirror1/way/QuesionMark/QuesionMarkM.png", "QuesionMarkMiddle"):
            getPic.winCap()
            if afc.autoFind("./pic/mirror/mirror1/way/Enter.png", "Enter"):
                return
        
        if afc.autoSinClick("./pic/mirror/mirror1/way/QuesionMark/QuesionMarkRH.png", "QuesionMarkRightHigh"):
            getPic.winCap()
            if afc.autoFind("./pic/mirror/mirror1/way/Enter.png", "Enter"):
                return

        if afc.autoSinClick("./pic/mirror/mirror1/way/QuesionMark/QuesionMarkRM.png", "QuesionMarkRightMiddle"):
            getPic.winCap()
            if afc.autoFind("./pic/mirror/mirror1/way/Enter.png", "Enter"):
                return

        if afc.autoSinClick("./pic/mirror/mirror1/way/QuesionMark/QuesionMarkRL.png", "QuesionMarkRightLow"):
            getPic.winCap()
            if afc.autoFind("./pic/mirror/mirror1/way/Enter.png", "Enter"):
                return

        if afc.autoSinClick("./pic/mirror/mirror1/way/QuesionMark/QuesionMarkLH.png", "QuesionMarkLeftHigh"):
            getPic.winCap()
            if afc.autoFind("./pic/mirror/mirror1/way/Enter.png", "Enter"):
                return

        if afc.autoSinClick("./pic/mirror/mirror1/way/QuesionMark/QuesionMarkLM.png", "QuesionMarkLeftMiddle"):
            getPic.winCap()
            if afc.autoFind("./pic/mirror/mirror1/way/Enter.png", "Enter"):
                return

        if afc.autoSinClick("./pic/mirror/mirror1/way/QuesionMark/QuesionMarkLL.png", "QuesionMarkLeftLow"):
            getPic.winCap()
            if afc.autoFind("./pic/mirror/mirror1/way/Enter.png", "Enter"):
                return


    #战斗部分
    def mirror1SinCoreFight(self):
        '''镜牢1单进程找普通战斗'''
        if afc.autoSinClick("./pic/mirror/mirror1/way/Fight/FightM.png", "FightMiddle"):
            getPic.winCap()
            if afc.autoFind("./pic/mirror/mirror1/way/Enter.png", "Enter"):
                return

        if afc.autoSinClick("./pic/mirror/mirror1/way/Fight/FightRH.png", "FightRightHigh"):
            getPic.winCap()
            if afc.autoFind("./pic/mirror/mirror1/way/Enter.png", "Enter"):
                return

        if afc.autoSinClick("./pic/mirror/mirror1/way/Fight/FightRM.png", "FightRightMiddle"):
            getPic.winCap()
            if afc.autoFind("./pic/mirror/mirror1/way/Enter.png", "Enter"):
                return

        if afc.autoSinClick("./pic/mirror/mirror1/way/Fight/FightRL.png", "FightRightLow"):
            getPic.winCap()
            if afc.autoFind("./pic/mirror/mirror1/way/Enter.png", "Enter"):
                return

        if afc.autoSinClick("./pic/mirror/mirror1/way/Fight/FightLH.png", "FightLeftHigh"):
            getPic.winCap()
            if afc.autoFind("./pic/mirror/mirror1/way/Enter.png", "Enter"):
                return

        if afc.autoSinClick("./pic/mirror/mirror1/way/Fight/FightLM.png", "FightLeftMiddle"):
            getPic.winCap()
            if afc.autoFind("./pic/mirror/mirror1/way/Enter.png", "Enter"):
                return

        if afc.autoSinClick("./pic/mirror/mirror1/way/Fight/FightLL.png", "FightLeftLow"):
            getPic.winCap()
            if afc.autoFind("./pic/mirror/mirror1/way/Enter.png", "Enter"):
                return
        
