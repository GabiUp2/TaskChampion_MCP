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
