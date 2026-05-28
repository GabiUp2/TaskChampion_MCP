"""Tests for schema loading and validation (ADR 7)."""

from __future__ import annotations

import pytest

# Schemas live inside the package as of v1.0.0 so the wheel ships them.
# Use default_schema_dir() rather than reconstructing the path here so the
# test follows the package layout wherever it moves next.
from taskchampion_mcp.config import default_schema_dir  # noqa: E402
from taskchampion_mcp.schema import (
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
