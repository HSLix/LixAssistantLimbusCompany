"""覆盖专用新增源码登记、重名/路径边界、局部校验及取消/失败回退。

在项目根目录运行：
QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest -q tests/test_add_source.py
"""

import json
from pathlib import Path

import pytest

from test_agent_repair import host_for
from test_repair_tools import invoke

COMPONENT = '''"""新增测试 Step。"""
from lalc import step
@step
def execute(ctx) -> str:
    """返回固定值。"""
    return "new"
'''
RULE = '''"""新增恢复规则。"""
def detect(ctx) -> bool:
    """只检测。"""
    return False
def recover(ctx) -> None:
    """无匹配时不调用。"""
    return None
'''


@pytest.mark.parametrize("tool,section,source", [("add_component", "components", COMPONENT),
                                                 ("add_recovery_rule", "recovery_rules", RULE)])
def test_create_register_and_validate_without_automatically_registering_other_files(tmp_path, tool, section, source):
    host, _ = host_for(tmp_path)
    (host.candidate / "temporary.py").write_text("# unreferenced")
    result = invoke(host.conversation.tools, tool, filename="new/source.py", logical_name="new.source", source=source)
    assert not result.get("isError"), result
    assert (host.candidate / "new/source.py").read_text() == source
    manifest = json.loads((host.candidate / "manifest.json").read_text())
    assert manifest[section]["new.source"] == {"source_path": "new/source.py"}
    assert all("temporary" not in entries for entries in (manifest["components"], manifest["recovery_rules"]))
    assert host.conversation.tools.created_files == {"new/source.py"}
    assert host.validate()["ok"]
    assert "new/source.py" in host.diff()


@pytest.mark.parametrize("filename,name,source", [("../outside.py", "new.source", COMPONENT),
    ("/tmp/outside.py", "new.source", COMPONENT), ("steps.total.py", "new.source", COMPONENT),
    ("plan.json/new.py", "new.source", COMPONENT), ("C:\\outside.py", "new.source", COMPONENT),
    ("new.py", "steps.total", COMPONENT), ("new.py", "bad/name", COMPONENT),
    ("new.py", "new.source", RULE), ("new.py", "new.source", "not Python !")])
def test_rejected_additions_do_not_change_candidate(tmp_path, filename, name, source):
    from lalc.developer import candidate_files
    host, _ = host_for(tmp_path)
    before = candidate_files(host.candidate)
    result = invoke(host.conversation.tools, "add_component", filename=filename, logical_name=name, source=source)
    assert result["isError"]
    assert candidate_files(host.candidate) == before
    assert not host.conversation.tools.created_files


def test_manifest_parse_and_cross_section_conflicts_and_unrelated_errors(tmp_path):
    host, _ = host_for(tmp_path)
    tools = host.conversation.tools
    assert not invoke(tools, "add_recovery_rule", filename="rule.py", logical_name="rules.test", source=RULE).get("isError")
    assert invoke(tools, "add_component", filename="new.py", logical_name="rules.test", source=COMPONENT)["isError"]
    (host.candidate / "steps.total.py").write_text("invalid source !")
    assert not invoke(tools, "add_component", filename="new.py", logical_name="steps.new", source=COMPONENT).get("isError")
    (host.candidate / "manifest.json").write_text("broken json")
    assert invoke(tools, "add_component", filename="other.py", logical_name="steps.other", source=COMPONENT)["isError"]
    assert not (host.candidate / "other.py").exists()


@pytest.mark.parametrize("cancel", [False, True])
def test_failed_or_cancelled_transaction_leaves_exact_original(tmp_path, monkeypatch, cancel):
    from lalc.developer import candidate_files
    host, _ = host_for(tmp_path)
    before = candidate_files(host.candidate)
    ticks = []
    def checkpoint():
        ticks.append(1)
        if cancel and len(ticks) == 2:
            raise RuntimeError("cancelled")
    original = Path.replace
    def failed_replace(path, target):
        if path.name == "manifest.json":
            raise OSError("commit unavailable")
        return original(path, target)
    if not cancel:
        monkeypatch.setattr(Path, "replace", failed_replace)
    with pytest.raises((RuntimeError, OSError)):
        host.add_source("components", "new/nested/source.py", "steps.new", COMPONENT, checkpoint)
    assert candidate_files(host.candidate) == before
    assert not (host.candidate / "new").exists()


def test_symlinks_are_rejected_before_addition(tmp_path):
    host, _ = host_for(tmp_path)
    (host.candidate / "linked").symlink_to(tmp_path, target_is_directory=True)
    with pytest.raises(ValueError, match="符号链接"):
        host.add_source("components", "linked/source.py", "steps.new", COMPONENT, lambda: None)
