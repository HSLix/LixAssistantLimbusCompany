# LALC

LALC automates supported Limbus Company tasks in a focused Windows game window.

The `architecture-refactor` branch is the clean Workflow 2.0 reconstruction. It intentionally does not contain or remain compatible with the legacy global node registry, JSON node graph, or manual Pipeline runtime. The former branch remains available for historical reference and rollback.

## Current status

- Stage 1 product and Agent boundaries: accepted.
- Stage 2 Workflow and deterministic-execution architecture: accepted.
- Stage 2 implementation: complete under the revised scope in [ADR 0026](docs/adr/0026-close-stage-2-without-a-real-game-workflow.md), covering deterministic execution and the developer loop. Real mailbox Workflow and remaining Windows integration/package acceptance are deferred in #317.
- Stage 3 Agent-assisted Component Repair: scope accepted; independent CLI repair implementation and reproducible acceptance pending.
- Stage 3.5 Agent Runtime Step Recovery and Maintenance: prior runtime architecture retained; implementation deferred.
- The historical Architecture Demo from Issue #306 remains design evidence; its hard-coded runtime is no longer the product path.
- Agent-assisted Workflow Drafting and autonomous Capability Expansion: explicitly deferred.

Start with:

- [Domain language](CONTEXT.md)
- [Reconstruction plan](docs/reconstruction-plan.md)
- [Stage 2 implementation slices](docs/stage-2-implementation-slices.md)
- [Developer Workflow tutorial](docs/developer-workflow-tutorial.md)
- [Three-level Workflow and all Trusted Actions sample](example/trusted-actions/README.md)
- [Stage 3 Agent-assisted Component Repair](docs/stage-3-agent-assisted-component-repair.md)
- [Stage 3.5 Agent Runtime Step Recovery and Maintenance](docs/stage-3.5-agent-runtime-step-recovery-and-maintenance.md)
- [Architecture decisions](docs/adr/)

## Development

The current formal runtime uses Python 3.12.10 and uv. It supports focused
Windows game observation and focused input (click, Esc/P/Enter, drag, wait).
Semantic Asset template matching, explicit local detection, and fresh-screenshot
template cropping are available through observe Trusted Actions; see
[the developer tutorial](docs/developer-workflow-tutorial.md).
Input takeover has automated coverage and prior standalone Windows acceptance;
current Workflow integration and Windows package acceptance remain deferred.
OCR and model calls are not implemented yet.

```bash
UV_CACHE_DIR=.generated/uv-cache UV_PYTHON_INSTALL_DIR=.generated/python312 uv sync --all-extras
UV_CACHE_DIR=.generated/uv-cache UV_PYTHON_INSTALL_DIR=.generated/python312 uv run lalc
UV_CACHE_DIR=.generated/uv-cache UV_PYTHON_INSTALL_DIR=.generated/python312 uv run --all-extras pytest
```

Running `lalc` without arguments opens the GUI. The developer workflow uses a
single Git-ignored `candidate/` directory in the current project:

```bash
uv run lalc init
# Edit candidate/manifest.json, candidate/asset-library.json and Component source.
uv run lalc validate
uv run lalc publish
uv run lalc set-default <publish输出的UUID>
uv run lalc run <logical-name> --inputs '{}'
uv run lalc run-plan <plan.json>
uv run lalc list-manifests
uv run lalc clear
uv run lalc data-dir
```

On Windows, `uv run lalc connect` finds the unique running Limbus Company
window, brings it to the foreground once, captures its client area, and writes
the PNG image plus a text log under the local application data directory's
`connections/` folder. It prints both paths; it does not keep a connection
after the command exits. `uv run lalc data-dir` prints the default data
directory for the current system. Every formal Run connects and focuses the game
window and starts physical input monitoring before Component execution.
Foreground activation is requested once and awaited without an automatic cutoff.
Run Stop or terminal Ctrl-C can interrupt cooperative waiting; actual errors retain
their original exception chain.

Physical input interrupts the current Step,
releases held input, and pauses until manual Resume. Resume refreshes observation,
checks the Step's optional condition, and invokes that same Step from its entrypoint;
it never replays the interrupted action. GUI notices appear once and remain movable;
CLI Runs offer an explicit resume/stop prompt. Release failure terminates the Run
and skips later Plan tasks. Reported errors retain the complete original traceback.

Use `publish` → `set-default` → `run` / `run-plan` for normal development. After selecting the Default, omit `--manifest`; reserve it for temporarily running another retained version.

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
