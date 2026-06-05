"""Schema loading and validation for TaskChampion MCP (ADR 7)."""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib  # type: ignore[no-redef]

from taskchampion_mcp.config import default_schema_dir  # noqa: E402


# ---------------------------------------------------------------------------
# Built-in field registry
# ---------------------------------------------------------------------------

#: TaskWarrior built-in fields that do not require UDA registration in .taskrc.
#: Kept as a local constant to avoid a cross-module import dependency on
#: schema_gen.py.  Must be kept in sync with ``BUILTIN_FIELDS`` there.
TASKWARRIOR_BUILTIN_FIELDS: frozenset[str] = frozenset({
    "id",
    "uuid",
    "description",
    "status",
    "project",
    "priority",
    "tags",
    "due",
    "wait",
    "until",
    "depends",
    "recur",
    "entry",
    "modified",
    "start",
    "end",
    "urgency",
    "annotations",
    "mask",
    "imask",
    "parent",
    "scheduled",
})


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------


@dataclass
class FieldDef:
    name: str
    type: str = "string"
    required: bool = False
    values: list[str] | None = None
    default: str | None = None
    description: str = ""
    uda: bool = False


@dataclass
class Condition:
    name: str
    when: str
    then_required: list[str] = field(default_factory=list)
    description: str = ""


@dataclass
class TaskSchema:
    name: str
    version: str = "1.0.0"
    description: str = ""
    taskwarrior_version: str = "3.x"
    fields: dict[str, FieldDef] = field(default_factory=dict)
    conditions: list[Condition] = field(default_factory=list)
    llm_provenance_fields: dict[str, FieldDef] = field(default_factory=dict)

    def required_field_names(self) -> list[str]:
        return [f.name for f in self.fields.values() if f.required]

    def enum_fields(self) -> dict[str, list[str]]:
        return {f.name: f.values for f in self.fields.values() if f.values}

    def all_field_names(self) -> list[str]:
        return list(self.fields.keys()) + list(self.llm_provenance_fields.keys())

    def field_context_for_llm(self) -> list[dict[str, Any]]:
        """Return field definitions formatted for LLM context."""
        result = []
        for f in self.fields.values():
            entry: dict[str, Any] = {
                "name": f.name,
                "type": f.type,
                "required": f.required,
                "description": f.description,
            }
            if f.values:
                entry["allowed_values"] = f.values
            result.append(entry)
        return result


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------


def load_schema(name_or_path: str, schema_dir: Path | None = None) -> TaskSchema:
    """Load a schema from a TOML file.

    If ``name_or_path`` is a path to an existing file, load it directly.
    Otherwise, look for ``<name>.toml`` in ``schema_dir`` (defaults to the
    bundled ``schemas/`` directory).
    """
    path = Path(name_or_path)
    if not path.exists():
        if schema_dir is None:
            schema_dir = default_schema_dir()
        path = schema_dir / f"{name_or_path}.toml"

    if not path.exists():
        raise FileNotFoundError(f"Schema file not found: {path}")

    with open(path, "rb") as f:
        data = tomllib.load(f)

    return _parse_schema(data)


def _parse_schema(data: dict[str, Any]) -> TaskSchema:
    meta = data.get("meta", {})
    schema = TaskSchema(
        name=meta.get("name", "unknown"),
        version=meta.get("version", "1.0.0"),
        description=meta.get("description", ""),
        taskwarrior_version=meta.get("taskwarrior_version", "3.x"),
    )

    for field_name, field_data in data.get("fields", {}).items():
        schema.fields[field_name] = FieldDef(
            name=field_name,
            type=field_data.get("type", "string"),
            required=field_data.get("required", False),
            values=field_data.get("values"),
            default=field_data.get("default"),
            description=field_data.get("description", ""),
            uda=field_data.get("uda", False),
        )

    for cond_name, cond_data in data.get("conditions", {}).items():
        schema.conditions.append(
            Condition(
                name=cond_name,
                when=cond_data.get("when", ""),
                then_required=cond_data.get("then_required", []),
                description=cond_data.get("description", ""),
            )
        )

    llm_prov = data.get("llm_provenance", {})
    for prov_name, prov_data in llm_prov.items():
        if isinstance(prov_data, dict) and "type" in prov_data:
            schema.llm_provenance_fields[prov_name] = FieldDef(
                name=prov_name,
                type=prov_data.get("type", "string"),
                required=prov_data.get("required", False),
                description=prov_data.get("description", ""),
            )

    return schema


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


class SchemaValidationError(ValueError):
    """Raised when task data does not conform to the loaded schema."""


def validate_task(task_data: dict[str, Any], schema: TaskSchema) -> list[str]:
    """Validate task data against the schema. Returns a list of error messages.

    Empty list = valid.
    """
    errors: list[str] = []

    for field_def in schema.fields.values():
        if field_def.required and field_def.name not in task_data:
            errors.append(f"Required field '{field_def.name}' is missing.")

    for field_def in schema.fields.values():
        if field_def.values and field_def.name in task_data:
            val = task_data[field_def.name]
            if val and val not in field_def.values:
                errors.append(
                    f"Field '{field_def.name}' value '{val}' "
                    f"not in allowed values: {field_def.values}"
                )

    for cond in schema.conditions:
        if _evaluate_condition(cond.when, task_data):
            for req_field in cond.then_required:
                if req_field not in task_data or not task_data[req_field]:
                    errors.append(
                        f"Condition '{cond.name}': field '{req_field}' is required when {cond.when}"
                    )

    return errors


def _evaluate_condition(when_expr: str, task_data: dict[str, Any]) -> bool:
    """Evaluate a simple condition expression against task data.

    Supports: ``field == 'value'`` and ``field != ''``
    """
    when_expr = when_expr.strip()

    if "==" in when_expr:
        parts = when_expr.split("==", 1)
        field_name = parts[0].strip()
        expected = parts[1].strip().strip("'\"")
        return task_data.get(field_name) == expected

    if "!=" in when_expr:
        parts = when_expr.split("!=", 1)
        field_name = parts[0].strip()
        expected = parts[1].strip().strip("'\"")
        actual = task_data.get(field_name, "")
        return actual != expected

    return False



def get_unregistered_uda_fields(
    schema: "TaskSchema",
    registered_udas: set[str],
) -> list[str]:
    """Return schema field names that require UDA registration but are absent from .taskrc.

    A field requires UDA registration when it is either explicitly marked
    ``uda = true`` in the schema, or its name is absent from
    :data:`TASKWARRIOR_BUILTIN_FIELDS`.

    Schemas auto-generated by :mod:`taskchampion_mcp.schema_gen` from existing
    tasks pass this check trivially — every field in such a schema was derived
    from data TaskWarrior already holds, so all non-builtin fields are
    necessarily registered UDAs.  File-provided schemas (bundled presets, author
    files, manually authored TOML) may reference UDA fields not yet present in
    the user's ``.taskrc``, producing tasks with silently dropped or rejected
    field values.

    Args:
        schema: The :class:`TaskSchema` to inspect.
        registered_udas: Set of UDA names currently registered in ``.taskrc``,
            obtained via
            :meth:`~taskchampion_mcp.cli.TaskwarriorCLI.udas`.

    Returns:
        Sorted list of field names that are non-builtin but absent from
        ``registered_udas``.  Empty list means the schema and ``.taskrc`` are
        consistent.
    """
    missing: list[str] = []
    all_fields: dict[str, FieldDef] = {
        **schema.fields,
        **schema.llm_provenance_fields,
    }
    for field_name, field_def in all_fields.items():
        needs_registration = (
            field_def.uda or field_name not in TASKWARRIOR_BUILTIN_FIELDS
        )
        if needs_registration and field_name not in registered_udas:
            missing.append(field_name)
    return sorted(missing)


def list_available_schemas(schema_dir: Path | None = None) -> list[dict[str, str]]:
    """List all .toml schemas in the schema directory."""
    if schema_dir is None:
        schema_dir = default_schema_dir()
    results = []
    if schema_dir.exists():
        for p in sorted(schema_dir.glob("*.toml")):
            try:
                s = load_schema(str(p))
                results.append(
                    {
                        "name": s.name,
                        "description": s.description,
                        "file": p.name,
                    }
                )
            except Exception:
                results.append({"name": p.stem, "description": "(failed to parse)", "file": p.name})
    return results
