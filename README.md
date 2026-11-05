# LALC

LixAssistantLimbusCompany (LALC) automates Limbus Company tasks in a focused Windows game window. It provides a user dashboard, Python Workflows and an Agent-assisted developer workspace.

## Deployment

LALC runs on **Windows x64**. Keep the game window restored and in the foreground during automation.

### Windows package

Extract the complete package, then launch:

- `LALC.exe` — User Dashboard.
- `Developer.cmd` — Developer workspace.
- `LALC-console.exe` — command-line tools.

The `with-agent` package includes pi, codesearch and the search embedding model. The `without-agent` package uses separately installed resources. Agent conversations require a separately configured model service.

Application data is stored in `%LOCALAPPDATA%\LALC`, independently of the program directory. Use General Settings → Sharing to import or export Workflows, Assets and pages; see [Sharing](docs/sharing.md).

### From source

Install [uv](https://docs.astral.sh/uv/), then run these commands from the project root. The project pins Python 3.12.10.

```sh
uv sync --frozen --all-extras
uv run --frozen lalc
```

Use `uv run --frozen lalc --developer` to open the developer workspace. Source development keeps the manual `candidate/` in the project directory; other application data uses the user data directory, shown by `uv run --frozen lalc data-dir`.

See [Windows build and resource preparation](docs/windows-packaging.md), [Workflow development](docs/developer-workflow-tutorial.md) and [Agent setup and usage](docs/agent-repair.md) for details.

## License

GNU Affero General Public License v3.0. See [LICENSE](LICENSE).
