"""
Unit tests for the dev.sh installation helpers.

These tests exercise the Python-side logic embedded in dev.sh:
- _upsert_mcp_entry  (JSON config write)
- _remove_mcp_entry  (JSON config remove)
- _claude_desktop_config_path resolution per platform (via subprocess mocking)

The bash helpers themselves are tested via subprocess calls to dev.sh with a
controlled environment.  No actual Claude Desktop installation is required.
"""

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
DEV_SH = PROJECT_ROOT / "dev.sh"


# ---------------------------------------------------------------------------
# Helpers — replicate the Python snippets embedded in dev.sh
# ---------------------------------------------------------------------------

def upsert_mcp_entry(cfg_path: Path, cmd: str, args: list[str]) -> dict:
    """Python equivalent of _upsert_mcp_entry in dev.sh."""
    cfg_path.parent.mkdir(parents=True, exist_ok=True)
    data = json.loads(cfg_path.read_text()) if cfg_path.exists() else {}
    data.setdefault("mcpServers", {})
    data["mcpServers"]["taskchampion"] = {"command": cmd, "args": args}
    cfg_path.write_text(json.dumps(data, indent=2) + "\n")
    return data


def remove_mcp_entry(cfg_path: Path) -> dict:
    """Python equivalent of _remove_mcp_entry in dev.sh."""
    if not cfg_path.exists():
        return {}
    data = json.loads(cfg_path.read_text())
    data.get("mcpServers", {}).pop("taskchampion", None)
    cfg_path.write_text(json.dumps(data, indent=2) + "\n")
    return data


# ---------------------------------------------------------------------------
# _upsert_mcp_entry tests
# ---------------------------------------------------------------------------

class TestUpsertMcpEntry:

    def test_creates_file_if_missing(self, tmp_path):
        cfg = tmp_path / "claude_desktop_config.json"
        result = upsert_mcp_entry(cfg, "wsl.exe", ["-e", "/venv/bin/python", "-m", "taskchampion_mcp.server"])
        assert cfg.exists()
        assert result["mcpServers"]["taskchampion"]["command"] == "wsl.exe"

    def test_creates_parent_dirs(self, tmp_path):
        cfg = tmp_path / "deep" / "nested" / "config.json"
        upsert_mcp_entry(cfg, "python", ["-m", "taskchampion_mcp.server"])
        assert cfg.exists()

    def test_preserves_existing_keys(self, tmp_path):
        cfg = tmp_path / "config.json"
        cfg.write_text(json.dumps({"preferences": {"theme": "dark"}, "mcpServers": {"other": {"command": "npx"}}}))
        result = upsert_mcp_entry(cfg, "wsl.exe", ["-e", "/venv/bin/python", "-m", "x"])
        assert result["preferences"]["theme"] == "dark"
        assert "other" in result["mcpServers"]
        assert "taskchampion" in result["mcpServers"]

    def test_overwrites_existing_taskchampion_entry(self, tmp_path):
        cfg = tmp_path / "config.json"
        upsert_mcp_entry(cfg, "old_command", ["old_arg"])
        result = upsert_mcp_entry(cfg, "new_command", ["new_arg"])
        entry = result["mcpServers"]["taskchampion"]
        assert entry["command"] == "new_command"
        assert entry["args"] == ["new_arg"]

    def test_output_is_valid_json(self, tmp_path):
        cfg = tmp_path / "config.json"
        upsert_mcp_entry(cfg, "wsl.exe", ["-e", "/path/bin/python", "-m", "taskchampion_mcp.server"])
        parsed = json.loads(cfg.read_text())
        assert isinstance(parsed, dict)

    def test_windows_path_with_backslashes(self, tmp_path):
        """Windows-style paths must survive JSON serialisation round-trip."""
        cfg = tmp_path / "config.json"
        win_path = r"C:\Users\user\.venv\Scripts\python.exe"
        upsert_mcp_entry(cfg, win_path, ["-m", "taskchampion_mcp.server"])
        parsed = json.loads(cfg.read_text())
        assert parsed["mcpServers"]["taskchampion"]["command"] == win_path

    def test_args_are_list_not_string(self, tmp_path):
        cfg = tmp_path / "config.json"
        args = ["-e", "/venv/bin/python", "-m", "taskchampion_mcp.server"]
        upsert_mcp_entry(cfg, "wsl.exe", args)
        parsed = json.loads(cfg.read_text())
        assert isinstance(parsed["mcpServers"]["taskchampion"]["args"], list)
        assert parsed["mcpServers"]["taskchampion"]["args"] == args


# ---------------------------------------------------------------------------
# _remove_mcp_entry tests
# ---------------------------------------------------------------------------

class TestRemoveMcpEntry:

    def test_removes_taskchampion_key(self, tmp_path):
        cfg = tmp_path / "config.json"
        upsert_mcp_entry(cfg, "wsl.exe", ["-e", "/venv/bin/python"])
        result = remove_mcp_entry(cfg)
        assert "taskchampion" not in result.get("mcpServers", {})

    def test_preserves_other_servers(self, tmp_path):
        cfg = tmp_path / "config.json"
        cfg.write_text(json.dumps({
            "mcpServers": {
                "taskchampion": {"command": "wsl.exe", "args": []},
                "other-server": {"command": "npx", "args": ["@other/server"]},
            }
        }))
        result = remove_mcp_entry(cfg)
        assert "taskchampion" not in result["mcpServers"]
        assert "other-server" in result["mcpServers"]

    def test_preserves_non_mcp_keys(self, tmp_path):
        cfg = tmp_path / "config.json"
        cfg.write_text(json.dumps({
            "preferences": {"theme": "dark"},
            "mcpServers": {"taskchampion": {"command": "wsl.exe", "args": []}},
        }))
        result = remove_mcp_entry(cfg)
        assert result["preferences"]["theme"] == "dark"

    def test_idempotent_on_missing_file(self, tmp_path):
        cfg = tmp_path / "nonexistent.json"
        result = remove_mcp_entry(cfg)
        assert result == {}

    def test_idempotent_when_key_already_absent(self, tmp_path):
        cfg = tmp_path / "config.json"
        cfg.write_text(json.dumps({"mcpServers": {}}))
        result = remove_mcp_entry(cfg)
        assert result["mcpServers"] == {}

    def test_output_remains_valid_json(self, tmp_path):
        cfg = tmp_path / "config.json"
        upsert_mcp_entry(cfg, "wsl.exe", ["-e", "/venv/bin/python"])
        remove_mcp_entry(cfg)
        parsed = json.loads(cfg.read_text())
        assert isinstance(parsed, dict)


# ---------------------------------------------------------------------------
# Platform-path tests — exercise the bash helper via subprocess
# ---------------------------------------------------------------------------

def _run_bash_helper(script: str, env: dict | None = None) -> str:
    """Run a bash snippet that sources dev.sh helpers and returns stdout."""
    full_env = {**os.environ, **(env or {})}
    # Inject a minimal uname stub if needed
    wrapper = f"""
set -euo pipefail
PROJECT_DIR="{PROJECT_ROOT}"
VENV_DIR="{PROJECT_ROOT}/.venv"
source "{DEV_SH}" 2>/dev/null || true
{script}
"""
    result = subprocess.run(
        ["bash", "-c", wrapper],
        capture_output=True,
        text=True,
        env=full_env,
        timeout=10,
    )
    return result.stdout.strip()


@pytest.mark.skipif(sys.platform == "win32", reason="bash not available on native Windows")
class TestClaudeDesktopConfigPath:
    """
    Test _claude_desktop_config_path() output by mocking the platform detection.
    We override uname by prepending a fake uname binary to PATH.
    """

    def _make_uname_stub(self, tmp_path: Path, os_name: str) -> Path:
        stub = tmp_path / "uname"
        stub.write_text(f'#!/bin/sh\necho "{os_name}"\n')
        stub.chmod(0o755)
        return tmp_path

    def test_linux_returns_xdg_path(self, tmp_path):
        stub_dir = self._make_uname_stub(tmp_path, "Linux")
        # Simulate a plain Linux environment (no /proc/version microsoft marker)
        script = """
# Override /proc/version check
_detect_platform() { echo "linux"; }
_claude_desktop_config_path
"""
        path = _run_bash_helper(script)
        # Claude Desktop on Linux uses the capitalised /Claude/ directory,
        # matching macOS/WSL/Windows. A lowercase /claude/ creates a sibling
        # directory that Claude Desktop never reads — silent install failure.
        # Assert the *exact* casing so a lowercase regression fails CI.
        assert "/Claude/claude_desktop_config.json" in path, (
            f"Expected capitalised /Claude/ in path, got: {path!r}"
        )
        assert "/claude/claude_desktop_config.json" not in path, (
            f"Lowercase /claude/ directory is wrong on Linux — Claude Desktop "
            f"reads from ~/.config/Claude/ (capital C). Got: {path!r}"
        )

    def test_macos_returns_library_path(self, tmp_path):
        script = """
_detect_platform() { echo "macos"; }
_claude_desktop_config_path
"""
        path = _run_bash_helper(script)
        assert "Library/Application Support/Claude" in path
        assert "claude_desktop_config.json" in path

    def test_windows_shell_uses_appdata(self, tmp_path):
        script = """
_detect_platform() { echo "windows_shell"; }
_claude_desktop_config_path
"""
        fake_appdata = str(tmp_path / "AppData" / "Roaming")
        path = _run_bash_helper(script, env={"APPDATA": fake_appdata})
        assert fake_appdata in path
        assert "Claude" in path
        assert "claude_desktop_config.json" in path

    def test_config_path_ends_with_correct_filename(self, tmp_path):
        for platform in ("linux", "macos", "windows_shell"):
            script = f"""
_detect_platform() {{ echo "{platform}"; }}
_claude_desktop_config_path
"""
            path = _run_bash_helper(
                script,
                env={"APPDATA": str(tmp_path)} if platform == "windows_shell" else {},
            )
            assert path.endswith("claude_desktop_config.json"), \
                f"Platform {platform}: unexpected path suffix: {path}"
