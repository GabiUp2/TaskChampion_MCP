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

# ---------------------------------------------------------------------------
# Minimal tool surface expected regardless of role / schema / onboarding state
# ---------------------------------------------------------------------------

# Onboarding tools — always registered on a fresh / uninitialised install
EXPECTED_ONBOARDING_TOOLS = {
    "get_initialisation_status",
    "propose_initialisation_options",
    "list_preset_schemas",
    "use_preset_schema",
    "save_initial_schema",
    "generate_initial_schema_preview",
    "analyse_existing_tasks_for_schema",
    "analyse_taxonomy_file",
}

# Contributor tools — registered after onboarding (or always, per stable-surface ADR)
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
}

# Minimum set that must be present in every smoke-test run
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
        '#!/bin/sh\n'
        'case "$1" in\n'
        '  _version) echo "3.99.0" ;;\n'
        '  export)   echo "[]" ;;\n'
        '  *) echo "[]" ;;\n'
        'esac\n'
    )
    stub.chmod(0o755)
    return tmp_dir


def run_smoke_test(python_bin: str | None = None) -> int:
    """
    Run the MCP smoke test.  Returns 0 on success, 1 on failure.

    Args:
        python_bin: path to the Python interpreter to use.  Defaults to the
                    same interpreter running this script.
    """
    python = python_bin or sys.executable
    project_root = Path(__file__).parent.parent

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        # Stub out `task` so the server starts cleanly without a real Taskwarrior install
        stub_dir = _make_task_stub(tmp / "bin")
        taskdata_dir = tmp / "taskdata"
        taskdata_dir.mkdir()

        env = {
            **os.environ,
            "PATH": f"{stub_dir}:{os.environ.get('PATH', '/usr/bin')}",
            "TASKDATA": str(taskdata_dir),
        }

        print(f"[smoke] Starting server: {python} -m taskchampion_mcp.server")
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
            _send(proc, {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "smoke-test", "version": "0.0.1"},
                },
            })

            resp = _recv(proc)
            assert resp.get("id") == 1, f"Unexpected id in initialize response: {resp}"
            result = resp.get("result", {})
            server_info = result.get("serverInfo", {})
            print(f"[smoke] Server identified as: {server_info.get('name', '?')} "
                  f"v{server_info.get('version', '?')}")

            # Send initialized notification
            _send(proc, {"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}})

            # --------------------------------------------------------------
            # Step 2: list tools
            # --------------------------------------------------------------
            _send(proc, {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/list",
                "params": {},
            })

            resp = _recv(proc)
            assert resp.get("id") == 2, f"Unexpected id in tools/list response: {resp}"
            tools = {t["name"] for t in resp.get("result", {}).get("tools", [])}
            print(f"[smoke] Tools registered: {sorted(tools)}")

            # --------------------------------------------------------------
            # Step 3: assert minimum tool surface
            # --------------------------------------------------------------
            missing = MINIMUM_REQUIRED_TOOLS - tools
            if missing:
                print(f"[smoke] FAIL — missing expected tools: {sorted(missing)}", file=sys.stderr)
                return 1

            print(f"[smoke] OK — all {len(MINIMUM_REQUIRED_TOOLS)} required tools present "
                  f"({len(tools)} total)")
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
# pytest entry point
# ---------------------------------------------------------------------------

def test_mcp_smoke():
    """Pytest wrapper — asserts exit code 0."""
    rc = run_smoke_test()
    assert rc == 0, "MCP smoke test failed — see stdout for details"


# ---------------------------------------------------------------------------
# Direct execution
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    sys.exit(run_smoke_test())
