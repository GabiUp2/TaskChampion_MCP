"""Tests for ToolRegistry tool implementations."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from taskchampion_mcp.audit import AuditLogger
from taskchampion_mcp.cli import CLIResult, TaskwarriorCLI
from taskchampion_mcp.config import ServerConfig
from taskchampion_mcp.rate_limiter import RateLimiter
from taskchampion_mcp.schema import TaskSchema
from taskchampion_mcp.tools import ToolRegistry


@pytest.fixture
def mock_config():
    config = MagicMock(spec=ServerConfig)
    config.role = "GENERATOR"
    config.redacted_fields = []
    config.dry_run_default = False
    config.require_confirmation = False
    return config


@pytest.fixture
def mock_task_cli():
    cli = MagicMock(spec=TaskwarriorCLI)
    return cli


@pytest.fixture
def mock_schema():
    schema = MagicMock(spec=TaskSchema)
    schema.name = "minimal"
    schema.version = "1.0.0"
    schema.enum_fields.return_value = {}
    schema.required_field_names.return_value = []
    return schema


@pytest.fixture
def mock_rate_limiter():
    limiter = MagicMock(spec=RateLimiter)
    return limiter


@pytest.fixture
def mock_audit():
    audit = MagicMock(spec=AuditLogger)
    return audit


@pytest.fixture
def tool_registry(mock_config, mock_task_cli, mock_schema, mock_rate_limiter, mock_audit):
    return ToolRegistry(
        config=mock_config,
        task_cli=mock_task_cli,
        timew_cli=None,
        schema=mock_schema,
        rate_limiter=mock_rate_limiter,
        audit=mock_audit,
    )


class TestCreateSubtask:
    @patch("taskchampion_mcp.tools.validate_task")
    def test_create_subtask_success(self, mock_validate, tool_registry, mock_task_cli):
        parent_uuid = "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
        lower_uuid = parent_uuid.lower()
        mock_validate.return_value = []
        mock_task_cli.get_task.return_value = {"uuid": lower_uuid, "description": "Parent task"}
        mock_task_cli.add_task.return_value = CLIResult(
            returncode=0, stdout="Created task 123", stderr=""
        )

        result = tool_registry.create_subtask(
            parent_uuid=parent_uuid,
            description="Subtask description",
        )

        assert result["success"] is True
        assert "Subtask created" in result["message"]
        mock_task_cli.get_task.assert_called_once_with(lower_uuid)
        mock_task_cli.add_task.assert_called_once()
        call_args = mock_task_cli.add_task.call_args
        assert call_args[1]["depends"] == lower_uuid

    @patch("taskchampion_mcp.tools.validate_task")
    def test_create_subtask_parent_not_found(self, mock_validate, tool_registry, mock_task_cli):
        parent_uuid = "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
        mock_validate.return_value = []
        mock_task_cli.get_task.return_value = None

        result = tool_registry.create_subtask(
            parent_uuid=parent_uuid,
            description="Subtask description",
        )

        assert result["error"] is True
        assert "not found" in result["message"]
        mock_task_cli.add_task.assert_not_called()

    @patch("taskchampion_mcp.tools.validate_task")
    def test_create_subtask_with_project_and_priority(
        self, mock_validate, tool_registry, mock_task_cli
    ):
        parent_uuid = "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
        lower_uuid = parent_uuid.lower()
        mock_validate.return_value = []
        mock_task_cli.get_task.return_value = {"uuid": lower_uuid, "description": "Parent task"}
        mock_task_cli.add_task.return_value = CLIResult(
            returncode=0, stdout="Created task 123", stderr=""
        )

        result = tool_registry.create_subtask(
            parent_uuid=parent_uuid,
            description="Subtask description",
            project="work.project",
            priority="H",
        )

        assert result["success"] is True
        call_args = mock_task_cli.add_task.call_args
        assert call_args[1]["project"] == "work.project"
        assert call_args[1]["priority"] == "H"
        assert call_args[1]["depends"] == lower_uuid

    @patch("taskchampion_mcp.tools.validate_task")
    def test_create_subtask_with_tags(self, mock_validate, tool_registry, mock_task_cli):
        parent_uuid = "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
        lower_uuid = parent_uuid.lower()
        mock_validate.return_value = []
        mock_task_cli.get_task.return_value = {"uuid": lower_uuid, "description": "Parent task"}
        mock_task_cli.add_task.return_value = CLIResult(
            returncode=0, stdout="Created task 123", stderr=""
        )

        result = tool_registry.create_subtask(
            parent_uuid=parent_uuid,
            description="Subtask description",
            tags=["python", "docker"],
        )

        assert result["success"] is True
        call_args = mock_task_cli.add_task.call_args
        assert call_args[1]["tags"] == ["python", "docker"]
        assert call_args[1]["depends"] == lower_uuid

    @patch("taskchampion_mcp.tools.validate_task")
    def test_create_subtask_cli_failure(self, mock_validate, tool_registry, mock_task_cli):
        parent_uuid = "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
        lower_uuid = parent_uuid.lower()
        mock_validate.return_value = []
        mock_task_cli.get_task.return_value = {"uuid": lower_uuid, "description": "Parent task"}
        mock_task_cli.add_task.return_value = CLIResult(
            returncode=1, stdout="", stderr="Taskwarrior error"
        )

        result = tool_registry.create_subtask(
            parent_uuid=parent_uuid,
            description="Subtask description",
        )

        assert result["error"] is True
        assert "Create subtask failed" in result["message"]


class TestErrorModel:
    def test_success_envelope_has_code_ok(self, tool_registry, mock_task_cli):
        mock_task_cli.export_tasks.return_value = []
        result = tool_registry.list_tasks()
        assert result["success"] is True
        assert result["code"] == "ok"

    def test_not_found_uses_not_found_code(self, tool_registry, mock_task_cli):
        mock_task_cli.get_task.return_value = None
        result = tool_registry.get_task("a1b2c3d4-e5f6-7890-abcd-ef1234567890")
        assert result["error"] is True
        assert result["code"] == "not_found"

    def test_rate_limit_uses_retryable_code(self, tool_registry, mock_rate_limiter):
        from taskchampion_mcp.rate_limiter import RateLimitError

        mock_rate_limiter.check_and_record.side_effect = RateLimitError("ops_per_minute", 30, 60)
        result = tool_registry.list_tasks()
        assert result["error"] is True
        assert result["code"] == "rate_limit"
        assert result["details"]["retry_after_s"] == 60

    def test_modify_task_dry_run_skips_cli_mutation(self, tool_registry, mock_task_cli):
        result = tool_registry.modify_task(
            uuid="a1b2c3d4-e5f6-7890-abcd-ef1234567890",
            fields={"priority": "H"},
            dry_run=True,
        )
        assert result["success"] is True
        assert result["code"] == "dry_run"
        mock_task_cli.modify_task.assert_not_called()

    def test_complete_task_confirmation_has_code(self, tool_registry, mock_task_cli, mock_config):
        mock_config.require_confirmation = True
        mock_task_cli.get_task.return_value = {
            "uuid": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
            "description": "Example",
        }
        result = tool_registry.complete_task(
            uuid="a1b2c3d4-e5f6-7890-abcd-ef1234567890",
            dry_run=False,
        )
        assert result["success"] is True
        assert result["code"] == "confirmation_required"

    def test_undo_supports_dry_run(self, tool_registry, mock_task_cli):
        result = tool_registry.undo(dry_run=True)
        assert result["success"] is True
        assert result["code"] == "dry_run"
        mock_task_cli.undo.assert_not_called()


class TestToolingExtensions:
    @patch("taskchampion_mcp.tools.validate_task")
    def test_batch_create_tasks_success(self, mock_validate, tool_registry, mock_task_cli):
        mock_validate.return_value = []
        mock_task_cli.add_task.return_value = CLIResult(returncode=0, stdout="Created", stderr="")

        result = tool_registry.batch_create_tasks(
            [
                {"description": "A", "project": "work"},
                {"description": "B", "project": "work"},
            ]
        )

        assert result["success"] is True
        assert result["created_count"] == 2
        assert mock_task_cli.add_task.call_count == 2

    def test_batch_create_tasks_stops_on_rate_limit(self, tool_registry, mock_rate_limiter):
        from taskchampion_mcp.rate_limiter import RateLimitError

        mock_rate_limiter.check_and_record.side_effect = RateLimitError("creates_per_hour", 1, 3600)
        result = tool_registry.batch_create_tasks([{"description": "A"}])
        assert result["error"] is True
        assert result["code"] == "rate_limit"

    def test_bulk_modify_dry_run_shows_preview(self, tool_registry, mock_task_cli):
        mock_task_cli.export_tasks.return_value = [
            {"uuid": "11111111-1111-1111-1111-111111111111"},
            {"uuid": "22222222-2222-2222-2222-222222222222"},
        ]

        result = tool_registry.bulk_modify(
            filters="project:work",
            fields={"priority": "H"},
            dry_run=True,
        )

        assert result["success"] is True
        assert result["code"] == "dry_run"
        assert result["preview"]["task_count"] == 2
        mock_task_cli.modify_task.assert_not_called()

    def test_bulk_modify_requires_confirmation(self, tool_registry, mock_task_cli, mock_config):
        mock_config.require_confirmation = True
        mock_task_cli.export_tasks.return_value = [{"uuid": "11111111-1111-1111-1111-111111111111"}]

        result = tool_registry.bulk_modify(
            filters="project:work",
            fields={"priority": "H"},
            dry_run=False,
        )

        assert result["success"] is True
        assert result["code"] == "confirmation_required"
        assert "confirmation_token" in result["details"]

    def test_get_task_report_success(self, tool_registry, mock_task_cli):
        mock_task_cli.run_report.return_value = CLIResult(
            returncode=0,
            stdout="report output",
            stderr="",
        )

        result = tool_registry.get_task_report("next", "project:work")
        assert result["success"] is True
        assert "report output" in result["report"]

    def test_get_task_report_invalid_name(self, tool_registry):
        result = tool_registry.get_task_report("next;rm -rf /", "")
        assert result["error"] is True
        assert result["code"] == "validation_error"


class TestToolsCoverageSprint:
    def test_list_tasks_internal_error(self, tool_registry, mock_task_cli):
        mock_task_cli.export_tasks.side_effect = RuntimeError("boom")
        result = tool_registry.list_tasks()
        assert result["error"] is True
        assert result["code"] == "internal_error"

    def test_get_task_success(self, tool_registry, mock_task_cli):
        mock_task_cli.get_task.return_value = {
            "uuid": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
            "description": "Task",
        }
        result = tool_registry.get_task("a1b2c3d4-e5f6-7890-abcd-ef1234567890")
        assert result["success"] is True
        assert result["task"]["description"] == "Task"

    def test_search_tasks_by_tags(self, tool_registry, mock_task_cli):
        mock_task_cli.export_tasks.return_value = [{"uuid": "x"}]
        result = tool_registry.search_tasks("python", "tags")
        assert result["success"] is True
        assert result["count"] == 1

    def test_search_tasks_internal_error(self, tool_registry, mock_task_cli):
        mock_task_cli.export_tasks.side_effect = RuntimeError("bad")
        result = tool_registry.search_tasks("x", "description")
        assert result["error"] is True
        assert result["code"] == "internal_error"

    def test_annotate_task_success(self, tool_registry, mock_task_cli):
        mock_task_cli.annotate_task.return_value = CLIResult(returncode=0, stdout="ok", stderr="")
        result = tool_registry.annotate_task(
            "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
            "note",
        )
        assert result["success"] is True

    def test_annotate_task_cli_error(self, tool_registry, mock_task_cli):
        mock_task_cli.annotate_task.return_value = CLIResult(returncode=1, stdout="", stderr="err")
        result = tool_registry.annotate_task(
            "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
            "note",
        )
        assert result["error"] is True
        assert result["code"] == "cli_error"

    def test_modify_task_success_with_tags(self, tool_registry, mock_task_cli):
        mock_task_cli.modify_task.return_value = CLIResult(returncode=0, stdout="ok", stderr="")
        result = tool_registry.modify_task(
            "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
            {"project": "work", "tags_add": ["python", "mcp"]},
        )
        assert result["success"] is True
        assert "fields_modified" in result

    def test_modify_task_cli_error(self, tool_registry, mock_task_cli):
        mock_task_cli.modify_task.return_value = CLIResult(returncode=1, stdout="", stderr="err")
        result = tool_registry.modify_task(
            "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
            {"priority": "H"},
        )
        assert result["error"] is True
        assert result["code"] == "cli_error"

    def test_start_and_stop_task_cli_errors(self, tool_registry, mock_task_cli):
        mock_task_cli.start_task.return_value = CLIResult(returncode=1, stdout="", stderr="err")
        start = tool_registry.start_task("a1b2c3d4-e5f6-7890-abcd-ef1234567890")
        assert start["error"] is True
        mock_task_cli.stop_task.return_value = CLIResult(returncode=1, stdout="", stderr="err")
        stop = tool_registry.stop_task("a1b2c3d4-e5f6-7890-abcd-ef1234567890")
        assert stop["error"] is True

    def test_get_projects_tags_context_internal_error(self, tool_registry, mock_task_cli):
        mock_task_cli.projects.side_effect = RuntimeError("x")
        projects = tool_registry.get_projects()
        assert projects["error"] is True
        mock_task_cli.tags.side_effect = RuntimeError("x")
        tags = tool_registry.get_tags()
        assert tags["error"] is True
        mock_task_cli.context.side_effect = RuntimeError("x")
        ctx = tool_registry.get_active_context()
        assert ctx["error"] is True

    def test_get_task_report_cli_error(self, tool_registry, mock_task_cli):
        mock_task_cli.run_report.return_value = CLIResult(
            returncode=1, stdout="", stderr="bad report"
        )
        result = tool_registry.get_task_report("next")
        assert result["error"] is True
        assert result["code"] == "cli_error"

    def test_timew_methods_when_unavailable(self, tool_registry):
        result_summary = tool_registry.timew_summary()
        result_status = tool_registry.timew_status()
        assert result_summary["error"] is True
        assert result_status["error"] is True

    @patch("taskchampion_mcp.tools.validate_task")
    def test_create_task_validation_error(self, mock_validate, tool_registry):
        mock_validate.return_value = ["missing field"]
        result = tool_registry.create_task(description="demo")
        assert result["error"] is True
        assert result["code"] == "validation_error"

    @patch("taskchampion_mcp.tools.validate_task")
    def test_create_task_cli_error(self, mock_validate, tool_registry, mock_task_cli):
        mock_validate.return_value = []
        mock_task_cli.add_task.return_value = CLIResult(returncode=1, stdout="", stderr="failed")
        result = tool_registry.create_task(description="demo")
        assert result["error"] is True
        assert result["code"] == "cli_error"

    @patch("taskchampion_mcp.tools.validate_task")
    def test_create_subtask_validation_error(self, mock_validate, tool_registry, mock_task_cli):
        mock_validate.return_value = ["bad depends"]
        mock_task_cli.get_task.return_value = {"uuid": "a1", "description": "parent"}
        result = tool_registry.create_subtask(
            parent_uuid="a1b2c3d4-e5f6-7890-abcd-ef1234567890",
            description="sub",
        )
        assert result["error"] is True
        assert result["code"] == "validation_error"

    def test_batch_create_tasks_empty_input(self, tool_registry):
        result = tool_registry.batch_create_tasks([])
        assert result["error"] is True
        assert result["code"] == "validation_error"

    def test_batch_create_tasks_partial_validation_failure(self, tool_registry):
        result = tool_registry.batch_create_tasks([{"description": "ok"}, "bad-item"])
        assert result["error"] is True
        assert result["code"] == "validation_error"

    def test_bulk_modify_not_found(self, tool_registry, mock_task_cli):
        mock_task_cli.export_tasks.return_value = []
        result = tool_registry.bulk_modify("project:none", {"priority": "H"})
        assert result["error"] is True
        assert result["code"] == "not_found"

    def test_bulk_modify_partial_failure(self, tool_registry, mock_task_cli):
        mock_task_cli.export_tasks.return_value = [
            {"uuid": "11111111-1111-1111-1111-111111111111"},
            {"uuid": "22222222-2222-2222-2222-222222222222"},
        ]
        original_modify = tool_registry.modify_task

        def _fake_modify(uuid, fields, dry_run):
            if uuid.startswith("1111"):
                return {"success": True, "code": "ok"}
            return {"error": True, "code": "validation_error", "message": "nope"}

        tool_registry.modify_task = _fake_modify  # type: ignore[method-assign]
        result = tool_registry.bulk_modify("project:work", {"priority": "H"})
        tool_registry.modify_task = original_modify  # type: ignore[method-assign]

        assert result["error"] is True
        assert result["code"] == "validation_error"

    def test_complete_and_delete_not_found_in_dry_run(self, tool_registry, mock_task_cli):
        mock_task_cli.get_task.return_value = None
        complete = tool_registry.complete_task(
            "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
            dry_run=True,
        )
        delete = tool_registry.delete_task(
            "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
            dry_run=True,
        )
        assert complete["code"] == "not_found"
        assert delete["code"] == "not_found"

    def test_complete_delete_undo_sync_cli_error_paths(
        self, tool_registry, mock_task_cli, mock_config
    ):
        mock_config.require_confirmation = False
        mock_task_cli.done_task.return_value = CLIResult(returncode=1, stdout="", stderr="x")
        mock_task_cli.delete_task.return_value = CLIResult(returncode=1, stdout="", stderr="x")
        mock_task_cli.undo.return_value = CLIResult(returncode=1, stdout="", stderr="x")
        mock_task_cli.sync.return_value = CLIResult(returncode=1, stdout="", stderr="x")

        complete = tool_registry.complete_task("a1b2c3d4-e5f6-7890-abcd-ef1234567890")
        delete = tool_registry.delete_task("a1b2c3d4-e5f6-7890-abcd-ef1234567890")
        undo = tool_registry.undo()
        sync = tool_registry.sync()

        assert complete["code"] == "cli_error"
        assert delete["code"] == "cli_error"
        assert undo["code"] == "cli_error"
        assert sync["code"] == "cli_error"
