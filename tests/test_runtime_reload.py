"""ADR 19 acceptance tests — runtime reload, gates, and stable tool surface.

Covers:
- Stale state before initialisation: tool calls return ``schema_unset``
- Post-onboarding: tools become callable without restart
- Explicit ``reload_configuration`` after hand-edit: state refreshes
- Role gating enforced at runtime (CONTRIBUTOR cannot call MANAGER tools)
- Timewarrior-absent fallback: time tools return structured error
- ``get_runtime_capabilities`` returns correct mode/role/tool-groups
"""

from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from taskchampion_mcp.config import Role, ServerConfig
from taskchampion_mcp.rate_limiter import RateLimiter
from taskchampion_mcp.server import (
    _build_capabilities,
    _gate_initialized,
    _gate_role,
    _register_contributor_tools,
    _register_generator_tools,
    _register_manager_tools,
    _register_reload_tool,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class FakeMCP:
    def __init__(self, *_a, **_kw):
        self.tools: dict[str, object] = {}

    def tool(self):
        def _decorator(fn):
            self.tools[fn.__name__] = fn
            return fn
        return _decorator


def _make_reg(
    role: str = Role.CONTRIBUTOR,
    initialized: bool = True,
    timew: bool = False,
) -> SimpleNamespace:
    cfg = ServerConfig(
        role=role,
        explicit_role_configured=initialized,
        explicit_schema_configured=initialized,
    )
    return SimpleNamespace(
        config=cfg,
        initialized=initialized,
        task=MagicMock(),
        timew=MagicMock() if timew else None,
        schema=SimpleNamespace(name="minimal", version="1.0.0",
                              field_context_for_llm=lambda: {},
                              required_field_names=lambda: [],
                              enum_fields=lambda: {},
                              description="test"),
        audit=MagicMock(),
        limiter=RateLimiter(
            ops_per_minute=10_000,
            ops_per_hour=10_000,
            creates_per_hour=10_000,
        ),
        reload=MagicMock(return_value=["config", "schema", "rate_limiter", "audit"]),
        list_tasks=lambda filters="": {"success": True, "tasks": []},
        get_task=lambda uuid: {"success": True, "task": {}},
        search_tasks=lambda query, field="description": {"success": True, "tasks": []},
        annotate_task=lambda uuid, ann, dry=None: {"success": True},
        modify_task=lambda uuid, fields, dry=None: {"success": True},
        start_task=lambda uuid, dry=None: {"success": True},
        stop_task=lambda uuid, dry=None: {"success": True},
        get_projects=lambda: {"success": True, "projects": []},
        get_tags=lambda: {"success": True, "tags": []},
        get_active_context=lambda: {"success": True, "context": "none"},
        get_schema_info=lambda: {"success": True, "schema_name": "minimal"},
        get_task_report=lambda name, f="": {"success": True},
        timew_summary=lambda period=":day": {"success": True},
        timew_status=lambda: {"success": True},
        create_task=lambda **kw: {"success": True},
        create_subtask=lambda **kw: {"success": True},
        batch_create_tasks=lambda tasks, dry_run=None: {"success": True},
        complete_task=lambda uuid, dry_run=None, confirm_token="": {"success": True},
        delete_task=lambda uuid, dry_run=None, confirm_token="": {"success": True},
        undo=lambda dry_run=None, confirm_token="": {"success": True},
        sync=lambda dry_run=None: {"success": True},
        bulk_modify=lambda **kw: {"success": True},
    )


# ---------------------------------------------------------------------------
# Gate unit tests
# ---------------------------------------------------------------------------


class TestRuntimeGates:

    def test_gate_initialized_returns_none_when_initialized(self) -> None:
        reg = _make_reg(initialized=True)
        assert _gate_initialized(reg) is None

    def test_gate_initialized_returns_error_when_uninitialised(self) -> None:
        reg = _make_reg(initialized=False)
        result = json.loads(_gate_initialized(reg))
        assert result["error"] is True
        assert result["code"] == "schema_unset"

    def test_gate_role_passes_when_sufficient(self) -> None:
        reg = _make_reg(role=Role.MANAGER, initialized=True)
        assert _gate_role(reg, Role.MANAGER) is None
        assert _gate_role(reg, Role.GENERATOR) is None
        assert _gate_role(reg, Role.CONTRIBUTOR) is None

    def test_gate_role_blocks_insufficient(self) -> None:
        reg = _make_reg(role=Role.CONTRIBUTOR, initialized=True)
        result = json.loads(_gate_role(reg, Role.GENERATOR))
        assert result["error"] is True
        assert result["code"] == "role_insufficient"

    def test_gate_role_checks_init_first(self) -> None:
        reg = _make_reg(role=Role.MANAGER, initialized=False)
        result = json.loads(_gate_role(reg, Role.MANAGER))
        assert result["code"] == "schema_unset"


# ---------------------------------------------------------------------------
# Stale state: contributor tools return schema_unset before initialisation
# ---------------------------------------------------------------------------


class TestSchemaUnsetBeforeInit:

    def test_contributor_tools_return_schema_unset(self) -> None:
        mcp = FakeMCP()
        reg = _make_reg(initialized=False)
        _register_contributor_tools(mcp, reg)

        for name in (
            "list_tasks", "get_task", "search_tasks", "get_projects",
            "get_tags", "get_active_context", "get_schema_info",
            "get_task_report", "get_time_summary", "get_time_status",
        ):
            fn = mcp.tools[name]
            if name == "get_task":
                result = json.loads(fn("some-uuid"))
            elif name == "search_tasks":
                result = json.loads(fn("query"))
            elif name == "get_task_report":
                result = json.loads(fn("next"))
            else:
                result = json.loads(fn())
            assert result["code"] == "schema_unset", f"{name} should return schema_unset"

    def test_generator_tools_return_schema_unset(self) -> None:
        mcp = FakeMCP()
        reg = _make_reg(initialized=False)
        _register_generator_tools(mcp, reg)

        result = json.loads(mcp.tools["create_task"](description="x"))
        assert result["code"] == "schema_unset"

    def test_manager_tools_return_schema_unset(self) -> None:
        mcp = FakeMCP()
        reg = _make_reg(initialized=False)
        _register_manager_tools(mcp, reg)

        result = json.loads(mcp.tools["complete_task"]("uuid"))
        assert result["code"] == "schema_unset"


# ---------------------------------------------------------------------------
# Role gating at runtime
# ---------------------------------------------------------------------------


class TestRoleGating:

    def test_contributor_cannot_call_generator(self) -> None:
        mcp = FakeMCP()
        reg = _make_reg(role=Role.CONTRIBUTOR, initialized=True)
        _register_generator_tools(mcp, reg)

        result = json.loads(mcp.tools["create_task"](description="x"))
        assert result["code"] == "role_insufficient"

    def test_contributor_cannot_call_manager(self) -> None:
        mcp = FakeMCP()
        reg = _make_reg(role=Role.CONTRIBUTOR, initialized=True)
        _register_manager_tools(mcp, reg)

        result = json.loads(mcp.tools["complete_task"]("uuid"))
        assert result["code"] == "role_insufficient"

    def test_generator_can_call_generator(self) -> None:
        mcp = FakeMCP()
        reg = _make_reg(role=Role.GENERATOR, initialized=True)
        _register_generator_tools(mcp, reg)

        result = json.loads(mcp.tools["create_task"](description="x"))
        assert result.get("success") is True

    def test_generator_cannot_call_manager(self) -> None:
        mcp = FakeMCP()
        reg = _make_reg(role=Role.GENERATOR, initialized=True)
        _register_manager_tools(mcp, reg)

        result = json.loads(mcp.tools["complete_task"]("uuid"))
        assert result["code"] == "role_insufficient"


# ---------------------------------------------------------------------------
# Reload configuration
# ---------------------------------------------------------------------------


class TestReloadConfiguration:

    def test_reload_tool_calls_registry_reload(self, monkeypatch: pytest.MonkeyPatch) -> None:
        mcp = FakeMCP()
        reg = _make_reg(initialized=True)
        _register_reload_tool(mcp, reg)

        result = json.loads(mcp.tools["reload_configuration"]())
        assert result["success"] is True
        assert result["restart_required"] is False
        assert "config" in result["reloaded"]


# ---------------------------------------------------------------------------
# get_runtime_capabilities (ADR 21a)
# ---------------------------------------------------------------------------


class TestGetRuntimeCapabilities:

    def test_onboarding_mode(self) -> None:
        reg = _make_reg(initialized=False)
        caps = _build_capabilities(reg)

        assert caps["mode"] == "onboarding"
        assert caps["role"] is None
        assert caps["schema"] is None

        callable_names = {g["group"] for g in caps["callable_tool_groups"]}
        assert "onboarding" in callable_names
        assert "introspection" in callable_names

        uncallable_names = {g["group"] for g in caps["uncallable_tool_groups"]}
        assert "contributor" in uncallable_names
        assert "generator" in uncallable_names
        assert "manager" in uncallable_names
        for g in caps["uncallable_tool_groups"]:
            assert g["uncallable_reason"] == "schema_unset"

    def test_operational_contributor(self) -> None:
        reg = _make_reg(role=Role.CONTRIBUTOR, initialized=True)
        caps = _build_capabilities(reg)

        assert caps["mode"] == "operational"
        assert caps["role"] == Role.CONTRIBUTOR
        assert caps["schema"]["name"] == "minimal"

        callable_names = {g["group"] for g in caps["callable_tool_groups"]}
        assert "contributor" in callable_names
        assert "reconfigure" in callable_names

        uncallable_names = {g["group"] for g in caps["uncallable_tool_groups"]}
        assert "generator" in uncallable_names
        assert "manager" in uncallable_names

    def test_operational_manager(self) -> None:
        reg = _make_reg(role=Role.MANAGER, initialized=True)
        caps = _build_capabilities(reg)

        callable_names = {g["group"] for g in caps["callable_tool_groups"]}
        assert "contributor" in callable_names
        assert "generator" in callable_names
        assert "manager" in callable_names
        assert len(caps["uncallable_tool_groups"]) == 0

    def test_integrations_reflect_timew_state(self) -> None:
        reg_with = _make_reg(timew=True)
        assert _build_capabilities(reg_with)["integrations"]["timewarrior"] is True

        reg_without = _make_reg(timew=False)
        assert _build_capabilities(reg_without)["integrations"]["timewarrior"] is False


# ---------------------------------------------------------------------------
# Timewarrior-absent fallback
# ---------------------------------------------------------------------------


class TestTimewAbsentFallback:

    def test_timew_tools_return_cli_error_when_absent(self) -> None:
        """When timew is None, ToolRegistry.timew_summary/timew_status return
        cli_error.  The test uses a real ToolRegistry to exercise that path."""
        from taskchampion_mcp.tools import ToolRegistry

        cfg = ServerConfig(
            role=Role.CONTRIBUTOR,
            explicit_role_configured=True,
            explicit_schema_configured=True,
        )
        task_cli = MagicMock()
        schema = SimpleNamespace(
            name="minimal", version="1.0.0",
            field_context_for_llm=lambda: {},
            required_field_names=lambda: [],
            enum_fields=lambda: {},
            description="test",
        )
        real_reg = ToolRegistry(
            config=cfg,
            task_cli=task_cli,
            timew_cli=None,
            schema=schema,
            rate_limiter=RateLimiter(
                ops_per_minute=10_000,
                ops_per_hour=10_000,
                creates_per_hour=10_000,
            ),
            audit=MagicMock(),
        )
        mcp = FakeMCP()
        _register_contributor_tools(mcp, real_reg)

        for name in ("get_time_summary", "get_time_status"):
            result = json.loads(mcp.tools[name]())
            assert result.get("code") == "cli_error", (
                f"{name} should return cli_error when timew is absent"
            )
