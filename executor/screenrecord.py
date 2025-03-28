# coding: utf-8
# https://stackoverflow.com/questions/30509573/writing-an-mp4-video-using-python-opencv
import cv2
import numpy as np
from PyQt5.QtWidgets import QApplication, QWidget, QPushButton, QVBoxLayout
from globals import VIDEO_DIR
import os
import mss
from datetime import datetime
from PyQt5.QtCore import QThread, pyqtSignal
from subprocess import Popen, PIPE, run

from globals import ignoreScaleAndDpi, FFMPEG_FILE
from .logger import lalc_logger




class ScreenRecorderThread(QThread):
    video_count_exceeded = pyqtSignal()
    video_count_warning = pyqtSignal()

    def remove_exceeded_video(self):
        video_files = [f for f in os.listdir(VIDEO_DIR) if f.endswith('.mp4')]
        video_count = len(video_files)
        if video_count >= 12:
            video_files.sort(key=lambda x: os.path.getctime(os.path.join(VIDEO_DIR, x)))
            while len(video_files) > 11:
                oldest_file = video_files.pop(0)
                os.remove(os.path.join(VIDEO_DIR, oldest_file))
            self.video_count_exceeded.emit()

    def check_video_count_after_recording(self):
        video_files = [f for f in os.listdir(VIDEO_DIR) if f.endswith('.mp4')]
        video_count = len(video_files)
        if video_count >= 11:
            self.video_count_warning.emit()

    def __init__(self):
        super().__init__()
        self.recording = False
        self.output_path = VIDEO_DIR
        self.safe_encoder = self.get_safe_encoder()

    def get_safe_encoder(self):
        """自动选择可用的最佳 H.264 编码器"""
        # 按优先级排序的编码器列表
        encoder_priority = [
            'h264_nvenc',    # NVIDIA 显卡（效率最高）
            'h264_qsv',      # Intel 核显
            'h264_amf',      # AMD 显卡
            'libx264'        # 软件后备
        ]
        
        try:
            # 获取 FFmpeg 支持的编码器列表
            result = run(
                [FFMPEG_FILE, '-hide_banner', '-encoders'],
                stdout=PIPE,
                stderr=PIPE,
                text=True
            )
            encoders_output = result.stderr

            # 按优先级检查可用编码器
            for encoder in encoder_priority:
                if encoder in encoders_output:
                    return encoder
        except Exception as e:
            print(f"检测编码器时出错: {e}")
        
        return 'libx264'  # 默认后备

    def set_recording_enabled(self, enabled):
        """设置录屏功能是否启用"""
        self.recording = enabled

    def run(self):
        self.remove_exceeded_video()
        lalc_logger.log_task("INFO", "record_fun", "STARTED", "Use Encoder [{0}]".format(self.safe_encoder))
        if not self.recording:
            self.recording = True

            with mss.mss() as sct:
                monitor = sct.monitors[0]
                w = monitor['width']
                h = monitor['height']
            monitor = {"top": 0, "left": 0, "width": w, "height": h}

            now = datetime.now()
            output_file = os.path.join(self.output_path, now.strftime("%Y-%m-%d-%H-%M-%S") + '.mp4')

            command = [
                FFMPEG_FILE,
                '-y',
                '-f', 'rawvideo',
                '-pix_fmt', 'bgr24',
                '-s', f'{w}x{h}',
                '-r', '8',
                '-i', '-',
                '-an',
                '-c:v', self.safe_encoder,
                '-pix_fmt', 'yuv420p',
                '-crf', '37',
                output_file
            ]

            process = Popen(command, stdin=PIPE)
            

            while self.recording:
                try:
                    with mss.mss() as sct:
                        sct_img = sct.grab(monitor)
                    frame = cv2.cvtColor(np.array(sct_img), cv2.COLOR_BGRA2BGR)

                    # 添加水印
                    text = "LixAssistantLimbusCompany"
                    font = cv2.FONT_HERSHEY_SIMPLEX
                    font_scale = 4
                    font_color = (128, 128, 128)
                    thickness = 5
                    text_size = cv2.getTextSize(text, font, font_scale, thickness)[0]
                    text_x = (frame.shape[1] - text_size[0]) // 2
                    text_y = (frame.shape[0] + text_size[1]) // 2
                    cv2.putText(frame, text, (text_x, text_y), font, font_scale, font_color, thickness, cv2.LINE_AA)

                    # 添加时间水印
                    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    time_font = cv2.FONT_HERSHEY_SIMPLEX
                    time_font_scale = 2
                    time_font_color = (128, 128, 128)
                    time_thickness = 5
                    time_x = 10
                    time_y = frame.shape[0] - 10
                    cv2.putText(frame, current_time, (time_x, time_y), time_font, time_font_scale,
                                time_font_color, time_thickness, cv2.LINE_AA)

                    process.stdin.write(frame.tobytes())
                    QApplication.processEvents()
                except Exception as e:
                    print(f"录制出错: {e}")
                    continue

            if process:
                process.stdin.close()
                process.wait()

            self.finished.emit()
            self.check_video_count_after_recording()

    def stop_recording(self):
        self.recording = False


screen_record_thread = ScreenRecorderThread()


# class ScreenRecorderDemo(QWidget):
#     def __init__(self):
#         super().__init__()
#         self.initUI()
#         self.recording = False
#         self.sct = mss.mss()
#         self.recording_enabled = False
#         self.process = None

#     def set_recording_enabled(self, enabled):
#         """设置录屏功能是否启用"""
#         self.recording_enabled = enabled

#     def get_output_path(self):
#         return VIDEO_DIR

#     def initUI(self):
#         self.start_button = QPushButton('开始录制', self)
#         self.start_button.clicked.connect(self.start_recording)

#         self.stop_button = QPushButton('停止录制', self)
#         self.stop_button.clicked.connect(self.stop_recording)
#         self.stop_button.setEnabled(False)

#         layout = QVBoxLayout()
#         layout.addWidget(self.start_button)
#         layout.addWidget(self.stop_button)

#         self.setLayout(layout)
#         self.setWindowTitle('屏幕录制')
#         self.show()

#     def start_recording(self):
#         if not self.recording:
#             self.recording = True
#             self.start_button.setEnabled(False)
#             self.stop_button.setEnabled(True)

#             # 获取屏幕尺寸
#             with mss.mss() as sct:
#                 monitor = sct.monitors[0]
#                 w = monitor['width']
#                 h = monitor['height']
#             monitor = {"top": 0, "left": 0, "width": w, "height": h}

#             # 按指定格式命名视频
#             now = datetime.now()
#             # output_file = os.path.join(self.get_output_path(), now.strftime("%Y-%m-%d-%H-%M-%S") + '.mp4')  # 使用 .mp4 格式
#             output_file = os.path.join(self.get_output_path(), ("test_ffmpeg") + '.mp4')  # 使用 .mp4 格式

#             # 构建 ffmpeg 命令
#             command = [
#                 FFMPEG_FILE,
#                 '-y',  # 覆盖已存在的文件
#                 '-f', 'rawvideo',
#                 '-pix_fmt', 'rgb24',
#                 '-s', f'{w}x{h}',
#                 '-r', '8',
#                 '-i', '-',  # 从标准输入读取数据
#                 '-pix_fmt', 'yuv420p',
#                 '-vcodec', 'libx264',
#                 '-crf', '37',
#                 output_file
#             ]

#             # 启动 ffmpeg 进程
#             self.process = Popen(command, stdin=PIPE)

#             # 开始录制循环
#             while self.recording:
#                 # 截取屏幕
#                 sct_img = self.sct.grab(monitor)
#                 frame = np.array(sct_img)
#                 frame = cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)

#                 # 添加水印
#                 text = "LixAssistantLimbusCompany"
#                 font = cv2.FONT_HERSHEY_SIMPLEX
#                 font_scale = 4
#                 font_color = (128, 128, 128)
#                 thickness = 5
#                 text_size = cv2.getTextSize(text, font, font_scale, thickness)[0]
#                 text_x = (frame.shape[1] - text_size[0]) // 2
#                 text_y = (frame.shape[0] + text_size[1]) // 2
#                 cv2.putText(frame, text, (text_x, text_y), font, font_scale, font_color, thickness, cv2.LINE_AA)

#                 # 添加时间水印
#                 current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
#                 time_font = cv2.FONT_HERSHEY_SIMPLEX
#                 time_font_scale = 2
#                 time_font_color = (128, 128, 128)
#                 time_thickness = 5
#                 time_x = 10
#                 time_y = frame.shape[0] - 10
#                 cv2.putText(frame, current_time, (time_x, time_y), time_font, time_font_scale,
#                             time_font_color, time_thickness, cv2.LINE_AA)

#                 # 写入视频帧
#                 self.process.stdin.write(
#                     cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
#                     .astype(np.uint8)
#                     .tobytes()
#                 )
#                 QApplication.processEvents()

#     def stop_recording(self):
#         if self.recording:
#             self.recording = False
#             self.start_button.setEnabled(True)
#             self.stop_button.setEnabled(False)
#             # 停止录制
#             if self.process:
#                 self.process.stdin.close()
#                 self.process.wait()
#             self.sct.close()


# if __name__ == '__main__':
#     ignoreScaleAndDpi()
#     app = QApplication(sys.argv)
#     recorder = ScreenRecorderDemo()
#     sys.exit(app.exec_())