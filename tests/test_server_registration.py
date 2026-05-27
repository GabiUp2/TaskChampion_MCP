from __future__ import annotations

import json
import sys
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from taskchampion_mcp.config import Role, ServerConfig
from taskchampion_mcp.rate_limiter import RateLimiter
from taskchampion_mcp.schema import TaskSchema
from taskchampion_mcp.server import (
    _configure_logging,
    _JsonLineFormatter,
    _register_contributor_tools,
    _register_generator_tools,
    _register_manager_tools,
    _register_onboarding_tools,
    _resolve_log_level,
    create_server,
)


class FakeMCP:
    def __init__(self, *_args, **_kwargs):
        self.tools: dict[str, object] = {}

    def tool(self):
        def _decorator(func):
            self.tools[func.__name__] = func
            return func

        return _decorator

    def run(self, **_kwargs):
        return None


def test_resolve_log_level_falls_back_for_invalid() -> None:
    level, invalid = _resolve_log_level("nope")
    assert invalid is True
    assert level > 0


def test_json_line_formatter_includes_exception() -> None:
    formatter = _JsonLineFormatter()
    try:
        raise RuntimeError("boom")
    except RuntimeError:
        import logging

        record = logging.LogRecord(
            name="x",
            level=logging.ERROR,
            pathname=__file__,
            lineno=1,
            msg="failed",
            args=(),
            exc_info=sys.exc_info(),
        )
        rendered = formatter.format(record)
    payload = json.loads(rendered)
    assert payload["message"] == "failed"


def test_configure_logging_non_tty_json_formatter() -> None:
    class _Stream:
        def isatty(self):
            return False

        def write(self, _x):
            return None

        def flush(self):
            return None

    _configure_logging(stream=_Stream())


def test_register_onboarding_tools_calls_wrapped_functions(monkeypatch: pytest.MonkeyPatch) -> None:
    mcp = FakeMCP()
    reg = SimpleNamespace(
        config=ServerConfig(role=Role.MANAGER),
        task=MagicMock(),
        timew=MagicMock(),
        audit=MagicMock(),
        # _audit_call calls limiter.check_and_record; use a real limiter with
        # generous bounds so onboarding tools execute normally (rate-limit
        # behaviour itself is covered in test_observability).
        limiter=RateLimiter(
            ops_per_minute=10_000,
            ops_per_hour=10_000,
            creates_per_hour=10_000,
        ),
    )
    monkeypatch.setattr(
        "taskchampion_mcp.server.onboarding_get_initialization_status",
        lambda **_kw: {"success": True, "needs_onboarding": True},
    )
    monkeypatch.setattr(
        "taskchampion_mcp.server.onboarding_propose_initialization_options",
        lambda _status: {"success": True, "options": []},
    )
    monkeypatch.setattr(
        "taskchampion_mcp.server.onboarding_analyze_existing_tasks",
        lambda _task: {"success": True},
    )
    monkeypatch.setattr(
        "taskchampion_mcp.server.onboarding_analyze_taxonomy_file",
        lambda _path: {"success": True},
    )
    monkeypatch.setattr(
        "taskchampion_mcp.server.onboarding_generate_schema_preview",
        lambda **_kw: {"success": True},
    )
    monkeypatch.setattr(
        "taskchampion_mcp.server.onboarding_save_initial_schema",
        lambda **_kw: {"success": True},
    )
    monkeypatch.setattr(
        "taskchampion_mcp.server.onboarding_list_preset_schemas",
        lambda: {"success": True},
    )
    monkeypatch.setattr(
        "taskchampion_mcp.server.onboarding_use_preset_schema",
        lambda **_kw: {"success": True},
    )
    monkeypatch.setattr(
        "taskchampion_mcp.server.onboarding_reconfigure_active_schema",
        lambda **_kw: {"success": True, "code": "ok"},
    )
    monkeypatch.setattr(
        "taskchampion_mcp.server.onboarding_reconfigure_taxonomy_path",
        lambda _path, **_kw: {"success": True, "code": "ok"},
    )
    monkeypatch.setattr(
        "taskchampion_mcp.server.onboarding_reconfigure_role",
        lambda **_kw: {"success": True, "code": "ok"},
    )

    _register_onboarding_tools(mcp, reg)

    assert json.loads(mcp.tools["get_initialization_status"]())["success"] is True
    assert json.loads(mcp.tools["propose_initialization_options"]())["success"] is True
    assert json.loads(mcp.tools["analyze_existing_tasks_for_schema"]())["success"] is True
    assert json.loads(mcp.tools["analyze_taxonomy_file"]("x"))["success"] is True
    assert json.loads(mcp.tools["generate_initial_schema_preview"]())["success"] is True
    assert json.loads(mcp.tools["save_initial_schema"]("x"))["success"] is True
    assert json.loads(mcp.tools["list_preset_schemas"]())["success"] is True
    assert json.loads(mcp.tools["use_preset_schema"]("minimal"))["success"] is True


def test_register_contributor_tools_calls_registry_methods(monkeypatch: pytest.MonkeyPatch) -> None:
    mcp = FakeMCP()
    reg = SimpleNamespace(
        list_tasks=lambda filters="": {"ok": filters},
        get_task=lambda uuid: {"uuid": uuid},
        search_tasks=lambda query, field="description": {"q": query, "f": field},
        annotate_task=lambda uuid, ann, dry=None: {"uuid": uuid, "ann": ann, "dry": dry},
        modify_task=lambda uuid, fields, dry=None: {"uuid": uuid, "fields": fields, "dry": dry},
        start_task=lambda uuid, dry=None: {"uuid": uuid, "dry": dry},
        stop_task=lambda uuid, dry=None: {"uuid": uuid, "dry": dry},
        get_projects=lambda: {"projects": []},
        get_tags=lambda: {"tags": []},
        get_active_context=lambda: {"context": "none"},
        get_schema_info=lambda: {"schema": "minimal"},
        get_task_report=lambda name, filters="": {"name": name, "filters": filters},
        timew_summary=lambda period=":day": {"period": period},
        timew_status=lambda: {"tracking": False},
        timew=object(),
        config=ServerConfig(),
        audit=MagicMock(),
        # _audit_call (used by the reconfigure tools registered alongside
        # contributor tools) needs limiter.check_and_record.
        limiter=RateLimiter(
            ops_per_minute=10_000,
            ops_per_hour=10_000,
            creates_per_hour=10_000,
        ),
    )
    monkeypatch.setattr(
        "taskchampion_mcp.server.onboarding_reconfigure_active_schema",
        lambda **_kw: {"success": True, "code": "ok"},
    )
    monkeypatch.setattr(
        "taskchampion_mcp.server.onboarding_reconfigure_taxonomy_path",
        lambda _path, **_kw: {"success": True, "code": "ok"},
    )
    monkeypatch.setattr(
        "taskchampion_mcp.server.onboarding_reconfigure_role",
        lambda **_kw: {"success": True, "code": "ok"},
    )
    _register_contributor_tools(mcp, reg)

    assert json.loads(mcp.tools["list_tasks"]("project:work"))["ok"] == "project:work"
    assert json.loads(mcp.tools["get_task"]("u"))["uuid"] == "u"
    assert json.loads(mcp.tools["search_tasks"]("abc"))["q"] == "abc"
    assert json.loads(mcp.tools["annotate_task"]("u", "a"))["ann"] == "a"
    assert json.loads(mcp.tools["modify_task"]("u", {"priority": "H"}))["fields"]["priority"] == "H"
    assert json.loads(mcp.tools["start_task"]("u"))["uuid"] == "u"
    assert json.loads(mcp.tools["stop_task"]("u"))["uuid"] == "u"
    assert json.loads(mcp.tools["get_projects"]())["projects"] == []
    assert json.loads(mcp.tools["get_tags"]())["tags"] == []
    assert json.loads(mcp.tools["get_active_context"]())["context"] == "none"
    assert json.loads(mcp.tools["get_schema_info"]())["schema"] == "minimal"
    assert json.loads(mcp.tools["get_task_report"]("next"))["name"] == "next"
    assert json.loads(mcp.tools["get_time_summary"](":week"))["period"] == ":week"
    assert json.loads(mcp.tools["get_time_status"]())["tracking"] is False
    assert json.loads(mcp.tools["set_active_schema"]("minimal", ""))["success"] is True
    assert json.loads(mcp.tools["set_taxonomy_path"]("taxonomy.md"))["success"] is True
    assert json.loads(mcp.tools["set_role"]("CONTRIBUTOR"))["success"] is True


def test_register_generator_tools_calls_registry_methods() -> None:
    mcp = FakeMCP()
    reg = SimpleNamespace(
        create_task=lambda **kwargs: kwargs,
        create_subtask=lambda **kwargs: kwargs,
        batch_create_tasks=lambda tasks, dry_run=None: {"tasks": tasks, "dry_run": dry_run},
    )
    _register_generator_tools(mcp, reg)

    created = json.loads(
        mcp.tools["create_task"](
            description="x",
            tags=["a", "b"],
            extra_fields={"scope": "work"},
            dry_run=True,
        )
    )
    assert created["description"] == "x"
    assert created["tags"] == ["a", "b"]
    assert created["scope"] == "work"
    assert created["dry_run"] is True

    sub = json.loads(mcp.tools["create_subtask"]("p", "child", tags=["x"]))
    assert sub["parent_uuid"] == "p"
    assert sub["tags"] == ["x"]

    batch = json.loads(mcp.tools["batch_create_tasks"]([{"description": "a"}], dry_run=True))
    assert batch["dry_run"] is True


def test_register_manager_tools_calls_registry_methods() -> None:
    mcp = FakeMCP()
    reg = SimpleNamespace(
        complete_task=lambda uuid, dry_run=None, confirm_token="": {
            "uuid": uuid,
            "dry_run": dry_run,
            "confirm_token": confirm_token,
        },
        delete_task=lambda uuid, dry_run=None, confirm_token="": {
            "uuid": uuid,
            "dry_run": dry_run,
            "confirm_token": confirm_token,
        },
        undo=lambda dry_run=None, confirm_token="": {
            "dry_run": dry_run,
            "confirm_token": confirm_token,
        },
        sync=lambda dry_run=None: {"dry_run": dry_run},
        bulk_modify=lambda **kwargs: kwargs,
    )
    _register_manager_tools(mcp, reg)

    assert json.loads(mcp.tools["complete_task"]("u"))["uuid"] == "u"
    assert json.loads(mcp.tools["delete_task"]("u"))["uuid"] == "u"
    assert json.loads(mcp.tools["undo_last_action"](dry_run=True))["dry_run"] is True
    assert json.loads(mcp.tools["sync_tasks"](dry_run=True))["dry_run"] is True
    bulk = json.loads(mcp.tools["bulk_modify"]("project:work", {"priority": "H"}, dry_run=True))
    assert bulk["filters"] == "project:work"


def test_create_server_registers_onboarding_when_required(monkeypatch: pytest.MonkeyPatch) -> None:
    cfg = ServerConfig(
        role=Role.CONTRIBUTOR,
        explicit_role_configured=False,
        explicit_schema_configured=False,
    )

    task_cli = MagicMock()
    task_cli.version.return_value = "3.1.0"
    timew = MagicMock()
    timew.available.return_value = False
    monkeypatch.setattr("taskchampion_mcp.server.TaskwarriorCLI", lambda **_kw: task_cli)
    monkeypatch.setattr("taskchampion_mcp.server.TimewarriorCLI", lambda **_kw: timew)
    monkeypatch.setattr(
        "taskchampion_mcp.server.load_schema",
        lambda _s: TaskSchema("minimal", "1.0.0"),
    )
    monkeypatch.setattr("taskchampion_mcp.server.RateLimiter", lambda **_kw: MagicMock())
    audit = MagicMock()
    monkeypatch.setattr("taskchampion_mcp.server.AuditLogger", lambda *_a, **_kw: audit)
    monkeypatch.setattr("taskchampion_mcp.server.ToolRegistry", lambda **_kw: SimpleNamespace())
    monkeypatch.setattr("taskchampion_mcp.server.FastMCP", FakeMCP)

    onb = MagicMock()
    ctb = MagicMock()
    monkeypatch.setattr("taskchampion_mcp.server._register_onboarding_tools", onb)
    monkeypatch.setattr("taskchampion_mcp.server._register_contributor_tools", ctb)
    monkeypatch.setattr("taskchampion_mcp.server._build_instructions", lambda *_a, **_kw: "x")

    _ = create_server(config=cfg)
    assert onb.called
    assert not ctb.called
    assert audit.log_startup.called


def test_create_server_registers_role_tools_when_initialised(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cfg = ServerConfig(
        role=Role.MANAGER,
        explicit_role_configured=True,
        explicit_schema_configured=True,
    )
    task_cli = MagicMock()
    task_cli.version.return_value = "3.1.0"
    timew = MagicMock()
    timew.available.return_value = False

    monkeypatch.setattr("taskchampion_mcp.server.TaskwarriorCLI", lambda **_kw: task_cli)
    monkeypatch.setattr("taskchampion_mcp.server.TimewarriorCLI", lambda **_kw: timew)
    monkeypatch.setattr(
        "taskchampion_mcp.server.load_schema",
        lambda _s: TaskSchema("minimal", "1.0.0"),
    )
    monkeypatch.setattr("taskchampion_mcp.server.RateLimiter", lambda **_kw: MagicMock())
    monkeypatch.setattr("taskchampion_mcp.server.AuditLogger", lambda *_a, **_kw: MagicMock())
    monkeypatch.setattr("taskchampion_mcp.server.ToolRegistry", lambda **_kw: SimpleNamespace())
    monkeypatch.setattr("taskchampion_mcp.server.FastMCP", FakeMCP)
    monkeypatch.setattr("taskchampion_mcp.server._build_instructions", lambda *_a, **_kw: "x")

    onb = MagicMock()
    ctb = MagicMock()
    gen = MagicMock()
    man = MagicMock()
    monkeypatch.setattr("taskchampion_mcp.server._register_onboarding_tools", onb)
    monkeypatch.setattr("taskchampion_mcp.server._register_contributor_tools", ctb)
    monkeypatch.setattr("taskchampion_mcp.server._register_generator_tools", gen)
    monkeypatch.setattr("taskchampion_mcp.server._register_manager_tools", man)

    _ = create_server(config=cfg)
    assert not onb.called
    assert ctb.called
    assert gen.called
    assert man.called


def test_create_server_exits_when_taskwarrior_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    cfg = ServerConfig()
    task_cli = MagicMock()
    task_cli.version.return_value = None
    monkeypatch.setattr("taskchampion_mcp.server.TaskwarriorCLI", lambda **_kw: task_cli)
    with pytest.raises(SystemExit):
        create_server(config=cfg)
