# coding:utf-8
import os
from PyQt5.QtCore import QTimer,QSize,  QPoint
from PyQt5.QtGui import QMovie, QPainter, QPixmap
from PyQt5.QtWidgets import  QLabel

from collections import deque
import random


from globals import GUI_DIR
from i18n import _

class GifPlayer(QLabel):
    def __init__(self, parent=None):
        super().__init__(parent)
        # 新增配置存储
        self.gif_configs = {}  # 存储特定GIF的配置 {gif_name: {pos, size}}
        self._init_playback_components()
        self.wait_count = 0
        self.next_random_threshold = random.randint(3, 8)

    def _init_playback_components(self):
        """初始化播放组件"""
        self.loop_gif = os.path.join(GUI_DIR, "magic_girl_waiting.gif")
        self.current_gif = None
        self.movie = QMovie(self)
        self.movie.setCacheMode(QMovie.CacheAll)
        self.play_queue = deque()
        self.background_pixmap = QPixmap(os.path.join(GUI_DIR, "containment_unit.png"))

        # 逐帧播放定时器
        self.frame_timer = QTimer(self)
        self.frame_timer.timeout.connect(self._update_frame)
        self._load_gif(self.loop_gif)

        self.set_gif_config("magic_girl_heart.gif", QPoint(15, 30), QSize(640, 400))
        self.set_gif_config("magic_girl_waiting.gif", QPoint(20, 100), QSize(500, 300))
        self.set_gif_config("magic_girl_shaking_hand.gif", QPoint(40, 100), QSize(510, 300))
        self.set_gif_config("magic_girl_blow_kiss.gif", QPoint(0, 30), QSize(640, 370))
        self.set_gif_config("magic_girl_black1.gif", QPoint(70, 125), QSize(580, 290))
        self.set_gif_config("magic_girl_black2.gif", QPoint(-5, -30), QSize(870, 500))

    def _load_gif(self, gif_path):
        """加载GIF"""
        self.current_gif = gif_path
        self.movie.stop()
        self.movie.setFileName(gif_path)
        self.movie.start()

        # 初始化播放参数
        self.total_frames = self.movie.frameCount()
        self.current_frame = 0
        self.frame_timer.start(60)

    def _update_frame(self):
        """更新帧"""
        if self.current_frame < self.total_frames:
            self.movie.jumpToFrame(self.current_frame)
            self.current_frame += 1
            self.update()
        else:
            self.frame_timer.stop()
            self._handle_gif_finished()

    def _handle_gif_finished(self):
        """完成处理"""
        # print(f"GIF播放完成: {self.current_gif}")
        if self.current_gif == self.loop_gif:
            self.wait_count += 1
            self._check_random_insertion()
        self._play_next()

    def _play_next(self):
        if self.play_queue:
            next_gif = self.play_queue.popleft()
            self._load_gif(next_gif)
            self.wait_count = 0
        else:
            self._load_gif(self.loop_gif)

    def _check_random_insertion(self):
        if self.wait_count >= self.next_random_threshold:
            self._add_random_gif()
            self.next_random_threshold = random.randint(3, 8)
            self.wait_count = 0

    def _add_random_gif(self):
        choices = [
                    "shaking_hand",
                    "blow_kiss", 
                    # "black1",
                    # "heart",
                    # "white_night"
                    ]
        self.push_gif_to_queue(random.choice(choices))

    def push_gif_to_queue(self, gif_name):
        if (len(self.play_queue) > 1):
            return
        gif_path = os.path.join(GUI_DIR, f"magic_girl_{gif_name}.gif")
        self.play_queue.append(gif_path)
        if (gif_name == "black1"):
            self.play_queue.append(os.path.join(GUI_DIR, "magic_girl_black2.gif"))

    def stop_playing(self):
        self.play_queue.clear()
        self.movie.stop()
        self.frame_timer.stop()
        self._load_gif(self.loop_gif)

    def set_gif_config(self, gif_name, pos, size):
        """设置特定GIF的位置和大小"""
        self.gif_configs[gif_name] = {'pos': pos, 'size': size}

    def set_play_area(self, x, y, width, height):
        """设置 GIF 播放区域"""
        self.setGeometry(x, y, width, height)

    def set_scale(self, width, height):
        """设置 GIF 缩放大小"""
        self.setFixedSize(width, height)
        self.movie.setScaledSize(QSize(width, height))

    def paintEvent(self, event):
        """绘制背景和GIF"""
        painter = QPainter(self)
        # 绘制背景
        painter.drawPixmap(self.rect(), self.background_pixmap)

        # 绘制GIF
        if self.movie.state() == QMovie.Running:
            pixmap = self.movie.currentPixmap()
            if not pixmap.isNull():
                gif_name = os.path.basename(self.current_gif)
                if gif_name in self.gif_configs:
                    # 应用配置的位置和大小
                    config = self.gif_configs[gif_name]
                    pos = config['pos']
                    size = config['size']
                    # 缩放GIF
                    scaled_pixmap = pixmap.scaled(size.width(), size.height())
                    # 绘制GIF
                    painter.drawPixmap(pos, scaled_pixmap)
                else:
                    # 如果没有配置，默认居中显示
                    x = (self.width() - pixmap.width()) // 2
                    y = (self.height() - pixmap.height()) // 2
                    painter.drawPixmap(x, y, pixmap)
