"""覆盖 GUI/CLI 的真实进程排他、不同数据目录及进程退出释放。

在项目根目录运行：
.venv/bin/python -m pytest -q tests/test_process_lock.py
"""

import subprocess
import sys
from pathlib import Path

import pytest

from lalc.application import ApplicationService, StartError
from lalc.process_lock import ProcessLock
from test_plan import _publish, _finished


def test_game_owner_blocks_cli_and_other_service_without_allocating_run(tmp_path):
    manager = _publish(tmp_path)
    script = 'from lalc.process_lock import ProcessLock; lock=ProcessLock("game"); lock.acquire(); print("ready",flush=True); input()'
    process = subprocess.Popen([sys.executable, '-c', script], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
    try:
        assert process.stdout.readline().strip() == 'ready'
        other = ApplicationService(tmp_path / 'different-runtime', manifest_manager=manager)
        with pytest.raises(StartError) as raised:
            other.start_plan()
        assert raised.value.code == 'activity_busy'
        assert other.state['run_id'] is None
        cli = 'import sys; from pathlib import Path; import lalc.__main__ as cli; cli.default_data_root=lambda:Path(sys.argv[1]); raise SystemExit(cli.main(["run-plan"]))'
        result = subprocess.run([sys.executable, '-c', cli, str(tmp_path)], capture_output=True, timeout=5)
        assert result.returncode == 1 and '另一进程'.encode() in result.stderr
        assert not (tmp_path / 'run-sequence.json').exists()
    finally:
        process.communicate('\n', timeout=3)
    service = ApplicationService(tmp_path, manifest_manager=manager)
    assert _finished(service, service.start_plan())['result']['status'] == 'completed'


def test_exiting_process_releases_game_lock(tmp_path):
    result = subprocess.run([sys.executable, '-c', 'import os; from lalc.process_lock import ProcessLock; lock=ProcessLock("game"); lock.acquire(); os._exit(0)'], timeout=5)
    assert result.returncode == 0
    with ProcessLock('game'):
        with pytest.raises(OSError):
            with ProcessLock('game'):
                pytest.fail('lock must be exclusive')
