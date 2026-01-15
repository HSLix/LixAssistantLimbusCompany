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
import cv2 

_instance = None

_LEVEL_MAP = {
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARNING": logging.WARNING,
    "ERROR": logging.ERROR,
    "CRITICAL": logging.CRITICAL,
}

class LALCLogger:
    def __init__(self, retain_folder_count: int = 3):
        # 检查是否已经存在logger实例
        self.logger = logging.getLogger("lalc_logger")
        
        self.run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.log_dir = Path("./logs") / self.run_id
        self.log_dir.mkdir(parents=True, exist_ok=True)
        (self.log_dir / "images").mkdir(exist_ok=True)
        self._clean_old_folders(retain_folder_count)
        
        # 如果logger还没有被配置（没有处理器），则进行配置
        if not self.logger.handlers:
            self.log_file = self.log_dir / "run.log"
            self.logger.setLevel(logging.DEBUG)

            fmt = logging.Formatter("%(asctime)s | %(levelname)s | %(message)s")
            fh = logging.FileHandler(self.log_file, encoding="utf-8")
            fh.setFormatter(fmt)
            self.logger.addHandler(fh)

            ch = logging.StreamHandler()
            ch.setFormatter(fmt)
            self.logger.addHandler(ch)

        

        # ========= 对外仅暴露 4 个级别 =========
    def debug(self, msg: str = "", image: Image.Image | None = None,
              task_name: str | None = None, compress_image: bool = True) -> None:
        self._base_log(msg, image, "DEBUG", task_name, compress_image)

    def info(self, msg: str = "", image: Image.Image | None = None,
             task_name: str | None = None, compress_image: bool = True) -> None:
        self._base_log(msg, image, "INFO", task_name, compress_image)

    def warning(self, msg: str = "", image: Image.Image | None = None,
                task_name: str | None = None, compress_image: bool = True) -> None:
        self._base_log(msg, image, "WARNING", task_name, compress_image)

    def error(self, msg: str = "", image: Image.Image | None = None,
              task_name: str | None = None, compress_image: bool = True) -> None:
        self._base_log(msg, image, "ERROR", task_name, compress_image)

    # --------- 统一底层实现 ---------
    def _base_log(self, msg, image, level, task_name, compress_image):
        try:
            if task_name is None:
                frame = inspect.currentframe().f_back.f_back  # 跨一层封装
                task_name = frame.f_code.co_name

            level_no = _LEVEL_MAP[level]
            if level_no >= logging.WARNING:
                frame = inspect.currentframe().f_back.f_back
                filename = os.path.basename(frame.f_code.co_filename)
                lineno = frame.f_lineno
                msg += f"  ({filename}:{lineno})"

            if image is not None:
                img_name = f"{datetime.now().strftime('%H%M%S_%f')[:-3]}.png"
                img_path = self.log_dir / "images" / img_name
                if level == "DEBUG":
                    self._save_resized(image, img_path)
                else:
                    image.save(img_path, format="PNG")

                if compress_image:
                    self.compress_image_with_pngquant(img_path)
                msg += f" | IMAGE:images/{img_name}"

            # 根据传入的level参数使用对应的日志级别
            if level == "DEBUG":
                self.logger.debug(f"[{task_name}] {msg}")
            elif level == "INFO":
                self.logger.info(f"[{task_name}] {msg}")
            elif level == "WARNING":
                self.logger.warning(f"[{task_name}] {msg}")
            elif level == "ERROR":
                self.logger.error(f"[{task_name}] {msg}")
            else:
                self.logger.info(f"[{task_name}] {msg}")  # 默认使用INFO级别
        except Exception as e:
            self.logger.error(f"[Logger] 记录日志时发生异常: {e}")

    # --------- 内部 ---------
    def _clean_old_folders(self, keep: int):
        root = Path("./logs")
        if not root.exists():
            self.logger.warning(f"日志文件夹不存在，跳过日志清理")
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
                self.warning(f"pngquant.exe未找到: {pngquant_exe}")
                return False
                
            # 检查图片文件是否存在
            if not image_path.exists():
                self.warning(f"图片文件不存在: {image_path}")
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
                self.debug(f"图片压缩成功: {image_path}")
                return True
            else:
                self.warning(f"图片压缩失败: {image_path}, 错误: {result.stderr.strip()}")
                return False
                
        except Exception as e:
            self.error(f"图片压缩发生异常: {e}")
            return False
        
        # --------- 内部：统一写图+resize ---------
    def _save_resized(self, image: Image.Image, save_path: Path) -> None:
        """
        将 PIL 图像宽高各缩小后保存为 PNG
        """
        w, h = image.size
        new_size = (w // 2, h // 2)
        image = image.resize(new_size, Image.LANCZOS)
        image.save(save_path, format="PNG")


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
        logger.info("出现警告", image=input_handler.capture_screenshot())  # 手动指定 task_name 也可
        logger.warning("出现警告", image=input_handler.capture_screenshot())  # 手动指定 task_name 也可
        logger.error("出现警告", image=input_handler.capture_screenshot())  # 手动指定 task_name 也可
    test_log()