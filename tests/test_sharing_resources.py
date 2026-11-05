"""覆盖无固定准入限额、实时资源估算、取消、暂存复用与遗留清理。

项目根目录运行：.venv/bin/python -m pytest -q tests/test_sharing_resources.py
"""

from pathlib import Path
from types import SimpleNamespace
import zipfile

import pytest

from lalc.file_content import (FileContent, ResourceUnknown, require_disk, require_memory,
                               file_operation, image_preview)
from lalc.sharing import SharingPackage, _index, cleanup_staging, save_package, staging_root


def objects():
    return [{"kind": "pages", "id": "sample.py", "files": {"page.py": b'PAGE_ID="sample"\nPAGE_NAME="Sample"'}}]


def test_prior_object_file_and_index_limits_are_not_admission_rules():
    many_objects = [{"kind": "pages", "id": f"page{i}.py", "files": {"page.py": b"pass"}} for i in range(1001)]
    assert len(_index(many_objects)["objects"]) == 1001
    files = {f"resources/{i}.txt": b"" for i in range(30000)}
    files["page.py"] = b"pass"
    assert len(_index([{"kind": "pages", "id": "sample.py", "files": files}])["objects"][0]["files"]) == 30001


def test_large_resource_roundtrip_uses_files_not_memory(tmp_path, monkeypatch):
    source = tmp_path / "large.bin"
    with source.open("wb") as stream:
        stream.seek(128 * 1024 * 1024)
        stream.write(b"end")
    blob = FileContent.from_path(source)
    selected = objects()
    selected[0]["files"]["resources/large.bin"] = blob
    archive = tmp_path / "share.zip"
    save_package(selected, archive)
    # FileContent reads must not be used for ZIP creation/extraction/verification.
    monkeypatch.setattr("lalc.file_content.content_bytes", lambda *_: pytest.fail("whole resource read"))
    package = SharingPackage(archive)
    try:
        archive.unlink()
        package.verify()
        imported = package.files(package.objects[0])["resources/large.bin"]
        assert isinstance(imported, FileContent) and imported == blob
    finally:
        package.close()


def test_capacity_checks_add_same_volume_requirements_and_unknown_is_explicit(tmp_path, monkeypatch):
    monkeypatch.setattr("lalc.file_content.shutil.disk_usage", lambda path: SimpleNamespace(free=15))
    with pytest.raises(OSError, match="磁盘空间不足"):
        require_disk([(tmp_path / "stage", 10), (tmp_path / "data", 10)])
    def unavailable(path):
        raise OSError("unavailable")
    monkeypatch.setattr("lalc.file_content.shutil.disk_usage", unavailable)
    with pytest.raises(ResourceUnknown):
        require_disk([(tmp_path, 1)])
    require_disk([(tmp_path, 1)], allow_unknown=True)
    monkeypatch.setattr("lalc.file_content.available_memory", lambda: 10)
    with pytest.raises(OSError, match="内存不足"):
        require_memory(11)
    require_memory(10)


def test_insufficient_space_precedes_any_payload_extraction(tmp_path, monkeypatch):
    archive = tmp_path / "share.zip"
    save_package(objects(), archive)
    opened = []
    original = zipfile.ZipFile.open
    def tracked(self, name, *args, **kwargs):
        opened.append(name)
        return original(self, name, *args, **kwargs)
    monkeypatch.setattr(zipfile.ZipFile, "open", tracked)
    monkeypatch.setattr("lalc.file_content.shutil.disk_usage", lambda path: SimpleNamespace(free=0))
    before = set(staging_root().iterdir())
    with pytest.raises(OSError, match="磁盘空间不足"):
        SharingPackage(archive, tmp_path / "target")
    assert opened == ["sharing.json"]
    assert set(staging_root().iterdir()) == before


def test_cancel_during_extraction_removes_only_its_stage(tmp_path):
    archive = tmp_path / "share.zip"
    selected = objects()
    selected[0]["files"]["large.txt"] = b"x" * (3 * 1024 * 1024)
    save_package(selected, archive)
    active = SharingPackage(archive)
    before = set(staging_root().iterdir())
    cancelled = [False]
    def progress(done, total, name):
        if done:
            cancelled[0] = True
    try:
        with file_operation(lambda: cancelled[0], progress):
            with pytest.raises(InterruptedError):
                SharingPackage(archive)
        assert set(staging_root().iterdir()) == before
        cleanup_staging()
        assert active.root.exists()
        orphan = staging_root() / "12345678-1234-1234-1234-123456789abc"
        orphan.mkdir()
        (orphan / "payload").write_bytes(b"old")
        unrelated = staging_root() / "unrelated"
        unrelated.mkdir(exist_ok=True)
        cleanup_staging()
        assert not orphan.exists() and unrelated.exists() and active.root.exists()
        unrelated.rmdir()
    finally:
        active.close()


def test_image_resource_above_old_pixel_threshold_is_previewable(tmp_path):
    from PIL import Image
    source = tmp_path / "large.png"
    Image.new("1", (7000, 6000)).save(source)
    preview = image_preview(FileContent.from_path(source), (64, 64))
    from io import BytesIO
    with Image.open(BytesIO(preview)) as image:
        assert max(image.size) <= 64
