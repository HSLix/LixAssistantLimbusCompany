"""只读识别调试页：共用固定截图，分别保留各方式的选区与结果。"""

from pathlib import PurePosixPath

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QSplitter, QTreeWidgetItem, QSizePolicy, QScrollArea
from qfluentwidgets import TreeWidget, DoubleSpinBox, SpinBox, CheckBox, LineEdit, BodyLabel, PlainTextEdit, SegmentedWidget

from .developer_gui import OcrView, button, capture_tags
from .i18n import tr


class RecognitionPage(QWidget):
    """三种识别共用一张原图；方式切换仅恢复状态，不触发识别。"""

    def __init__(self, window):
        super().__init__()
        self.window, self.host = window, window.host
        self.snapshot = None
        self.method = "template"
        self.states = {key: {"region": None, "items": [], "text": ""} for key in ("template", "feature", "ocr")}
        self.signature = None
        self.refresh_pending = False
        self.busy = False
        layout = QVBoxLayout(self)
        layout.addWidget(BodyLabel(tr('Recognition Lab')))
        self.methods = SegmentedWidget(self)
        self.methods.addItem('template', tr('Template Match'))
        self.methods.addItem('feature', tr('Feature Match (SIFT)'))
        self.methods.addItem('ocr', tr('OCR'))
        self.methods.setCurrentItem('template')
        self.methods.setFixedWidth(420)
        layout.addWidget(self.methods)
        row = QHBoxLayout()
        self.capture_button = button(tr('Capture screenshot'), self.capture, row)
        self.full_button = button(tr('Match full image'), self.full_image, row)
        self.run_button = button(tr('Match selected region'), self.run_recognition, row)
        row.addStretch()
        layout.addLayout(row)
        hint = BodyLabel(tr('Capture does not run recognition. Release a selection to process it, or use the full-image button. Korean OCR is not supported.'))
        hint.setWordWrap(True)
        layout.addWidget(hint)
        split = QSplitter(Qt.Orientation.Horizontal)
        layout.addWidget(split, 1)
        self.assets_panel = left = QWidget()
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
        right = QWidget()
        split.addWidget(right)
        split.setStretchFactor(1, 2)
        upper_layout = QVBoxLayout(right)
        self.view = OcrView()
        upper_layout.addWidget(self.view, 3)
        self.results = PlainTextEdit()
        self.results.setReadOnly(True)
        self.results.setAccessibleName(tr('Template match results'))
        self.results.setMinimumHeight(80)
        upper_layout.addWidget(self.results, 1)
        self.parameters_panel = lower = QWidget()
        lower_layout = QVBoxLayout(lower)
        heading = QHBoxLayout()
        heading.addWidget(BodyLabel(tr('Match parameters')))
        heading.addStretch()
        self.reset_parameters_button = button(tr('Restore defaults'), self.reset_parameters, heading)
        lower_layout.addLayout(heading)
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
        self.template_parameters = QWidget()
        self.template_parameters.setLayout(form)
        lower_layout.addWidget(self.template_parameters)
        self.feature_parameters = QScrollArea()
        self.feature_parameters.setWidgetResizable(True)
        self.feature_parameters.setMinimumWidth(235)
        feature_body = QWidget()
        feature_form = QFormLayout(feature_body)
        feature_form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapAllRows)
        self.feature_controls = {}
        for key, label, value in (("grayscale", tr('Grayscale before enhancement'), True),
                                  ("clahe", tr('CLAHE enhancement'), True),
                                  ("precise_upscale", tr('Precise SIFT upscale'), False),
                                  ("nms", tr('Suppress overlapping matches (NMS)'), True)):
            control = CheckBox(label)
            control.setChecked(value)
            control.toggled.connect(self.clear_feature_results)
            self.feature_controls[key] = control
            feature_form.addRow(control)
        specs = (
            ("scale", tr('Image scale'), 3, 1, 5, 0),
            ("nfeatures", tr('Feature limit (0: unlimited)'), 0, 0, 100000, 0),
            ("n_octave_layers", tr('Octave layers'), 3, 1, 10, 0),
            ("contrast_threshold", tr('Contrast threshold'), .04, .001, 1, 3),
            ("edge_threshold", tr('Edge threshold'), 10., .1, 100, 2),
            ("sigma", tr('Sigma'), 1.6, .1, 10, 2),
            ("pair_ratio", tr('Descriptor pair ratio'), .75, .01, .99, 3),
            ("ransac_threshold", tr('Geometry tolerance (original px)'), 4 / 3, .001, 100, 6),
            ("min_inliers", tr('Minimum inliers'), 6, 4, 100000, 0),
            ("min_inlier_ratio", tr('Minimum inlier ratio'), .5, .001, 1, 3),
            ("min_scale", tr('Minimum target scale'), .5, .001, 100, 3),
            ("max_scale", tr('Maximum target scale'), 2., .001, 100, 3),
            ("max_deformation", tr('Maximum deformation ratio'), 2., 1, 100, 3),
            ("min_coverage", tr('Minimum inlier coverage'), .1, 0, 1, 3),
            ("nms_iou_threshold", tr('NMS IoU threshold'), .5, 0, 1, 3),
        )
        for key, label, value, low, high, decimals in specs:
            control = DoubleSpinBox() if decimals else SpinBox()
            control.setRange(low, high)
            if decimals:
                control.setDecimals(decimals)
                control.setSingleStep(.01)
            control.setValue(value)
            control.valueChanged.connect(self.clear_feature_results)
            self.feature_controls[key] = control
            feature_form.addRow(label, control)
        self.feature_defaults = {key: control.isChecked() if isinstance(control, CheckBox) else control.value()
                                 for key, control in self.feature_controls.items()}
        note = BodyLabel(tr('SIFT uses grayscale features. Score = inliers; ratio is local to each target.'))
        note.setWordWrap(True)
        feature_form.addRow(note)
        coverage_note = BodyLabel(tr('Target scale is relative to the original template. Coverage checks both images; higher coverage or lower deformation is stricter.'))
        coverage_note.setWordWrap(True)
        feature_form.addRow(coverage_note)
        self.feature_parameters.setWidget(feature_body)
        self.feature_parameters.hide()
        lower_layout.addWidget(self.feature_parameters, 1)
        self.region = BodyLabel()
        self.region.setWordWrap(True)
        lower_layout.addWidget(self.region)
        lower_layout.addStretch()
        split.addWidget(lower)

        self.tree.currentItemChanged.connect(self.select_template)
        self.view.selected.connect(self.selection_changed)
        self.methods.currentItemChanged.connect(self.switch_method)
        self.clear_results()
        split.setSizes([220, 560, 230])

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
        self.preview.setVisible(False)
        self.clear_results()
        self.clear_feature_results()
        selected = self.selected_template()
        self.selection.setText(tr('No template selected.'))
        self.selection.setToolTip('')
        if selected:
            name, digest = selected
            self.selection.setText(tr('Single image: {0}').format(f'{name}\n{digest[:12]}….png') if digest
                                   else tr('Asset group: {0}').format(name))
            self.selection.setToolTip(f'{name}/{digest}.png' if digest else name)
            if digest:
                self.preview.setVisible(True)
                def shown(content):
                    image = QImage.fromData(content)
                    if image.isNull():
                        raise ValueError('Asset image cannot be decoded.')
                    self.preview.setPixmap(QPixmap.fromImage(image).scaled(
                        280, 150, Qt.AspectRatioMode.KeepAspectRatio))
                self.window.launch(lambda: self.host.template_preview(name, digest), shown)
        self.render(self.busy)

    def save_state(self):
        """只保留方式相关状态，不复制截图像素。"""
        self.states[self.method] = dict(region=dict(self.view.region) if self.view.region else None,
                                        items=self.view.items, text=self.results.toPlainText())

    def switch_method(self, method):
        """恢复当前方式的区域与标注；画布原图不重新赋值。"""
        if method == self.method:
            return
        self.save_state()
        self.method = method
        state = self.states[method]
        self.view.region = dict(state["region"]) if state["region"] else None
        self.view.anchor = None
        self.view.magnifier.hide()
        self.view.items = state["items"]
        self.view.update()
        self.results.setPlainText(state["text"])
        matching = method != "ocr"
        self.assets_panel.setVisible(matching)
        self.parameters_panel.setVisible(matching)
        self.template_parameters.setVisible(method == "template")
        self.feature_parameters.setVisible(method == "feature")
        self.full_button.setText(tr('Match full image') if matching else tr('Recognize full image'))
        self.results.setAccessibleName(tr('Feature match results') if method == "feature" else
                                      tr('Template match results') if matching else tr('OCR results'))
        self.render(self.busy)
        if matching:
            self.refresh_pending = True
            self.refresh_assets()

    def clear_results(self, *_):
        """素材和参数只使模板结果失效，不清除 OCR 的结果。"""
        self.states["template"]["items"] = []
        self.states["template"]["text"] = ""
        if self.method == "template":
            self.clear_current_results()

    def clear_current_results(self):
        self.view.items = []
        self.view.update()
        self.results.clear()
        self.region.setText(tr('Search region: {0}').format(self.view.region or tr('Full image')))
        self.save_state()

    def clear_feature_results(self, *_):
        """SIFT 参数只使自身结果失效；不改变原图和其他方式。"""
        self.states["feature"]["items"] = []
        self.states["feature"]["text"] = ""
        if self.method == "feature":
            self.clear_current_results()
        self.render(self.busy)

    def selection_changed(self, region):
        self.clear_current_results()
        self.render(self.busy)
        if region:
            self.run_recognition()

    def parameters_changed(self):
        self.clear_results()
        self.render(self.busy)

    def reset_parameters(self):
        """恢复当前匹配方式的默认参数；保留选区和素材，不自动执行。"""
        if self.method == "feature":
            for key, control in self.feature_controls.items():
                value = self.feature_defaults[key]
                if isinstance(control, CheckBox):
                    control.setChecked(value)
                else:
                    control.setValue(value)
            self.clear_feature_results()
        elif self.method == "template":
            self.threshold.setValue(0.9)
            self.iou.setValue(0.5)
            self.nms.setChecked(True)
            self.tags.clear()
            self.parameters_changed()

    def capture(self):
        """仅成功时提交新截图；失败完整保留原图、选区与结果。"""
        def shown(snapshot):
            self.snapshot = snapshot
            for key in self.states:
                self.states[key] = dict(region=None, items=[], text="")
            self.view.blockSignals(True)
            try:
                self.view.set_image(snapshot[0], snapshot[1])
            finally:
                self.view.blockSignals(False)
            self.clear_current_results()
            self.render(self.busy)
        self.window.launch(lambda: self.host.capture(update_preview=False), shown)

    def full_image(self):
        self.view.region = None
        self.run_recognition()

    def run_recognition(self):
        """在主线程固定输入；执行失败清本方式结果，保留截图与选区。"""
        if self.snapshot is None or (self.method != "ocr" and not self.selected_template()):
            return
        self.clear_current_results()
        snapshot, method = self.snapshot, self.method
        region = dict(self.view.region) if self.view.region else None
        def operation():
            if method == "ocr":
                worker = lambda: self.host.recognize_preview(snapshot, region)
            else:
                name, digest = self.selected_template()
                if method == "feature":
                    options = {key: control.isChecked() if isinstance(control, CheckBox) else control.value()
                               for key, control in self.feature_controls.items()}
                    worker = lambda: self.host.match_feature_preview(snapshot, name, digest, region=region, **options)
                else:
                    options = dict(region=region, threshold=self.threshold.value(), nms=self.nms.isChecked(),
                                   nms_iou_threshold=self.iou.value(),
                                   priority_tags=capture_tags(self.tags.text()) if digest is None else None)
                    worker = lambda: self.host.match_template_preview(snapshot, name, digest, **options)
            def shown(result):
                if method == "ocr":
                    self.view.items = result["items"]
                    text = '\n'.join(f'{number}. {item["text"]}'
                                     for number, item in enumerate(result["items"], 1)) or tr('No text recognized.')
                else:
                    self.view.items = [{"box": match} for match in result]
                    text = '\n'.join(
                        (f'{number}. ' + tr('Inliers: {0}; ratio: {1}').format(match['inliers'], f'{match["inlier_ratio"]:.3f}') + ' · '
                         + tr('Coverage: template {0}, target {1}').format(
                             f'{match["template_coverage"]:.3f}', f'{match["target_coverage"]:.3f}') + ' · '
                         if method == "feature" else f'{number}. score={match["score"]:.6f} · ') +
                        f'({match["x"]}, {match["y"]}, {match["width"]}, {match["height"]}) · '
                        f'centerxy={match["centerxy"]} · {match["path"]}'
                        for number, match in enumerate(result, 1)) or tr('No matches.')
                self.view.update()
                self.results.setPlainText(text)
                self.save_state()
            self.window.launch(worker, shown)
        self.window._interact(operation)

    def render(self, busy):
        self.busy = busy
        selected = self.selected_template()
        matching = self.method != "ocr"
        for control in (self.methods, self.tree, self.capture_button, self.threshold, self.nms, self.view,
                        self.reset_parameters_button):
            control.setEnabled(not busy)
        self.iou.setEnabled(not busy and self.nms.isChecked())
        self.tags.setEnabled(not busy and bool(selected) and selected[1] is None)
        for key, control in self.feature_controls.items():
            control.setEnabled(not busy and (key != 'nms_iou_threshold' or self.feature_controls['nms'].isChecked()))
        ready = not busy and self.snapshot is not None and (not matching or bool(selected))
        self.full_button.setEnabled(ready)
        self.run_button.setVisible(matching)
        self.run_button.setEnabled(ready and bool(self.view.region))
        self.region.setText(tr('Search region: {0}').format(self.view.region or tr('Full image')))
        if not busy and self.refresh_pending and self.isVisible():
            QTimer.singleShot(0, self.refresh_assets)
