"""Tests for schema auto-generation from tasks and taxonomy files (IDEA-003)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib  # type: ignore[no-redef]

from taskchampion_mcp.schema_gen import (
    TaxonomyInfo,
    analyze_tasks,
    generate_schema_from_tasks_and_taxonomy,
    generate_schema_toml,
    parse_taxonomy,
    save_generated_schema,
)

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "gold"
TAXONOMY_FIXTURE = FIXTURES_DIR / "sample_taxonomy.md"
USER_TAXONOMY = Path(__file__).parent.parent / "user" / "TAXONOMY.md"


def _load_fixture(name: str) -> list[dict]:
    path = FIXTURES_DIR / name
    return json.loads(path.read_text())


# ---------------------------------------------------------------------------
# Task analysis tests
# ---------------------------------------------------------------------------


class TestAnalyzeTasks:
    def test_empty_tasks(self):
        analysis = analyze_tasks([])
        assert analysis.total_tasks == 0
        assert analysis.fields == {}

    def test_basic_field_detection(self):
        tasks = _load_fixture("minimal_tasks.json")
        analysis = analyze_tasks(tasks)
        assert analysis.total_tasks > 0
        assert "description" in analysis.fields
        assert "project" in analysis.fields

    def test_uda_detection_from_authors_custom(self):
        tasks = _load_fixture("authors_custom_tasks.json")
        analysis = analyze_tasks(tasks)
        assert analysis.total_tasks == 15

        uda_fields = analysis.uda_fields()
        assert "scope" in uda_fields
        assert "phase" in uda_fields
        assert "area" in uda_fields
        assert "effort" in uda_fields
        assert "confidence" in uda_fields

        builtin_fields = analysis.builtin_fields()
        assert "description" in builtin_fields
        assert "project" in builtin_fields

    def test_scope_is_detected_as_required(self):
        tasks = _load_fixture("authors_custom_tasks.json")
        analysis = analyze_tasks(tasks)
        scope = analysis.fields["scope"]
        assert scope.inferred_required is True
        assert scope.usage_ratio >= 0.9

    def test_enum_detection(self):
        tasks = _load_fixture("authors_custom_tasks.json")
        analysis = analyze_tasks(tasks)

        scope = analysis.fields["scope"]
        assert scope.is_likely_enum is True
        vals = scope.inferred_values
        assert vals is not None
        assert "personal" in vals
        assert "work" in vals

        phase = analysis.fields["phase"]
        assert phase.is_likely_enum is True

    def test_optional_field_detection(self):
        tasks = _load_fixture("authors_custom_tasks.json")
        analysis = analyze_tasks(tasks)

        hypothesis = analysis.fields.get("hypothesis")
        assert hypothesis is not None
        assert hypothesis.inferred_required is False

    def test_project_list(self):
        tasks = _load_fixture("authors_custom_tasks.json")
        analysis = analyze_tasks(tasks)
        assert len(analysis.projects) > 0
        assert any("personal" in p for p in analysis.projects)

    def test_tag_list(self):
        tasks = _load_fixture("authors_custom_tasks.json")
        analysis = analyze_tasks(tasks)
        assert len(analysis.tags) > 0
        assert "linux" in analysis.tags

    def test_excluded_fields_not_in_analysis(self):
        tasks = _load_fixture("authors_custom_tasks.json")
        analysis = analyze_tasks(tasks)
        assert "uuid" not in analysis.fields
        assert "id" not in analysis.fields
        assert "urgency" not in analysis.fields

    def test_list_field_detection(self):
        tasks = _load_fixture("authors_custom_tasks.json")
        analysis = analyze_tasks(tasks)
        tags_field = analysis.fields.get("tags")
        assert tags_field is not None
        assert tags_field.is_list is True
        assert tags_field.inferred_type == "list"

    def test_date_field_detection(self):
        tasks = _load_fixture("authors_custom_tasks.json")
        analysis = analyze_tasks(tasks)
        if "due" in analysis.fields:
            due_field = analysis.fields["due"]
            assert due_field.is_date is True
            assert due_field.inferred_type == "date"

    def test_all_gold_fixtures(self):
        for fixture_name in (
            "minimal_tasks.json",
            "gtd_tasks.json",
            "kanban_tasks.json",
            "scrum_tasks.json",
            "authors_custom_tasks.json",
        ):
            tasks = _load_fixture(fixture_name)
            analysis = analyze_tasks(tasks)
            assert analysis.total_tasks == len(tasks)
            assert "description" in analysis.fields


# ---------------------------------------------------------------------------
# Taxonomy parser tests
# ---------------------------------------------------------------------------


class TestParseTaxonomy:
    def test_missing_file_raises(self):
        with pytest.raises(FileNotFoundError):
            parse_taxonomy("/nonexistent/path/taxonomy.md")

    def test_parse_sample_taxonomy(self):
        info = parse_taxonomy(TAXONOMY_FIXTURE)
        assert isinstance(info, TaxonomyInfo)
        assert len(info.fields) > 0

    def test_field_extraction(self):
        info = parse_taxonomy(TAXONOMY_FIXTURE)
        assert "scope" in info.fields
        assert "area" in info.fields
        assert "phase" in info.fields
        assert "hypothesis" in info.fields
        assert "effort" in info.fields
        assert "confidence" in info.fields

    def test_scope_values(self):
        info = parse_taxonomy(TAXONOMY_FIXTURE)
        scope = info.fields["scope"]
        assert scope.allowed_values is not None
        assert "personal" in scope.allowed_values
        assert "work" in scope.allowed_values

    def test_phase_values_from_heading(self):
        info = parse_taxonomy(TAXONOMY_FIXTURE)
        phase = info.fields["phase"]
        assert phase.allowed_values is not None
        assert "impl" in phase.allowed_values
        assert "research" in phase.allowed_values

    def test_area_values_from_table(self):
        info = parse_taxonomy(TAXONOMY_FIXTURE)
        area = info.fields["area"]
        assert area.allowed_values is not None
        assert "infra" in area.allowed_values
        assert "dev" in area.allowed_values

    def test_effort_values_from_heading(self):
        info = parse_taxonomy(TAXONOMY_FIXTURE)
        effort = info.fields["effort"]
        assert effort.allowed_values is not None
        assert "XS" in effort.allowed_values
        assert "XL" in effort.allowed_values

    def test_scope_required(self):
        info = parse_taxonomy(TAXONOMY_FIXTURE)
        scope = info.fields["scope"]
        assert scope.required is True

    def test_field_descriptions_extracted(self):
        info = parse_taxonomy(TAXONOMY_FIXTURE)
        scope = info.fields["scope"]
        assert len(scope.description) > 0

    def test_uda_flag(self):
        info = parse_taxonomy(TAXONOMY_FIXTURE)
        assert info.fields["scope"].uda is True
        assert info.fields["phase"].uda is True

    def test_conditions_extracted(self):
        info = parse_taxonomy(TAXONOMY_FIXTURE)
        assert len(info.conditions) > 0
        cond_names = [c.name for c in info.conditions]
        assert any("research" in n for n in cond_names)
        assert any("testing" in n for n in cond_names)

    def test_phase_transitions_extracted(self):
        info = parse_taxonomy(TAXONOMY_FIXTURE)
        assert len(info.phase_transitions) > 0
        transitions = {(pt.from_phase, pt.to_phase) for pt in info.phase_transitions}
        assert ("idea", "research") in transitions

    def test_raw_sections(self):
        info = parse_taxonomy(TAXONOMY_FIXTURE)
        assert len(info.raw_sections) > 0

    @pytest.mark.skipif(
        not USER_TAXONOMY.exists(),
        reason="user/TAXONOMY.md not present",
    )
    def test_parse_real_taxonomy(self):
        info = parse_taxonomy(USER_TAXONOMY)
        assert "scope" in info.fields
        assert "phase" in info.fields
        assert "hypothesis" in info.fields
        assert len(info.conditions) > 0


# ---------------------------------------------------------------------------
# Schema TOML generation tests
# ---------------------------------------------------------------------------


class TestGenerateSchemaToml:
    def test_analysis_only(self):
        tasks = _load_fixture("authors_custom_tasks.json")
        analysis = analyze_tasks(tasks)
        toml_str = generate_schema_toml(analysis=analysis, name="test_analysis")
        assert "[meta]" in toml_str
        assert 'name = "test_analysis"' in toml_str
        assert "[fields.description]" in toml_str
        assert "[fields.scope]" in toml_str

    def test_taxonomy_only(self):
        taxonomy = parse_taxonomy(TAXONOMY_FIXTURE)
        toml_str = generate_schema_toml(taxonomy=taxonomy, name="test_taxonomy")
        assert "[meta]" in toml_str
        assert "[fields.scope]" in toml_str
        assert "[fields.phase]" in toml_str
        assert "[conditions." in toml_str

    def test_combined_analysis_and_taxonomy(self):
        tasks = _load_fixture("authors_custom_tasks.json")
        analysis = analyze_tasks(tasks)
        taxonomy = parse_taxonomy(TAXONOMY_FIXTURE)
        toml_str = generate_schema_toml(
            analysis=analysis,
            taxonomy=taxonomy,
            name="test_combined",
        )
        assert "[meta]" in toml_str
        assert "[fields.scope]" in toml_str
        assert "uda = true" in toml_str
        assert "[conditions." in toml_str
        assert "# Analysis Summary" in toml_str

    def test_generated_toml_is_parseable(self):
        tasks = _load_fixture("authors_custom_tasks.json")
        analysis = analyze_tasks(tasks)
        taxonomy = parse_taxonomy(TAXONOMY_FIXTURE)
        toml_str = generate_schema_toml(
            analysis=analysis,
            taxonomy=taxonomy,
            name="parseable_test",
        )
        parsed = tomllib.loads(toml_str)
        assert parsed["meta"]["name"] == "parseable_test"
        assert "fields" in parsed
        assert "scope" in parsed["fields"]

    def test_taxonomy_descriptions_win(self):
        tasks = _load_fixture("authors_custom_tasks.json")
        analysis = analyze_tasks(tasks)
        taxonomy = parse_taxonomy(TAXONOMY_FIXTURE)
        toml_str = generate_schema_toml(
            analysis=analysis,
            taxonomy=taxonomy,
            name="desc_test",
        )
        # Taxonomy description should override analysis-inferred description
        assert "Detected from task data" not in toml_str or (
            "scope" not in toml_str.split("Detected")[0]
        )
        parsed = tomllib.loads(toml_str)
        scope_desc = parsed["fields"]["scope"].get("description", "")
        assert "Detected from task data" not in scope_desc

    def test_phase_transitions_in_output(self):
        taxonomy = parse_taxonomy(TAXONOMY_FIXTURE)
        toml_str = generate_schema_toml(taxonomy=taxonomy, name="pt_test")
        assert "[phase_transitions]" in toml_str or "phase_transitions" in toml_str

    def test_empty_inputs(self):
        toml_str = generate_schema_toml(name="empty_test")
        assert "[meta]" in toml_str
        assert 'name = "empty_test"' in toml_str


# ---------------------------------------------------------------------------
# Convenience function tests
# ---------------------------------------------------------------------------


class TestGenerateSchemaFromTasksAndTaxonomy:
    def test_tasks_only(self):
        tasks = _load_fixture("authors_custom_tasks.json")
        toml_str = generate_schema_from_tasks_and_taxonomy(tasks=tasks, name="conv_tasks")
        assert "[meta]" in toml_str
        assert "[fields.scope]" in toml_str

    def test_taxonomy_only(self):
        toml_str = generate_schema_from_tasks_and_taxonomy(
            tasks=[],
            taxonomy_path=str(TAXONOMY_FIXTURE),
            name="conv_tax",
        )
        assert "[meta]" in toml_str
        assert "[fields.scope]" in toml_str

    def test_both_sources(self):
        tasks = _load_fixture("authors_custom_tasks.json")
        toml_str = generate_schema_from_tasks_and_taxonomy(
            tasks=tasks,
            taxonomy_path=str(TAXONOMY_FIXTURE),
            name="conv_both",
        )
        parsed = tomllib.loads(toml_str)
        assert parsed["meta"]["name"] == "conv_both"
        assert "scope" in parsed["fields"]

    def test_missing_taxonomy_raises(self):
        with pytest.raises(FileNotFoundError):
            generate_schema_from_tasks_and_taxonomy(
                tasks=[],
                taxonomy_path="/nonexistent.md",
            )


# ---------------------------------------------------------------------------
# Save tests
# ---------------------------------------------------------------------------


class TestSaveGeneratedSchema:
    def test_save_creates_file(self, tmp_path):
        toml_str = generate_schema_toml(name="save_test")
        output = tmp_path / "test_schema.toml"
        result = save_generated_schema(toml_str, output)
        assert result.exists()
        assert result.read_text().startswith("# TaskChampion MCP")

    def test_save_creates_parents(self, tmp_path):
        output = tmp_path / "sub" / "dir" / "schema.toml"
        toml_str = generate_schema_toml(name="nested_test")
        result = save_generated_schema(toml_str, output)
        assert result.exists()

    def test_save_refuses_overwrite(self, tmp_path):
        output = tmp_path / "existing.toml"
        output.write_text("existing content")
        toml_str = generate_schema_toml(name="overwrite_test")
        with pytest.raises(FileExistsError):
            save_generated_schema(toml_str, output)

    def test_saved_file_is_valid_toml(self, tmp_path):
        tasks = _load_fixture("authors_custom_tasks.json")
        taxonomy = parse_taxonomy(TAXONOMY_FIXTURE)
        toml_str = generate_schema_toml(
            analysis=analyze_tasks(tasks),
            taxonomy=taxonomy,
            name="save_parse_test",
        )
        output = tmp_path / "full_schema.toml"
        save_generated_schema(toml_str, output)
        parsed = tomllib.loads(output.read_text())
        assert parsed["meta"]["name"] == "save_parse_test"
        assert "fields" in parsed
