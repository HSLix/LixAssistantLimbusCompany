# LALC

LALC automates supported Limbus Company tasks in a focused Windows game window.

The `architecture-refactor` branch is the clean Workflow 2.0 reconstruction. It intentionally does not contain or remain compatible with the legacy global node registry, JSON node graph, or manual Pipeline runtime. The former branch remains available for historical reference and rollback.

## Current status

- Stage 1 product and Agent boundaries: accepted.
- Stage 2 Workflow and deterministic-execution architecture: accepted.
- Stage 2 implementation: Component Manifest loading and the model-free formal Workflow execution loop are implemented.
- Stage 3 Agent Runtime Step Recovery and Maintenance architecture: accepted.
- The historical Architecture Demo from Issue #306 remains design evidence; its hard-coded runtime is no longer the product path.
- Agent-assisted Workflow Drafting and autonomous Capability Expansion: explicitly deferred.

Start with:

- [Domain language](CONTEXT.md)
- [Reconstruction plan](docs/reconstruction-plan.md)
- [Stage 2 implementation slices](docs/stage-2-implementation-slices.md)
- [Developer Workflow tutorial](docs/developer-workflow-tutorial.md)
- [Runnable virtual Workflow example](examples/virtual-workflow/manifest.json)
- [Stage 3 Agent Runtime Step Recovery and Maintenance](docs/stage-3-agent-runtime-step-recovery-and-maintenance.md)
- [Architecture decisions](docs/adr/)

## Development

The current formal runtime uses Python 3.12.10 and uv. It does not yet perform
real game, OCR, model, or Windows automation.

```bash
UV_CACHE_DIR=.generated/uv-cache UV_PYTHON_INSTALL_DIR=.generated/python312 uv sync --all-extras
UV_CACHE_DIR=.generated/uv-cache UV_PYTHON_INSTALL_DIR=.generated/python312 uv run lalc
UV_CACHE_DIR=.generated/uv-cache UV_PYTHON_INSTALL_DIR=.generated/python312 uv run pytest
```

Running `lalc` without arguments opens the GUI. The developer workflow uses a
single Git-ignored `candidate/` directory in the current project:

```bash
uv run lalc init
# Edit candidate/manifest.json and its flat Python Component files.
uv run lalc validate
uv run lalc publish
uv run lalc list-manifests
uv run lalc run <logical-name> --manifest <manifest-id> --inputs '{}'
uv run lalc set-default <manifest-id>
uv run lalc run <logical-name>
uv run lalc run-plan examples/virtual-workflow/plan.json
uv run lalc clear
```

`publish` keeps the editable candidate and does not change the Default
Manifest. `clear` is the only command that removes it and asks for confirmation.
`run-plan` reads an existing JSON file; edit and save that file with any text
editor. Each Plan uses one Run ID, and its Task/Subworkflow records are saved
under the local data directory's `ledger/` folder.

Release-like dependency installation and the internal `onedir` spike use a
non-editable environment:

```bash
UV_CACHE_DIR=.generated/uv-cache UV_PYTHON_INSTALL_DIR=.generated/python312 uv sync --locked --no-editable --no-default-groups --group build --all-extras
UV_CACHE_DIR=.generated/uv-cache UV_PYTHON_INSTALL_DIR=.generated/python312 uv run --no-sync pyinstaller --clean --noconfirm LALC.spec
```

`--packaging-probe EXTERNAL.py RESULT.json` is a temporary internal diagnostic;
delete it after the later formal external-process runner covers external source
loading and frozen `lalc` API imports. Windows x64 acceptance must be run on
Windows and is not implied by a macOS spike.

## Text encoding

- Project-controlled text files and JSON use UTF-8 without relying on the
  operating-system locale.
- Python text reads and writes must pass `encoding="utf-8"` explicitly,
  including `Path.read_text()`, `Path.write_text()`, and `open()`.
- External text in another encoding must be decoded explicitly at its input
  boundary. Component hashing continues to use the original bytes without a
  decode-and-reencode round trip.

## License

This project is licensed under the GNU Affero General Public License v3.0. See [LICENSE](LICENSE).
