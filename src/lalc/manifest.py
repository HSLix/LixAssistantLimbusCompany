from __future__ import annotations

import ast
import json
import logging
import os
import shutil
import sys
import tempfile
import types
import uuid
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from types import MappingProxyType

from .actions import TrustedAction, application_actions
from .runtime import _exception_fields, atomic_write_json, sha256_bytes

SCHEMA_VERSION = 2
SECTIONS = ("components", "recovery_rules")
ROLES = {"task_workflow", "sub_workflow", "step", "automation_plan"}
TOP_LEVEL_FIELDS = {"schema_version", *SECTIONS}
SAVED_TOP_LEVEL_FIELDS = {*TOP_LEVEL_FIELDS, "manifest_id"}
COMPONENT_ID_PREFIX = "sha256:"
EMPTY_PLAN = '"""空调度 Plan；由开发者填写 Task 调用。"""\nfrom typing import Any\nfrom lalc import automation_plan\n\n@automation_plan\ndef execute(ctx, *, task_repetitions: dict[str, int], settings: dict[str, Any]) -> None:\n    return None\n'



@dataclass(frozen=True)
class ValidationError:
    """一次 Manifest 校验发现的、可稳定序列化的问题。"""

    code: str
    message: str
    logical_name: str | None = None
    line: int | None = None
    column: int | None = None
    cause: Exception | None = field(default=None, repr=False, compare=False)

    def as_dict(self) -> dict[str, Any]:
        result = {name: value for name, value in vars(self).items() if value is not None and name != "cause"}
        if self.cause is not None:
            result["traceback"] = _exception_fields(self.cause)["traceback"]
        return result


@dataclass(frozen=True)
class LoadedComponent:
    """已验证并加载的 Component，以及本次 Manifest 赋予它的运行信息。"""

    component_id: str
    module: types.ModuleType
    role: str
    supported_task_ids: tuple[str, ...] = ()


def plan_task_ids(content: str | bytes) -> tuple[str, ...]:
    """只读取 Plan 的字面量任务声明，不推测调用或运行模块表达式。"""
    tree = ast.parse(content)
    declarations = []
    for node in tree.body:
        targets = node.targets if isinstance(node, ast.Assign) else [node.target] if isinstance(node, ast.AnnAssign) else []
        if any(isinstance(target, ast.Name) and target.id == "SUPPORTED_TASK_IDS" for target in targets):
            declarations.append(node.value)
    if not declarations:
        return ()
    try:
        value = ast.literal_eval(declarations[0])
    except (ValueError, TypeError, SyntaxError):
        raise ValueError("SUPPORTED_TASK_IDS must be a literal list of unique non-empty task IDs") from None
    if (len(declarations) != 1 or type(value) is not list or
            any(type(item) is not str or not item.strip() for item in value) or len(set(value)) != len(value)):
        raise ValueError("SUPPORTED_TASK_IDS must be a literal list of unique non-empty task IDs")
    return tuple(value)


@dataclass(frozen=True)
class LoadedManifest:
    """完整加载后的 Manifest；各映射继续以稳定逻辑名称索引。"""

    manifest: dict[str, Any]
    components: dict[str, LoadedComponent]
    recovery_rules: dict[str, LoadedComponent]

    @property
    def manifest_id(self) -> str:
        return self.manifest["manifest_id"]


@dataclass(frozen=True)
class ManifestResult:
    """Manifest 操作结果；成功与结构化错误不会同时出现。"""

    loaded: LoadedManifest | None = None
    errors: tuple[ValidationError, ...] = ()

    @property
    def ok(self) -> bool:
        return self.loaded is not None and not self.errors


@dataclass
class _Source:
    """一次校验所使用的源码快照。"""

    component_id: str
    path: Path
    content: bytes
    tree: ast.Module | None = None


@dataclass
class _Prepared:
    """静态校验阶段生成的正式 Manifest 草稿和源码集合。"""

    manifest: dict[str, Any] | None = None
    sources: dict[str, _Source] = field(default_factory=dict)
    roles: dict[str, str] = field(default_factory=dict)
    errors: list[ValidationError] = field(default_factory=list)


# 同一内容在不同存储根目录加载时，源码位置也必须对应各自的哈希文件。
_MODULE_CACHE: dict[tuple[Path, str], tuple[bytes, types.ModuleType]] = {}


class ManifestManager:
    """校验、加载、发布并选择已信任的完整 Component Manifest。"""

    def __init__(
        self,
        data_root: Path,
        *,
        logger: logging.Logger | None = None,
        actions: Mapping[str, TrustedAction] | None = None,
    ) -> None:
        self.data_root = Path(data_root)
        self.components_dir = self.data_root / "components"
        self.manifests_dir = self.data_root / "manifests"
        self.logger = logger or logging.getLogger(__name__)
        self.actions = MappingProxyType(dict(application_actions() if actions is None else actions))
        self.default: LoadedManifest | None = None

    def publish(self, candidate_path: Path) -> ManifestResult:
        """完整校验并发布开发者候选，但不改变 Default Manifest。"""

        candidate_path = Path(candidate_path)
        phase = "validate_manifest"
        try:
            prepared = self._prepare(candidate_path, saved=False)
            if prepared.errors:
                # 静态错误必须阻止整个批次导入，避免部分顶层代码提前执行。
                return ManifestResult(errors=tuple(prepared.errors))

            manifest_id = str(uuid.uuid4())
            assert prepared.manifest is not None
            manifest = {"schema_version": SCHEMA_VERSION, "manifest_id": manifest_id}
            manifest.update({name: prepared.manifest[name] for name in SECTIONS})
            phase = "write_components"
            self.components_dir.mkdir(parents=True, exist_ok=True)
            self.manifests_dir.mkdir(parents=True, exist_ok=True)
            for source in prepared.sources.values():
                self._store_component(source)
                source.path = (self.components_dir / f"{source.component_id.removeprefix(COMPONENT_ID_PREFIX)}.py").resolve()
            phase = "load_components"
            loaded, errors = self._load(manifest, prepared)
            if errors:
                return ManifestResult(errors=tuple(errors))
            phase = "write_manifest"
            manifest_path = self.manifests_dir / f"{manifest_id}.json"
            if manifest_path.exists():
                raise FileExistsError(manifest_path)
            atomic_write_json(manifest_path, manifest)
            return ManifestResult(loaded=loaded)
        except Exception as error:
            self.logger.exception("Manifest update failed during %s", phase)
            return ManifestResult(
                errors=(ValidationError("manifest_update_failed", str(error), cause=error),)
            )

    def load(self, manifest_id: str) -> ManifestResult:
        """完整校验并加载一个既有 Manifest，不改变 Default。"""

        try:
            parsed_id = uuid.UUID(manifest_id)
        except (TypeError, ValueError, AttributeError):
            return ManifestResult(
                errors=(ValidationError("manifest_id_invalid", "Manifest ID must be a UUID."),)
            )
        if str(parsed_id) != manifest_id:
            return ManifestResult(
                errors=(ValidationError("manifest_id_invalid", "Manifest ID must be a canonical UUID."),)
            )
        path = self.manifests_dir / f"{manifest_id}.json"
        prepared = self._prepare(path, saved=True)
        if prepared.errors:
            return ManifestResult(errors=tuple(prepared.errors))
        assert prepared.manifest is not None
        if prepared.manifest.get("manifest_id") != manifest_id:
            return ManifestResult(
                errors=(ValidationError("manifest_id_mismatch", "Manifest ID does not match its file name."),)
            )
        loaded, errors = self._load(prepared.manifest, prepared)
        if errors:
            return ManifestResult(errors=tuple(errors))
        return ManifestResult(loaded=loaded)

    def set_default(self, manifest_id: str) -> ManifestResult:
        """完整加载一个既有 Manifest 后原子选择为 Default。"""

        result = self.load(manifest_id)
        if not result.ok:
            return result
        if self.default_manifest_id() == manifest_id:
            self.default = result.loaded
            return result
        try:
            self.manifests_dir.mkdir(parents=True, exist_ok=True)
            atomic_write_json(self.manifests_dir / "default.json", {"manifest_id": manifest_id})
        except Exception as error:
            self.logger.exception("Manifest update failed during set_default")
            return ManifestResult(errors=(ValidationError("manifest_update_failed", str(error), cause=error),))
        self.default = result.loaded
        return result

    def load_default(self) -> ManifestResult:
        """按照 default.json 加载 Default Manifest，但不重写磁盘状态。"""

        data, errors = self._read_json(self.manifests_dir / "default.json")
        if errors:
            return ManifestResult(errors=tuple(errors))
        if not isinstance(data, dict) or set(data) != {"manifest_id"} or not isinstance(
            data.get("manifest_id"), str
        ):
            return ManifestResult(
                errors=(ValidationError("default_manifest_invalid", "default.json must contain only manifest_id."),)
            )
        result = self.load(data["manifest_id"])
        if result.ok:
            self.default = result.loaded
        return result

    def validate(self, path: Path, *, saved: bool = False) -> tuple[ValidationError, ...]:
        """完整校验并导入可信源码，但不写入发布物或改变 Default。"""

        prepared = self._prepare(Path(path), saved=saved)
        if prepared.errors:
            return tuple(prepared.errors)
        assert prepared.manifest is not None
        manifest = dict(prepared.manifest)
        _, errors = self._load(manifest, prepared, cache=saved)
        return tuple(errors)

    def default_manifest_id(self) -> str | None:
        """读取 Default ID；无效指针返回 None，且不导入 Component。"""

        data, errors = self._read_json(self.manifests_dir / "default.json")
        if errors or not isinstance(data, dict) or set(data) != {"manifest_id"}:
            return None
        manifest_id = data.get("manifest_id")
        if not isinstance(manifest_id, str):
            return None
        try:
            parsed_id = uuid.UUID(manifest_id)
        except ValueError:
            return None
        if str(parsed_id) != manifest_id:
            return None
        manifest, manifest_errors = self._read_json(
            self.manifests_dir / f"{manifest_id}.json"
        )
        if manifest_errors or not isinstance(manifest, dict):
            return None
        return manifest_id if manifest.get("manifest_id") == manifest_id else None

    def list_manifests(self) -> list[dict[str, Any]]:
        """按文件时间倒序列出 retained Manifest，不导入 Component。"""

        summaries: list[dict[str, Any]] = []
        for path in self.manifests_dir.glob("*.json"):
            if path.name == "default.json":
                continue
            data, errors = self._read_json(path)
            if (errors or not isinstance(data, dict)
                    or set(data) != SAVED_TOP_LEVEL_FIELDS
                    or type(data.get("schema_version")) is not int
                    or data["schema_version"] != SCHEMA_VERSION):
                continue
            sections = {
                name: len(data.get(name, {})) if isinstance(data.get(name), dict) else 0
                for name in SECTIONS
            }
            try:
                saved_at = path.stat().st_mtime
            except OSError:
                continue
            summaries.append(
                {
                    "manifest_id": data.get("manifest_id", path.stem),
                    "saved_at": saved_at,
                    **sections,
                }
            )
        return sorted(summaries, key=lambda item: item["saved_at"], reverse=True)

    def initialize_candidate(
        self, candidate_dir: Path, *, manifest_id: str | None = None
    ) -> tuple[ValidationError, ...]:
        """把一个 retained Manifest 原子物化为扁平 Developer Candidate。"""

        target = Path(candidate_dir)
        if target.exists() and (not target.is_dir() or any(target.iterdir())):
            return (
                ValidationError(
                    "candidate_not_empty",
                    f"{target} is not empty; run lalc clear before initialization.",
                ),
            )

        if manifest_id is None:
            retained = any(
                path.name != "default.json" for path in self.manifests_dir.glob("*.json")
            )
            if not retained:
                manifest = {
                    "schema_version": SCHEMA_VERSION,
                    "components": {},
                    "recovery_rules": {},
                }
            else:
                result = self.load_default()
                if not result.ok:
                    return result.errors
                assert result.loaded is not None
                manifest = result.loaded.manifest
        else:
            result = self.load(manifest_id)
            if not result.ok:
                return result.errors
            assert result.loaded is not None
            manifest = result.loaded.manifest

        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = Path(tempfile.mkdtemp(prefix=f".{target.name}.", dir=target.parent))
        try:
            candidate: dict[str, Any] = {
                "schema_version": SCHEMA_VERSION,
                "components": {},
                "recovery_rules": {},
            }
            if not manifest["components"]:
                (temporary / "plan.py").write_text(EMPTY_PLAN, encoding="utf-8")
                candidate["components"]["plans.default"] = {"source_path": "plan.py"}
            for section in SECTIONS:
                for logical_name, entry in manifest.get(section, {}).items():
                    filename = f"{logical_name}.py"
                    component_id = entry["component_id"]
                    digest = component_id.removeprefix(COMPONENT_ID_PREFIX)
                    (temporary / filename).write_bytes(
                        (self.components_dir / f"{digest}.py").read_bytes()
                    )
                    candidate_entry = {"source_path": filename}
                    candidate[section][logical_name] = candidate_entry
            atomic_write_json(temporary / "manifest.json", candidate)
            if target.exists():
                target.rmdir()
            temporary.replace(target)
            return ()
        except Exception as error:
            self.logger.exception("Candidate initialization failed")
            return (ValidationError("candidate_initialization_failed", str(error), cause=error),)
        finally:
            if temporary.exists():
                shutil.rmtree(temporary)

    def _prepare(self, manifest_path: Path, *, saved: bool) -> _Prepared:
        """解析完整文档并尽可能收集互不依赖的静态错误。"""

        prepared = _Prepared()
        data, read_errors = self._read_json(manifest_path)
        prepared.errors.extend(read_errors)
        if data is None:
            return prepared
        if not isinstance(data, dict):
            prepared.errors.append(ValidationError("manifest_type_invalid", "Manifest must be an object."))
            return prepared

        allowed = SAVED_TOP_LEVEL_FIELDS if saved else TOP_LEVEL_FIELDS
        required = allowed
        self._check_fields(data, allowed, required, prepared.errors)
        if data.get("schema_version") != SCHEMA_VERSION or isinstance(data.get("schema_version"), bool):
            prepared.errors.append(
                ValidationError("schema_version_unsupported", "schema_version must be integer 2; legacy formats are not supported.")
            )
        if saved:
            self._check_manifest_id(data.get("manifest_id"), prepared.errors)
        elif "manifest_id" in data:
            prepared.errors.append(
                ValidationError("manifest_id_forbidden", "Candidate Manifest cannot provide manifest_id.")
            )

        for section in SECTIONS:
            if section in data and not isinstance(data[section], dict):
                prepared.errors.append(
                    ValidationError("manifest_field_type_invalid", f"{section} must be an object.")
                )
        if any(not isinstance(data.get(section), dict) for section in SECTIONS):
            return prepared

        names: dict[str, str] = {}
        for section in SECTIONS:
            for logical_name in data[section]:
                if not isinstance(logical_name, str) or not self._valid_logical_name(logical_name):
                    prepared.errors.append(
                        ValidationError(
                            "logical_name_invalid",
                            "Logical name must contain case-sensitive Python identifiers separated by '.'.",
                            str(logical_name),
                        )
                    )
                if logical_name in names:
                    prepared.errors.append(
                        ValidationError(
                            "logical_name_duplicate",
                            f"Logical name also appears in {names[logical_name]}.",
                            logical_name,
                        )
                    )
                else:
                    names[logical_name] = section

        normalized = {
            "schema_version": SCHEMA_VERSION,
            "components": {},
            "recovery_rules": {},
        }
        if saved and isinstance(data.get("manifest_id"), str):
            normalized["manifest_id"] = data["manifest_id"]

        for section in SECTIONS:
            for logical_name, entry in data[section].items():
                normalized_entry = self._prepare_entry(
                    manifest_path, section, logical_name, entry, saved, prepared
                )
                if normalized_entry is not None:
                    normalized[section][logical_name] = normalized_entry
        prepared.manifest = normalized

        self._parse_sources(normalized, prepared)
        if sum(role == "automation_plan" for role in prepared.roles.values()) != 1:
            prepared.errors.append(ValidationError("unique_plan_required",
                "Manifest is incompatible: exactly one Python Automation Plan is required; explicitly republish to migrate."))
        self._validate_calls(normalized, prepared)
        return prepared

    def _prepare_entry(
        self,
        manifest_path: Path,
        section: str,
        logical_name: str,
        entry: Any,
        saved: bool,
        prepared: _Prepared,
    ) -> dict[str, Any] | None:
        if not isinstance(entry, dict):
            prepared.errors.append(
                ValidationError("entry_type_invalid", "Manifest entry must be an object.", logical_name)
            )
            return None
        allowed = {"component_id"}
        if not saved:
            allowed.add("source_path")
        required: set[str] = set()
        self._check_fields(entry, allowed, required, prepared.errors, logical_name)

        component_id = entry.get("component_id")
        source_path = entry.get("source_path")
        if saved:
            if source_path is not None or not isinstance(component_id, str):
                prepared.errors.append(
                    ValidationError(
                        "component_reference_invalid",
                        "Saved entry must contain one component_id.",
                        logical_name,
                    )
                )
                return None
        else:
            has_component_id = "component_id" in entry
            has_source_path = "source_path" in entry
            if has_component_id == has_source_path:
                prepared.errors.append(
                    ValidationError(
                        "component_reference_invalid",
                        "Candidate entry must contain either component_id or source_path, but not both.",
                        logical_name,
                    )
                )
                return None
            selected = component_id if has_component_id else source_path
            if not isinstance(selected, str):
                prepared.errors.append(
                    ValidationError(
                        "manifest_field_type_invalid",
                        "component_id or source_path must be a string.",
                        logical_name,
                    )
                )
                return None

        if isinstance(source_path, str):
            source = self._candidate_source(manifest_path, source_path, logical_name, prepared.errors)
            if source is None:
                return None
            component_id = COMPONENT_ID_PREFIX + sha256_bytes(source[1])
            stored_path = self.components_dir / f"{component_id.removeprefix(COMPONENT_ID_PREFIX)}.py"
            if stored_path.exists():
                try:
                    stored_content = stored_path.read_bytes()
                except OSError as error:
                    prepared.errors.append(
                        ValidationError("component_source_unreadable", str(error), logical_name, cause=error)
                    )
                    return None
                if stored_content != source[1]:
                    prepared.errors.append(
                        ValidationError(
                            "component_id_mismatch",
                            "Stored source does not match the candidate Component ID.",
                            logical_name,
                        )
                    )
                    return None
            prepared.sources.setdefault(component_id, _Source(component_id, source[0], source[1]))
        elif isinstance(component_id, str):
            source = self._stored_source(component_id, logical_name, prepared.errors)
            if source is None:
                return None
            prepared.sources.setdefault(component_id, source)
        else:
            return None

        normalized = {"component_id": component_id}
        return normalized

    def _candidate_source(
        self,
        manifest_path: Path,
        source_path: str,
        logical_name: str,
        errors: list[ValidationError],
    ) -> tuple[Path, bytes] | None:
        relative = Path(source_path)
        base = manifest_path.parent.resolve()
        if relative.is_absolute():
            errors.append(
                ValidationError("source_path_invalid", "source_path must be relative.", logical_name)
            )
            return None
        path = (manifest_path.parent / relative).resolve()
        if not path.is_relative_to(base):
            errors.append(
                ValidationError(
                    "source_path_escape", "source_path must remain inside the candidate directory.", logical_name
                )
            )
            return None
        try:
            return path, path.read_bytes()
        except OSError as error:
            errors.append(ValidationError("source_unreadable", str(error), logical_name, cause=error))
            return None

    def _stored_source(
        self, component_id: str, logical_name: str, errors: list[ValidationError]
    ) -> _Source | None:
        digest = self._component_digest(component_id)
        if digest is None:
            errors.append(
                ValidationError("component_id_invalid", "Component ID must be sha256:<64 lowercase hex>.", logical_name)
            )
            return None
        path = self.components_dir / f"{digest}.py"
        try:
            content = path.read_bytes()
        except OSError as error:
            errors.append(ValidationError("component_source_unreadable", str(error), logical_name, cause=error))
            return None
        if sha256_bytes(content) != digest:
            errors.append(
                ValidationError("component_id_mismatch", "Stored source does not match Component ID.", logical_name)
            )
            return None
        return _Source(component_id, path, content)

    def _parse_sources(self, manifest: dict[str, Any], prepared: _Prepared) -> None:
        """按源码快照解析结构；同一 Component ID 只解析一次。"""

        references: dict[str, list[tuple[str, str]]] = {}
        for section in SECTIONS:
            for name, entry in manifest[section].items():
                references.setdefault(entry["component_id"], []).append((section, name))

        for component_id, source in prepared.sources.items():
            try:
                source.tree = ast.parse(source.content, filename=str(source.path))
            except (SyntaxError, UnicodeDecodeError) as error:
                prepared.errors.append(
                    ValidationError(
                        "source_syntax_invalid",
                        str(error),
                        references.get(component_id, [("", None)])[0][1],
                        getattr(error, "lineno", None),
                        getattr(error, "offset", None),
                    )
                )
                continue

            assert source.tree is not None
            for section, logical_name in references.get(component_id, []):
                if section == "components":
                    role = self._validate_component_source(source.tree, logical_name, prepared.errors)
                    if role:
                        prepared.roles[logical_name] = role
                elif section == "recovery_rules":
                    self._validate_recovery_source(source.tree, logical_name, prepared.errors)
            self._validate_source_structure(source.tree, references.get(component_id, []), prepared.errors)

    def _validate_component_source(
        self, tree: ast.Module, logical_name: str, errors: list[ValidationError]
    ) -> str | None:
        functions = self._top_functions(tree)
        execute = functions.get("execute", [])
        decorated = [
            (node, decorator)
            for node in ast.walk(tree)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            for decorator in node.decorator_list
            if self._decorator_name(decorator) in ROLES
        ]
        role: str | None = None
        if len(execute) != 1:
            errors.append(
                ValidationError("execute_invalid", "Component must define exactly one execute function.", logical_name)
            )
        else:
            decorators = [self._decorator_name(item) for item in execute[0].decorator_list]
            if (
                len(decorators) != 1
                or decorators[0] not in ROLES
                or len(decorated) != 1
                or decorated[0][0] is not execute[0]
            ):
                errors.append(
                    self._node_error(
                        "component_role_invalid",
                        "execute must have exactly one plain role decorator.",
                        logical_name,
                        execute[0],
                    )
                )
            else:
                role = decorators[0]
                self._validate_execute_signature(execute[0], logical_name, errors, plan=role == "automation_plan")

        condition = functions.get("condition", [])
        verify = functions.get("verify", [])
        if role == "automation_plan":
            try:
                plan_task_ids(ast.unparse(tree))
            except ValueError as error:
                errors.append(ValidationError("plan_tasks_invalid", str(error), logical_name))
            if condition or verify:
                errors.append(ValidationError("plan_callable_forbidden", "Plan cannot define condition or verify.", logical_name))
            if execute and not (self._input_annotation_allowed(execute[0].returns)
                                or isinstance(execute[0].returns, ast.Name) and execute[0].returns.id == "Any"):
                errors.append(ValidationError("signature_invalid", "Plan return must be JSON-compatible.", logical_name))
        elif role == "task_workflow":
            if execute and not self._input_annotation_allowed(execute[0].returns):
                errors.append(
                    self._node_error(
                        "signature_invalid",
                        "Task Workflow return annotation must be directly JSON-compatible.",
                        logical_name,
                        execute[0],
                    )
                )
            if condition:
                errors.append(ValidationError(
                    "condition_forbidden", "Task Workflow entry checks belong in a Step, not condition.", logical_name,
                ))
            if verify:
                errors.append(ValidationError(
                    "verify_forbidden", "Task Workflow result checks belong in a Step, not verify.", logical_name,
                ))
        elif role == "sub_workflow":
            if condition or verify:
                errors.append(
                    ValidationError(
                        "subworkflow_callable_forbidden",
                        "Subworkflow cannot define condition or verify.",
                        logical_name,
                    )
                )
        elif role == "step":
            if verify:
                errors.append(ValidationError("verify_forbidden", "Step cannot define verify.", logical_name))
            if len(condition) > 1:
                errors.append(ValidationError("condition_invalid", "condition may be defined once.", logical_name))
            elif condition and execute:
                self._validate_condition_signature(condition[0], execute[0], logical_name, errors)
        return role

    def _validate_recovery_source(
        self, tree: ast.Module, logical_name: str, errors: list[ValidationError]
    ) -> None:
        functions = self._top_functions(tree)
        for name, return_name in (("detect", "bool"), ("recover", "None")):
            nodes = functions.get(name, [])
            if len(nodes) != 1:
                errors.append(
                    ValidationError(
                        "recovery_callable_invalid", f"Recovery Rule must define exactly one {name} function.", logical_name
                    )
                )
            elif not self._simple_ctx_signature(nodes[0], return_name):
                errors.append(
                    self._node_error(
                        "signature_invalid", f"{name} must have signature {name}(ctx) -> {return_name}.", logical_name, nodes[0]
                    )
                )
        self._reject_role_decorators(tree, logical_name, errors)

    def _validate_source_structure(
        self,
        tree: ast.Module,
        references: list[tuple[str, str]],
        errors: list[ValidationError],
    ) -> None:
        logical_name = references[0][1] if references else None
        if not ast.get_docstring(tree, clean=False):
            errors.append(ValidationError("module_docstring_missing", "Component needs a module docstring.", logical_name))
        for node in ast.walk(tree):
            if isinstance(node, ast.ExceptHandler):
                errors.append(
                    self._node_error("except_forbidden", "Formal Component cannot catch exceptions.", logical_name, node)
                )
            if isinstance(node, ast.Try):
                for child in node.finalbody:
                    for nested in ast.walk(child):
                        if isinstance(nested, (ast.Return, ast.Break, ast.Continue, ast.Raise)):
                            errors.append(
                                self._node_error(
                                    "finally_control_flow_forbidden",
                                    "finally cannot replace or suppress the active result or exception.",
                                    logical_name,
                                    nested,
                                )
                            )
        self._validate_imports(tree, logical_name, errors)

    def _validate_imports(
        self,
        tree: ast.Module,
        logical_name: str | None,
        errors: list[ValidationError],
    ) -> None:
        allowed = sys.stdlib_module_names
        for node in ast.walk(tree):
            modules: list[str] = []
            relative = False
            if isinstance(node, ast.Import):
                modules = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                relative = node.level > 0
                modules = [node.module or ""]
            else:
                continue
            if relative or any(
                module != "lalc"
                and module.split(".", 1)[0] not in allowed
                for module in modules
            ):
                errors.append(
                    self._node_error(
                        "import_forbidden",
                        "Import is not part of the allowed Component runtime.",
                        logical_name,
                        node,
                    )
                )

    def _validate_calls(self, manifest: dict[str, Any], prepared: _Prepared) -> None:
        """校验静态调用目标、角色限制和 Trusted Action 权限。"""

        actions = {name: action.classification for name, action in self.actions.items()}
        for logical_name, entry in manifest["components"].items():
            source = prepared.sources.get(entry["component_id"])
            role = prepared.roles.get(logical_name)
            if source is None or source.tree is None or role is None:
                continue
            forbidden_nodes: set[int] = set()
            for function_name in ("condition",):
                for function in self._top_functions(source.tree).get(function_name, []):
                    for call in self._ctx_calls(function):
                        forbidden_nodes.add(id(call))
                        prepared.errors.append(
                            self._node_error(
                                "component_call_forbidden",
                                f"ctx.call is forbidden inside {function_name}.",
                                logical_name,
                                call,
                            )
                        )
            for call in self._ctx_calls(source.tree):
                if id(call) in forbidden_nodes:
                    continue
                if role == "step":
                    prepared.errors.append(
                        self._node_error(
                            "component_call_forbidden", "Step cannot use ctx.call.", logical_name, call
                        )
                    )
                    continue
                target = self._literal_call_target(call)
                if target is None:
                    prepared.errors.append(
                        self._node_error(
                            "component_call_dynamic", "ctx.call target must be a string literal.", logical_name, call
                        )
                    )
                    continue
                target_role = prepared.roles.get(target)
                if target_role is None:
                    prepared.errors.append(
                        self._node_error(
                            "component_call_unresolved", f"Unknown Component target: {target}", logical_name, call
                        )
                    )
                elif target_role == "automation_plan" or (role == "automation_plan" and target_role != "task_workflow"):
                    prepared.errors.append(self._node_error("component_call_role_invalid",
                        "Plan may only call Task Workflows; Components cannot call Plan.", logical_name, call))
                elif target_role == "task_workflow" and role != "automation_plan":
                    prepared.errors.append(
                        self._node_error(
                            "component_call_role_invalid", "Task Workflow cannot be called through ctx.call.", logical_name, call
                        )
                    )
                elif role == "sub_workflow" and target_role == "sub_workflow":
                    prepared.errors.append(
                        self._node_error(
                            "component_call_role_invalid",
                            "Subworkflow cannot call another Subworkflow.",
                            logical_name,
                            call,
                        )
                    )
            self._validate_action_calls(source.tree, logical_name, role, actions, prepared.errors)

        for logical_name, entry in manifest["recovery_rules"].items():
            source = prepared.sources.get(entry["component_id"])
            if source is None or source.tree is None:
                continue
            for call in self._ctx_calls(source.tree):
                prepared.errors.append(
                    self._node_error(
                        "component_call_forbidden", "Recovery Rule cannot use ctx.call.", logical_name, call
                    )
                )
            self._validate_action_calls(source.tree, logical_name, "recovery_rule", actions, prepared.errors)

    def _validate_action_calls(
        self,
        tree: ast.Module,
        logical_name: str,
        role: str,
        actions: dict[str, str],
        errors: list[ValidationError],
    ) -> None:
        allowed = {
            ("automation_plan", "execute"): set(),
            ("task_workflow", "execute"): {"observe"},
            ("sub_workflow", "execute"): {"observe"},
            ("step", "execute"): {"observe", "control"},
            ("step", "condition"): {"observe"},
            ("recovery_rule", "detect"): {"observe"},
            ("recovery_rule", "recover"): {"observe", "control"},
        }
        for function_name, nodes in self._top_functions(tree).items():
            permission = allowed.get((role, function_name))
            if permission is None:
                continue
            for function in nodes:
                for call in self._ctx_action_calls(function):
                    target = self._literal_call_target(call)
                    if target is None:
                        errors.append(
                            self._node_error(
                                "trusted_action_dynamic",
                                "ctx.action target must be a string literal.",
                                logical_name,
                                call,
                            )
                        )
                        continue
                    classification = actions.get(target)
                    if classification is None:
                        errors.append(
                            self._node_error(
                                "trusted_action_unresolved",
                                f"Unknown Trusted Action target: {target}",
                                logical_name,
                                call,
                            )
                        )
                    elif classification not in permission:
                        errors.append(
                            self._node_error(
                                "trusted_action_forbidden",
                                f"{function_name} cannot call a {classification} Trusted Action.",
                                logical_name,
                                call,
                            )
                        )

    def _load(
        self, manifest: dict[str, Any], prepared: _Prepared, *, cache: bool = True,
    ) -> tuple[LoadedManifest | None, list[ValidationError]]:
        """在零静态错误之后加载全部 Component，并收集全部导入失败。"""

        modules: dict[str, types.ModuleType] = {}
        errors: list[ValidationError] = []
        references = {
            entry["component_id"]: name
            for section in SECTIONS
            for name, entry in manifest[section].items()
        }
        for component_id, source in prepared.sources.items():
            try:
                modules[component_id] = self._load_module(source, cache=cache)
            except Exception as error:
                self.logger.exception("Component import failed: %s (%s)", references.get(component_id), source.path)
                errors.append(
                    ValidationError("component_import_failed", str(error), references.get(component_id), cause=error)
                )
        if errors:
            return None, errors

        loaded_sections: dict[str, dict[str, LoadedComponent]] = {name: {} for name in SECTIONS}
        for section in SECTIONS:
            for name, entry in manifest[section].items():
                component_id = entry["component_id"]
                module = modules[component_id]
                if section == "components":
                    role = prepared.roles[name]
                    marker = getattr(getattr(module, "execute", None), "__lalc_role__", None)
                    if marker != role:
                        errors.append(
                            ValidationError(
                                "component_runtime_role_invalid",
                                "Imported execute role does not match validated source.",
                                name,
                            )
                        )
                        continue
                elif section == "recovery_rules":
                    role = "recovery_rule"
                    if not all(callable(getattr(module, item, None)) for item in ("detect", "recover")):
                        errors.append(
                            ValidationError("component_runtime_callable_missing", "Recovery callable missing.", name)
                        )
                        continue
                loaded_sections[section][name] = LoadedComponent(
                    component_id, module, role,
                    plan_task_ids(prepared.sources[component_id].content) if role == "automation_plan" else (),
                )
        if errors:
            return None, errors
        return (
            LoadedManifest(
                manifest,
                loaded_sections["components"],
                loaded_sections["recovery_rules"],
            ),
            [],
        )

    def _load_module(self, source: _Source, *, cache: bool = True) -> types.ModuleType:
        """正式模块只从哈希存储加载；候选校验使用不进入缓存的临时模块。"""

        path = source.path.resolve()
        digest = source.component_id.removeprefix(COMPONENT_ID_PREFIX)
        if cache and path != (self.components_dir / f"{digest}.py").resolve():
            raise ValueError("formal_component_path_invalid")
        key = (path, source.component_id)
        cached = _MODULE_CACHE.get(key) if cache else None
        if cached is not None:
            if cached[0] != source.content:
                raise ValueError("cached_component_source_mismatch")
            return cached[1]
        name = f"lalc_{'component' if cache else 'candidate'}_{digest}_{uuid.uuid4().hex}"
        module = types.ModuleType(name)
        module.__file__ = str(path)
        module.__package__ = ""
        sys.modules[name] = module
        try:
            exec(compile(source.content, str(path), "exec"), module.__dict__)
        except Exception:
            sys.modules.pop(name, None)
            raise
        if cache:
            _MODULE_CACHE[key] = (source.content, module)
        else:
            sys.modules.pop(name, None)
        return module

    def _store_component(self, source: _Source) -> None:
        """以不覆盖既有文件的方式保存一个内容寻址的 Component。"""

        digest = source.component_id.removeprefix(COMPONENT_ID_PREFIX)
        target = self.components_dir / f"{digest}.py"
        if target.exists():
            if target.read_bytes() != source.content:
                raise ValueError("immutable_component_conflict")
            return
        descriptor, temporary_name = tempfile.mkstemp(prefix=f".{digest}.", suffix=".tmp", dir=target.parent)
        temporary = Path(temporary_name)
        try:
            with os.fdopen(descriptor, "wb") as stream:
                stream.write(source.content)
                stream.flush()
                os.fsync(stream.fileno())
            try:
                # 硬链接创建目标文件时不会覆盖并发产生的同名不可变文件。
                os.link(temporary, target)
            except FileExistsError:
                if target.read_bytes() != source.content:
                    raise ValueError("immutable_component_conflict")
        finally:
            temporary.unlink(missing_ok=True)

    def _read_json(self, path: Path) -> tuple[Any | None, list[ValidationError]]:
        """读取 JSON，并在构造普通字典前保留重复键错误。"""

        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as error:
            return None, [ValidationError("manifest_unreadable", str(error), cause=error)]
        duplicates: list[str] = []

        def pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
            result: dict[str, Any] = {}
            for key, value in items:
                if key in result:
                    duplicates.append(key)
                result[key] = value
            return result

        try:
            data = json.loads(text, object_pairs_hook=pairs)
        except json.JSONDecodeError as error:
            return None, [
                ValidationError("manifest_json_invalid", error.msg, line=error.lineno, column=error.colno)
            ]
        errors = [
            ValidationError("json_key_duplicate", f"Duplicate JSON key: {key}") for key in duplicates
        ]
        return data, errors

    @staticmethod
    def _check_fields(
        value: dict[str, Any],
        allowed: set[str],
        required: set[str],
        errors: list[ValidationError],
        logical_name: str | None = None,
    ) -> None:
        for name in sorted(set(value) - allowed):
            errors.append(ValidationError("field_unknown", f"Unknown field: {name}", logical_name))
        for name in sorted(required - set(value)):
            errors.append(ValidationError("field_missing", f"Missing field: {name}", logical_name))

    @staticmethod
    def _check_manifest_id(value: Any, errors: list[ValidationError]) -> None:
        try:
            parsed = uuid.UUID(value)
        except (TypeError, ValueError, AttributeError):
            errors.append(ValidationError("manifest_id_invalid", "manifest_id must be a canonical UUID."))
            return
        if str(parsed) != value:
            errors.append(ValidationError("manifest_id_invalid", "manifest_id must be a canonical UUID."))

    @staticmethod
    def _valid_logical_name(value: str) -> bool:
        return bool(value) and all(part.isidentifier() for part in value.split("."))

    @staticmethod
    def _component_digest(component_id: str) -> str | None:
        if not component_id.startswith(COMPONENT_ID_PREFIX):
            return None
        digest = component_id[len(COMPONENT_ID_PREFIX) :]
        if len(digest) != 64 or any(character not in "0123456789abcdef" for character in digest):
            return None
        return digest

    @staticmethod
    def _top_functions(tree: ast.Module) -> dict[str, list[ast.FunctionDef | ast.AsyncFunctionDef]]:
        result: dict[str, list[ast.FunctionDef | ast.AsyncFunctionDef]] = {}
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                result.setdefault(node.name, []).append(node)
        return result

    @staticmethod
    def _decorator_name(node: ast.expr) -> str | None:
        return node.id if isinstance(node, ast.Name) else None

    @staticmethod
    def _reject_role_decorators(
        tree: ast.Module, logical_name: str, errors: list[ValidationError]
    ) -> None:
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and any(
                ManifestManager._decorator_name(item) in ROLES for item in node.decorator_list
            ):
                errors.append(
                    ManifestManager._node_error(
                        "component_role_forbidden", "This Component does not use a role decorator.", logical_name, node
                    )
                )

    def _validate_execute_signature(
        self,
        function: ast.FunctionDef | ast.AsyncFunctionDef,
        logical_name: str,
        errors: list[ValidationError],
        *, plan: bool = False,
    ) -> None:
        arguments = function.args
        valid = (
            not isinstance(function, ast.AsyncFunctionDef)
            and not arguments.posonlyargs
            and [item.arg for item in arguments.args] == ["ctx"]
            and not arguments.defaults
            and arguments.vararg is None
            and arguments.kwarg is None
            and function.returns is not None
            and all(item.annotation is not None for item in arguments.kwonlyargs)
        )
        if valid and plan:
            valid = ([item.arg for item in arguments.kwonlyargs] == ["task_repetitions", "settings"]
                     and [ast.unparse(item.annotation) for item in arguments.kwonlyargs]
                     == ["dict[str, int]", "dict[str, Any]"]
                     and all(default is None for default in arguments.kw_defaults))
        elif valid:
            valid = all(self._input_annotation_allowed(item.annotation) for item in arguments.kwonlyargs)
        if valid:
            for default in arguments.kw_defaults:
                if default is not None and not self._json_literal(default):
                    valid = False
        if not valid:
            errors.append(
                self._node_error(
                    "signature_invalid",
                    "execute must be typed execute(ctx, *, ...) with JSON-compatible inputs.",
                    logical_name,
                    function,
                )
            )

    def _validate_condition_signature(
        self,
        function: ast.FunctionDef | ast.AsyncFunctionDef,
        execute: ast.FunctionDef | ast.AsyncFunctionDef,
        logical_name: str,
        errors: list[ValidationError],
    ) -> None:
        positional = [item.arg for item in function.args.posonlyargs + function.args.args]
        expected = ["ctx"]
        valid = (
            not isinstance(function, ast.AsyncFunctionDef)
            and not function.args.posonlyargs
            and positional == expected
            and not function.args.defaults
            and function.args.vararg is None
            and function.args.kwarg is None
            and isinstance(function.returns, ast.Name)
            and function.returns.id == "bool"
            and self._parameter_contract(function.args) == self._parameter_contract(execute.args)
        )
        if not valid:
            errors.append(
                self._node_error("signature_invalid", "condition signature must match execute.", logical_name, function)
            )

    @staticmethod
    def _parameter_contract(arguments: ast.arguments) -> list[tuple[str, str, str | None]]:
        return [
            (
                argument.arg,
                ManifestManager._annotation_dump(argument.annotation),
                None if default is None else ast.dump(default, include_attributes=False),
            )
            for argument, default in zip(arguments.kwonlyargs, arguments.kw_defaults, strict=True)
        ]

    @staticmethod
    def _annotation_dump(annotation: ast.expr | None) -> str:
        return "" if annotation is None else ast.dump(annotation, include_attributes=False)

    @staticmethod
    def _simple_ctx_signature(
        function: ast.FunctionDef | ast.AsyncFunctionDef, return_name: str
    ) -> bool:
        args = function.args
        return_annotation = function.returns
        return_valid = (
            isinstance(return_annotation, ast.Name) and return_annotation.id == return_name
        ) or (return_name == "None" and isinstance(return_annotation, ast.Constant) and return_annotation.value is None)
        return (
            not isinstance(function, ast.AsyncFunctionDef)
            and not args.posonlyargs
            and [item.arg for item in args.args] == ["ctx"]
            and not args.defaults
            and not args.kwonlyargs
            and args.vararg is None
            and args.kwarg is None
            and return_valid
        )

    @staticmethod
    def _input_annotation_allowed(node: ast.expr | None) -> bool:
        if isinstance(node, ast.Name):
            return node.id in {"str", "int", "float", "bool"}
        if isinstance(node, ast.Constant):
            return node.value is None
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.BitOr):
            sides = (node.left, node.right)
            return sum(isinstance(item, ast.Constant) and item.value is None for item in sides) == 1 and all(
                ManifestManager._input_annotation_allowed(item) for item in sides
            )
        if not isinstance(node, ast.Subscript):
            return False
        name = node.value.id if isinstance(node.value, ast.Name) else None
        elements = list(node.slice.elts) if isinstance(node.slice, ast.Tuple) else [node.slice]
        if name == "Literal":
            return bool(elements) and all(
                isinstance(item, ast.Constant) and isinstance(item.value, (str, int, float, bool, type(None)))
                for item in elements
            )
        if name == "list" and len(elements) == 1:
            return ManifestManager._input_annotation_allowed(elements[0])
        if name == "dict" and len(elements) == 2:
            return isinstance(elements[0], ast.Name) and elements[0].id == "str" and ManifestManager._input_annotation_allowed(
                elements[1]
            )
        return False

    @staticmethod
    def _json_literal(node: ast.expr) -> bool:
        try:
            value = ast.literal_eval(node)
            json.dumps(value, allow_nan=False)
            return True
        except (ValueError, TypeError):
            return False

    @staticmethod
    def _ctx_calls(tree: ast.AST) -> list[ast.Call]:
        return [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "ctx"
            and node.func.attr == "call"
        ]

    @staticmethod
    def _ctx_action_calls(tree: ast.AST) -> list[ast.Call]:
        return [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "ctx"
            and node.func.attr == "action"
        ]

    @staticmethod
    def _literal_call_target(call: ast.Call) -> str | None:
        if not call.args or not isinstance(call.args[0], ast.Constant) or not isinstance(call.args[0].value, str):
            return None
        return call.args[0].value

    @staticmethod
    def _node_error(
        code: str, message: str, logical_name: str | None, node: ast.AST
    ) -> ValidationError:
        return ValidationError(
            code,
            message,
            logical_name,
            getattr(node, "lineno", None),
            getattr(node, "col_offset", -1) + 1 if hasattr(node, "col_offset") else None,
        )
