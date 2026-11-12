"""覆盖 Agent 整包页面工具、旧 Session 兼容、受控资源复制与固定资源审批。

项目根目录运行：
QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest -q tests/test_page_package_tools.py
"""

import base64
import json
from pathlib import Path

import pytest

from lalc.agent_log import read_json
from lalc.developer_session import DeveloperSession
from lalc.page_drafts import PageDrafts
from lalc.page_preview import PagePreviewDialog, PreviewRequest
from lalc.runtime import sha256_bytes
from test_page_drafts import SOURCE, drafts
from test_page_packages import PAGE
from test_user_pages import app
from test_developer_gui import gui


def test_directory_create_resource_update_remove_and_reopen(drafts):
    drafts.create("sample.py", SOURCE)
    assert not (drafts.root / "sample.py").exists()
    assert drafts.path("sample.py") == drafts.root / "sample/page.py"
    original = drafts.snapshot("sample.py")["sha256"]
    drafts.write_resource("sample.py", "assets/info.txt", b"hello")
    assert drafts.snapshot("sample.py")["sha256"] != original
    drafts.update("sample.py", SOURCE.replace('"Sample"', '"Updated"'))
    restored = PageDrafts(DeveloperSession(drafts.session.host.service, drafts.session.identity, entry="gui"))
    assert restored.file_bytes("drafts", "sample.py", "assets/info.txt") == b"hello"
    assert {row["path"] for row in restored.list("drafts", filename="sample.py")["items"]} == {"page.py", "assets/info.txt"}
    assert restored.read("drafts", "sample.py", path="assets/info.txt")["source"] == "hello"
    restored.write_resource("sample.py", "assets/info.txt", remove=True)
    assert set(restored.snapshot("sample.py")["package"].files) == {"page.py"}


def test_old_single_file_session_still_updates_after_target_converts_to_package(drafts):
    drafts.root.mkdir()
    legacy = drafts.root / "sample.py"
    legacy.write_text(SOURCE)
    (drafts.root / "sample.json").write_text(json.dumps({"filename": "sample.py", "replace": False}))
    # 模拟旧 Session 留有单文件草稿，而正式页已由其他 Session 换成目录。
    (drafts.installed / "sample").mkdir(parents=True)
    (drafts.installed / "sample/page.py").write_text(SOURCE)
    restored = PageDrafts(DeveloperSession(drafts.session.host.service, drafts.session.identity, entry="gui"))
    restored.update("sample.py", SOURCE.replace('"Sample"', '"Updated"'))
    assert legacy.is_file()
    frozen = restored.snapshot("sample.py")
    restored.install(frozen, "sample.page", "sample.task")
    assert restored.path("sample.py", "installed").read_bytes() == frozen["source"]
    restored.write_resource("sample.py", "assets/info.txt", b"promoted")
    assert not legacy.exists()
    assert restored.file_bytes("drafts", "sample.py", "assets/info.txt") == b"promoted"


def test_copy_installed_page_preserves_complete_resource_package(drafts):
    drafts.create("sample.py", SOURCE)
    drafts.write_resource("sample.py", "assets/info.txt", b"complete copy")
    frozen = drafts.snapshot("sample.py")
    drafts.install(frozen, "sample.page", "sample.task")
    other = PageDrafts(DeveloperSession.create(drafts.session.host.service, None, mode="Construct", entry="gui"))
    other.create("sample.py", copy_from="sample.py")
    assert other.snapshot("sample.py")["package"].files == frozen["package"].files
    assert not (other.root / "sample.json").exists()


def test_invalid_resource_inputs_leave_draft_unchanged_and_large_files_work(drafts, monkeypatch):
    tools = drafts.session.host.conversation.tools
    drafts.create("sample.py", SOURCE)
    before = drafts.snapshot("sample.py")
    result = read_json(tools.call("page_resource", {"filename": "sample.py", "path": "assets/bad.png",
                                                   "content_base64": "not base64!"}))
    assert result["isError"]
    assert drafts.snapshot("sample.py") == before
    large = b"x" * (2 * 1024 * 1024 + 1)
    drafts.write_resource("sample.py", "assets/large.txt", large)
    assert drafts.file_bytes("drafts", "sample.py", "assets/large.txt") == large
    assert len(drafts.read("drafts", "sample.py", path="assets/large.txt")["source"]) == 16000


def test_resource_tool_copies_only_bounded_sources_and_never_writes_installed(drafts, tmp_path):
    tools = drafts.session.host.conversation.tools
    drafts.create("sample.py", SOURCE)
    knowledge = tools.knowledge.root
    knowledge.mkdir()
    (knowledge / "info.txt").write_bytes(b"reference")
    args = {"filename": "sample.py", "path": "assets/info.txt",
            "copy_from": {"scope": "knowledge", "path": "info.txt"}}
    assert not read_json(tools.call("page_resource", args)).get("isError")
    assert drafts.file_bytes("drafts", "sample.py", "assets/info.txt") == b"reference"
    allowed = tools.allowed
    tools.allowed = allowed - {"knowledge_read"}
    assert read_json(tools.call("page_resource", args))["isError"]
    assert drafts.file_bytes("drafts", "sample.py", "assets/info.txt") == b"reference"
    tools.allowed = allowed
    asset_content = b"asset bytes"
    digest = sha256_bytes(asset_content)
    asset = tools.library.root / "sample" / f"{digest}.png"
    asset.parent.mkdir(parents=True)
    asset.write_bytes(asset_content)
    args["copy_from"] = {"scope": "assets", "path": f"sample/{digest}.png", "sha256": digest}
    assert not read_json(tools.call("page_resource", args)).get("isError")
    assert drafts.file_bytes("drafts", "sample.py", "assets/info.txt") == asset_content
    args["copy_from"] = {"scope": "drafts", "filename": "sample.py", "path": "assets/info.txt"}
    args["path"] = "assets/copy.txt"
    assert not read_json(tools.call("page_resource", args)).get("isError")
    args["copy_from"] = {"scope": "knowledge", "path": "../private.txt"}
    assert read_json(tools.call("page_resource", args))["isError"]
    args["copy_from"] = {"scope": "file", "path": str(tmp_path / "private.txt")}
    assert read_json(tools.call("page_resource", args))["isError"]
    assert not drafts.installed.exists()


@pytest.mark.parametrize("path", ["../escape.txt", "/escape.txt", "page.py", "assets/helper.py", "assets/CON.txt"])
def test_resource_tool_cannot_escape_or_rewrite_python(drafts, path):
    tools = drafts.session.host.conversation.tools
    drafts.create("sample.py", SOURCE)
    frozen = drafts.snapshot("sample.py")
    result = read_json(tools.call("page_resource", {"filename": "sample.py", "path": path,
                                                   "content_base64": base64.b64encode(b"bad").decode()}))
    assert result["isError"]
    assert drafts.snapshot("sample.py") == frozen


def test_image_resource_read_and_preview_install_exact_package(gui, drafts):
    from PySide6.QtGui import QImage
    app, window = gui
    picture = drafts.root.parent / "picture.png"
    image = QImage(3, 2, QImage.Format.Format_RGB32)
    image.fill(0xFF112233)
    assert image.save(str(picture))
    original = picture.read_bytes()
    drafts.create("sample.py", PAGE)
    tools = drafts.session.host.conversation.tools
    result = read_json(tools.call("page_resource", {"filename": "sample.py", "path": "assets/banner.png",
                          "content_base64": base64.b64encode(original).decode()}))
    assert not result.get("isError")
    result = read_json(tools.call("page_read", {"scope": "drafts", "filename": "sample.py", "path": "assets/banner.png", "image": True}))
    assert not result.get("isError")
    block = next(block for block in result["content"] if block["type"] == "image")
    assert block["mimeType"] == "image/jpeg"
    assert drafts.file_bytes("drafts", "sample.py", "assets/banner.png") == original
    assert result["details"]["preview"] is True
    request = PreviewRequest(drafts, drafts.snapshot("sample.py"), "图片说明", (drafts.session.identity, 1, 1))
    dialog = PagePreviewDialog(request, window)
    assert dialog.ready
    dialog.show()
    app.processEvents()
    preview_root = dialog.proposed.context.package_root
    assert preview_root != drafts.path("sample.py").parent
    try:
        assert dialog.proposed.widget.banner.pixmap().width() == 3
        image = QImage(7, 2, QImage.Format.Format_RGB32)
        image.fill(0xFF445566)
        assert image.save(str(picture))
        drafts.write_resource("sample.py", "assets/banner.png", picture.read_bytes())
        assert drafts.snapshot("sample.py")["sha256"] != request.snapshot["sha256"]
        assert (preview_root / "assets/banner.png").read_bytes() == original
        dialog.install_button.click()
        assert request.result["sha256"] == request.snapshot["sha256"]
        assert drafts.file_bytes("installed", "sample.py", "assets/banner.png") == original
    finally:
        dialog.close()
        app.processEvents()
    assert not preview_root.exists()


def test_page_preview_evidence_includes_frozen_resources(drafts):
    tools = drafts.session.host.conversation.tools
    drafts.create("sample.py", SOURCE)
    drafts.write_resource("sample.py", "assets/info.txt", b"original")
    def close(request):
        drafts.write_resource("sample.py", "assets/info.txt", b"changed after request")
        request.finish({"status": "not_installed"})
    tools.on_page_preview = close
    assert not read_json(tools.call("page_preview", {"filename": "sample.py", "summary": "资源版本"})).get("isError")
    record, = tools.log.path.glob("tool-*-page-preview.json")
    evidence = read_json(record)
    files = {row["path"]: row for row in evidence["files"]}
    assert files["assets/info.txt"]["sha256"] == sha256_bytes(b"original")
    assert (tools.log.path / evidence["package_path"] / "assets/info.txt").read_bytes() == b"original"


def test_source_parsing_checks_resources_before_changing_draft(drafts, monkeypatch):
    drafts.create("sample.py", SOURCE)
    before = drafts.snapshot("sample.py")
    def unavailable(size):
        raise OSError("当前可用内存不足")
    monkeypatch.setattr("lalc.page_drafts.require_memory", unavailable)
    with pytest.raises(OSError, match="内存不足"):
        drafts.update("sample.py", SOURCE + "\n# unchanged on failure")
    assert drafts.snapshot("sample.py")["sha256"] == before["sha256"]
