"""Cursor acceptance target — stdio subprocess runner."""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.targets.conftest import (
    MCPClient,
    launch_server,
    make_task_stub,
    seed_post_onboarding_config,
)


@pytest.fixture(scope="session")
def _cursor_env(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Path]:
    base = tmp_path_factory.mktemp("cursor")
    stub_dir = make_task_stub(base / "bin")
    xdg = base / "xdg"
    taskdata = base / "taskdata"
    taskdata.mkdir()
    seed_post_onboarding_config(xdg)
    return {"stub_dir": stub_dir, "xdg": xdg, "taskdata": taskdata}


@pytest.fixture()
def mcp_client(_cursor_env: dict[str, Path]) -> MCPClient:
    proc = launch_server(
        xdg_dir=_cursor_env["xdg"],
        stub_dir=_cursor_env["stub_dir"],
        taskdata_dir=_cursor_env["taskdata"],
    )
    client = MCPClient(proc)
    client.initialize()
    yield client
    client.close()
