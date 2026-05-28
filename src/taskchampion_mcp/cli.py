"""CLI wrapper for Taskwarrior (task) and Timewarrior (timew) subprocess calls.

All interaction with Taskwarrior/Timewarrior goes through this module.
No other module should call subprocess directly.  See ADR 4.
"""

from __future__ import annotations

import json
import logging
import subprocess
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger("taskchampion_mcp.cli")


# ---------------------------------------------------------------------------
# Result type
# ---------------------------------------------------------------------------


@dataclass
class CLIResult:
    returncode: int
    stdout: str
    stderr: str

    @property
    def ok(self) -> bool:
        return self.returncode == 0

    def json(self) -> Any:
        """Parse stdout as JSON."""
        return json.loads(self.stdout) if self.stdout.strip() else []


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class CLIError(Exception):
    """Raised when a CLI command fails."""

    def __init__(self, command: list[str], result: CLIResult) -> None:
        self.command = command
        self.result = result
        super().__init__(
            f"Command failed (rc={result.returncode}): {' '.join(command)}\n"
            f"stderr: {result.stderr[:500]}"
        )


class ToolNotFoundError(Exception):
    """Raised when a required CLI tool is not found on PATH."""


# ---------------------------------------------------------------------------
# Core runner
# ---------------------------------------------------------------------------


def _run(args: list[str], timeout: int = 30) -> CLIResult:
    """Run a command as a subprocess with argument list (never shell=True).

    This is the ONLY place subprocess is invoked in the entire codebase.
    """
    logger.debug("CLI exec: %s", args)
    try:
        proc = subprocess.run(
            args,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=None,  # inherit parent env
        )
    except FileNotFoundError as exc:
        raise ToolNotFoundError(f"Command not found: {args[0]}") from exc
    except subprocess.TimeoutExpired as exc:
        raise CLIError(args, CLIResult(returncode=-1, stdout="", stderr="Timeout")) from exc

    return CLIResult(
        returncode=proc.returncode,
        stdout=proc.stdout,
        stderr=proc.stderr,
    )


# ---------------------------------------------------------------------------
# Taskwarrior commands
# ---------------------------------------------------------------------------


class TaskwarriorCLI:
    """Wrapper for the ``task`` command-line interface."""

    def __init__(self, binary: str = "task", override_rc: str | None = None) -> None:
        self._binary = binary
        self._rc_args: list[str] = []
        if override_rc:
            self._rc_args = [f"rc:{override_rc}"]
        self._rc_args.append("rc.confirmation:off")
        self._rc_args.append("rc.bulk:0")
        self._rc_args.append("rc.verbose:nothing")

    def _cmd(self, *args: str) -> list[str]:
        return [self._binary] + self._rc_args + list(args)

    def version(self) -> str | None:
        """Return Taskwarrior version string or None if not installed."""
        try:
            result = _run([self._binary, "_version"])
            return result.stdout.strip() if result.ok else None
        except ToolNotFoundError:
            return None

    def export_tasks(self, *filters: str) -> list[dict[str, Any]]:
        """Export tasks as JSON, optionally with filters."""
        result = _run(self._cmd(*filters, "export"))
        if not result.ok:
            raise CLIError(self._cmd(*filters, "export"), result)
        return result.json()

    def get_task(self, uuid: str) -> dict[str, Any] | None:
        """Get a single task by UUID."""
        tasks = self.export_tasks(uuid)
        return tasks[0] if tasks else None

    def add_task(self, description: str, **fields: str) -> CLIResult:
        """Create a new task."""
        args = ["add", description]
        for key, value in fields.items():
            if key == "tags":
                for tag in value if isinstance(value, list) else [value]:
                    args.append(f"+{tag}")
            else:
                args.append(f"{key}:{value}")
        return _run(self._cmd(*args))

    def modify_task(self, uuid: str, **fields: str) -> CLIResult:
        """Modify fields on an existing task."""
        args = [uuid, "modify"]
        for key, value in fields.items():
            if key == "tags_add":
                for tag in value if isinstance(value, list) else [value]:
                    args.append(f"+{tag}")
            elif key == "tags_remove":
                for tag in value if isinstance(value, list) else [value]:
                    args.append(f"-{tag}")
            else:
                args.append(f"{key}:{value}")
        return _run(self._cmd(*args))

    def annotate_task(self, uuid: str, annotation: str) -> CLIResult:
        """Add an annotation to a task."""
        return _run(self._cmd(uuid, "annotate", annotation))

    def denotate_task(self, uuid: str, annotation: str) -> CLIResult:
        """Remove an annotation from a task."""
        return _run(self._cmd(uuid, "denotate", annotation))

    def start_task(self, uuid: str) -> CLIResult:
        """Start working on a task."""
        return _run(self._cmd(uuid, "start"))

    def stop_task(self, uuid: str) -> CLIResult:
        """Stop working on a task."""
        return _run(self._cmd(uuid, "stop"))

    def done_task(self, uuid: str) -> CLIResult:
        """Mark a task as done."""
        return _run(self._cmd(uuid, "done"))

    def delete_task(self, uuid: str) -> CLIResult:
        """Delete a task."""
        return _run(self._cmd(uuid, "delete"))

    def undo(self) -> CLIResult:
        """Undo the last Taskwarrior operation."""
        return _run(self._cmd("undo"))

    def sync(self) -> CLIResult:
        """Trigger task sync."""
        return _run(self._cmd("sync"), timeout=60)

    def count(self, *filters: str) -> int:
        """Count tasks matching a filter."""
        result = _run(self._cmd(*filters, "count"))
        if result.ok:
            try:
                return int(result.stdout.strip())
            except ValueError:
                return 0
        return 0

    def projects(self) -> list[str]:
        """List all project names."""
        result = _run(self._cmd("_projects"))
        if result.ok and result.stdout.strip():
            return [p.strip() for p in result.stdout.strip().split("\n") if p.strip()]
        return []

    def tags(self) -> list[str]:
        """List all tags."""
        result = _run(self._cmd("_tags"))
        if result.ok and result.stdout.strip():
            return [t.strip() for t in result.stdout.strip().split("\n") if t.strip()]
        return []

    def context(self) -> str:
        """Get the active Taskwarrior context name."""
        result = _run(self._cmd("_get", "rc.context"))
        return result.stdout.strip() if result.ok else ""

    def diagnostics(self) -> str:
        """Return Taskwarrior diagnostics output."""
        result = _run([self._binary, "diagnostics"])
        return result.stdout if result.ok else result.stderr

    def run_report(self, report_name: str, *filters: str) -> CLIResult:
        """Run a named Taskwarrior report and return raw CLI output."""
        return _run(self._cmd(*filters, report_name))


# ---------------------------------------------------------------------------
# Timewarrior commands
# ---------------------------------------------------------------------------


class TimewarriorCLI:
    """Wrapper for the ``timew`` command-line interface."""

    def __init__(self, binary: str = "timew") -> None:
        self._binary = binary

    def _cmd(self, *args: str) -> list[str]:
        return [self._binary] + list(args)

    def available(self) -> bool:
        """Check if Timewarrior is installed."""
        try:
            result = _run([self._binary, "--version"])
            return result.ok
        except ToolNotFoundError:
            return False

    def version(self) -> str | None:
        """Return Timewarrior version or None."""
        try:
            result = _run([self._binary, "--version"])
            return result.stdout.strip() if result.ok else None
        except ToolNotFoundError:
            return None

    def summary(self, *filters: str) -> str:
        """Get time summary."""
        result = _run(self._cmd("summary", *filters))
        return result.stdout if result.ok else result.stderr

    def export(self, *filters: str) -> list[dict[str, Any]]:
        """Export intervals as JSON."""
        result = _run(self._cmd("export", *filters))
        if result.ok and result.stdout.strip():
            return json.loads(result.stdout)
        return []

    def status(self) -> dict[str, Any]:
        """Check if currently tracking and return info."""
        result = _run(self._cmd())
        tracking = "Tracking" in result.stdout
        return {
            "tracking": tracking,
            "output": result.stdout.strip(),
        }

    def start(self, *tags: str) -> CLIResult:
        """Start tracking with optional tags."""
        return _run(self._cmd("start", *tags))

    def stop(self) -> CLIResult:
        """Stop current tracking."""
        return _run(self._cmd("stop"))
