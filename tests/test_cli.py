from __future__ import annotations

import subprocess
from unittest.mock import patch

import pytest

from taskchampion_mcp.cli import (
    CLIError,
    CLIResult,
    TaskwarriorCLI,
    TimewarriorCLI,
    ToolNotFoundError,
    _run,
)


def test_run_success(monkeypatch: pytest.MonkeyPatch) -> None:
    class _Proc:
        returncode = 0
        stdout = "ok"
        stderr = ""

    monkeypatch.setattr("taskchampion_mcp.cli.subprocess.run", lambda *a, **k: _Proc())
    result = _run(["echo", "x"])
    assert result.ok is True
    assert result.stdout == "ok"


def test_cliresult_json_parsing() -> None:
    assert CLIResult(returncode=0, stdout='[{"k":"v"}]', stderr="").json() == [{"k": "v"}]
    assert CLIResult(returncode=0, stdout="", stderr="").json() == []


def test_run_missing_binary_raises_tool_not_found(monkeypatch: pytest.MonkeyPatch) -> None:
    def _raise(*_a, **_k):
        raise FileNotFoundError("missing")

    monkeypatch.setattr("taskchampion_mcp.cli.subprocess.run", _raise)
    with pytest.raises(ToolNotFoundError):
        _run(["missing-binary"])


def test_run_timeout_raises_cli_error(monkeypatch: pytest.MonkeyPatch) -> None:
    def _raise(*_a, **_k):
        raise subprocess.TimeoutExpired(cmd="task", timeout=1)

    monkeypatch.setattr("taskchampion_mcp.cli.subprocess.run", _raise)
    with pytest.raises(CLIError):
        _run(["task"])


def test_taskwarrior_version_handles_missing_tool(monkeypatch: pytest.MonkeyPatch) -> None:
    cli = TaskwarriorCLI(binary="task")
    monkeypatch.setattr("taskchampion_mcp.cli._run", lambda *_a, **_k: (_ for _ in ()).throw(ToolNotFoundError("x")))
    assert cli.version() is None


def test_taskwarrior_export_failure_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    cli = TaskwarriorCLI(binary="task")
    monkeypatch.setattr(
        "taskchampion_mcp.cli._run",
        lambda *_a, **_k: CLIResult(returncode=1, stdout="", stderr="err"),
    )
    with pytest.raises(CLIError):
        cli.export_tasks("status:pending")


def test_taskwarrior_add_task_and_get_task(monkeypatch: pytest.MonkeyPatch) -> None:
    cli = TaskwarriorCLI(binary="task", override_rc="/tmp/taskrc")
    outputs = [
        CLIResult(returncode=0, stdout="", stderr=""),  # add_task
        CLIResult(returncode=0, stdout='[{"uuid":"u"}]', stderr=""),  # get_task/export
    ]
    monkeypatch.setattr("taskchampion_mcp.cli._run", lambda *_a, **_k: outputs.pop(0))

    add_result = cli.add_task("Ship coverage", project="work", tags=["python"])
    task = cli.get_task("u")
    assert add_result.ok is True
    assert task == {"uuid": "u"}


def test_taskwarrior_modify_and_annotate_commands(monkeypatch: pytest.MonkeyPatch) -> None:
    cli = TaskwarriorCLI(binary="task")
    calls: list[list[str]] = []

    def _fake_run(args, timeout=30):
        calls.append(args)
        return CLIResult(returncode=0, stdout="", stderr="")

    monkeypatch.setattr("taskchampion_mcp.cli._run", _fake_run)
    cli.modify_task("uuid", tags_add=["one"], tags_remove=["old"], priority="H")
    cli.annotate_task("uuid", "note")
    cli.denotate_task("uuid", "note")

    assert any("+one" in " ".join(call) for call in calls)
    assert any("-old" in " ".join(call) for call in calls)
    assert any("annotate" in " ".join(call) for call in calls)
    assert any("denotate" in " ".join(call) for call in calls)


def test_taskwarrior_lifecycle_commands(monkeypatch: pytest.MonkeyPatch) -> None:
    cli = TaskwarriorCLI(binary="task")
    monkeypatch.setattr(
        "taskchampion_mcp.cli._run",
        lambda *_a, **_k: CLIResult(returncode=0, stdout="ok", stderr=""),
    )
    assert cli.start_task("u").ok is True
    assert cli.stop_task("u").ok is True
    assert cli.done_task("u").ok is True
    assert cli.delete_task("u").ok is True
    assert cli.undo().ok is True
    assert cli.sync().ok is True


def test_taskwarrior_count_projects_tags_context_and_diagnostics(monkeypatch: pytest.MonkeyPatch) -> None:
    cli = TaskwarriorCLI(binary="task")
    outputs = [
        CLIResult(returncode=0, stdout="7\n", stderr=""),
        CLIResult(returncode=0, stdout="work\nhome\n", stderr=""),
        CLIResult(returncode=0, stdout="python\nmcp\n", stderr=""),
        CLIResult(returncode=0, stdout="ctx.work", stderr=""),
        CLIResult(returncode=0, stdout="diag", stderr=""),
    ]

    def _fake(*_a, **_k):
        return outputs.pop(0)

    monkeypatch.setattr("taskchampion_mcp.cli._run", _fake)
    assert cli.count("status:pending") == 7
    assert cli.projects() == ["work", "home"]
    assert cli.tags() == ["python", "mcp"]
    assert cli.context() == "ctx.work"
    assert cli.diagnostics() == "diag"


def test_taskwarrior_count_handles_bad_and_failed_values(monkeypatch: pytest.MonkeyPatch) -> None:
    cli = TaskwarriorCLI(binary="task")
    outputs = [
        CLIResult(returncode=0, stdout="not-a-number", stderr=""),
        CLIResult(returncode=1, stdout="", stderr="err"),
    ]
    monkeypatch.setattr("taskchampion_mcp.cli._run", lambda *_a, **_k: outputs.pop(0))
    assert cli.count("x") == 0
    assert cli.count("x") == 0


def test_taskwarrior_run_report(monkeypatch: pytest.MonkeyPatch) -> None:
    cli = TaskwarriorCLI(binary="task")
    monkeypatch.setattr(
        "taskchampion_mcp.cli._run",
        lambda *_a, **_k: CLIResult(returncode=0, stdout="report", stderr=""),
    )
    result = cli.run_report("next", "project:work")
    assert result.ok is True
    assert result.stdout == "report"


def test_timewarrior_methods(monkeypatch: pytest.MonkeyPatch) -> None:
    cli = TimewarriorCLI(binary="timew")
    outputs = [
        CLIResult(returncode=0, stdout="Timewarrior 1.5", stderr=""),  # available
        CLIResult(returncode=0, stdout="Timewarrior 1.5", stderr=""),  # version
        CLIResult(returncode=0, stdout="summary", stderr=""),  # summary
        CLIResult(returncode=0, stdout='[{"id":1}]', stderr=""),  # export
        CLIResult(returncode=0, stdout="Tracking foo", stderr=""),  # status
        CLIResult(returncode=0, stdout="start", stderr=""),  # start
        CLIResult(returncode=0, stdout="stop", stderr=""),  # stop
    ]
    monkeypatch.setattr("taskchampion_mcp.cli._run", lambda *_a, **_k: outputs.pop(0))

    assert cli.available() is True
    assert cli.version() == "Timewarrior 1.5"
    assert cli.summary(":day") == "summary"
    assert cli.export() == [{"id": 1}]
    assert cli.status()["tracking"] is True
    assert cli.start("tag").ok is True
    assert cli.stop().ok is True


def test_timewarrior_missing_binary_paths(monkeypatch: pytest.MonkeyPatch) -> None:
    cli = TimewarriorCLI(binary="timew")
    monkeypatch.setattr("taskchampion_mcp.cli._run", lambda *_a, **_k: (_ for _ in ()).throw(ToolNotFoundError("x")))
    assert cli.available() is False
    assert cli.version() is None
