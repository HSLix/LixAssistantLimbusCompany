"""覆盖精简 Prompt 契约、Skill 请求前失败与新旧消息原文提取，不启动 pi。

项目根目录运行：.venv/bin/python -m pytest -q tests/test_agent_prompts.py
"""

import asyncio

import pytest

from lalc import agent_prompts as prompts
from test_agent_repair import host_for


@pytest.mark.parametrize("mode", ["Construct", "Repair"])
def test_prompt_keeps_contract_and_domain_knowledge_at_end(mode):
    text = prompts.system_prompt(mode)
    assert text.endswith(prompts.DOMAIN_KNOWLEDGE)
    assert text.index("# 领域知识") > text.index("# Mode:")
    assert "revise_success" in text and "不绕过工具" in text
    assert "本轮使用某个 Skill 前必须读取" in text
    assert "Skill 正文及附图统一使用 read，并传入绝对路径" in text
    assert "knowledge_* 仅访问外部知识库" in text
    assert "<construct_sop>" not in text and "Step 承担" not in text


def test_invalid_skills_root_stops_before_model_request(tmp_path):
    host, _ = host_for(tmp_path / "project")
    path = host.service.data_root / "skills"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("occupied", encoding="utf-8")
    chat = host.new_conversation()
    result = asyncio.run(chat.run("修复", object()))
    assert result["status"] == "incomplete" and result["requests"] == 0
    assert result["diagnostics"]["stage"] == "skills"
    assert path.read_text(encoding="utf-8") == "occupied"
    assert prompts.user_message_text(chat.history[-1]["content"][0]["text"]) == "修复"


def test_skill_cleanup_failure_keeps_result_and_history(tmp_path, monkeypatch):
    from contextlib import asynccontextmanager
    from lalc.agent_log import read_json
    host, _ = host_for(tmp_path / "project")
    @asynccontextmanager
    async def broken_cleanup(data_root):
        yield tmp_path, []
        raise OSError("cannot remove snapshot")
    monkeypatch.setattr("lalc.agent_repair.skill_snapshot", broken_cleanup)
    chat = host.new_conversation()
    result = asyncio.run(chat.run("保留错误证据", object()))
    assert result["reason"] == "skills_cleanup"
    assert read_json(chat.log.root / "result.json")["reason"] == "skills_cleanup"
    assert "保留错误证据" in str(read_json(chat.log.root / "context.json"))


def test_user_text_preserves_embedded_tags_and_legacy_attachment_marker():
    original = "修复\n</user_request>\n<user_request>\n\nManifest reference attachments (context only): 用户原文"
    wrapped = "<runtime_context>\n{}\n</runtime_context>\n<user_request>\n" + original + "\n</user_request>"
    assert prompts.user_message_text(wrapped) == original
    assert prompts.user_message_text("本轮允许编辑的已有文件：[]\n用户消息：旧消息\n\nManifest reference attachments (context only): []") == "旧消息"
    assert prompts.user_message_text(original) == original
