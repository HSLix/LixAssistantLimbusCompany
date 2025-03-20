# coding: utf-8
import sys
import cv2
import numpy as np
from PyQt5.QtWidgets import QApplication, QWidget, QPushButton, QVBoxLayout
from globals import VIDEO_DIR
import os
import mss
from datetime import datetime
from PyQt5.QtCore import QThread, pyqtSignal

from globals import ignoreScaleAndDpi



class ScreenRecorderThread(QThread):
    finished = pyqtSignal()

    def __init__(self):
        super().__init__()
        ignoreScaleAndDpi()
        self.recording = False
        self.out = None
        #self.sct = mss.mss()
        self.recording_enabled = False
        self.output_path = VIDEO_DIR

    def set_recording_enabled(self, enabled):
        """设置录屏功能是否启用"""
        self.recording_enabled = enabled


    def run(self):
        if not self.recording:
            self.recording = True

            # 获取屏幕尺寸
            # desktop = QApplication.desktop().availableGeometry()
            # w, h = desktop.width(), desktop.height()
            with mss.mss() as sct:
                monitor = sct.monitors[0]
                w = monitor['width']
                h = monitor['height']
            monitor = {"top": 0, "left": 0, "width": w, "height": h}

            # 定义视频编码器和输出文件
            fourcc = cv2.VideoWriter_fourcc(*'XVID')  # 使用 XVID 编码器
            if not os.path.exists(self.output_path):
                os.makedirs(self.output_path)
            # 按指定格式命名视频
            now = datetime.now()
            output_file = os.path.join(self.output_path, now.strftime("%Y-%m-%d-%H-%M-%S") + '.avi')  # 使用 .avi 格式
            self.out = cv2.VideoWriter(output_file, fourcc, 8, (w, h))

            # 开始录制循环
            while self.recording:
                # 截取屏幕
                with mss.mss() as sct:
                    sct_img = sct.grab(monitor)
                frame = np.array(sct_img)
                frame = cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)

                # 添加水印
                text = "LixAssistantLimbusCompany"
                font = cv2.FONT_HERSHEY_SIMPLEX
                font_scale = 4
                font_color = (128, 128, 128)
                thickness = 15
                text_size = cv2.getTextSize(text, font, font_scale, thickness)[0]
                text_x = (frame.shape[1] - text_size[0]) // 2
                text_y = (frame.shape[0] + text_size[1]) // 2
                overlay = frame.copy()
                cv2.putText(overlay, text, (text_x, text_y), font, font_scale, font_color, thickness, cv2.LINE_AA)

                # 确保 overlay 和 frame 的大小相等
                if overlay.shape != frame.shape:
                    overlay = cv2.resize(overlay, (frame.shape[1], frame.shape[0]))

                alpha = 0.2
                frame = cv2.addWeighted(overlay, alpha, frame, 1 - alpha, 0)

                # 添加时间水印
                current_time = datetime.now().strftime("%Y-%m-%d-%H-%M-%S")
                time_font = cv2.FONT_HERSHEY_SIMPLEX
                time_font_scale = 2
                time_font_color = (128, 128, 128)
                time_thickness = 5
                time_x = 10
                time_y = frame.shape[0] - 10
                cv2.putText(frame, current_time, (time_x, time_y), time_font, time_font_scale,
                            time_font_color, time_thickness, cv2.LINE_AA)

                # 写入视频帧
                self.out.write(frame)
                QApplication.processEvents()

            # 释放视频写入器
            if self.out:
                self.out.release()
            self.finished.emit()

    def stop_recording(self):
        self.recording = False


screen_record_thread = ScreenRecorderThread()


class ScreenRecorderDemo(QWidget):
    def __init__(self):
        super().__init__()
        self.initUI()
        self.recording = False
        self.out = None
        self.sct = mss.mss()
        self.recording_enabled = False

    def set_recording_enabled(self, enabled):
        """设置录屏功能是否启用"""
        self.recording_enabled = enabled

    def get_output_path():
        return VIDEO_DIR

    def initUI(self):
        self.start_button = QPushButton('开始录制', self)
        self.start_button.clicked.connect(self.start_recording)

        self.stop_button = QPushButton('停止录制', self)
        self.stop_button.clicked.connect(self.stop_recording)
        self.stop_button.setEnabled(False)

        layout = QVBoxLayout()
        layout.addWidget(self.start_button)
        layout.addWidget(self.stop_button)

        self.setLayout(layout)
        self.setWindowTitle('屏幕录制')
        self.show()

    def start_recording(self):
        if not self.recording:
            self.recording = True
            self.start_button.setEnabled(False)
            self.stop_button.setEnabled(True)

            # 获取屏幕尺寸
            desktop = QApplication.desktop().availableGeometry()
            w, h = desktop.width(), desktop.height()
            monitor = {"top": 0, "left": 0, "width": w, "height": h}

            # 定义视频编码器和输出文件
            fourcc = cv2.VideoWriter_fourcc(*'XVID')  # 使用 XVID 编码器
            if not os.path.exists(VIDEO_DIR):
                os.makedirs(VIDEO_DIR)
            # 按指定格式命名视频
            now = datetime.now()
            output_file = os.path.join(VIDEO_DIR, now.strftime("%Y-%m-%d-%H-%M-%S") + '.avi')  # 使用 .avi 格式
            self.out = cv2.VideoWriter(output_file, fourcc, 8, (w, h))

            # 开始录制循环
            while self.recording:
                # 截取屏幕
                sct_img = self.sct.grab(monitor)
                frame = np.array(sct_img)
                frame = cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)

                # 添加水印
                text = "LixAssistantLimbusCompany"
                font = cv2.FONT_HERSHEY_SIMPLEX
                font_scale = 4
                font_color = (128, 128, 128)
                thickness = 15
                text_size = cv2.getTextSize(text, font, font_scale, thickness)[0]
                text_x = (frame.shape[1] - text_size[0]) // 2
                text_y = (frame.shape[0] + text_size[1]) // 2
                overlay = frame.copy()
                cv2.putText(overlay, text, (text_x, text_y), font, font_scale, font_color, thickness, cv2.LINE_AA)
                alpha = 0.2
                frame = cv2.addWeighted(overlay, alpha, frame, 1 - alpha, 0)

                # 写入视频帧
                self.out.write(frame)
                QApplication.processEvents()
            return VIDEO_DIR

    def stop_recording(self):
        if self.recording:
            self.recording = False
            self.start_button.setEnabled(True)
            self.stop_button.setEnabled(False)
            # 释放视频写入器
            if self.out:
                self.out.release()
            self.sct.close()


if __name__ == '__main__':
    ignoreScaleAndDpi()
    app = QApplication(sys.argv)
    recorder = ScreenRecorderDemo()
    sys.exit(app.exec_())