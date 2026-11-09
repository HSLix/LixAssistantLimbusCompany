"""只读模板匹配调试页：增量素材树、固定截图及正式参数。"""

from pathlib import PurePosixPath

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QSplitter, QTreeWidgetItem, QSizePolicy
from qfluentwidgets import TreeWidget, DoubleSpinBox, CheckBox, LineEdit, BodyLabel, PlainTextEdit

from .developer_gui import OcrView, button, capture_tags
from .i18n import tr


class TemplateMatchPage(QWidget):
    """调试仅持有本页截图；切换输入清除结果，进入页面只检查文件状态。"""

    def __init__(self, window):
        super().__init__()
        self.window, self.host = window, window.host
        self.snapshot = None
        self.signature = None
        self.refresh_pending = False
        self.busy = False
        layout = QVBoxLayout(self)
        layout.addWidget(BodyLabel(tr('Template Match')))
        hint = BodyLabel(tr('Select an Asset or image. Capture once, adjust parameters, then run on the frozen screenshot.'))
        hint.setWordWrap(True)
        layout.addWidget(hint)
        split = QSplitter(Qt.Orientation.Horizontal)
        layout.addWidget(split, 1)
        left = QWidget()
        left_layout = QVBoxLayout(left)
        self.tree = TreeWidget()
        self.tree.setHeaderLabel(tr('Assets / Templates'))
        self.tree.setMinimumWidth(220)
        left_layout.addWidget(self.tree, 1)
        self.selection = BodyLabel(tr('No template selected.'))
        self.selection.setWordWrap(True)
        self.selection.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self.selection.setTextFormat(Qt.TextFormat.PlainText)
        left_layout.addWidget(self.selection)
        self.preview = BodyLabel()
        self.preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview.setMinimumHeight(150)
        left_layout.addWidget(self.preview)
        split.addWidget(left)
        right = QSplitter(Qt.Orientation.Vertical)
        split.addWidget(right)
        split.setStretchFactor(1, 2)
        upper = QWidget()
        upper_layout = QVBoxLayout(upper)
        row = QHBoxLayout()
        self.capture_button = button(tr('Capture screenshot'), self.capture, row)
        self.full_button = button(tr('Use full image'), self.full_image, row)
        upper_layout.addLayout(row)
        self.view = OcrView()
        upper_layout.addWidget(self.view, 3)
        self.results = PlainTextEdit()
        self.results.setReadOnly(True)
        self.results.setAccessibleName(tr('Template match results'))
        self.results.setMinimumHeight(80)
        upper_layout.addWidget(self.results, 1)
        right.addWidget(upper)
        lower = QWidget()
        lower_layout = QVBoxLayout(lower)
        lower_layout.addWidget(BodyLabel(tr('Match parameters')))
        form = QFormLayout()
        self.threshold = DoubleSpinBox()
        self.iou = DoubleSpinBox()
        for control, value in ((self.threshold, 0.9), (self.iou, 0.5)):
            control.setRange(0, 1)
            control.setDecimals(3)
            control.setSingleStep(0.01)
            control.setValue(value)
            control.valueChanged.connect(self.clear_results)
        self.nms = CheckBox(tr('Suppress overlapping matches (NMS)'))
        self.nms.setChecked(True)
        self.tags = LineEdit()
        self.tags.setPlaceholderText(tr('Group only; comma-separated, empty for no priority'))
        self.tags.textChanged.connect(self.clear_results)
        self.nms.toggled.connect(self.parameters_changed)
        form.addRow(tr('Threshold'), self.threshold)
        form.addRow(self.nms)
        form.addRow(tr('NMS IoU threshold'), self.iou)
        form.addRow(tr('Priority tags'), self.tags)
        lower_layout.addLayout(form)
        self.region = BodyLabel()
        lower_layout.addWidget(self.region)
        self.run_button = button(tr('Run match'), self.run_match, lower_layout)
        right.addWidget(lower)
        right.setStretchFactor(0, 3)
        right.setSizes([500, 240])
        self.tree.currentItemChanged.connect(self.select_template)
        self.view.selected.connect(self.clear_results)
        self.clear_results()
        split.setSizes([300, 700])

    def showEvent(self, event):
        super().showEvent(event)
        self.refresh_pending = True
        QTimer.singleShot(0, self.refresh_assets)

    def refresh_assets(self):
        """后台检查文件状态；未变化时不动树、预览、展开及选择。"""
        if not self.refresh_pending or self.busy or self.window.jobs or not self.isVisible():
            return
        self.refresh_pending = False
        self.window.launch(self.host.template_catalog, self.update_catalog)

    def update_catalog(self, catalog):
        signature, images = catalog
        if signature == self.signature:
            return
        selected = self.selected_template()
        expanded = set()
        def remember(item):
            if item.isExpanded():
                expanded.add(item.data(0, Qt.ItemDataRole.UserRole + 1))
            for index in range(item.childCount()):
                remember(item.child(index))
        remember(self.tree.invisibleRootItem())
        self.tree.blockSignals(True)
        self.tree.clear()
        nodes = {"": self.tree.invisibleRootItem()}
        restore = None
        for relative in images:
            path = PurePosixPath(relative)
            parent = ""
            for segment in path.parts[:-1]:
                key = f"{parent}/{segment}".lstrip("/")
                if key not in nodes:
                    node = QTreeWidgetItem(nodes[parent], [segment])
                    node.setData(0, Qt.ItemDataRole.UserRole + 1, key)
                    node.setExpanded(key in expanded or (self.signature is None and "/" not in key))
                    nodes[key] = node
                parent = key
            if not parent:
                continue
            nodes[parent].setData(0, Qt.ItemDataRole.UserRole, (parent, None))
            leaf = QTreeWidgetItem(nodes[parent], [path.name])
            leaf.setToolTip(0, relative)
            leaf.setData(0, Qt.ItemDataRole.UserRole, (parent, path.stem))
            if selected == (parent, path.stem):
                restore = leaf
            elif selected == (parent, None):
                restore = nodes[parent]
        if restore:
            self.tree.setCurrentItem(restore)
        # Qt 恢复当前叶子时会展开祖先；随后还原用户折叠状态。
        for key, node in nodes.items():
            if key:
                node.setExpanded(key in expanded or (self.signature is None and "/" not in key))
        self.tree.blockSignals(False)
        self.signature = signature
        self.select_template()

    def selected_template(self):
        item = self.tree.currentItem()
        return item.data(0, Qt.ItemDataRole.UserRole) if item else None

    def select_template(self, *_):
        """图片叶子才解码预览；目录选择不批量加载图片。"""
        self.preview.clear()
        self.clear_results()
        selected = self.selected_template()
        self.selection.setText(tr('No template selected.'))
        self.selection.setToolTip('')
        if selected:
            name, digest = selected
            self.selection.setText(tr('Single image: {0}').format(f'{name}\n{digest[:12]}….png') if digest
                                   else tr('Asset group: {0}').format(name))
            self.selection.setToolTip(f'{name}/{digest}.png' if digest else name)
            if digest:
                def shown(content):
                    image = QImage.fromData(content)
                    if image.isNull():
                        raise ValueError('Asset image cannot be decoded.')
                    self.preview.setPixmap(QPixmap.fromImage(image).scaled(
                        280, 150, Qt.AspectRatioMode.KeepAspectRatio))
                self.window.launch(lambda: self.host.template_preview(name, digest), shown)
        self.render(self.busy)

    def clear_results(self, *_):
        self.view.items = []
        self.view.update()
        self.results.clear()
        self.region.setText(tr('Search region: {0}').format(self.view.region or tr('Full image')))

    def parameters_changed(self):
        self.clear_results()
        self.render(self.busy)

    def capture(self):
        self.clear_results()
        def shown(snapshot):
            self.snapshot = snapshot
            self.view.set_image(snapshot[0], snapshot[1])
            self.render(self.busy)
        self.window.launch(lambda: self.host.capture(update_preview=False), shown)

    def full_image(self):
        self.view.region = None
        self.clear_results()

    def run_match(self):
        """启动前固定本次选择和参数，失败时不保留旧结果。"""
        self.clear_results()
        if self.snapshot is None or not self.selected_template():
            return
        def operation():
            name, digest = self.selected_template()
            options = dict(region=dict(self.view.region) if self.view.region else None,
                           threshold=self.threshold.value(), nms=self.nms.isChecked(),
                           nms_iou_threshold=self.iou.value(),
                           priority_tags=capture_tags(self.tags.text()) if digest is None else None)
            snapshot = self.snapshot
            def shown(matches):
                self.view.items = [{"box": match} for match in matches]
                self.view.update()
                self.results.setPlainText('\n'.join(
                    f'{number}. score={match["score"]:.6f} · '
                    f'({match["x"]}, {match["y"]}, {match["width"]}, {match["height"]}) · '
                    f'centerxy={match["centerxy"]} · {match["path"]}'
                    for number, match in enumerate(matches, 1)) or tr('No matches.'))
            self.window.launch(lambda: self.host.match_template_preview(snapshot, name, digest, **options), shown)
        self.window._interact(operation)

    def render(self, busy):
        self.busy = busy
        selected = self.selected_template()
        for control in (self.tree, self.capture_button, self.threshold, self.nms, self.view):
            control.setEnabled(not busy)
        self.iou.setEnabled(not busy and self.nms.isChecked())
        self.tags.setEnabled(not busy and bool(selected) and selected[1] is None)
        self.full_button.setEnabled(not busy and self.snapshot is not None)
        self.run_button.setEnabled(not busy and self.snapshot is not None and bool(selected))
        if not busy and self.refresh_pending and self.isVisible():
            QTimer.singleShot(0, self.refresh_assets)
