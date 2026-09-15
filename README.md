# LALC

LALC automates supported Limbus Company tasks in a focused Windows game window.

The `architecture-refactor` branch is the clean Workflow 2.0 reconstruction. It intentionally does not contain or remain compatible with the legacy global node registry, JSON node graph, or manual Pipeline runtime. The former branch remains available for historical reference and rollback.

## Current status

- Stage 1 product and Agent boundaries: accepted.
- Stage 2 Workflow and deterministic-execution architecture: accepted.
- Stage 2 implementation: not started.
- Stage 3 Agent Runtime Step Recovery and Maintenance architecture: accepted.
- Architecture Demo and internal packaging spike: implemented by Issue #306.
- Agent-assisted Workflow Drafting and autonomous Capability Expansion: explicitly deferred.

Start with:

- [Domain language](CONTEXT.md)
- [Reconstruction plan](docs/reconstruction-plan.md)
- [Stage 2 implementation slices](docs/stage-2-implementation-slices.md)
- [Stage 3 Agent Runtime Step Recovery and Maintenance](docs/stage-3-agent-runtime-step-recovery-and-maintenance.md)
- [Architecture decisions](docs/adr/)

## Architecture Demo

The Demo uses Python 3.12.10 and uv. Example behavior is deterministic and
replaceable; it performs no real game, OCR, model, or Windows automation.

```bash
UV_CACHE_DIR=.generated/uv-cache UV_PYTHON_INSTALL_DIR=.generated/python312 uv sync --all-extras
UV_CACHE_DIR=.generated/uv-cache UV_PYTHON_INSTALL_DIR=.generated/python312 uv run lalc
UV_CACHE_DIR=.generated/uv-cache UV_PYTHON_INSTALL_DIR=.generated/python312 uv run pytest
```

Release-like dependency installation and the internal `onedir` spike use a
non-editable environment:

```bash
UV_CACHE_DIR=.generated/uv-cache UV_PYTHON_INSTALL_DIR=.generated/python312 uv sync --locked --no-editable --no-default-groups --group build --all-extras
UV_CACHE_DIR=.generated/uv-cache UV_PYTHON_INSTALL_DIR=.generated/python312 uv run --no-sync pyinstaller --clean --noconfirm LALC.spec
```

`--candidate-runner REQUEST.json` is the minimal candidate trial protocol.
`--packaging-probe EXTERNAL.py RESULT.json` is a temporary internal diagnostic;
delete it after packaged Candidate Runner acceptance covers external source
loading and frozen `lalc` API imports. Windows x64 acceptance must be run on
Windows and is not implied by a macOS spike.

## License

This project is licensed under the GNU Affero General Public License v3.0. See [LICENSE](LICENSE).
