"""覆盖页面整包版本、资源加载、旧页兼容、替换回退及资源路径边界。

项目根目录运行：
QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest -q tests/test_page_packages.py
"""

from pathlib import Path

import pytest

from lalc.page_packages import PageSnapshot, install_page_package, materialized_page, resource_path, snapshot_page
from lalc.user_pages import UserSettings, discover_pages
from test_page_drafts import SOURCE, drafts
from test_user_pages import app


PAGE = '''from PySide6.QtWidgets import QWidget, QLabel
from PySide6.QtGui import QPixmap
PAGE_ID = "package.page"
PAGE_NAME = "Package"
def create_page(context):
    page = QWidget()
    page.banner = QLabel(page)
    page.banner.setPixmap(QPixmap(str(context.resource_path("assets/banner.png"))))
    page.submit = lambda: context.load({})
    return page
'''


def test_snapshot_is_nonexecuting_immutable_and_includes_resource_version(tmp_path):
    package = tmp_path / "sample"
    (package / "assets").mkdir(parents=True)
    (package / "page.py").write_text("raise AssertionError('must not execute')", encoding="utf-8")
    image = package / "assets/banner.png"
    image.write_bytes(b"original image")
    frozen = snapshot_page(package)
    version = frozen.sha256
    image.write_bytes(b"changed image")
    assert snapshot_page(package).sha256 != version
    assert frozen.sha256 == version and frozen.files["assets/banner.png"] == b"original image"
    with pytest.raises(TypeError):
        frozen.files["assets/banner.png"] = b"replace"
    with materialized_page(frozen) as entry:
        assert resource_path(entry.parent, "assets/banner.png").read_bytes() == b"original image"
        assert snapshot_page(entry.parent).sha256 == version
    assert not entry.exists()
    image.unlink()
    assert snapshot_page(package).sha256 != version
    legacy = tmp_path / "legacy.py"
    legacy.write_bytes(frozen.files["page.py"].path.read_bytes())
    assert snapshot_page(legacy).files == {"page.py": legacy.read_bytes()}


def test_installed_package_loads_real_image_and_preserves_private_settings(tmp_path, app):
    from PySide6.QtGui import QImage
    source = tmp_path / "source"
    (source / "assets").mkdir(parents=True)
    (source / "page.py").write_text(PAGE, encoding="utf-8")
    image = QImage(3, 2, QImage.Format.Format_RGB32)
    image.fill(0xFF112233)
    assert image.save(str(source / "assets/banner.png"))
    store = UserSettings(tmp_path)
    store.save("pages", "package.page", {"private": "keep local"})
    original_settings = store.path.read_bytes()
    install_page_package(tmp_path / "pages", "sample", snapshot_page(source))
    pages, errors = discover_pages(tmp_path / "pages", store)
    assert not errors and len(pages) == 1
    try:
        assert pages[0].widget.banner.pixmap().width() == 3
        assert pages[0].widget.submit() == {"private": "keep local"}
        assert store.path.read_bytes() == original_settings
    finally:
        pages[0].widget.close()


def test_whole_package_replaces_old_resources_and_converts_matching_legacy(tmp_path):
    pages = tmp_path / "pages"
    pages.mkdir()
    legacy = pages / "sample.py"
    legacy.write_bytes(b"old source")
    frozen = PageSnapshot({"page.py": b"new source", "assets/old.png": b"old image"})
    with pytest.raises(FileExistsError):
        install_page_package(pages, "sample", frozen, legacy_filename="sample.py")
    target = install_page_package(pages, "sample", frozen, replace=True, legacy_filename="sample.py")
    assert not legacy.exists()
    new = PageSnapshot({"page.py": b"replacement", "assets/new.png": b"new image"})
    install_page_package(pages, "sample", new, replace=True)
    assert snapshot_page(target).files == new.files
    assert not (target / "assets/old.png").exists()
    assert not list(pages.glob(".page-install-*"))


@pytest.mark.parametrize("legacy", [False, True])
def test_failed_commit_restores_original_page_and_resources(tmp_path, monkeypatch, legacy):
    pages = tmp_path / "pages"
    pages.mkdir()
    original = PageSnapshot({"page.py": b"original", "assets/image.png": b"original image"})
    if legacy:
        target = pages / "sample.py"
        target.write_bytes(b"original")
    else:
        target = install_page_package(pages, "sample", original)
    before = snapshot_page(target)
    rename = Path.rename
    def fail_commit(path, destination):
        if path.name == "new":
            raise OSError("commit failed")
        return rename(path, destination)
    monkeypatch.setattr(Path, "rename", fail_commit)
    with pytest.raises(OSError, match="commit failed"):
        install_page_package(pages, "sample", PageSnapshot({"page.py": b"replacement"}),
                             replace=True, legacy_filename="sample.py" if legacy else None)
    assert snapshot_page(target).files == before.files
    assert not list(pages.glob(".page-install-*"))


def test_failed_restore_keeps_only_old_copy_for_recovery(tmp_path, monkeypatch):
    pages = tmp_path / "pages"
    original = PageSnapshot({"page.py": b"original", "assets/image.png": b"original image"})
    install_page_package(pages, "sample", original)
    rename = Path.rename
    def fail_commit_and_restore(path, destination):
        if path.name in {"new", "previous"}:
            raise OSError("locked")
        return rename(path, destination)
    monkeypatch.setattr(Path, "rename", fail_commit_and_restore)
    with pytest.raises(OSError, match="原内容保留在"):
        install_page_package(pages, "sample", PageSnapshot({"page.py": b"replacement"}), replace=True)
    work, = pages.glob(".page-install-*")
    assert snapshot_page(work / "previous").files == original.files


def test_resource_write_failure_never_moves_old_package(tmp_path, monkeypatch):
    pages = tmp_path / "pages"
    original = PageSnapshot({"page.py": b"original"})
    target = install_page_package(pages, "sample", original)
    from lalc.page_packages import write_content
    def fail_resource_write(path, content):
        if "new" in path.parts and path.name == "banner.png":
            raise OSError("resource write failed")
        return write_content(path, content)
    monkeypatch.setattr("lalc.page_packages.write_content", fail_resource_write)
    replacement = PageSnapshot({"page.py": b"replacement", "assets/banner.png": b"image"})
    with pytest.raises(OSError, match="resource write failed"):
        install_page_package(pages, "sample", replacement, replace=True)
    assert snapshot_page(target).files == original.files
    assert not list(pages.glob(".page-install-*"))


@pytest.mark.parametrize("name", ["../outside", "/outside", "assets/CON.png", "assets/a.", "assets\\a.png"])
def test_unsafe_resource_paths_are_rejected(tmp_path, name):
    with pytest.raises(ValueError):
        PageSnapshot({"page.py": b"source", name: b"resource"})
    with pytest.raises(ValueError):
        resource_path(tmp_path, name)


@pytest.mark.parametrize("extra", [
    {"Assets/a.png": b"a", "assets/b.png": b"b"},
    {"assets": b"file", "assets/a.png": b"a"},
])
def test_windows_aliases_and_file_directory_collisions_are_rejected(extra):
    with pytest.raises(ValueError, match="冲突"):
        PageSnapshot({"page.py": b"source", **extra})


def test_linked_resource_is_rejected_before_snapshot_or_lookup(tmp_path):
    package = tmp_path / "sample"
    package.mkdir()
    (package / "page.py").write_bytes(b"source")
    outside = tmp_path / "outside.png"
    outside.write_bytes(b"private")
    (package / "image.png").symlink_to(outside)
    with pytest.raises(ValueError, match="链接"):
        snapshot_page(package)
    with pytest.raises(ValueError, match="普通文件"):
        resource_path(package, "image.png")


def test_legacy_agent_install_checks_directory_page_id_conflicts(drafts):
    package = drafts.installed / "existing"
    package.mkdir(parents=True)
    (package / "page.py").write_text(SOURCE, encoding="utf-8")
    drafts.create("new.py", SOURCE)
    with pytest.raises(ValueError, match="冲突"):
        drafts.install(drafts.snapshot("new.py"), "sample.page", "sample.task")
    assert not (drafts.installed / "new.py").exists()


def test_duplicate_ids_across_old_file_and_package_are_not_registered(tmp_path, app):
    pages = tmp_path / "pages"
    (pages / "package").mkdir(parents=True)
    (pages / "package/page.py").write_text(SOURCE, encoding="utf-8")
    (pages / "legacy.py").write_text(SOURCE, encoding="utf-8")
    found, errors = discover_pages(pages, UserSettings(tmp_path))
    assert not found and len(errors) == 2
    assert all("冲突" in error for error in errors)
