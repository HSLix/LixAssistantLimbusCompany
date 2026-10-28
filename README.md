# LALC

2026-10-27 Fluent GUI：User/Developer 已正式迁到完整 FluentWindow，固定页/外置页及三页开发工具使用 Fluent 导航；原有共享服务、即时保存、单一编辑入口和重载边界保持。当前操作与验证见[迁移记录](docs/fluent-gui-migration.md)。


LALC automates supported Limbus Company tasks in a focused Windows game window.

The `architecture-refactor` branch is the clean Workflow 2.0 reconstruction. It intentionally does not contain or remain compatible with the legacy global node registry, JSON node graph, or manual Pipeline runtime. The former branch remains available for historical reference and rollback.

## Current status

- Stage 1 product and Agent boundaries: accepted.
- Stage 2 Workflow and deterministic-execution architecture: accepted.
- Stage 2 implementation: complete under the revised scope in [ADR 0026](docs/adr/0026-close-stage-2-without-a-real-game-workflow.md), covering deterministic execution and the developer loop. Real mailbox Workflow and remaining Windows integration/package acceptance are deferred in #317.
- Stage 3 Agent-assisted Component Repair: CLI/Developer GUI and later Developer Policy increments implemented; final Windows/model/game acceptance remains tracked in #329.
- Stage 4 Extensible User GUI and Python Plan: #331 Python Plan/coexisting windows and #332 external pages/shared Agent settings implemented locally; #333–#334 remain pending. See [#332 usage and evidence](docs/stage-4-332-implementation.md). See [current usage and evidence](docs/stage-4-331-implementation.md) and [accepted design](docs/stage-4-extensible-user-gui.md); see [vertical slices](docs/stage-4-implementation-slices.md).
- Stage 6 (formerly Stage 3.5) Agent Runtime Step Recovery and Maintenance: deferral confirmed on 2026-10-26; prior runtime architecture retained. Other Stage 5–6 proposals remain [pending discussion](docs/reconstruction-plan.md#2026-10-26-规划记录已确认排期与待讨论草案).
- The historical Architecture Demo from Issue #306 remains design evidence; its hard-coded runtime is no longer the product path.
- Agent-assisted Workflow Drafting and autonomous Capability Expansion: explicitly deferred.

Start with:

- [Domain language](CONTEXT.md)
- [Reconstruction plan](docs/reconstruction-plan.md)
- [Stage 2 implementation slices](docs/stage-2-implementation-slices.md)
- [Developer Workflow tutorial](docs/developer-workflow-tutorial.md)
- [Three-level Workflow and all Trusted Actions sample](example/workflow/README.md)
- [Stage 3 Agent-assisted Component Repair](docs/stage-3-agent-assisted-component-repair.md)
- [Stage 6 (formerly Stage 3.5) Agent Runtime Step Recovery and Maintenance](docs/stage-3.5-agent-runtime-step-recovery-and-maintenance.md)
- [Architecture decisions](docs/adr/)

## Development

The commands below use the Python Plan implementation from #331 under [ADR 0032](docs/adr/0032-use-python-plans-and-coexisting-user-developer-guis.md). External settings pages, shared Agent profiles, bilingual information panels and final Windows packaged acceptance belong to later slices.

The current formal runtime uses Python 3.12.10 and uv. It supports focused
Windows game observation and focused input (click, Esc/P/Enter, drag, wait).
Semantic Asset matching with optional priority tags, explicit local detection, and fresh-screenshot
template cropping are available through observe Trusted Actions; Assets update independently of Manifests; see
[the developer tutorial](docs/developer-workflow-tutorial.md).
Input takeover has automated coverage and prior standalone Windows acceptance;
current Workflow integration and Windows package acceptance remain deferred.
OCR and model calls are not implemented yet.

```bash
UV_CACHE_DIR=.generated/uv-cache UV_PYTHON_INSTALL_DIR=.generated/python312 uv sync --all-extras
UV_CACHE_DIR=.generated/uv-cache UV_PYTHON_INSTALL_DIR=.generated/python312 uv run lalc
UV_CACHE_DIR=.generated/uv-cache UV_PYTHON_INSTALL_DIR=.generated/python312 uv run --all-extras pytest
```

Running `lalc` without arguments opens User Dashboard; `lalc --developer` opens Developer GUI. Both windows share one application service. Repeated GUI launches activate the existing application, and game activities also exclude independent CLI runs. The developer workflow uses a
single Git-ignored `candidate/` directory in the current project:

```bash
uv run lalc init
# Edit candidate/manifest.json and Component source.
uv run lalc validate
uv run lalc publish
uv run lalc set-default <publish输出的UUID>
uv run lalc run <logical-name> --inputs '{}'
uv run lalc run-plan
uv run lalc --developer
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
`init` creates and registers an empty `plan.py`. Edit it in the Candidate, then validate and publish. Each runnable Manifest requires exactly one `@automation_plan`; `run-plan` executes its saved immutable source, with optional `--inputs` / `--inputs-file` containing `task_repetitions` and `settings`. JSON Plan paths are no longer executable; old data is preserved and requires explicit republication. CLI returns 1 for completed Plans containing failed tasks. Each Plan uses one Run ID, and its Task/Subworkflow records are saved
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
