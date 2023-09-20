'''
* Author: LuYaoQi
* Time  : 2023/9/16 9:25
* File  : myError.py      
* Project   :LixAssistantLimbusCompany
* Function  :设置自己错误类型以便Gui做反馈   
'''
class withOutAdminError(Exception):
    '''没有获取管理员权限'''
    __slots__ = ()
    def __init__(self, ErrorInfo):
        # 初始化父类
        super().__init__(self)
        self.errorInfo = ErrorInfo
    
    def __str__(self):
        return self.errorInfo

class withOutPicError(Exception):
    '''图片读取失败'''
    __slots__ = ()
    def __init__(self, ErrorInfo):
        # 初始化父类
        super().__init__(self)
        self.errorInfo = ErrorInfo
    
    def __str__(self):
        return self.errorInfo

class notWaitError(Exception):
    '''点击开始下载后不等待下载进程'''
    __slots__ = ()
    def __init__(self, ErrorInfo):
        # 初始化父类
        super().__init__(self)
        self.errorInfo = ErrorInfo
    
    def __str__(self):
        return self.errorInfo

class withOutGameWinError(Exception):
    '''没有检测到游戏窗口'''
    __slots__ = ()
    def __init__(self, ErrorInfo):
        # 初始化父类
        super().__init__(self)
        self.errorInfo = ErrorInfo
    
    def __str__(self):
        return self.errorInfo

class backMainWinError(Exception):
    '''无法回到初始主界面'''
    __slots__ = ()
    def __init__(self, ErrorInfo):
        # 初始化父类
        super().__init__(self)
        self.errorInfo = ErrorInfo
    
    def __str__(self):
        return self.errorInfo

class netWorkUnstableError(Exception):
    '''检测到网络不稳只能退出的反馈'''
    __slots__ = ()
    def __init__(self, ErrorInfo):
        # 初始化父类
        super().__init__(self)
        self.errorInfo = ErrorInfo
    
    def __str__(self):
        return self.errorInfo

class cannotOperateGameError(Exception):
    '''重试失败过多反馈'''
    __slots__ = ()
    def __init__(self, ErrorInfo):
        # 初始化父类
        super().__init__(self)
        self.errorInfo = ErrorInfo
    
    def __str__(self):
        return self.errorInfo
    

class unexpectNumError(Exception):
    '''出现未知选择'''
    __slots__ = ()
    def __init__(self, ErrorInfo):
        # 初始化父类
        super().__init__(self)
        self.errorInfo = ErrorInfo
    
    def __str__(self):
        return self.errorInfo
    
class noSavedPresetsError(Exception):
    '''没有之前选人记录'''
    __slots__ = ()
    def __init__(self, ErrorInfo):
        # 初始化父类
        super().__init__(self)
        self.errorInfo = ErrorInfo
    
    def __str__(self):
        return self.errorInfo

class mirrorInProgressError(Exception):
    '''其它镜牢未结束时不能下一把'''
    __slots__ = ()
    def __init__(self, ErrorInfo):
        # 初始化父类
        super().__init__(self)
        self.errorInfo = ErrorInfo
    
    def __str__(self):
        return self.errorInfo

class userStopError(Exception):
    '''用户主动终止，不算错误，但要保持队列'''
    __slots__ = ()
    def __init__(self, ErrorInfo):
        # 初始化父类
        super().__init__(self)
        self.errorInfo = ErrorInfo
    
    def __str__(self):
        return self.errorInfo
    

class previousClaimRewardError(Exception):
    '''镜牢换季而之前的奖励未领'''
    __slots__ = ()
    def __init__(self, ErrorInfo):
        # 初始化父类
        super().__init__(self)
        self.errorInfo = ErrorInfo
    
    def __str__(self):
        return self.errorInfo