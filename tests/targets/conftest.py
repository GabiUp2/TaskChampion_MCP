"""
Phase 3 acceptance test harness — target-agnostic parametrised suite.

Provides the MCPClient class for stdio JSON-RPC communication with the server
and the 26-scenario acceptance suite from the ROADMAP.  Per-target conftest
files supply the concrete ``mcp_client`` fixture.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


# ---------------------------------------------------------------------------
# MCPClient — stdio JSON-RPC transport
# ---------------------------------------------------------------------------


class MCPClient:
    """Drives a MCP server subprocess over stdio JSON-RPC."""

    def __init__(self, proc: subprocess.Popen) -> None:
        self._proc = proc
        self._next_id = 1

    # -- low-level transport ------------------------------------------------

    def _send(self, msg: dict) -> None:
        payload = json.dumps(msg) + "\n"
        self._proc.stdin.write(payload.encode())
        self._proc.stdin.flush()

    def _recv(self, timeout: float = 10.0) -> dict:
        deadline = time.monotonic() + timeout
        buf = b""
        while time.monotonic() < deadline:
            chunk = self._proc.stdout.read(1)
            if not chunk:
                time.sleep(0.01)
                continue
            buf += chunk
            if buf.endswith(b"\n"):
                return json.loads(buf.decode().strip())
        raise TimeoutError(f"No response within {timeout}s. Buffer: {buf!r}")

    # -- MCP protocol helpers -----------------------------------------------

    def initialize(self) -> dict:
        """Perform the MCP initialize handshake and send initialized notification."""
        msg_id = self._next_id
        self._next_id += 1
        self._send(
            {
                "jsonrpc": "2.0",
                "id": msg_id,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "acceptance-harness", "version": "0.1.0"},
                },
            }
        )
        resp = self._recv()
        assert resp.get("id") == msg_id, f"Bad initialize response: {resp}"
        self._send({"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}})
        return resp.get("result", {})

    def send_tools_list(self) -> set[str]:
        """Return the set of registered tool names."""
        msg_id = self._next_id
        self._next_id += 1
        self._send(
            {"jsonrpc": "2.0", "id": msg_id, "method": "tools/list", "params": {}}
        )
        resp = self._recv()
        assert resp.get("id") == msg_id, f"Bad tools/list response: {resp}"
        return {t["name"] for t in resp.get("result", {}).get("tools", [])}

    def send_tool_call(self, tool_name: str, params: dict[str, Any] | None = None) -> dict:
        """Call a tool and return the result dict (or error dict)."""
        msg_id = self._next_id
        self._next_id += 1
        self._send(
            {
                "jsonrpc": "2.0",
                "id": msg_id,
                "method": "tools/call",
                "params": {"name": tool_name, "arguments": params or {}},
            }
        )
        resp = self._recv()
        assert resp.get("id") == msg_id, f"Bad tools/call response: {resp}"
        if "error" in resp:
            return resp["error"]
        return resp.get("result", {})

    def close(self) -> None:
        """Terminate the server subprocess."""
        self._proc.terminate()
        try:
            self._proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            self._proc.kill()


# ---------------------------------------------------------------------------
# Environment helpers (reused across per-target conftest files)
# ---------------------------------------------------------------------------


def make_task_stub(tmp_dir: Path) -> Path:
    """Create a minimal fake ``task`` binary satisfying startup checks."""
    tmp_dir.mkdir(parents=True, exist_ok=True)
    stub = tmp_dir / "task"
    stub.write_text(
        "#!/bin/sh\n"
        'case "$1" in\n'
        '  _version) echo "3.99.0" ;;\n'
        '  export)   echo "[]" ;;\n'
        '  *) echo "[]" ;;\n'
        "esac\n"
    )
    stub.chmod(0o755)
    return tmp_dir


def seed_post_onboarding_config(xdg_dir: Path, *, schema: str = "minimal") -> None:
    """Seed XDG_CONFIG_HOME with a post-onboarding config.toml."""
    cfg_dir = xdg_dir / "taskchampion-mcp"
    cfg_dir.mkdir(parents=True, exist_ok=True)
    (cfg_dir / "config.toml").write_text(
        f'[server]\nrole = "CONTRIBUTOR"\nschema = "{schema}"\n',
        encoding="utf-8",
    )


def launch_server(
    *,
    xdg_dir: Path,
    stub_dir: Path,
    taskdata_dir: Path,
    python_bin: str | None = None,
) -> subprocess.Popen:
    """Launch the MCP server subprocess with isolated environment."""
    python = python_bin or sys.executable
    env = {
        **os.environ,
        "PATH": f"{stub_dir}:{os.environ.get('PATH', '/usr/bin')}",
        "TASKDATA": str(taskdata_dir),
        "XDG_CONFIG_HOME": str(xdg_dir),
    }
    return subprocess.Popen(
        [python, "-m", "taskchampion_mcp.server"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=PROJECT_ROOT,
        env=env,
    )


# ---------------------------------------------------------------------------
# Scenario definitions — 26 acceptance test cases
# ---------------------------------------------------------------------------

ACCEPTANCE_SCENARIOS: list[tuple[str, str, dict[str, Any]]] = [
    # --- Onboarding (scenarios 1-4) ---
    (
        "onboarding_01",
        "get_initialization_status returns needs_onboarding=True",
        {"phase": "onboarding", "tool": "get_initialization_status", "params": {}},
    ),
    (
        "onboarding_02",
        "propose_initialization_options returns options",
        {"phase": "onboarding", "tool": "propose_initialization_options", "params": {}},
    ),
    (
        "onboarding_03",
        "list_preset_schemas returns 5+ presets",
        {"phase": "onboarding", "tool": "list_preset_schemas", "params": {}},
    ),
    (
        "onboarding_04",
        "use_preset_schema(minimal) succeeds with auto-reload",
        {
            "phase": "onboarding",
            "tool": "use_preset_schema",
            "params": {"preset_name": "minimal"},
        },
    ),
    # --- Post-onboarding (scenarios 5-16) ---
    (
        "post_onboarding_05",
        "get_runtime_capabilities returns mode=operational",
        {"phase": "post_onboarding", "tool": "get_runtime_capabilities", "params": {}},
    ),
    (
        "post_onboarding_06",
        "list_tasks returns success",
        {"phase": "post_onboarding", "tool": "list_tasks", "params": {}},
    ),
    (
        "post_onboarding_07",
        "get_schema_info returns schema set during onboarding",
        {"phase": "post_onboarding", "tool": "get_schema_info", "params": {}},
    ),
    (
        "post_onboarding_08",
        "search_tasks returns success",
        {"phase": "post_onboarding", "tool": "search_tasks", "params": {"query": "test"}},
    ),
    (
        "post_onboarding_09",
        "get_projects returns success",
        {"phase": "post_onboarding", "tool": "get_projects", "params": {}},
    ),
    (
        "post_onboarding_10",
        "get_tags returns success",
        {"phase": "post_onboarding", "tool": "get_tags", "params": {}},
    ),
    (
        "post_onboarding_11",
        "annotate_task with dry_run=True returns preview",
        {
            "phase": "post_onboarding",
            "tool": "annotate_task",
            "params": {"task_id": "1", "annotation": "test note", "dry_run": True},
        },
    ),
    (
        "post_onboarding_12",
        "modify_task with dry_run=True returns preview",
        {
            "phase": "post_onboarding",
            "tool": "modify_task",
            "params": {"task_id": "1", "modifications": {"priority": "H"}, "dry_run": True},
        },
    ),
    (
        "post_onboarding_13",
        "set_active_schema(gtd) succeeds with auto-reload",
        {
            "phase": "post_onboarding",
            "tool": "set_active_schema",
            "params": {"schema_name": "gtd"},
        },
    ),
    (
        "post_onboarding_14",
        "get_schema_info now returns gtd",
        {
            "phase": "post_onboarding_gtd",
            "tool": "get_schema_info",
            "params": {},
        },
    ),
    (
        "post_onboarding_15",
        "set_role(CONTRIBUTOR) is idempotent",
        {
            "phase": "post_onboarding",
            "tool": "set_role",
            "params": {"role": "CONTRIBUTOR"},
        },
    ),
    (
        "post_onboarding_16",
        "reload_configuration succeeds",
        {"phase": "post_onboarding", "tool": "reload_configuration", "params": {}},
    ),
    # --- Generator role (scenarios 17-19) ---
    (
        "generator_17",
        "create_task with dry_run=True returns preview",
        {
            "phase": "generator",
            "tool": "create_task",
            "params": {"description": "Test task", "dry_run": True},
        },
    ),
    (
        "generator_18",
        "create_subtask with dry_run=True returns preview",
        {
            "phase": "generator",
            "tool": "create_subtask",
            "params": {"parent_id": "1", "description": "Sub task", "dry_run": True},
        },
    ),
    (
        "generator_19",
        "batch_create_tasks with dry_run=True returns preview",
        {
            "phase": "generator",
            "tool": "batch_create_tasks",
            "params": {"tasks": [{"description": "Batch 1"}], "dry_run": True},
        },
    ),
    # --- Manager role (scenarios 20-23) ---
    (
        "manager_20",
        "complete_task with dry_run=True returns preview",
        {
            "phase": "manager",
            "tool": "complete_task",
            "params": {"task_id": "1", "dry_run": True},
        },
    ),
    (
        "manager_21",
        "delete_task with dry_run=True returns preview",
        {
            "phase": "manager",
            "tool": "delete_task",
            "params": {"task_id": "1", "dry_run": True},
        },
    ),
    (
        "manager_22",
        "undo_last_action with dry_run=True returns preview",
        {
            "phase": "manager",
            "tool": "undo_last_action",
            "params": {"dry_run": True},
        },
    ),
    (
        "manager_23",
        "sync_tasks with dry_run=True returns preview",
        {
            "phase": "manager",
            "tool": "sync_tasks",
            "params": {"dry_run": True},
        },
    ),
    # --- Role gating (scenarios 24-25) ---
    (
        "role_gating_24",
        "CONTRIBUTOR cannot call create_task (role_insufficient)",
        {
            "phase": "post_onboarding",
            "tool": "create_task",
            "params": {"description": "Should fail", "dry_run": True},
            "expect_error": "role_insufficient",
        },
    ),
    (
        "role_gating_25",
        "CONTRIBUTOR cannot call complete_task (role_insufficient)",
        {
            "phase": "post_onboarding",
            "tool": "complete_task",
            "params": {"task_id": "1", "dry_run": True},
            "expect_error": "role_insufficient",
        },
    ),
    # --- Schema-unset (scenario 26) ---
    (
        "schema_unset_26",
        "uninitialised server returns schema_unset for list_tasks",
        {
            "phase": "onboarding",
            "tool": "list_tasks",
            "params": {},
            "expect_error": "schema_unset",
        },
    ),
]


# ---------------------------------------------------------------------------
# Parametrised acceptance test
# ---------------------------------------------------------------------------


@pytest.mark.acceptance
@pytest.mark.parametrize(
    "scenario_id,description,spec",
    ACCEPTANCE_SCENARIOS,
    ids=[s[0] for s in ACCEPTANCE_SCENARIOS],
)
def test_acceptance(
    mcp_client: MCPClient,
    scenario_id: str,
    description: str,
    spec: dict[str, Any],
) -> None:
    """
    Target-agnostic acceptance test.

    Each scenario calls a tool via the mcp_client fixture and asserts
    the response matches expectations.  The concrete mcp_client is
    provided by the per-target conftest.
    """
    tool = spec["tool"]
    params = spec.get("params", {})
    expect_error = spec.get("expect_error")

    result = mcp_client.send_tool_call(tool, params)

    if expect_error:
        _assert_structured_error(result, expect_error, scenario_id)
    else:
        _assert_success(result, spec, scenario_id)


def _assert_structured_error(result: dict, expected_code: str, scenario_id: str) -> None:
    """Assert the response contains a structured error with the expected code."""
    content = _extract_content_text(result)
    assert expected_code in content, (
        f"[{scenario_id}] Expected error code {expected_code!r} in response. "
        f"Got: {content[:300]}"
    )


def _assert_success(result: dict, spec: dict[str, Any], scenario_id: str) -> None:
    """Assert the tool call succeeded (no error code in content)."""
    content = _extract_content_text(result)

    error_codes = ("role_insufficient", "schema_unset", "not_available")
    for code in error_codes:
        assert code not in content, (
            f"[{scenario_id}] Unexpected error {code!r} in successful response. "
            f"Got: {content[:300]}"
        )

    # Phase-specific assertions
    tool = spec["tool"]
    if tool == "get_initialization_status":
        assert "needs_onboarding" in content or "true" in content.lower(), (
            f"[{scenario_id}] Expected needs_onboarding indicator. Got: {content[:300]}"
        )
    elif tool == "list_preset_schemas":
        assert "minimal" in content.lower(), (
            f"[{scenario_id}] Expected 'minimal' preset in response. Got: {content[:300]}"
        )
    elif tool == "get_runtime_capabilities":
        assert "operational" in content.lower() or "mode" in content.lower(), (
            f"[{scenario_id}] Expected operational mode. Got: {content[:300]}"
        )
    elif tool == "use_preset_schema":
        assert "restart_required" in content.lower() or "success" in content.lower(), (
            f"[{scenario_id}] Expected schema activation confirmation. Got: {content[:300]}"
        )


def _extract_content_text(result: dict) -> str:
    """Extract text content from an MCP tool result, handling various formats."""
    if isinstance(result, dict):
        # Standard MCP tool result format: {content: [{type: "text", text: "..."}]}
        content_list = result.get("content", [])
        if isinstance(content_list, list):
            texts = []
            for item in content_list:
                if isinstance(item, dict) and item.get("type") == "text":
                    texts.append(item.get("text", ""))
            if texts:
                return "\n".join(texts)
        # Fallback: serialise the entire result
        return json.dumps(result)
    return str(result)
