"""覆盖按图片内容识别、原样多附件留存、GUI 多选与 CLI 重复图片参数。

在项目根目录运行：
QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest -q tests/test_image_attachments.py
"""

import base64
from io import BytesIO
import json

import pytest
from PIL import Image

from lalc.agent_repair import image_attachments
from test_developer_gui import gui


def make_images(folder, formats=("PNG", "JPEG", "WEBP", "GIF", "BMP", "TIFF", "AVIF")):
    paths = []
    for index, kind in enumerate(formats):
        path = folder / f"image-{index}.not-an-extension"
        image = Image.new("RGB", (4, 3), (80, 50, 30))
        output = BytesIO()
        image.save(output, format=kind)
        path.write_bytes(output.getvalue())
        paths.append(path)
    return paths


def test_content_types_are_detected_without_format_or_count_filter(tmp_path):
    paths = make_images(tmp_path)
    saved = tmp_path / "round"
    saved.mkdir()
    payloads, records = image_attachments(paths, saved)
    assert len(payloads) == len(paths)
    assert [p["mimeType"] for p in payloads] == ["image/png", "image/jpeg", "image/webp", "image/gif", "image/bmp", "image/tiff", "image/avif"]
    for path, payload, record in zip(paths, payloads, records):
        assert base64.b64decode(payload["data"]) == path.read_bytes()
        assert (saved / record["filename"]).read_bytes() == path.read_bytes()
        assert record["original_name"] == path.name
    assert image_attachments([], saved) == ([], [])


def test_non_image_and_corrupt_image_are_errors(tmp_path):
    for content in (b"not image", b"\x89PNG\r\n\x1a\ninvalid"):
        path = tmp_path / "fake.png"
        path.write_bytes(content)
        with pytest.raises(ValueError, match="不是有效图片"):
            image_attachments([path], tmp_path)


def test_gui_accumulates_selection_displays_paths_and_clears_all(gui, monkeypatch, tmp_path):
    from PySide6.QtWidgets import QFileDialog
    app, window = gui
    paths = make_images(tmp_path, ("PNG", "JPEG"))
    monkeypatch.setattr(QFileDialog, "getOpenFileNames", lambda *args: ([str(path) for path in paths], ""))
    page = window.repair_page
    page.attach_image()
    page.attach_image()
    assert page.images == paths * 2
    assert "4" in page.attach.text()
    assert str(paths[1]) in page.attach.toolTip()
    page.clear_image()
    assert not page.images and not page.attach.toolTip()


def test_cli_accepts_repeated_image_options():
    from pathlib import Path
    from lalc.__main__ import _parser
    args = _parser().parse_args(["repair", "--problem", "test", "--image", "a.jpg", "--image", "b.webp"])
    assert args.image == [Path("a.jpg"), Path("b.webp")]


def test_text_only_does_not_import_optional_image_decoder(tmp_path, monkeypatch):
    import sys
    monkeypatch.setitem(sys.modules, "PIL", None)
    assert image_attachments([], tmp_path) == ([], [])
