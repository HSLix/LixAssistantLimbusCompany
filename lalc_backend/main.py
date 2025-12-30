# main.py  (Windows only)
import asyncio, os, sys, signal, ctypes
from server import ServerController
from utils.logger import init_logger

logger = init_logger()

# ---------- 工具函数 ----------
def obtain_mutex_and_lock():
    """
    创建命名互斥量，防止脚本被复制后重复启动。
    成功返回句柄（仅作占位，不再关闭），失败直接 sys.exit
    """
    mutex_name = r"Global\MyAppSingleInstanceMutex"
    # 第 3 个参数 True 表示“创建后立即持有”
    h = ctypes.windll.kernel32.CreateMutexW(None, True, mutex_name)
    if ctypes.windll.kernel32.GetLastError() == 183:   # ERROR_ALREADY_EXISTS
        logger.error("互斥量已存在，另一个实例正在运行。")
        sys.exit(1)
    return h        # 只保存，不关闭


# ---------- 主流程 ----------
async def amain():
    # 获取互斥量锁（句柄不再使用，但占个位方便调试）
    _mutex_handle = obtain_mutex_and_lock()

    # 隐藏控制台窗口（无窗模式）
    # ctypes.windll.user32.ShowWindow(ctypes.windll.kernel32.GetConsoleWindow(), 0)

    # 正常跑业务
    await ServerController().run_forever()


if __name__ == "__main__":
    asyncio.run(amain())