"""真实 pi＋本机 HTTP 替身覆盖 Skill 按需读取、权限、诊断、图片及跨轮固定，不访问真实模型。

项目根目录运行：QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest --run-agent-tests -q tests/test_agent_skills_agent.py
"""

import asyncio
from pathlib import Path
import re

import pytest

from lalc.agent_log import read_json, read_events
from lalc.developer_session import DeveloperSession
from test_agent_repair_agent import conversation, tool, answer
from agent_test_server import agent_server


pytestmark = pytest.mark.agent


def write_skill(root, folder="demo", name="demo", description="CATALOG_V1", body="BODY_V1"):
    path = root / folder / "SKILL.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"---\nname: {name}\ndescription: {description}\n---\n{body}", encoding="utf-8")
    return path


def skill_path(body, name="demo"):
    system = body["messages"][0]["content"]
    return Path(re.search(rf"<name>{name}</name>.*?<location>(.*?)</location>", system, re.S)[1])


@pytest.mark.parametrize("mode,entry", [("Construct", "gui"), ("Repair", "gui"), ("Repair", "cli")])
def test_skill_reads_are_frozen_readonly_and_refresh_without_restarting_pi(conversation, tmp_path, mode, entry):
    original, options, state = conversation
    session = DeveloperSession.create(original.host.service, original.host.manager.default_manifest_id(), mode=mode, entry=entry)
    chat = session.conversation()
    root = chat.host.service.data_root / "skills"
    source = write_skill(root)
    unread = write_skill(root, "unread", "unread", body="UNREAD_BODY_SECRET")
    reference = source.with_name("reference.txt")
    reference.write_text("REFERENCE_V1", encoding="utf-8")
    outside = tmp_path / "outside.txt"
    outside.write_text("OUTSIDE_SECRET", encoding="utf-8")
    calls = []
    def respond(body):
        path = skill_path(body)
        calls.append(path)
        system = body["messages"][0]["content"]
        assert "CATALOG_V1" in system and "BODY_V1" not in system and "UNREAD_BODY_SECRET" not in system
        assert {item["function"]["name"] for item in body["tools"]} == set(chat.allowed)
        if len(calls) == 1:
            source.write_text(source.read_text(encoding="utf-8").replace("V1", "V2"), encoding="utf-8")
            reference.write_text("REFERENCE_V2", encoding="utf-8")
            return tool("read", {"path": str(path)})
        requests = [tool("read", {"path": str(path.with_name("reference.txt"))}),
                    tool("edit", {"path": str(path), "oldText": "BODY_V1", "newText": "ILLEGAL_EDIT"}),
                    tool("read", {"path": str(source)}), tool("read", {"path": str(outside)}),
                    tool("read", {"path": "steps.total.py"}), answer()]
        return requests[len(calls) - 2]
    state["respond"] = respond
    result = asyncio.run(chat.run("检查 Skill 和权限", options))
    assert result["status"] == "completed", result
    first_pid = chat.host.service.pi_process.process.pid
    fixed = Path(next(row["event"]["skills_root"] for row in read_events(chat.log.root / "events.jsonl")
                      if row["event"].get("type") == "lalc_ready"))
    assert not fixed.exists()
    assert "BODY_V2" in source.read_text(encoding="utf-8") and "ILLEGAL_EDIT" not in source.read_text(encoding="utf-8")
    returned = [item for item in chat.history if item.get("role") == "toolResult"]
    assert sum(bool(item.get("isError")) for item in returned) == 2
    assert "BODY_V1" in str(returned) and "REFERENCE_V1" in str(returned)
    assert "BODY_V2" not in str(returned) and "REFERENCE_V2" not in str(returned)
    saved = read_json(chat.log.root / "round-1/input.json")
    assert {item["name"] for item in saved["skills"]} == {"demo", "unread"}
    assert "sop" not in saved and "UNREAD_BODY_SECRET" not in str(saved)
    unread.unlink()
    write_skill(root, "fresh", "fresh", "NEW_SKILL", "FRESH_BODY")
    next_calls = []
    def next_round(body):
        system = body["messages"][0]["content"]
        assert "CATALOG_V2" in system and "<name>fresh</name>" in system and "<name>unread</name>" not in system
        path = skill_path(body)
        next_calls.append(path)
        return tool("read", {"path": str(path)}) if len(next_calls) == 1 else answer()
    state["respond"] = next_round
    assert asyncio.run(chat.run("继续读取当前版本", options))["status"] == "completed"
    assert chat.host.service.pi_process.process.pid == first_pid
    assert next_calls[0] == calls[0]
    fixed_roots = [Path(row["event"]["skills_root"]) for row in read_events(chat.log.root / "events.jsonl")
                   if row["event"].get("type") == "lalc_ready"]
    assert fixed_roots[0] != fixed_roots[-1] and all(not path.exists() for path in fixed_roots)
    source.unlink()
    history = read_json(chat.log.root / "context.json")
    assert "BODY_V1" in str(history) and "BODY_V2" in str(history) and "REFERENCE_V1" in str(history)
    assert "UNREAD_BODY_SECRET" not in str(list(read_events(chat.log.root / "events.jsonl")))


def test_native_skill_diagnostics_and_empty_directory_do_not_stop_round(conversation):
    chat, options, state = conversation
    root = chat.host.service.data_root / "skills"
    write_skill(root, "one")
    write_skill(root, "two")
    broken = root / "broken/SKILL.md"
    broken.parent.mkdir()
    broken.write_text("---\nname: broken\n---\nMISSING_DESCRIPTION_BODY", encoding="utf-8")
    events = []
    assert asyncio.run(chat.run("查看目录", options, on_event=events.append))["status"] == "completed"
    warnings = [row["event"]["message"] for row in events if row["event"].get("type") == "skill_warning"]
    assert any("description" in message for message in warnings)
    assert any("collision" in message for message in warnings)
    assert broken.read_text(encoding="utf-8").endswith("MISSING_DESCRIPTION_BODY")
    for path in root.glob("*/SKILL.md"):
        path.unlink()
    for path in root.iterdir():
        path.rmdir()
    assert asyncio.run(chat.run("空目录仍可工作", options))["status"] == "completed"
    assert read_json(chat.log.root / "round-2/input.json")["skills"] == []
    assert list(root.iterdir()) == []


def test_skill_reference_image_survives_source_and_snapshot_cleanup(conversation):
    from test_image_attachments import make_images
    chat, options, state = conversation
    path = write_skill(chat.host.service.data_root / "skills")
    image = make_images(path.parent, formats=("PNG",))[0].rename(path.with_name("reference.png"))
    seen = []
    def respond(body):
        seen.append(body)
        fixed = skill_path(body).with_name("reference.png")
        return tool("read", {"path": str(fixed)}) if len(seen) == 1 else answer()
    state["respond"] = respond
    assert asyncio.run(chat.run("读取 Skill 图片", options))["status"] == "completed"
    image.unlink()
    history = read_json(chat.log.root / "context.json")
    results = [item for item in history if item.get("toolName") == "read"]
    assert any(part["type"] == "image" for part in results[-1]["content"])
