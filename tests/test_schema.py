"""Tests for schema loading and validation (ADR 7)."""

from __future__ import annotations

import pytest

# Schemas live inside the package as of v1.0.0 so the wheel ships them.
# Use default_schema_dir() rather than reconstructing the path here so the
# test follows the package layout wherever it moves next.
from taskchampion_mcp.config import default_schema_dir  # noqa: E402
from taskchampion_mcp.schema import (
    TASKWARRIOR_BUILTIN_FIELDS,
    FieldDef,
    TaskSchema,
    get_unregistered_uda_fields,
    list_available_schemas,
    load_schema,
    validate_task,
)

SCHEMAS_DIR = default_schema_dir()


class TestLoadSchema:
    def test_load_minimal(self):
        schema = load_schema("minimal", SCHEMAS_DIR)
        assert schema.name == "minimal"
        assert "description" in schema.fields
        assert schema.fields["description"].required is True

    def test_load_authors_custom(self):
        schema = load_schema("authors_custom_example", SCHEMAS_DIR)
        assert schema.name == "authors_custom_example"
        assert "scope" in schema.fields
        assert schema.fields["scope"].values == ["personal", "work"]
        assert len(schema.conditions) > 0

    def test_load_all_presets(self):
        for name in ("minimal", "gtd", "kanban", "scrum", "authors_custom_example"):
            schema = load_schema(name, SCHEMAS_DIR)
            assert schema.name == name
            assert "description" in schema.fields

    def test_load_missing_raises(self):
        with pytest.raises(FileNotFoundError):
            load_schema("nonexistent_schema", SCHEMAS_DIR)

    def test_load_by_path(self):
        path = SCHEMAS_DIR / "minimal.toml"
        schema = load_schema(str(path))
        assert schema.name == "minimal"


class TestListSchemas:
    def test_lists_all(self):
        schemas = list_available_schemas(SCHEMAS_DIR)
        names = [s["name"] for s in schemas]
        assert "minimal" in names
        assert "gtd" in names
        assert "kanban" in names
        assert "scrum" in names
        assert "authors_custom_example" in names


class TestValidateTask:
    @pytest.fixture()
    def minimal_schema(self):
        return load_schema("minimal", SCHEMAS_DIR)

    @pytest.fixture()
    def custom_schema(self):
        return load_schema("authors_custom_example", SCHEMAS_DIR)

    def test_valid_minimal_task(self, minimal_schema):
        task = {"description": "Fix the bug"}
        errors = validate_task(task, minimal_schema)
        assert errors == []

    def test_missing_required_field(self, minimal_schema):
        task = {}
        errors = validate_task(task, minimal_schema)
        assert any("description" in e for e in errors)

    def test_invalid_enum_value(self, minimal_schema):
        task = {"description": "Fix", "priority": "ULTRA"}
        errors = validate_task(task, minimal_schema)
        assert any("priority" in e for e in errors)

    def test_valid_enum_value(self, minimal_schema):
        task = {"description": "Fix", "priority": "H"}
        errors = validate_task(task, minimal_schema)
        assert errors == []

    def test_custom_schema_required_fields(self, custom_schema):
        task = {"description": "Fix"}
        errors = validate_task(task, custom_schema)
        assert any("scope" in e for e in errors)
        assert any("area" in e for e in errors)
        assert any("phase" in e for e in errors)
        assert any("project" in e for e in errors)

    def test_custom_schema_full_valid(self, custom_schema):
        task = {
            "description": "Set up backups",
            "project": "personal.infra.server",
            "scope": "personal",
            "area": "infra",
            "phase": "impl",
        }
        errors = validate_task(task, custom_schema)
        assert errors == []

    def test_conditional_hypothesis_required(self, custom_schema):
        task = {
            "description": "Research backup tools",
            "project": "personal.infra.server",
            "scope": "personal",
            "area": "infra",
            "phase": "research",
        }
        errors = validate_task(task, custom_schema)
        assert any("hypothesis" in e for e in errors)

    def test_conditional_hypothesis_satisfied(self, custom_schema):
        task = {
            "description": "Research backup tools",
            "project": "personal.infra.server",
            "scope": "personal",
            "area": "infra",
            "phase": "research",
            "hypothesis": "restic is faster than borgbackup",
        }
        errors = validate_task(task, custom_schema)
        assert errors == []

    def test_conditional_testing_needs_versus(self, custom_schema):
        task = {
            "description": "Compare backup tools",
            "project": "personal.infra.server",
            "scope": "personal",
            "area": "infra",
            "phase": "testing",
            "hypothesis": "restic is faster",
        }
        errors = validate_task(task, custom_schema)
        assert any("versus" in e for e in errors)

    def test_conditional_work_needs_client(self, custom_schema):
        task = {
            "description": "Fix monitoring",
            "project": "work.acme.monitoring",
            "scope": "work",
            "area": "ops",
            "phase": "impl",
        }
        errors = validate_task(task, custom_schema)
        assert any("client" in e for e in errors)


class TestTaskwarriorBuiltinFields:
    def test_common_builtins_present(self):
        for field in ("description", "project", "priority", "tags", "due", "status"):
            assert field in TASKWARRIOR_BUILTIN_FIELDS

    def test_uda_fields_absent(self):
        # UDA fields like scope/area/phase must NOT be in the builtin set
        for field in ("scope", "area", "phase", "effort", "confidence", "hypothesis"):
            assert field not in TASKWARRIOR_BUILTIN_FIELDS


class TestGetUnregisteredUdaFields:
    """Tests for the schema-vs-taskrc UDA consistency check (bug fix)."""

    def _make_schema(self, fields: dict) -> TaskSchema:
        """Build a minimal TaskSchema with the given field definitions."""
        schema = TaskSchema(name="test")
        for name, uda in fields.items():
            schema.fields[name] = FieldDef(name=name, uda=uda)
        return schema

    # ------------------------------------------------------------------
    # Basic correctness
    # ------------------------------------------------------------------

    def test_empty_schema_returns_empty(self):
        schema = TaskSchema(name="empty")
        assert get_unregistered_uda_fields(schema, set()) == []

    def test_builtin_only_schema_returns_empty(self):
        """Built-in fields never need UDA registration."""
        schema = self._make_schema({"description": False, "project": False, "priority": False})
        # Even with zero registered UDAs, no missing fields reported
        assert get_unregistered_uda_fields(schema, set()) == []

    def test_registered_uda_returns_empty(self):
        """UDA present in .taskrc → no mismatch."""
        schema = self._make_schema({"scope": True, "area": True})
        registered = {"scope", "area", "phase"}
        assert get_unregistered_uda_fields(schema, registered) == []

    def test_unregistered_explicit_uda_returned(self):
        """Field marked uda=True but absent from .taskrc → reported."""
        schema = self._make_schema({"scope": True, "area": True})
        registered: set[str] = set()
        missing = get_unregistered_uda_fields(schema, registered)
        assert "scope" in missing
        assert "area" in missing

    def test_unregistered_implicit_uda_returned(self):
        """Non-builtin field without explicit uda=True is still treated as UDA."""
        schema = self._make_schema({"myfancyfield": False})
        missing = get_unregistered_uda_fields(schema, set())
        assert "myfancyfield" in missing

    def test_partial_registration(self):
        """Only unregistered fields are returned, not already-registered ones."""
        schema = self._make_schema({"scope": True, "area": True, "phase": True})
        registered = {"scope"}  # area and phase are missing
        missing = get_unregistered_uda_fields(schema, registered)
        assert "scope" not in missing
        assert "area" in missing
        assert "phase" in missing

    def test_result_is_sorted(self):
        """Return value is alphabetically sorted for deterministic output."""
        schema = self._make_schema({"zzz": True, "aaa": True, "mmm": True})
        missing = get_unregistered_uda_fields(schema, set())
        assert missing == sorted(missing)

    def test_builtin_mixed_with_uda(self):
        """Builtin fields are never flagged even when UDAs around them are missing."""
        schema = self._make_schema({
            "description": False,   # builtin — never flagged
            "project": False,       # builtin — never flagged
            "scope": True,          # UDA — flagged when unregistered
        })
        missing = get_unregistered_uda_fields(schema, set())
        assert "description" not in missing
        assert "project" not in missing
        assert "scope" in missing

    # ------------------------------------------------------------------
    # Analysis-generated schemas pass trivially (regression guard)
    # ------------------------------------------------------------------

    def test_analysis_generated_schema_passes_with_its_own_fields(self):
        """A schema generated from task analysis only contains fields that
        TaskWarrior already knows about, so all its UDAs must be in .taskrc.
        This test confirms that pattern: if we feed back the schema's own
        field names as registered_udas, there are no mismatches."""
        schema = load_schema("authors_custom_example", SCHEMAS_DIR)
        # Simulate: every field name in the schema IS registered
        registered = set(schema.fields.keys()) | set(schema.llm_provenance_fields.keys())
        assert get_unregistered_uda_fields(schema, registered) == []

    def test_preset_schema_with_empty_taskrc_reports_all_udas(self):
        """A bundled preset schema loaded with zero registered UDAs reports
        every non-builtin field — this is the core bug scenario."""
        schema = load_schema("authors_custom_example", SCHEMAS_DIR)
        missing = get_unregistered_uda_fields(schema, set())
        # Must report UDA fields like scope, area, phase, effort, confidence
        for expected in ("scope", "area", "phase"):
            assert expected in missing, f"Expected '{expected}' in {missing}"
        # Must NOT report builtins
        for builtin in ("description", "project", "priority"):
            assert builtin not in missing

    def test_llm_provenance_fields_also_checked(self):
        """llm_provenance_fields are also subject to UDA registration."""
        schema = TaskSchema(name="prov_test")
        schema.fields["description"] = FieldDef(name="description", uda=False)
        schema.llm_provenance_fields["gen_model"] = FieldDef(name="gen_model", uda=True)
        # gen_model not registered
        missing = get_unregistered_uda_fields(schema, set())
        assert "gen_model" in missing
        # gen_model registered
        missing2 = get_unregistered_uda_fields(schema, {"gen_model"})
        assert "gen_model" not in missing2
