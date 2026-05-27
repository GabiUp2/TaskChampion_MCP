from __future__ import annotations

import os
import shutil
import uuid
from pathlib import Path

import pytest

from taskchampion_mcp.cli import TaskwarriorCLI, TimewarriorCLI

pytestmark = pytest.mark.integration


def _task_available() -> bool:
    return shutil.which("task") is not None


def _version_matches_target(cli: TaskwarriorCLI) -> bool:
    target = os.environ.get("TASKWARRIOR_VERSION_TARGET", "").strip()
    if not target:
        return True
    actual = cli.version() or ""
    if target == "3.x-latest":
        return actual.startswith("3.")
    if target == "3.0":
        return actual.startswith("3.0")
    return True


@pytest.mark.skipif(not _task_available(), reason="task binary not available")
def test_task_cli_roundtrip_with_ephemeral_taskdata(tmp_path: Path) -> None:
    taskdata = tmp_path / "taskdata"
    taskrc = tmp_path / "taskrc"
    taskdata.mkdir(parents=True, exist_ok=True)
    taskrc.write_text(f"data.location={taskdata}\n", encoding="utf-8")

    cli = TaskwarriorCLI(override_rc=str(taskrc))
    if not _version_matches_target(cli):
        pytest.skip("Installed Taskwarrior version does not match target matrix axis")

    desc = f"integration test task {uuid.uuid4().hex[:8]}"
    add_res = cli.add_task(desc, project="integration.tests", tags=["integration"])
    assert add_res.ok, add_res.stderr

    tasks = cli.export_tasks("project:integration.tests")
    assert any(t.get("description") == desc for t in tasks)

    task = next(t for t in tasks if t.get("description") == desc)
    task_uuid = task["uuid"]

    mod_res = cli.modify_task(task_uuid, priority="H")
    assert mod_res.ok, mod_res.stderr

    updated = cli.get_task(task_uuid)
    assert updated is not None
    assert updated.get("priority") == "H"

    del_res = cli.delete_task(task_uuid)
    assert del_res.ok, del_res.stderr


@pytest.mark.skipif(shutil.which("timew") is None, reason="timew binary not available")
def test_timewarrior_cli_is_callable() -> None:
    timew = TimewarriorCLI()
    assert timew.available() is True
    status = timew.status()
    assert "tracking" in status
