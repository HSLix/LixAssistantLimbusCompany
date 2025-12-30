# coding: utf-8
import logging
import os
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from PIL import Image
import inspect

_instance = None

_LEVEL_MAP = {
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARNING": logging.WARNING,
    "ERROR": logging.ERROR,
    "CRITICAL": logging.CRITICAL,
}

class LALCLogger:
    def __init__(self, retain_folder_count: int = 5):
        if logging.getLogger("lalc_logger").handlers:
            return

        self.run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.log_dir = Path("./logs") / self.run_id
        self.log_dir.mkdir(parents=True, exist_ok=True)
        (self.log_dir / "images").mkdir(exist_ok=True)
        self._clean_old_folders(retain_folder_count)

        self.log_file = self.log_dir / "run.log"
        self.logger = logging.getLogger("lalc_logger")
        self.logger.setLevel(logging.DEBUG)

        fmt = logging.Formatter("%(asctime)s | %(levelname)s | %(message)s")
        fh = logging.FileHandler(self.log_file, encoding="utf-8")
        fh.setFormatter(fmt)
        self.logger.addHandler(fh)

        ch = logging.StreamHandler()
        ch.setFormatter(fmt)
        self.logger.addHandler(ch)

    def log(self,
            msg: str = "",
            image: Image.Image | None = None,
            level: str = "INFO",
            task_name: str | None = None,
            compress_image: bool = True):
        """
        通用日志入口
        task_name 为 None 时自动取调用处函数名；
        级别 ≥ WARNING 时自动附加 文件:行号
        """
        try:
            # ---- 自动 task_name ----
            if task_name is None:
                frame = inspect.currentframe().f_back
                task_name = frame.f_code.co_name

            # ---- 级别 ≥ WARNING 附加定位信息 ----
            level_no = _LEVEL_MAP.get(level.upper(), logging.INFO)
            if level_no >= logging.WARNING:
                frame = inspect.currentframe().f_back
                filename = os.path.basename(frame.f_code.co_filename)
                lineno = frame.f_lineno
                msg += f"  ({filename}:{lineno})"

            # ---- 图片逻辑（保持原样） ----
            if image is not None:
                img_name = f"{datetime.now().strftime('%H%M%S_%f')[:-3]}.png"
                img_path = self.log_dir / "images" / img_name
                image.save(img_path, format="PNG")
                
                # 如果需要压缩图片
                if compress_image:
                    self.compress_image_with_pngquant(img_path)
                    
                msg += f" | IMAGE:images/{img_name}"

            self.logger.log(getattr(logging, level), f"[{task_name}] {msg}")
        except Exception as e:
            self.log(f"日志记录 log 发生错误：{e}", level="ERROR")


    def debug(self,
              msg: str = "",
              image: Image.Image | None = None,
              level: str = "DEBUG",
              task_name: str | None = None,
              compress_image: bool = True):
        try:
            # ---- 自动 task_name ----
            if task_name is None:
                frame = inspect.currentframe().f_back
                task_name = frame.f_code.co_name

            # ---- 级别 ≥ WARNING 附加定位信息 ----
            level_no = _LEVEL_MAP.get(level.upper(), logging.INFO)
            if level_no >= logging.WARNING:
                frame = inspect.currentframe().f_back
                filename = os.path.basename(frame.f_code.co_filename)
                lineno = frame.f_lineno
                msg += f"  ({filename}:{lineno})"

            # ---- 图片逻辑（保持原样） ----
            if image is not None:
                img_name = f"{datetime.now().strftime('%H%M%S_%f')[:-3]}.png"
                img_path = self.log_dir / "images" / img_name
                image.save(img_path, format="PNG")
                # image.close()
                
                # 如果需要压缩图片
                if compress_image:
                    self.compress_image_with_pngquant(img_path)
                    
                msg += f" | IMAGE:images/{img_name}"

            self.logger.log(getattr(logging, level), f"[{task_name}] {msg}")
        except Exception as e:
            self.log(f"日志记录 debug 发生错误：{e}", level="ERROR")

    # --------- 内部 ---------
    def _clean_old_folders(self, keep: int):
        root = Path("./logs")
        if not root.exists():
            return
        dirs = sorted((d for d in root.iterdir() if d.is_dir()), key=lambda x: x.name)
        for d in dirs[:-keep]:
            shutil.rmtree(d, ignore_errors=True)

    def compress_image_with_pngquant(self, image_path: str | Path) -> bool:
        """
        使用pngquant.exe压缩图片
        
        :param image_path: 图片路径
        :return: 压缩是否成功
        """
        try:
            # 确保路径是Path对象
            image_path = Path(image_path)
            
            # 检查pngquant.exe是否存在
            pngquant_exe = Path(__file__).parent / "pngquant.exe"
            if not pngquant_exe.exists():
                self.log(f"pngquant.exe未找到: {pngquant_exe}", level="WARNING")
                return False
                
            # 检查图片文件是否存在
            if not image_path.exists():
                self.log(f"图片文件不存在: {image_path}", level="WARNING")
                return False

            # 构建命令，按照要求使用特定参数进行快速压缩
            # ./pngquant.exe --force --skip-if-larger --ext .png --speed 11 图片名字.png
            cmd = [
                str(pngquant_exe),
                "--force",
                "--skip-if-larger",
                "--ext", ".png",
                "--speed", "11",
                str(image_path.resolve())
            ]
            
            # 执行命令
            result = subprocess.run(
                cmd,
                cwd=pngquant_exe.parent,
                capture_output=True,
                text=True,
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform.startswith("win") else 0
            )
            
            if result.returncode == 0:
                self.log(f"图片压缩成功: {image_path}")
                return True
            else:
                self.log(f"图片压缩失败: {image_path}, 错误: {result.stderr.strip()}", level="WARNING")
                return False
                
        except Exception as e:
            self.log(f"图片压缩发生异常: {e}", level="ERROR")
            return False

def init_logger() -> LALCLogger:
    global _instance
    if _instance is None:
        _instance = LALCLogger()
    return _instance



if __name__ == "__main__":
    from input.input_handler import input_handler
    input_handler.refresh_window_state()
    def test_log():
        logger = init_logger()
        logger.debug("开始战斗", input_handler.capture_screenshot())                       # task_name 自动 = "fight"
        logger.log("出现警告", level="WARNING", image=input_handler.capture_screenshot())  # 手动指定 task_name 也可
    test_log()