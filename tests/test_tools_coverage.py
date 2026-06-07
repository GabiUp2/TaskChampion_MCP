"""Extra coverage tests for ToolRegistry — targets the uncovered branches in tools.py."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from taskchampion_mcp.audit import AuditLogger
from taskchampion_mcp.cli import CLIResult, TaskwarriorCLI, TimewarriorCLI
from taskchampion_mcp.config import ServerConfig
from taskchampion_mcp.rate_limiter import RateLimiter
from taskchampion_mcp.schema import TaskSchema
from taskchampion_mcp.tools import (
    ToolRegistry,
    _make_coded_error,
    _make_error,
    _make_success,
    _redact_fields,
    _redact_list,
    _result_code_from_exception,
    _validate_code,
)

_UUID = "a1b2c3d4-e5f6-7890-abcd-ef1234567890"


@pytest.fixture()
def cfg():
    c = MagicMock(spec=ServerConfig)
    c.role = "MANAGER"
    c.redacted_fields = []
    c.dry_run_default = False
    c.require_confirmation = False
    c.rate_limit_per_minute = 30
    c.rate_limit_per_hour = 200
    c.create_limit_per_hour = 50
    return c


@pytest.fixture()
def task_cli():
    cli = MagicMock(spec=TaskwarriorCLI)
    cli.udas.return_value = []
    return cli


@pytest.fixture()
def schema():
    s = MagicMock(spec=TaskSchema)
    s.name = "minimal"
    s.version = "1.0.0"
    s.enum_fields.return_value = {}
    s.required_field_names.return_value = []
    s.fields = {}
    s.llm_provenance_fields = {}
    return s


@pytest.fixture()
def limiter():
    return MagicMock(spec=RateLimiter)


@pytest.fixture()
def audit():
    return MagicMock(spec=AuditLogger)


@pytest.fixture()
def reg(cfg, task_cli, schema, limiter, audit):
    return ToolRegistry(
        config=cfg,
        task_cli=task_cli,
        timew_cli=None,
        schema=schema,
        rate_limiter=limiter,
        audit=audit,
    )


@pytest.fixture()
def timew_cli():
    tw = MagicMock(spec=TimewarriorCLI)
    tw.available.return_value = True
    return tw


@pytest.fixture()
def reg_with_timew(cfg, task_cli, schema, limiter, audit, timew_cli):
    return ToolRegistry(
        config=cfg,
        task_cli=task_cli,
        timew_cli=timew_cli,
        schema=schema,
        rate_limiter=limiter,
        audit=audit,
    )


# -----------------------------------------------------------------------
# Module-level helpers
# -----------------------------------------------------------------------

class TestHelpers:
    def test_validate_code_invalid(self):
        with pytest.raises(ValueError, match="Invalid result code"):
            _validate_code("bogus", {"ok"})

    def test_make_error(self):
        r = _make_error("boom")
        assert r["error"] is True
        assert r["code"] == "internal_error"

    def test_make_success_default_code(self):
        r = _make_success("ok msg")
        assert r["code"] == "ok"
        assert r["success"] is True

    def test_make_coded_error_with_details(self):
        r = _make_coded_error("fail", "not_found", details={"foo": 1})
        assert r["details"]["foo"] == 1

    def test_redact_fields_strips_keys(self):
        task = {"uuid": "1", "secret": "s", "desc": "d"}
        out = _redact_fields(task, ["secret"])
        assert "secret" not in out
        assert "desc" in out

    def test_redact_fields_noop_when_empty(self):
        task = {"uuid": "1", "secret": "s"}
        assert _redact_fields(task, []) is task

    def test_redact_list(self):
        tasks = [{"a": 1, "b": 2}, {"a": 3, "b": 4}]
        out = _redact_list(tasks, ["b"])
        assert all("b" not in t for t in out)

    def test_result_code_from_generic_exception(self):
        assert _result_code_from_exception(RuntimeError("x")) == "internal_error"


# -----------------------------------------------------------------------
# search_tasks field branches
# -----------------------------------------------------------------------

class TestSearchTasksBranches:
    def test_search_by_project(self, reg, task_cli):
        task_cli.export_tasks.return_value = [{"uuid": _UUID}]
        r = reg.search_tasks("myproj", field="project")
        assert r["success"] is True
        task_cli.export_tasks.assert_called_once()
        assert "project:" in task_cli.export_tasks.call_args[0][0]

    def test_search_by_uda(self, reg, task_cli):
        task_cli.export_tasks.return_value = []
        r = reg.search_tasks("val", field="custom_uda")
        assert r["success"] is True
        assert "custom_uda:" in task_cli.export_tasks.call_args[0][0]


# -----------------------------------------------------------------------
# start_task / stop_task success
# -----------------------------------------------------------------------

class TestStartStop:
    def test_start_success(self, reg, task_cli):
        task_cli.start_task.return_value = CLIResult(returncode=0, stdout="ok", stderr="")
        r = reg.start_task(_UUID)
        assert r["success"] is True

    def test_stop_success(self, reg, task_cli):
        task_cli.stop_task.return_value = CLIResult(returncode=0, stdout="ok", stderr="")
        r = reg.stop_task(_UUID)
        assert r["success"] is True

    def test_start_internal_error(self, reg, task_cli):
        task_cli.start_task.side_effect = RuntimeError("boom")
        r = reg.start_task(_UUID)
        assert r["code"] == "internal_error"

    def test_stop_internal_error(self, reg, task_cli):
        task_cli.stop_task.side_effect = RuntimeError("boom")
        r = reg.stop_task(_UUID)
        assert r["code"] == "internal_error"


# -----------------------------------------------------------------------
# get_projects / get_tags / get_active_context success
# -----------------------------------------------------------------------

class TestReadOnlyTools:
    def test_get_projects_success(self, reg, task_cli):
        task_cli.projects.return_value = ["proj_a", "proj_b"]
        r = reg.get_projects()
        assert r["success"] is True
        assert len(r["projects"]) == 2

    def test_get_tags_success(self, reg, task_cli):
        task_cli.tags.return_value = ["tag1"]
        r = reg.get_tags()
        assert r["success"] is True

    def test_get_tags_internal_error(self, reg, task_cli):
        task_cli.tags.side_effect = RuntimeError("boom")
        r = reg.get_tags()
        assert r["code"] == "internal_error"

    def test_get_active_context_success(self, reg, task_cli):
        task_cli.context.return_value = "work"
        r = reg.get_active_context()
        assert r["success"] is True

    def test_get_active_context_internal_error(self, reg, task_cli):
        task_cli.context.side_effect = RuntimeError("boom")
        r = reg.get_active_context()
        assert r["code"] == "internal_error"


# -----------------------------------------------------------------------
# Timewarrior with real cli mock
# -----------------------------------------------------------------------

class TestTimewWithCli:
    def test_timew_summary_success(self, reg_with_timew, timew_cli):
        timew_cli.summary.return_value = "Tracking: 1h"
        r = reg_with_timew.timew_summary(":day")
        assert r["success"] is True

    def test_timew_summary_internal_error(self, reg_with_timew, timew_cli):
        timew_cli.summary.side_effect = RuntimeError("boom")
        r = reg_with_timew.timew_summary(":day")
        assert r["code"] == "internal_error"

    def test_timew_status_success(self, reg_with_timew, timew_cli):
        timew_cli.status.return_value = {"tracking": False}
        r = reg_with_timew.timew_status()
        assert r["success"] is True

    def test_timew_status_internal_error(self, reg_with_timew, timew_cli):
        timew_cli.status.side_effect = RuntimeError("boom")
        r = reg_with_timew.timew_status()
        assert r["code"] == "internal_error"


# -----------------------------------------------------------------------
# create_task success path
# -----------------------------------------------------------------------

class TestCreateTask:
    @patch("taskchampion_mcp.tools.validate_task")
    def test_create_task_success(self, mock_validate, reg, task_cli):
        mock_validate.return_value = []
        task_cli.add_task.return_value = CLIResult(
            returncode=0, stdout="Created task 1.", stderr=""
        )
        r = reg.create_task(description="Buy milk")
        assert r["success"] is True
        assert "Created" in r["message"]

    @patch("taskchampion_mcp.tools.validate_task")
    def test_create_task_with_all_fields(self, mock_validate, reg, task_cli, schema):
        mock_validate.return_value = []
        schema.enum_fields.return_value = {"custom": ["a", "b"]}
        reg._registered_udas = {"custom"}  # seed UDA registration for this test
        task_cli.add_task.return_value = CLIResult(
            returncode=0, stdout="Created task 1.", stderr=""
        )
        r = reg.create_task(
            description="Complex",
            project="work",
            priority="H",
            due="tomorrow",
            tags=["urgent"],
            custom="a",
        )
        assert r["success"] is True

    @patch("taskchampion_mcp.tools.validate_task")
    def test_create_task_internal_error(self, mock_validate, reg, task_cli):
        mock_validate.return_value = []
        task_cli.add_task.side_effect = RuntimeError("boom")
        r = reg.create_task(description="fail")
        assert r["code"] == "internal_error"


# -----------------------------------------------------------------------
# MANAGER lifecycle — success paths
# -----------------------------------------------------------------------

class TestManagerSuccess:
    def test_complete_task_success(self, reg, task_cli, cfg):
        cfg.require_confirmation = False
        task_cli.done_task.return_value = CLIResult(returncode=0, stdout="ok", stderr="")
        r = reg.complete_task(_UUID)
        assert r["success"] is True

    def test_delete_task_success(self, reg, task_cli, cfg):
        cfg.require_confirmation = False
        task_cli.delete_task.return_value = CLIResult(returncode=0, stdout="ok", stderr="")
        r = reg.delete_task(_UUID)
        assert r["success"] is True

    def test_undo_success(self, reg, task_cli, cfg):
        cfg.require_confirmation = False
        task_cli.undo.return_value = CLIResult(returncode=0, stdout="ok", stderr="")
        r = reg.undo()
        assert r["success"] is True

    def test_sync_success(self, reg, task_cli):
        task_cli.sync.return_value = CLIResult(returncode=0, stdout="Synced", stderr="")
        r = reg.sync()
        assert r["success"] is True

    def test_complete_internal_error(self, reg, task_cli, cfg):
        cfg.require_confirmation = False
        task_cli.done_task.side_effect = RuntimeError("boom")
        r = reg.complete_task(_UUID)
        assert r["code"] == "internal_error"

    def test_delete_internal_error(self, reg, task_cli, cfg):
        cfg.require_confirmation = False
        task_cli.delete_task.side_effect = RuntimeError("boom")
        r = reg.delete_task(_UUID)
        assert r["code"] == "internal_error"

    def test_undo_internal_error(self, reg, task_cli, cfg):
        cfg.require_confirmation = False
        task_cli.undo.side_effect = RuntimeError("boom")
        r = reg.undo()
        assert r["code"] == "internal_error"

    def test_sync_internal_error(self, reg, task_cli):
        task_cli.sync.side_effect = RuntimeError("boom")
        r = reg.sync()
        assert r["code"] == "internal_error"


# -----------------------------------------------------------------------
# Dry-run and confirmation paths for complete/delete
# -----------------------------------------------------------------------

class TestDryRunAndConfirmation:
    def test_complete_dry_run_success(self, reg, task_cli):
        task_cli.get_task.return_value = {"uuid": _UUID, "description": "t"}
        r = reg.complete_task(_UUID, dry_run=True)
        assert r["code"] == "dry_run"

    def test_delete_dry_run_success(self, reg, task_cli):
        task_cli.get_task.return_value = {"uuid": _UUID, "description": "t"}
        r = reg.delete_task(_UUID, dry_run=True)
        assert r["code"] == "dry_run"

    def test_undo_dry_run(self, reg):
        r = reg.undo(dry_run=True)
        assert r["code"] == "dry_run"

    def test_sync_dry_run(self, reg):
        r = reg.sync(dry_run=True)
        assert r["code"] == "dry_run"

    def test_delete_confirmation_required(self, reg, task_cli, cfg):
        cfg.require_confirmation = True
        task_cli.get_task.return_value = {"uuid": _UUID, "description": "t"}
        r = reg.delete_task(_UUID)
        assert r["code"] == "confirmation_required"

    def test_delete_confirmation_not_found(self, reg, task_cli, cfg):
        cfg.require_confirmation = True
        task_cli.get_task.return_value = None
        r = reg.delete_task(_UUID)
        assert r["code"] == "not_found"

    def test_undo_confirmation_required(self, reg, cfg):
        cfg.require_confirmation = True
        r = reg.undo()
        assert r["code"] == "confirmation_required"


# -----------------------------------------------------------------------
# bulk_modify success path
# -----------------------------------------------------------------------

class TestBulkModifySuccess:
    def test_success(self, reg, task_cli, cfg):
        cfg.require_confirmation = False
        task_cli.export_tasks.return_value = [
            {"uuid": _UUID, "description": "t1"},
        ]
        task_cli.modify_task.return_value = CLIResult(returncode=0, stdout="ok", stderr="")
        r = reg.bulk_modify(filters="project:work", fields={"priority": "H"})
        assert r["success"] is True
        assert r["modified_count"] == 1

    def test_internal_error(self, reg, task_cli, cfg):
        cfg.require_confirmation = False
        task_cli.export_tasks.side_effect = RuntimeError("boom")
        r = reg.bulk_modify(filters="all", fields={"priority": "L"})
        assert r["code"] == "internal_error"


# -----------------------------------------------------------------------
# Redaction in MANAGER lifecycle
# -----------------------------------------------------------------------

class TestRedaction:
    def test_complete_dry_run_redacts(self, reg, task_cli, cfg):
        cfg.redacted_fields = ["secret"]
        task_cli.get_task.return_value = {"uuid": _UUID, "description": "t", "secret": "x"}
        r = reg.complete_task(_UUID, dry_run=True)
        assert "secret" not in r.get("task", {})

    def test_delete_confirmation_redacts(self, reg, task_cli, cfg):
        cfg.require_confirmation = True
        cfg.redacted_fields = ["secret"]
        task_cli.get_task.return_value = {"uuid": _UUID, "description": "t", "secret": "x"}
        r = reg.delete_task(_UUID)
        assert "secret" not in r.get("task", {})


# -----------------------------------------------------------------------
# ToolRegistry.reload()
# -----------------------------------------------------------------------

class TestReload:
    @patch("taskchampion_mcp.tools.TimewarriorCLI")
    @patch("taskchampion_mcp.tools.TaskwarriorCLI")
    def test_reload_happy_path(self, mock_tw_cls, mock_timew_cls, reg, tmp_path):
        reg._config_path = tmp_path

        mock_timew_instance = MagicMock()
        mock_timew_instance.available.return_value = False
        mock_timew_cls.return_value = mock_timew_instance

        with patch("taskchampion_mcp.config.load_config") as mock_load_cfg, \
             patch("taskchampion_mcp.schema.load_schema") as mock_load_schema:
            mock_load_cfg.return_value = reg.config
            mock_load_schema.return_value = reg.schema
            reloaded = reg.reload()

        assert "config" in reloaded
        assert "schema" in reloaded
        assert "rate_limiter" in reloaded
        assert "audit" in reloaded
        assert "task_cli" in reloaded
        assert "timew_cli" in reloaded

    @patch("taskchampion_mcp.tools.TimewarriorCLI")
    @patch("taskchampion_mcp.tools.TaskwarriorCLI")
    def test_reload_schema_failure_keeps_previous(
        self, mock_tw_cls, mock_timew_cls, reg, tmp_path
    ):
        reg._config_path = tmp_path
        old_schema = reg.schema

        mock_timew_instance = MagicMock()
        mock_timew_instance.available.return_value = False
        mock_timew_cls.return_value = mock_timew_instance

        with patch("taskchampion_mcp.config.load_config") as mock_load_cfg, \
             patch("taskchampion_mcp.schema.load_schema") as mock_load_schema:
            mock_load_cfg.return_value = reg.config
            mock_load_schema.side_effect = FileNotFoundError("gone")
            reloaded = reg.reload()

        assert "schema" not in reloaded
        assert reg.schema is old_schema

    @patch("taskchampion_mcp.tools.TimewarriorCLI")
    @patch("taskchampion_mcp.tools.TaskwarriorCLI")
    def test_reload_schema_via_schema_path(
        self, mock_tw_cls, mock_timew_cls, reg, tmp_path
    ):
        reg._config_path = tmp_path

        mock_timew_instance = MagicMock()
        mock_timew_instance.available.return_value = True
        mock_timew_cls.return_value = mock_timew_instance

        cfg_with_path = MagicMock(spec=ServerConfig)
        cfg_with_path.schema_path = "/some/schema.toml"
        cfg_with_path.schema_name = None
        cfg_with_path.rate_limit_per_minute = 30
        cfg_with_path.rate_limit_per_hour = 200
        cfg_with_path.create_limit_per_hour = 50
        cfg_with_path.audit_log_path = str(tmp_path / "audit.log")
        cfg_with_path.redacted_fields = []
        cfg_with_path.task_binary = "task"
        cfg_with_path.taskwarrior_override_rc = None
        cfg_with_path.timew_binary = "timew"

        with patch("taskchampion_mcp.config.load_config") as mock_load_cfg, \
             patch("taskchampion_mcp.schema.load_schema") as mock_load_schema:
            mock_load_cfg.return_value = cfg_with_path
            mock_load_schema.return_value = reg.schema
            reloaded = reg.reload()

        mock_load_schema.assert_called_once_with("/some/schema.toml")
        assert "schema" in reloaded
        assert reg.timew is not None


# -----------------------------------------------------------------------
# get_task_report extra branches
# -----------------------------------------------------------------------

class TestGetTaskReport:
    def test_internal_error(self, reg, task_cli):
        task_cli.run_report.side_effect = RuntimeError("boom")
        r = reg.get_task_report("next")
        assert r["code"] == "internal_error"


# -----------------------------------------------------------------------
# get_schema_info
# -----------------------------------------------------------------------

class TestGetSchemaInfo:
    def test_success(self, reg, schema):
        schema.description = "A minimal schema"
        schema.field_context_for_llm.return_value = {"description": {"type": "string"}}
        r = reg.get_schema_info()
        assert r["success"] is True
        assert r["schema_name"] == "minimal"
