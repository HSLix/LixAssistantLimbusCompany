"""覆盖完整 Context 声明生成、签名边界、CLI 失败和 Pyright 调用检查。

在项目根目录运行：
UV_CACHE_DIR=.generated/uv-cache uv run --frozen pytest -q tests/test_stubgen.py
"""

import ast
import inspect
import json
import os
import subprocess
import sys
from functools import wraps
from pathlib import Path
from typing import Dict, List, Optional

import pytest

import lalc.__main__ as cli
from lalc import RunContext
from lalc.actions import TrustedAction, application_actions
from lalc.runtime import RunContext as RuntimeContext
from lalc import stubgen


def test_generated_stub_matches_registration_and_all_public_members():
    content = stubgen.render_stubs()
    assert Path(stubgen.__file__).with_name('run_context.pyi').read_text(encoding='utf-8') == content
    context = ast.parse(content).body[-1]
    methods = [node for node in context.body if isinstance(node, ast.FunctionDef)]
    assert {node.name for node in methods} == {
        name for name in vars(RunContext) if not name.startswith('_') or name == '__init__'
    }
    actions = [node for node in methods if node.name == 'action']
    assert [node.args.args[1].annotation.slice.value for node in actions] == sorted(application_actions())
    for node in actions:
        name = node.args.args[1].annotation.slice.value
        signature = inspect.signature(application_actions()[name].execute)
        assert [arg.arg for arg in node.args.kwonlyargs] == list(signature.parameters)[1:]
        assert ast.unparse(node.returns) == inspect.formatannotation(
            inspect.signature(application_actions()[name].execute, eval_str=True).return_annotation
        )
        assert node.args.kwarg is None
    drag = next(node for node in actions if node.args.args[1].annotation.slice.value == 'control.drag')
    assert ast.literal_eval(drag.args.kw_defaults[-1]) == 2.5
    assert RuntimeContext is RunContext


def test_wrapped_signature_injection_and_keyword_conversion():
    def original(ctx, /, value: int, *, enabled: bool = True) -> str:
        return str(value)

    @wraps(original)
    def wrapped(*args, **kwargs):
        return original(*args, **kwargs)

    actions = {'observe.wrapped': TrustedAction(wrapped, 'observe')}
    content = stubgen.render_stubs(actions)
    assert "def action(self, logical_name: Literal['observe.wrapped'], *, value: int, enabled: bool = True) -> str" in content
    assert '@typing.overload' not in content  # 单个签名不构成 overload 集。
    wrapped.__signature__ = inspect.signature(original).replace(return_annotation=bool)
    assert ') -> bool: ...' in stubgen.render_stubs(actions)


def test_resolved_annotations_do_not_require_action_module_imports():
    def action(ctx, *, values: 'Optional[List[int]]' = None) -> 'Dict[str, int]':
        return {}

    content = stubgen.render_stubs({'observe.aliases': TrustedAction(action, 'observe')})
    assert 'values: list[int] | None = None) -> dict[str, int]' in content


@pytest.mark.parametrize('source', [
    'def action(ctx, *, value) -> str: pass',
    'def action(ctx, *, value: int): pass',
    'def action(ctx, value: int, /) -> str: pass',
    'def action(ctx, **values: int) -> str: pass',
    'def action() -> str: pass',
    'def action(ctx, *, value: object) -> str: pass',
    'def action(ctx, *, value: str = object()) -> str: pass',
])
def test_unreliable_action_contract_is_an_error(source):
    namespace = {}
    exec(source, namespace)
    with pytest.raises(ValueError, match='observe.invalid'):
        stubgen.render_stubs({'observe.invalid': TrustedAction(namespace['action'], 'observe')})


def test_cli_generates_without_manifest_or_runtime_data(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(stubgen, '__file__', str(tmp_path / 'stubgen.py'))
    monkeypatch.setattr(cli, 'default_data_root', lambda: pytest.fail('generation must not use runtime data'))
    monkeypatch.setattr(cli, 'ManifestManager', lambda *_: pytest.fail('generation must not load a Manifest'))
    assert cli.main(['generate-stubs']) == 0
    target = tmp_path / 'run_context.pyi'
    assert target.read_text(encoding='utf-8') == stubgen.render_stubs()
    assert str(target) in capsys.readouterr().out
    before = target.read_bytes()

    def fail():
        raise ValueError('observe.broken: missing annotation')

    monkeypatch.setattr(stubgen, 'render_stubs', fail)
    assert cli.main(['generate-stubs']) == 1
    assert 'observe.broken: missing annotation' in capsys.readouterr().err
    assert target.read_bytes() == before


def test_pyright_valid_and_invalid_calls(tmp_path):
    """通过根包公开类型检查调用，并确认其他 Context 成员未被 Stub 遮蔽。"""
    root = Path(__file__).resolve().parents[1]
    source = '''from typing import Any, assert_type
from lalc import RunContext, step

@step
def execute(ctx: RunContext) -> None:
    assert_type(ctx.action("control.click", x=1, y=2), None)
    assert_type(ctx.action("observe.capture_screen"), dict[str, int | str])
    assert_type(ctx.action("observe.match_asset", asset="ui/claim"), list[dict[str, str | int | float | list[str] | dict[str, float]]])
    ctx.action("control.drag", x=1, y=2, end_x=3, end_y=4)
    ctx.action(logical_name="control.wait", seconds=0.1)
    assert_type(ctx.call("steps.example", value=1), Any)
    assert_type(ctx.game_language, str)
    assert_type(ctx.capture_screen(), dict[str, Any])
    assert_type(ctx.match_asset("ui/claim"), list[dict[str, Any]])
    assert_type(ctx.crop_asset("ui/claim", region={}), dict[str, Any])
    assert_type(ctx.control_input("wait", seconds=0.1), None)
    ctx.action("control.unknown")  # error
    ctx.action("control.click", x=1)  # error
    ctx.action("control.click", x=1, y=2, typo=3)  # error
    ctx.action("control.click", x="wrong", y=2)  # error
    ctx.action("control.click", 1, 2)  # error
    ctx.action("control.click", ctx=ctx, x=1, y=2)  # error
    result: str = ctx.action("control.click", x=1, y=2)  # error
'''
    fixture = tmp_path / 'calls.py'
    fixture.write_text(source, encoding='utf-8')
    config = tmp_path / 'pyrightconfig.json'
    config.write_text(json.dumps({
        'include': ['calls.py', os.path.relpath(root / 'src/lalc/run_context.pyi', tmp_path)],
        'extraPaths': [str(root / 'src')],
        'pythonVersion': '3.12',
        'typeCheckingMode': 'standard',
    }), encoding='utf-8')
    result = subprocess.run(
        [sys.executable, '-m', 'pyright', '--outputjson', '--pythonpath', sys.executable, '--project', str(config)],
        capture_output=True, text=True, timeout=60,
    )
    assert result.returncode == 1, result.stdout + result.stderr
    report = json.loads(result.stdout)
    assert report['summary']['filesAnalyzed'] == 2, result.stdout + result.stderr
    diagnostics = report['generalDiagnostics']
    assert all(item['file'] == str(fixture) and item['severity'] == 'error' for item in diagnostics), diagnostics
    assert {item['range']['start']['line'] for item in diagnostics} == {
        index for index, line in enumerate(source.splitlines()) if '# error' in line
    }, diagnostics
