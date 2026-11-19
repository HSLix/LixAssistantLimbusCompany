"""覆盖页面 JSON 在正式 Plan、开发者试跑和页面之间共享及安全写入。

在项目根目录运行：
QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest -q tests/test_page_resources.py
"""

import json
from pathlib import Path

import pytest

from lalc.application import ApplicationService
from lalc.page_drafts import MemorySettings
from lalc.user_pages import PageContext, UserSettings
from runtime_support import add_plan


def test_plan_trial_and_page_share_rotation(tmp_path):
    candidate = tmp_path / "candidate"
    candidate.mkdir()
    path = candidate / "manifest.json"
    path.write_text(json.dumps({"schema_version": 2, "components": {}, "recovery_rules": {}}))
    add_plan(path, """    rotation = ctx.action("page_resource.read_json", page_id="mirror.settings", name="rotation")
    teams = [2, 5, 8]
    team = rotation["next_team"] if rotation else teams[0]
    next_team = teams[(teams.index(team) + 1) % len(teams)]
    ctx.action("page_resource.write_json", page_id="mirror.settings", name="rotation",
               value={"next_team": next_team, "previous": {"team": team, "settled": True}})
""")
    service = ApplicationService(tmp_path)
    published = service.manifest_manager.publish(path)
    assert published.ok, published.errors
    identity = published.loaded.manifest_id
    store = UserSettings(tmp_path)
    page = PageContext(store, "mirror.settings")
    page.save({"mirror_teams": [2, 5, 8]})

    def run(*, trial=False):
        run_id = service.start_plan(manifest_id=identity, _developer_trial=trial)
        state = service.wait_for(lambda state: state["run_id"] == run_id and state["phase"] == "finished")
        assert state["result"]["status"] == "completed", state["result"]
        return [event["return_value"] for event in state["trace"]
                if event["event"] == "trusted_action_returned"
                and event["logical_name"] == "page_resource.read_json"]

    assert run() == [None]
    assert page.read_resource_json("rotation")["next_team"] == 5
    with service.activity("Agent"):
        assert run(trial=True) == [{"next_team": 5, "previous": {"team": 2, "settled": True}}]
    assert page.read_resource_json("rotation")["next_team"] == 8
    page.save({"mirror_teams": [2, 5, 8]})
    assert run()[0]["next_team"] == 8
    assert page.load() == {"mirror_teams": [2, 5, 8]}
    assert page.read_resource_json("rotation")["next_team"] == 2

    preview = PageContext(MemorySettings(store.value), page.page_id)
    assert preview.read_resource_json("rotation") is None
    preview.write_resource_json("rotation", {"next_team": 40})
    assert page.read_resource_json("rotation")["next_team"] == 2


def test_failed_page_resource_write_keeps_previous_json(tmp_path, monkeypatch):
    page = PageContext(UserSettings(tmp_path), "mirror.settings")
    page.write_resource_json("rotation", {"next_team": 5})
    with pytest.raises(ValueError):
        page.write_resource_json("../rotation", {})
    with pytest.raises(ValueError):
        page.write_resource_json("rotation", {"next_team": float("nan")})

    def fail_replace(self, target):
        raise OSError("replace failed")

    monkeypatch.setattr(Path, "replace", fail_replace)
    with pytest.raises(OSError, match="replace failed"):
        page.write_resource_json("rotation", {"next_team": 8})
    assert page.read_resource_json("rotation") == {"next_team": 5}
    assert len(list((tmp_path / "page-resources").rglob("*.*"))) == 1
