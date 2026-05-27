"""
MCP protocol smoke test for TaskChampion MCP server.

Starts the server as a subprocess, performs the MCP initialize handshake and
a tools/list call over stdio, and asserts the response contains the expected
tools.  Does not require a running Claude Desktop instance.

Usage (direct):
    python tests/smoke_test_mcp.py

Usage via dev.sh:
    ./dev.sh smoke-test

Usage in CI:
    python -m pytest tests/smoke_test_mcp.py -v
"""

import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Tool-surface expectations per scenario
# ---------------------------------------------------------------------------

# Onboarding tools — registered when config.toml is empty / missing
EXPECTED_ONBOARDING_TOOLS = {
    "get_initialization_status",
    "propose_initialization_options",
    "list_preset_schemas",
    "use_preset_schema",
    "save_initial_schema",
    "generate_initial_schema_preview",
    "analyze_existing_tasks_for_schema",
    "analyze_taxonomy_file",
}

# Contributor tools — registered after onboarding completes
EXPECTED_CONTRIBUTOR_TOOLS = {
    "list_tasks",
    "get_task",
    "search_tasks",
    "get_projects",
    "get_tags",
    "annotate_task",
    "modify_task",
    "start_task",
    "stop_task",
    "get_active_context",
    "get_schema_info",
    "get_task_report",
}

# Reconfigure tools — registered alongside CONTRIBUTOR tools (ADR 17 surface)
EXPECTED_RECONFIGURE_TOOLS = {
    "set_active_schema",
    "set_taxonomy_path",
    "set_role",
}

# Per-scenario required-tool sets and exclusions
SCENARIOS = {
    "onboarding": {
        "must_have": EXPECTED_ONBOARDING_TOOLS,
        "must_not_have": EXPECTED_CONTRIBUTOR_TOOLS | EXPECTED_RECONFIGURE_TOOLS,
    },
    "post_onboarding": {
        "must_have": EXPECTED_CONTRIBUTOR_TOOLS | EXPECTED_RECONFIGURE_TOOLS,
        "must_not_have": EXPECTED_ONBOARDING_TOOLS,
    },
}

# Back-compat alias kept while the test harness migrates to scenario names.
MINIMUM_REQUIRED_TOOLS = EXPECTED_ONBOARDING_TOOLS


def _send(proc: subprocess.Popen, msg: dict) -> None:
    """Write one JSON-RPC message to the server's stdin."""
    payload = json.dumps(msg) + "\n"
    proc.stdin.write(payload.encode())
    proc.stdin.flush()


def _recv(proc: subprocess.Popen, timeout: float = 5.0) -> dict:
    """Read one JSON-RPC line from the server's stdout."""
    deadline = time.monotonic() + timeout
    buf = b""
    while time.monotonic() < deadline:
        chunk = proc.stdout.read(1)
        if not chunk:
            time.sleep(0.01)
            continue
        buf += chunk
        if buf.endswith(b"\n"):
            return json.loads(buf.decode().strip())
    raise TimeoutError(f"No response within {timeout}s. Buffer: {buf!r}")


def _make_task_stub(tmp_dir: Path) -> Path:
    """
    Create a minimal fake `task` binary that satisfies the server's startup checks.

    The server calls `task _version` and `task export` — the stub returns a 3.x
    version string and an empty JSON array respectively.
    """
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


def _seed_post_onboarding_config(xdg_dir: Path) -> None:
    """Seed an XDG_CONFIG_HOME with a minimal post-onboarding config.toml so
    the server starts in CONTRIBUTOR mode (not onboarding mode).

    The two keys (``role`` + ``schema``) are both required for
    ``requires_onboarding`` to return False per the server-factory logic.
    """
    cfg_dir = xdg_dir / "taskchampion-mcp"
    cfg_dir.mkdir(parents=True, exist_ok=True)
    (cfg_dir / "config.toml").write_text(
        '[server]\nrole = "CONTRIBUTOR"\nschema = "minimal"\n',
        encoding="utf-8",
    )


def run_smoke_test(
    python_bin: str | None = None,
    scenario: str = "onboarding",
) -> int:
    """
    Run the MCP smoke test for one scenario.  Returns 0 on success, 1 on failure.

    Scenarios:
        - ``onboarding`` (default): empty XDG, expects the 8 onboarding tools.
        - ``post_onboarding``: XDG seeded with role + schema, expects the
          CONTRIBUTOR + reconfigure surface and the absence of onboarding tools.

    Args:
        python_bin: path to the Python interpreter to use.  Defaults to the
                    same interpreter running this script.
        scenario:   which configuration to set up.  Must be a key in SCENARIOS.
    """
    if scenario not in SCENARIOS:
        print(f"[smoke] FAIL — unknown scenario {scenario!r}", file=sys.stderr)
        return 1

    python = python_bin or sys.executable
    project_root = Path(__file__).parent.parent

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        # Stub out `task` so the server starts cleanly without a real Taskwarrior install
        stub_dir = _make_task_stub(tmp / "bin")
        taskdata_dir = tmp / "taskdata"
        taskdata_dir.mkdir()

        # Isolate XDG_CONFIG_HOME so the smoke test does NOT inherit the local
        # user's ~/.config/taskchampion-mcp/config.toml. Without this isolation
        # the test result depends on whether the developer has completed
        # onboarding on their machine — onboarding-complete configs cause the
        # server to start in CONTRIBUTOR mode and the test's onboarding-mode
        # expectation to fail spuriously. CI environments don't have a user
        # config so they pass; local devs hit phantom failures.
        xdg_isolated = tmp / "xdg"
        xdg_isolated.mkdir()
        if scenario == "post_onboarding":
            _seed_post_onboarding_config(xdg_isolated)

        env = {
            **os.environ,
            "PATH": f"{stub_dir}:{os.environ.get('PATH', '/usr/bin')}",
            "TASKDATA": str(taskdata_dir),
            "XDG_CONFIG_HOME": str(xdg_isolated),
        }

        print(f"[smoke] Starting server [scenario={scenario}]: {python} -m taskchampion_mcp.server")
        proc = subprocess.Popen(
            [python, "-m", "taskchampion_mcp.server"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=project_root,
            env=env,
        )

        try:
            # --------------------------------------------------------------
            # Step 1: initialize handshake
            # --------------------------------------------------------------
            _send(
                proc,
                {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "initialize",
                    "params": {
                        "protocolVersion": "2024-11-05",
                        "capabilities": {},
                        "clientInfo": {"name": "smoke-test", "version": "0.0.1"},
                    },
                },
            )

            resp = _recv(proc)
            assert resp.get("id") == 1, f"Unexpected id in initialize response: {resp}"
            result = resp.get("result", {})
            server_info = result.get("serverInfo", {})
            print(
                f"[smoke] Server identified as: {server_info.get('name', '?')} "
                f"v{server_info.get('version', '?')}"
            )

            # Send initialized notification
            _send(proc, {"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}})

            # --------------------------------------------------------------
            # Step 2: list tools
            # --------------------------------------------------------------
            _send(
                proc,
                {
                    "jsonrpc": "2.0",
                    "id": 2,
                    "method": "tools/list",
                    "params": {},
                },
            )

            resp = _recv(proc)
            assert resp.get("id") == 2, f"Unexpected id in tools/list response: {resp}"
            tools = {t["name"] for t in resp.get("result", {}).get("tools", [])}
            print(f"[smoke] Tools registered: {sorted(tools)}")

            # --------------------------------------------------------------
            # Step 3: assert per-scenario tool surface
            # --------------------------------------------------------------
            expectations = SCENARIOS[scenario]
            must_have = expectations["must_have"]
            must_not_have = expectations["must_not_have"]

            missing = must_have - tools
            unexpected = must_not_have & tools

            if missing:
                print(
                    f"[smoke] FAIL [{scenario}] — missing expected tools: {sorted(missing)}",
                    file=sys.stderr,
                )
                return 1
            if unexpected:
                print(
                    f"[smoke] FAIL [{scenario}] — tools registered that should NOT be: "
                    f"{sorted(unexpected)}",
                    file=sys.stderr,
                )
                return 1

            print(
                f"[smoke] OK [{scenario}] — all {len(must_have)} expected tools present, "
                f"{len(must_not_have)} forbidden tools absent ({len(tools)} total registered)"
            )
            return 0

        except TimeoutError as exc:
            stderr_output = proc.stderr.read().decode(errors="replace") if proc.stderr else ""
            print(f"[smoke] FAIL — {exc}", file=sys.stderr)
            if stderr_output:
                print(f"[smoke] Server stderr:\n{stderr_output}", file=sys.stderr)
            return 1

        except AssertionError as exc:
            print(f"[smoke] FAIL — assertion error: {exc}", file=sys.stderr)
            return 1

        except Exception as exc:
            print(f"[smoke] FAIL — unexpected error: {exc}", file=sys.stderr)
            return 1

        finally:
            proc.terminate()
            try:
                proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                proc.kill()


# ---------------------------------------------------------------------------
# pytest entry points — one parametrised test per scenario so failures
# point at the specific tool surface that broke.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("scenario", sorted(SCENARIOS.keys()))
def test_mcp_smoke(scenario: str) -> None:
    """Pytest wrapper — asserts exit code 0 for each scenario."""
    rc = run_smoke_test(scenario=scenario)
    assert rc == 0, f"MCP smoke test failed for scenario={scenario!r} — see stdout"


# ---------------------------------------------------------------------------
# Direct execution — run both scenarios; exit non-zero if either fails
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    exit_code = 0
    for _scenario in sorted(SCENARIOS.keys()):
        rc = run_smoke_test(scenario=_scenario)
        if rc != 0:
            exit_code = rc
    sys.exit(exit_code)
