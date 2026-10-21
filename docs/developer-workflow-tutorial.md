# 从空白 Candidate 编写第一个 Workflow

本文面向第一次为 LALC 编写 Workflow 的开发者。跟着示例操作后，你会从空白 `candidate/manifest.json` 得到一个可以校验、发布、运行的 model-free Task Workflow。示例只处理字符串，不操作游戏、OCR 或模型；它用于先学会正式组件之间的连接方式。

请在仓库根目录运行以下命令。项目使用 Python 3.12.10 和 uv；首次使用先安装依赖：

```bash
uv sync --all-extras
```

## 先理解这五种文件

一次运行会按这条路径前进：

```text
tasks.greet              Task Workflow：先观察条件，再组织任务并验证结果
  ├─ actions.name_ready  observe Trusted Action：判断输入是否有效
  └─ subworkflows.greet  Subworkflow：组合可复用的工作
       └─ steps.say_hello Step：先观察条件，再执行动作
            ├─ actions.name_ready          observe Trusted Action
            └─ actions.simulated_greeting  control Trusted Action（仅模拟）
```

`manifest.json` 负责把这些稳定的**逻辑名**映射到 Python 源码。文件名只是一种方便编辑的约定；运行时通过 Manifest 映射查找组件，不从文件名推断角色。Task Workflow、Subworkflow 和 Step 在 `components` 中；Trusted Action 在 `trusted_actions` 中。当前示例不需要 Recovery Rule，所以 `recovery_rules` 留空。

## 1. 初始化候选目录

```bash
uv run lalc init
```

如果这是全新安装，且尚无已发布的 Manifest，命令会创建 `candidate/manifest.json`：

```json
{
  "schema_version": 1,
  "components": {},
  "recovery_rules": {},
  "trusted_actions": {},
  "assets": {}
}
```

这只是完整格式的空草稿。`candidate/` 在 Git 忽略列表中，供当前项目目录持续编辑使用。如果该目录已经有内容，`init` 会拒绝覆盖；请先检查原文件。确定不再需要它们时，才运行会二次确认的 `uv run lalc clear`。

如果系统已有已发布的 Manifest，普通 `init` 会把 Default Manifest 的源码复制为可编辑候选；`uv run lalc init --from <manifest-id>` 可以改从另一份已发布 Manifest 开始。若已有 Manifest 但 Default 指针缺失或损坏，命令会列出可用 ID，并提示先执行 `uv run lalc set-default <manifest-id>`。

## 2. 编写五个 Python 文件

在 `candidate/` 下新建以下五个文件。仓库也在 `examples/virtual-workflow/` 保存了相同的可运行样例；若刚初始化的是空白 Candidate，可以用 `cp examples/virtual-workflow/* candidate/` 复制它们（这会覆盖空白 `manifest.json`）。已有手工草稿时不要直接复制覆盖。组件彼此不直接 `import`；跨组件调用统一经过 `ctx.call()` 或 `ctx.action()`，名称必须是字符串字面量。

`candidate/tasks.greet.py`：

```python
"""虚拟问候任务：检查输入、组织流程并验证最终结果。"""

from lalc import task_workflow


@task_workflow
def execute(ctx, *, name: str) -> str:
    """通过一个 Subworkflow 完成问候。"""
    return ctx.call("subworkflows.greet", name=name)


def condition(ctx, *, name: str) -> bool:
    """只在观察到有效名字时进入任务。"""
    return ctx.action("actions.name_ready", name=name)


```

`candidate/subworkflows.greet.py`：

```python
"""虚拟问候 Subworkflow：把一个完整动作交给 Step。"""

from lalc import sub_workflow


@sub_workflow
def execute(ctx, *, name: str) -> str:
    """调用问候 Step 并返回其结果。"""
    return ctx.call("steps.say_hello", name=name)
```

`candidate/steps.say_hello.py`：

```python
"""虚拟问候 Step：检查条件后执行模拟控制动作。"""

from lalc import step


@step
def execute(ctx, *, name: str) -> str:
    """通过 Trusted Action 返回模拟动作结果。"""
    return ctx.action("actions.simulated_greeting", name=name)


def condition(ctx, *, name: str) -> bool:
    """独立启动 Step 时也拒绝空白名字。"""
    return ctx.action("actions.name_ready", name=name)
```

`candidate/actions.name_ready.py`：

```python
"""虚拟 observe Action：判断名字是否有非空白字符。"""


def execute(ctx, *, name: str) -> bool:
    """返回问候输入是否有效，不读取外部环境。"""
    return bool(name.strip())
```

`candidate/actions.simulated_greeting.py`：

```python
"""虚拟 control Action：模拟一次问候，不操作真实设备。"""


def execute(ctx, *, name: str) -> str:
    """仅返回模拟动作结果。"""
    return f"Hello, {name}！"
```

这里的 `control` Action 故意没有真实副作用。它仅证明 Step 可以经正式边界调用控制类操作；真实游戏输入必须由后续实际实现的 Trusted Action 承担，不能把这份示例当作游戏自动化能力。

## 3. 填写完整 Manifest

用以下内容替换 `candidate/manifest.json`。`source_path` 相对于该 JSON 文件所在目录，必须与刚创建的文件名一致；`classification` 决定 Trusted Action 的调用权限。

```json
{
  "schema_version": 1,
  "components": {
    "tasks.greet": {"source_path": "tasks.greet.py"},
    "subworkflows.greet": {"source_path": "subworkflows.greet.py"},
    "steps.say_hello": {"source_path": "steps.say_hello.py"}
  },
  "recovery_rules": {},
  "trusted_actions": {
    "actions.name_ready": {
      "source_path": "actions.name_ready.py",
      "classification": "observe"
    },
    "actions.simulated_greeting": {
      "source_path": "actions.simulated_greeting.py",
      "classification": "control"
    }
  },
  "assets": {}
}
```

候选 Manifest 不填写 `manifest_id`。本教程全部使用 `source_path`，方便编辑源码。候选 Manifest 也允许通过 `component_id` 复用已保存的组件；每个条目必须在两者中选择一种。发布时程序会为整份 Manifest 分配新 ID，并按每个 Python 文件的准确字节计算不可变 Component ID。当前 schema v1 的 `assets` 必须为空。

## 4. 校验、发布、运行

先校验候选：

```bash
uv run lalc validate
```

成功时输出 `Candidate is valid.`。校验会解析完整 Manifest、检查源码和调用关系，并**实际导入候选模块**；因此只在信任这些源码时使用。它不保存发布物，也不改变 Default Manifest。

接着发布：

```bash
uv run lalc publish
```

输出中的 `Published: <manifest-id>` 是这次发布的 ID，请复制实际值。发布会保存不可变组件和 Manifest，但保留 `candidate/`，也不会自动切换 Default。可以用下面的命令查看已发布的版本：

```bash
uv run lalc list-manifests
uv run lalc list-manifests -n 20
```

列表按本地保存时间从新到旧排列，默认最多显示 9 份，最后单独显示 Default Manifest ID。第一次发布后若还没有设置 Default，该行会显示 `unavailable`。

先用刚发布的 ID 显式运行，不必设置 Default：

```bash
uv run lalc run tasks.greet --manifest <manifest-id> --inputs '{"name":"Lix"}'
```

把 `<manifest-id>` 连同尖括号替换为实际 ID。成功的 Run Result JSON 中应包含以下字段，`component_id` 则会是实际源码哈希：

```json
{
  "status": "success",
  "logical_name": "tasks.greet",
  "role": "task_workflow",
  "output": "Hello, Lix！"
}
```

命令输出的实际 JSON 还包含 `component_id`。详细 Execution Trace 保存在应用数据目录的 `traces/<run-id>.jsonl`，不混入标准输出。macOS/Linux 默认数据目录是 `~/.local/share/LALC`，Windows 是 `%LOCALAPPDATA%/LALC`。

确认结果后，才把这份 Manifest 设为后续运行的默认选择：

```bash
uv run lalc set-default <manifest-id>
uv run lalc run tasks.greet --inputs '{"name":"Lix"}'
```

也可以把输入保存在一个 JSON 文件中，再运行 `uv run lalc run tasks.greet --inputs-file <文件路径>`。`--inputs` 与 `--inputs-file` 不能同时使用；两者都不提供时输入是 `{}`，而本例的 `name` 是必填参数，所以会在启动前被拒绝。

开发时也可以直接启动 `subworkflows.greet` 或 `steps.say_hello`，例如：

```bash
uv run lalc run steps.say_hello --inputs '{"name":"Lix"}'
```

它们保留各自的角色和返回值；Task 没有独立 condition 或 verify，前置检查和结果核验建议通过普通 Step 完成。

## 5. 修改与继续开发

发布后，`candidate/` 仍是可编辑草稿。修改其中的 Python 文件或 Manifest 映射，重新执行 `validate` 和 `publish` 就会得到新的 Manifest ID。即使内容没有变化，每次成功发布也会得到新的 Manifest ID；字节完全相同的组件则复用原 Component ID。旧版不会被覆盖，Default 也不会跟着改变。需要采用新版时，再执行 `set-default`。

角色和权限有几个必须遵守的边界：

| 位置 | 可以调用什么 |
| --- | --- |
| Task Workflow 的 `execute()` | Subworkflow、Step、`observe` Action |
| Subworkflow 的 `execute()` | Step、`observe` Action |
| Step 的 `execute()` | `observe` 或 `control` Action；不能调用其他 Workflow Component |


所有 Workflow/Step 使用同步 execute 和直接 JSON 兼容的参数、返回类型。只有 Step 可提供同签名的只读 condition。Task 不提供 condition 或 verify；建议在普通 Step 中核验重要结果，失败时抛出 ExecutionFailure，复用 Step 恢复。

若 `validate` 失败，先看错误中的逻辑名、行号和错误码：

- `source_unreadable`：`source_path` 对应的文件不存在或无法读取。
- `signature_invalid`：execute 或 Step condition 的参数、类型注解不符合要求。
- `component_call_unresolved` / `trusted_action_unresolved`：调用的逻辑名没有在 Manifest 中登记。
- `trusted_action_forbidden`：当前角色调用了不允许的 Action 分类，例如 Task Workflow 直接调用 `control`。
- `component_call_role_invalid`：调用目标的角色不允许，例如 Subworkflow 调用另一个 Subworkflow。
- `condition_forbidden` / `verify_forbidden`：旧 Task 回调需要迁移到普通 Step。

`validate` 通过只表示结构、导入和调用关系有效；是否完成真实任务仍取决于实际 Trusted Action、业务判断和运行验证。修改真实外部操作时，先把副作用限制在对应的 Trusted Action 中。当前 #309 尚未提供真实游戏、OCR、模型操作或 Agent 恢复。
