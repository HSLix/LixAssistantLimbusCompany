"""覆盖日志双向分页、快照尾行、筛选定位、延迟图片和动作标注。

从项目根目录运行：
QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest -q tests/test_run_logs.py
"""

import json
import time
from threading import Event

import pytest

from lalc.run_logs import image_path, lines, read_page, snapshot


def write_logs(root, count=2000):
    path = root / 'traces' / '1.jsonl'
    path.parent.mkdir(exist_ok=True)
    records = [dict(event='component_log', sequence=i + 1, level='info', logical_name='steps.example',
                    recorded_at=f'2026-11-06T12:{i // 60:02}:{i % 60:02}Z',
                    message=f'中文日志 {i} ' + 'x' * (i % 127)) for i in range(count)]
    path.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in records), encoding="utf-8")
    return path, records


def test_chunk_boundaries_and_reverse_forward_agree(tmp_path):
    path, records = write_logs(tmp_path)
    end = path.stat().st_size
    forward = list(lines(path, 0, end, False, Event()))
    backward = list(lines(path, 0, end, True, Event()))
    assert backward == forward[::-1]
    assert [json.loads(raw) for _, _, raw in forward] == records
    boundary = snapshot(tmp_path, 1)
    newest = read_page(tmp_path, 1, boundary)['rows']
    assert [r['record']['sequence'] for r in newest] == list(range(2000, 1940, -1))
    older = read_page(tmp_path, 1, boundary, end=newest[-1]['offset'])['rows']
    assert older[0]['record']['sequence'] == 1940
    newer = read_page(tmp_path, 1, boundary, start=older[0]['end'], reverse=False)['rows']
    assert [r['offset'] for r in newer] == [r['offset'] for r in newest]


def test_snapshot_ignores_partial_tail_and_retains_old_boundary(tmp_path):
    path, _ = write_logs(tmp_path, 2)
    old = snapshot(tmp_path, 1)
    with path.open('ab') as stream:
        stream.write(b'{"event":"component_log", "level":"info", "message":"new"')
    partial = snapshot(tmp_path, 1)
    assert partial[2] == old[2]
    assert len(read_page(tmp_path, 1, partial)['rows']) == 2
    with path.open('ab') as stream:
        stream.write(b'}\n')
    current = snapshot(tmp_path, 1)
    assert len(read_page(tmp_path, 1, old)['rows']) == 2
    added = read_page(tmp_path, 1, current, start=old[2])['rows']
    assert [r['text'] for r in added] == ['new']
    path.write_text('', encoding="utf-8")
    with pytest.raises(ValueError, match='truncated'):
        read_page(tmp_path, 1, current)


def test_full_text_filters_and_damaged_records(tmp_path):
    path, _ = write_logs(tmp_path, 2)
    action = dict(event='trusted_action_returned', logical_name='observe.ocr', inputs={},
                  return_value={'items': [{'text': 'buried result'}]})
    with path.open('a', encoding="utf-8") as stream:
        stream.write('{broken}\n' + json.dumps(action) + '\n')
    boundary = snapshot(tmp_path, 1)
    assert len(read_page(tmp_path, 1, boundary)['rows']) == 2
    result = read_page(tmp_path, 1, boundary, levels=('debug',), keyword='BURIED')
    assert len(result['rows']) == 1 and result['damaged'] == 1
    assert not read_page(tmp_path, 1, boundary, keyword='absent')['rows']
    assert len(read_page(tmp_path, 1, boundary, keyword='STEPS.EXAMPLE')['rows']) == 2


def test_image_evidence_stays_in_run_and_dimensions_are_reserved(tmp_path):
    from PIL import Image
    path, _ = write_logs(tmp_path, 1)
    folder = tmp_path / 'evidence' / '1'
    folder.mkdir(parents=True)
    Image.new('RGB', (160, 90)).save(folder / '1.png')
    image_record = dict(event='component_log', level='info', message='image', evidence_id='1/1')
    with path.open('a', encoding="utf-8") as stream:
        stream.write(json.dumps(image_record) + '\n')
    rows = read_page(tmp_path, 1, snapshot(tmp_path, 1), images=True)['rows']
    assert len(rows) == 1 and rows[0]['dimensions'] == (160, 90)
    assert image_path(tmp_path, 1, {'evidence_id': '2/1'}) is None
    assert image_path(tmp_path, 1, {'evidence_path': '/etc/passwd'}) is None
    (folder / '1.png').unlink()
    (folder / '1.png').symlink_to(path)
    assert image_path(tmp_path, 1, image_record) is None


@pytest.fixture
def log_page(tmp_path, monkeypatch):
    monkeypatch.setenv('QT_QPA_PLATFORM', 'offscreen')
    from PySide6.QtWidgets import QApplication
    from lalc.run_log_gui import RunLogPage
    app = QApplication.instance() or QApplication([])
    path, _ = write_logs(tmp_path, 320)
    page = RunLogPage(tmp_path)
    page.resize(1100, 700)
    page.show()
    def until(predicate):
        end = time.monotonic() + 8
        while not predicate() and time.monotonic() < end:
            app.processEvents()
            time.sleep(.005)
        assert predicate()
    until(lambda: bool(page.model.rows) and not page.loading)
    yield app, page, path, until
    page.invalidate()
    page.close()
    app.processEvents()


def test_selection_checks_for_updates_without_moving_view(log_page):
    app, page, path, until = log_page
    original = page.model.rows[0]['record']['sequence']
    with path.open('a', encoding="utf-8") as stream:
        stream.write(json.dumps(dict(event='component_log', level='info', message='new', sequence=321)) + '\n')
    app.processEvents()
    assert not page.new_logs.isVisible()
    assert page.model.rows[0]['record']['sequence'] == original
    page.select_run(page.runs.item(0))
    until(lambda: page.new_logs.isVisible())
    assert page.model.rows[0]['record']['sequence'] == original
    page.accept_new()
    until(lambda: not page.loading and page.model.rows[0]['text'] == 'new')
    assert page.view.verticalScrollBar().value() == 0


def test_wheel_step_stays_small_with_tall_logs(log_page):
    """长日志改变行高后，普通滚轮仍按小像素步长滚动。"""
    from PySide6.QtCore import QPoint, QPointF, Qt
    from PySide6.QtGui import QWheelEvent
    app, page, _, _ = log_page
    for row in page.model.rows:
        row.update(text='detail\n' * 80, expanded=True)
    page.view.doItemsLayout()
    app.processEvents()
    bar = page.view.verticalScrollBar()
    assert bar.singleStep() == 20
    bar.setValue(0)
    event = QWheelEvent(QPointF(20, 20), QPointF(20, 20), QPoint(), QPoint(0, -120),
                        Qt.MouseButton.NoButton, Qt.KeyboardModifier.NoModifier, Qt.ScrollPhase.NoScrollPhase, False)
    app.sendEvent(page.view.viewport(), event)
    assert 0 < bar.value() <= 120


def test_filter_retains_anchor_and_collapsed_text_is_searchable(log_page):
    app, page, path, until = log_page
    index = page.model.index(20)
    page.view.scrollTo(index, page.view.ScrollHint.PositionAtTop)
    app.processEvents()
    anchor = page.anchor()
    page.search.setText('中文日志')
    until(lambda: not page.debounce.isActive() and not page.loading)
    app.processEvents()
    assert page.anchor()[0] == anchor[0]
    row = page.model.rows[0]
    row['text'] = 'first\nsecond\nthird\nburied result'
    _, collapsed, toggle, _ = page.delegate.geometry(row, 500, page.font())
    assert toggle
    row['expanded'] = True
    _, expanded, _, _ = page.delegate.geometry(row, 500, page.font())
    assert expanded > collapsed


def test_annotation_interface_scales_without_changing_original(monkeypatch):
    monkeypatch.setenv('QT_QPA_PLATFORM', 'offscreen')
    from PySide6.QtCore import QRectF
    from PySide6.QtGui import QImage, QPainter
    from lalc.image_annotations import action_annotations, paint_annotations
    image = QImage(200, 100, QImage.Format.Format_RGB32)
    image.fill(0xffffff)
    original = image.copy()
    painter = QPainter(image)
    annotations = action_annotations({'logical_name': 'control.click', 'inputs': {'centerxy': [50, 25]}})
    paint_annotations(painter, QRectF(0, 0, 200, 100), (100, 50), annotations)
    painter.end()
    assert image.pixelColor(100, 50).red() > image.pixelColor(100, 50).green()
    assert original.pixelColor(100, 50).name() == '#ffffff'


def test_browsing_evicts_old_pages_and_can_read_them_again(log_page):
    app, page, path, until = log_page
    while not page.older_done:
        page.more(True)
        until(lambda: not page.loading)
    assert len(page.model.rows) == 240
    assert page.model.rows[-1]['record']['sequence'] == 1
    assert not page.newer_done
    page.more(False)
    until(lambda: not page.loading)
    sequences = [row['record']['sequence'] for row in page.model.rows]
    assert sequences == sorted(set(sequences), reverse=True)
    assert sequences[0] > 240 and len(sequences) == 240


def test_decoding_image_does_not_change_reserved_row_height(log_page):
    from PIL import Image
    app, page, path, until = log_page
    image = path.parent.parent / 'evidence' / '1' / '1.png'
    image.parent.mkdir(parents=True)
    Image.new('RGB', (640, 360)).save(image)
    row = page.model.rows[0]
    row['image'], row['dimensions'] = image, (640, 360)
    page.model.replace([row])
    _, text, toggle, height = page.delegate.geometry(row, 800, page.font())
    page.request_image(row)
    until(lambda: str(image) in page.images)
    assert page.delegate.geometry(row, 800, page.font())[1:] == (text, toggle, height)


def test_matching_annotation_numbers_follow_return_order():
    from lalc.image_annotations import action_annotations
    record = {'logical_name': 'observe.match_asset', 'return_value': [
        dict(x=30, y=20, width=12, height=8, score=.98),
        dict(x=2, y=1, width=12, height=8, score=.91)]}
    annotations = action_annotations(record)
    assert [(item['number'], item['x']) for item in annotations] == [(1, 30), (2, 2)]
    assert action_annotations({'logical_name': 'control.drag', 'inputs': {
        'x': 1, 'y': 2, 'end_x': 20, 'end_y': 30}})[0]['kind'] == 'arrow'


def test_image_resource_failure_finishes_as_unavailable(log_page, monkeypatch):
    """解码资源不足不能让占位一直停在加载中。"""
    import lalc.run_log_gui as gui
    app, page, path, until = log_page
    row = {**page.model.rows[0], 'image': path.parent / 'missing.png'}
    def unavailable(*_):
        raise MemoryError('test memory shortage')
    monkeypatch.setattr(gui, 'image_preview', unavailable)
    page.request_image(row)
    until(lambda: str(row['image']) in page.images)
    assert page.images[str(row['image'])] is None
    assert str(row['image']) not in page.pending_images


def test_collapsing_partially_visible_long_entry_keeps_entry_visible(log_page):
    app, page, path, until = log_page
    row = page.model.rows[0]
    row['text'], row['expanded'] = 'detail\n' * 200, True
    page.model.replace(page.model.rows[:])
    app.processEvents()
    page.view.verticalScrollBar().setValue(1200)
    app.processEvents()
    assert page.anchor()[0] == row['offset']
    page.toggle_details(page.model.index(0))
    app.processEvents()
    assert page.anchor()[0] == row['offset']


@pytest.mark.parametrize('text', [
    'VISIBLE ONE\nVISIBLE TWO\nVISIBLE THREE\nHIDDEN FOUR\nHIDDEN FIVE',
    'VISIBLE ' * 100,
], ids=['explicit-newlines', 'automatic-wrap'])
def test_collapsed_paint_matches_first_three_expanded_lines(log_page, text):
    """比较真实绘制像素，隐藏内容不得重叠到前三行；覆盖换行与自动折行。"""
    from math import ceil
    from PySide6.QtCore import QRect, Qt
    from PySide6.QtGui import QImage, QPainter
    from PySide6.QtWidgets import QStyleOptionViewItem
    app, page, path, until = log_page
    row = {**page.model.rows[0], 'text': text, 'image': None, 'expanded': True}
    page.model.replace([row])
    option = QStyleOptionViewItem()
    option.initFrom(page.view)
    option.font = page.font()

    def painted():
        _, height, _, _ = page.delegate.geometry(row, 500, option.font)
        option.rect = QRect(0, 0, 500, ceil(height) + 100)
        image = QImage(option.rect.size(), QImage.Format.Format_RGB32)
        image.fill(Qt.GlobalColor.white)
        painter = QPainter(image)
        page.delegate.paint(painter, option, page.model.index(0))
        painter.end()
        return image

    expanded = painted()
    page.toggle_details(page.model.index(0))
    _, visible_height, toggle, _ = page.delegate.geometry(row, 500, option.font)
    assert toggle and not row['expanded']
    body = QRect(12, 32, 476, ceil(visible_height))
    assert painted().copy(body) == expanded.copy(body)
    page.toggle_details(page.model.index(0))
    assert row['expanded']
    assert painted() == expanded
    page.toggle_details(page.model.index(0))
    assert painted().copy(body) == expanded.copy(body)


@pytest.mark.parametrize('value,expected', [
    ('2026-11-07T12:34:56.789', '2026-11-07 12:34:56'),
    (None, '—'), ('invalid', '—'),
])
def test_log_time_displays_seconds_without_inventing_missing_time(value, expected):
    from lalc.run_log_gui import log_time
    assert log_time(value) == expected


@pytest.mark.parametrize('dark', [False, True])
@pytest.mark.parametrize('level', ['info', 'warning', 'error', 'debug'])
def test_log_delegate_paints_shared_level_background(log_page, monkeypatch, dark, level):
    """检查实际绘制的色块像素；两种主题的四个等级均复用运行窗口配色。"""
    from PySide6.QtCore import QRect
    from PySide6.QtGui import QColor, QImage, QPainter
    from PySide6.QtWidgets import QStyleOptionViewItem
    import lalc.run_log_gui as gui
    app, page, path, until = log_page
    monkeypatch.setattr(gui, 'isDarkTheme', lambda: dark)
    row = {**page.model.rows[0], 'level': level, 'image': None}
    page.model.replace([row])
    option = QStyleOptionViewItem()
    option.initFrom(page.view)
    option.font = page.font()
    option.rect = QRect(0, 0, 800, 160)
    image = QImage(option.rect.size(), QImage.Format.Format_RGB32)
    image.fill(QColor('white'))
    painter = QPainter(image)
    try:
        page.delegate.paint(painter, option, page.model.index(0))
    finally:
        painter.end()
    background, foreground = gui.log_colors(level)
    assert image.pixelColor(6, 6) == QColor(background)
    assert QColor(background) != QColor(foreground)
