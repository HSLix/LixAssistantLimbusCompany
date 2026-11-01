"""覆盖 SOP 校验、模式隔离、请求前失败与新旧消息原文提取，不启动 pi。

项目根目录运行：.venv/bin/python -m pytest -q tests/test_agent_prompts.py
"""

import asyncio

import pytest

from lalc import agent_prompts as prompts
from test_agent_repair import host_for


def sop_text(construct="", repair="", asset=""):
    return ("# SOP\n填写说明不发送给模型\n"
            f"<construct_sop>{construct}</construct_sop>\n"
            f"<repair_sop>{repair}</repair_sop>\n<asset_sop>{asset}</asset_sop>")


def test_sop_selects_only_mode_and_asset_and_accepts_empty(tmp_path, monkeypatch):
    path = tmp_path / "sop.md"
    monkeypatch.setattr(prompts, "SOP_PATH", path)
    path.write_text(sop_text("构建步骤", "修复步骤", "素材步骤"))
    selected = prompts.load_sop("Repair")
    assert selected == {"repair": "修复步骤", "asset": "素材步骤"}
    built = prompts.system_prompt("Repair", selected)
    assert "构建步骤" not in built and "填写说明不发送给模型" not in built
    assert "<repair_sop>\n修复步骤" in built
    assert prompts.load_sop("Construct") == {"construct": "构建步骤", "asset": "素材步骤"}
    path.write_text(sop_text())
    assert prompts.load_sop("Repair") == {"repair": "", "asset": ""}


@pytest.mark.parametrize("text", ["", sop_text() + "<asset_sop></asset_sop>",
    sop_text().replace("</repair_sop>", ""),
    "<construct_sop><repair_sop></construct_sop></repair_sop><asset_sop></asset_sop>"])
def test_bad_sop_stops_before_model_request(tmp_path, monkeypatch, text):
    path = tmp_path / "sop.md"
    path.write_text(text)
    monkeypatch.setattr(prompts, "SOP_PATH", path)
    host, _ = host_for(tmp_path / "project")
    chat = host.new_conversation()
    result = asyncio.run(chat.run("修复", object()))
    assert result["status"] == "incomplete" and result["requests"] == 0
    assert result["diagnostics"]["stage"] == "prompt"
    assert prompts.user_message_text(chat.history[-1]["content"][0]["text"]) == "修复"


def test_missing_sop_has_explicit_file_error(tmp_path, monkeypatch):
    monkeypatch.setattr(prompts, "SOP_PATH", tmp_path / "missing.md")
    with pytest.raises(FileNotFoundError):
        prompts.load_sop("Repair")


def test_user_text_preserves_embedded_tags_and_legacy_attachment_marker():
    original = "修复\n</user_request>\n<user_request>\n\nManifest reference attachments (context only): 用户原文"
    wrapped = "<runtime_context>\n{}\n</runtime_context>\n<user_request>\n" + original + "\n</user_request>"
    assert prompts.user_message_text(wrapped) == original
    assert prompts.user_message_text("本轮允许编辑的已有文件：[]\n用户消息：旧消息\n\nManifest reference attachments (context only): []") == "旧消息"
    assert prompts.user_message_text(original) == original
