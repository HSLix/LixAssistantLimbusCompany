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

## pi and model setup

pi runs Agent conversations. Deterministic Workflows do not require pi or a model service. LALC does not automatically install pi or read another pi instance's personal configuration.

- **with-agent package**: uses the bundled `pi/pi.exe` first, then an installed pi if the bundled program is unavailable.
- **without-agent package / source**: install pi for your platform and add the directory containing `pi.exe` (`pi` on other platforms) to `PATH`. The verified integration baseline is **pi 1.4.0**; other versions produce a warning and require separate compatibility checks. CLI Repair also accepts `--pi <absolute-path-to-pi>`.

For example, in PowerShell, with pi extracted to `C:\Tools\pi`:

```powershell
$env:PATH = "C:\Tools\pi;$env:PATH"
pi --version
uv run --frozen lalc --developer
```

For a packaged application, launch `Developer.cmd` from that terminal instead. The example changes `PATH` only for the current terminal and its child processes; add the directory to Windows environment settings for future launches. The source tree's `pi_resources/pi-windows-x64.zip` is a Windows build input, not a runtime installation.

Open **Agent Settings** in the developer workspace and configure:

| Setting | llama.cpp | DeepSeek |
| --- | --- | --- |
| Provider | `llama.cpp` | `deepseek` |
| Base URL | Complete API base URL, e.g. `http://localhost:12138/v1` | `https://api.deepseek.com` |
| Model | Exact model ID reported by your service; required | `deepseek-flash` |
| API Key | Set if your service requires authentication | Set your DeepSeek API key |

LALC does not append `/v1`. For llama.cpp, start the model service separately and select a model whose service metadata declares image support. Settings save when a field loses focus or a selection changes. User and Developer share provider settings but select their providers independently. Windows saves keys with the current user's DPAPI; other platforms retain GUI keys only until the application exits.

Use **Test connection** and **Check model loading status** to query the service; these checks do not send inference requests or load models. The request limit defaults to 20 per message (minimum 2); output length uses the server default. See [Agent setup and usage](docs/agent-repair.md) for CLI configuration and credentials.

## codesearch setup

codesearch provides indexed reference-code search for Developer GUI Construct / Repair. It requires **codesearch 1.7.9 base build**, the fixed quantized MiniLM model and system Git. It is separate from the model service used for Agent conversations; LALC does not automatically download its resources.

- **with-agent package**: includes `agent/codesearch.exe` and `agent/models/`; install Git separately and make it available on `PATH`.
- **without-agent package / source**: put the base executable and a `models/` directory together, then add the executable's directory to `PATH`, just like pi. Source runs also discover `codesearch_resources/codesearch.exe` (`codesearch` on other platforms); if no bundled executable is present, LALC searches `PATH`.

To download the model on Windows, open PowerShell **inside the extracted codesearch folder containing `codesearch.exe`** and run the following commands. They download the five required files into `models/` in the current directory, using LALC's fixed model revision. Internet access to Hugging Face is required.

```powershell
$ErrorActionPreference = 'Stop'
if (-not (Test-Path -LiteralPath '.\codesearch.exe' -PathType Leaf)) {
    throw 'Open PowerShell in the folder containing codesearch.exe first.'
}
$revision = '751bff37182d3f1213fa05d7196b954e230abad9'
$modelRoot = Join-Path (Get-Location).Path "models\models--Xenova--all-MiniLM-L6-v2\snapshots\$revision"
$baseUrl = "https://huggingface.co/Xenova/all-MiniLM-L6-v2/resolve/$revision"

$files = @(
    'config.json'
    'tokenizer_config.json'
    'special_tokens_map.json'
    'tokenizer.json'
    'onnx/model_quantized.onnx'
)

foreach ($file in $files) {
    $destination = Join-Path $modelRoot $file
    New-Item -ItemType Directory -Force -Path (Split-Path $destination) | Out-Null
    Write-Host "Downloading $file"
    Invoke-WebRequest -UseBasicParsing -Uri "$baseUrl/$file" -OutFile $destination
}

Write-Host 'Model download complete. LALC will verify the file hashes before use.'
```

Add this codesearch folder to Windows `Path` for future launches, then restart LALC. For example, if you extracted codesearch to `C:\Tools\codesearch`, you can temporarily configure it in the terminal used to launch LALC:

```powershell
$env:PATH = "C:\Tools\codesearch;$env:PATH"
git --version
codesearch --version
uv run --frozen lalc --developer
```

Run the source launch command from the LALC project root; for a packaged application, launch `Developer.cmd` from its application folder in the same terminal instead. This `PATH` change applies only to that terminal and its child processes. The download commands create the following cache layout under the codesearch folder's `models/` directory (including the fixed revision):

```text
models--Xenova--all-MiniLM-L6-v2/
  snapshots/751bff37182d3f1213fa05d7196b954e230abad9/
    config.json
    tokenizer_config.json
    special_tokens_map.json
    tokenizer.json
    onnx/model_quantized.onnx
```

LALC discovers `models/` beside the selected executable, then falls back to bundled models and its application-data cache if the directories are absent. Optional `LALC_CODESEARCH` and `LALC_CODESEARCH_MODELS` override the executable and model paths; an absent explicit model directory retains the application-data cache fallback. LALC verifies the model files' hashes and prepares its own cache under the application data directory. An existing but incomplete or invalid model directory fails validation rather than silently selecting another model.

Prepare independent Git clones under `<data-dir>/knowledge/`, with an explicit upstream and non-interactive authentication for private repositories. The first content access in each round attempts a version update and index build; LALC manages its own search process, so no manual `codesearch serve` is needed. If search resources are unavailable, literal search and file reading remain available.

See [External knowledge search](docs/external-code-search.md) for repository rules, version updates and fallback behavior, and [Windows resource preparation](docs/windows-packaging.md) for the resource archives and checksums.

## License

GNU Affero General Public License v3.0. See [LICENSE](LICENSE).
