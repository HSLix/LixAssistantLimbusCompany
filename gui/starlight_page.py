from PyQt5.QtWidgets import QFrame, QVBoxLayout,QWidget, QGridLayout,QHBoxLayout
from qfluentwidgets import StrongBodyLabel, PushButton, ImageLabel, CheckBox, LargeTitleLabel
import os
import json
from PyQt5.QtCore import Qt, pyqtSignal

from i18n import _, getLang
from globals import CONFIG_DIR, GUI_DIR, starlight_name


class StarlightPage(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.setObjectName("StarlightPage")
        self.vBoxLayout = QVBoxLayout(self)
        
        # 标题
        self.titleLabel = LargeTitleLabel(_('Edit Starlight'), self)
        self.titleLabel.setAlignment(Qt.AlignCenter)
        self.vBoxLayout.addWidget(self.titleLabel)
        
        # 创建网格布局容器
        self.gridWidget = QWidget()
        self.gridLayout = QGridLayout(self.gridWidget)
        self.vBoxLayout.addWidget(self.gridWidget)
        
        # 创建10个可点击的框
        self.starlight_boxes = []
        for i in range(10):
            box = StarlightBox(i, self)
            row = i // 5  # 第一行0-4，第二行5-9
            col = i % 5   # 每行5个
            self.gridLayout.addWidget(box, row, col)
            self.starlight_boxes.append(box)
        
        # 按钮布局
        self.buttonLayout = QHBoxLayout()
        self.vBoxLayout.addLayout(self.buttonLayout)
        
        # 保存、恢复和全部取消按钮
        self.cancelAllButton = PushButton(_('Cancel All'), self)
        self.saveButton = PushButton(_('Save'), self)
        self.restoreButton = PushButton(_('Restore'), self)
        
        
        self.buttonLayout.addWidget(self.restoreButton)
        self.buttonLayout.addWidget(self.cancelAllButton)
        self.buttonLayout.addWidget(self.saveButton)
        
        # 连接信号
        self.saveButton.clicked.connect(self.save_config)
        self.restoreButton.clicked.connect(self.restore_config)
        self.cancelAllButton.clicked.connect(self.cancel_all_selection)
        
        # 初始化选择列表
        self.selected_indices = []
        
        # 按照 starlight_name 顺序设置图片
        self.set_starlight_images()
        
        # 连接所有框的点击信号
        for i, box in enumerate(self.starlight_boxes):
            box.clicked.connect(lambda index=i: self.on_box_clicked(index))
        
        # 初始化配置
        self.load_config()
    
    def on_box_clicked(self, box_index):
        """当任何框被点击时，处理选择逻辑"""
        box = self.starlight_boxes[box_index]
        
        # 切换选中状态
        new_selected = not box.is_selected
        box.set_selected(new_selected)
        
        # 更新选择顺序
        if new_selected:
            # 添加到选择列表
            if box_index not in self.selected_indices:
                self.selected_indices.append(box_index)
        else:
            # 从选择列表移除
            if box_index in self.selected_indices:
                self.selected_indices.remove(box_index)
        
        # 更新所有框的顺序显示
        self.update_order_display()
        
        # 标题变红表示有未保存的更改
        self.titleLabel.setStyleSheet("color: red;")
    
    def save_config(self):
        """保存配置"""
        config = {}
        # 只保存选中的星光顺序
        for order, box_index in enumerate(self.selected_indices, 1):
            box = self.starlight_boxes[box_index]
            # 从图片路径中提取文件名（去除.png后缀）
            image_name = os.path.basename(box.image_path)
            if image_name.endswith('.png'):
                image_name = image_name[:-4]  # 去除.png后缀
            
            config[f'starlight_{order-1}'] = {
                'name': image_name,
                'order': order
            }
        
        config_path = os.path.join(CONFIG_DIR, 'starlight_config.json')
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
        
        self.titleLabel.setStyleSheet("color: black;")
    
    def restore_config(self):
        """恢复配置"""
        self.load_config()
        self.titleLabel.setStyleSheet("color: black;")
    
    def load_config(self):
        """加载配置"""
        config_path = os.path.join(CONFIG_DIR, 'starlight_config.json')
        if os.path.exists(config_path):
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
            
            # 重置选择状态
            self.selected_indices = []
            for box in self.starlight_boxes:
                box.set_selected(False)
                box.set_order(0)
            
            # 加载选中的星光
            for key, value in config.items():
                if 'name' in value:
                    # 找到对应的星光框
                    image_name = value['name']
                    image_path = os.path.join(GUI_DIR, f"{image_name}.png")
                    
                    # 找到对应的框索引
                    for i, box in enumerate(self.starlight_boxes):
                        if box.image_path == image_path:
                            order = value.get('order', 1)
                            self.selected_indices.append(i)
                            box.set_selected(True)
                            box.set_order(order)
                            break
            
            # 更新顺序显示
            self.update_order_display()
    
    def set_starlight_images(self):
        """按照 starlight_name 顺序设置图片"""
        for i, box in enumerate(self.starlight_boxes):
            if i < len(starlight_name):
                image_path = os.path.join(GUI_DIR, starlight_name[i])
                box.set_image(image_path + ".png")
                box.set_order(0)  # 初始顺序为0，显示为??
    
    def update_order_display(self):
        """更新所有框的顺序显示"""
        # 重置所有未选中框的顺序
        for i, box in enumerate(self.starlight_boxes):
            if i not in self.selected_indices:
                box.set_order(0)  # 显示为??
        
        # 设置选中框的顺序
        for order, box_index in enumerate(self.selected_indices, 1):
            self.starlight_boxes[box_index].set_order(order)
    
    def cancel_all_selection(self):
        """取消所有选中状态"""
        # 清空选择列表
        self.selected_indices = []
        
        # 重置所有框的选中状态和顺序
        for box in self.starlight_boxes:
            box.set_selected(False)
            box.set_order(0)  # 显示为??
        
        # 标题变红表示有未保存的更改
        self.titleLabel.setStyleSheet("color: red;")


class StarlightBox(QFrame):
    def __init__(self, index, parent=None):
        super().__init__(parent=parent)
        self.index = index
        self.image_path = ""
        self.order = 0
        self.is_selected = False
        
        self.setFixedSize(150, 110)
        self.setStyleSheet("""
            QFrame {
                border: 2px solid #ccc;
                border-radius: 8px;
                background-color: white;
            }
            QFrame:hover {
                border-color: #0078d4;
                background-color: #f0f0f0;
            }
            QFrame[selected="true"] {
                border-color: #4CAF50;
                background-color: #f0fff0;
            }
        """)
        
        self.vBoxLayout = QVBoxLayout(self)
        
        # 图片标签
        self.imageLabel = ImageLabel(self)
        self.imageLabel.setFixedSize(135, 90)
        self.imageLabel.setAlignment(Qt.AlignCenter)
        self.vBoxLayout.addWidget(self.imageLabel, alignment=Qt.AlignCenter)
        
        # 顺序标签
        self.orderLabel = StrongBodyLabel("??", self)
        self.orderLabel.setAlignment(Qt.AlignCenter)
        self.orderLabel.setStyleSheet("color: red; font-weight: bold; font-size: 15px")
        self.vBoxLayout.addWidget(self.orderLabel)
        
        # 设置默认图片
        self.set_image(os.path.join(GUI_DIR, "default_starlight.png"))
    
    def set_image(self, image_path):
        """设置图片"""
        self.image_path = image_path
        if os.path.exists(image_path):
            self.imageLabel.setImage(image_path)
        else:
            # 设置默认图片或占位符
            self.imageLabel.setText("No Image")
    
    def set_order(self, order):
        """设置顺序"""
        self.order = order
        if order > 0:
            self.orderLabel.setText(str(order))
        else:
            self.orderLabel.setText("??")
    
    def set_selected(self, selected):
        """设置选中状态"""
        self.is_selected = selected
        self.setProperty("selected", selected)
        self.style().unpolish(self)
        self.style().polish(self)
    
    def mousePressEvent(self, event):
        """鼠标点击事件"""
        if event.button() == Qt.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)
    
    # 定义点击信号
    clicked = pyqtSignal()