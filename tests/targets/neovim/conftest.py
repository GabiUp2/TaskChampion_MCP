"""Neovim acceptance target — stdio subprocess runner (via Claude Code CLI path).

Neovim uses Claude Code CLI as the in-editor runner (ADR 18). The acceptance
harness still communicates over the same stdio JSON-RPC transport; the only
difference is that the real integration would go through ``claude mcp``.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.targets.conftest import (
    MCPClient,
    launch_server,
    make_task_stub,
    seed_config_for_phase,
)


@pytest.fixture(scope="session")
def _neovim_env(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Path]:
    """Session-scoped sandbox; ``mcp_client`` re-seeds the XDG per scenario phase."""
    base = tmp_path_factory.mktemp("neovim")
    stub_dir = make_task_stub(base / "bin")
    xdg = base / "xdg"
    taskdata = base / "taskdata"
    taskdata.mkdir()
    return {"stub_dir": stub_dir, "xdg": xdg, "taskdata": taskdata}


def _phase_from_request(request: pytest.FixtureRequest) -> str:
    callspec = getattr(request.node, "callspec", None)
    if callspec is None:
        return "post_onboarding"
    spec = callspec.params.get("spec")
    if not isinstance(spec, dict):
        return "post_onboarding"
    return spec.get("phase", "post_onboarding")


@pytest.fixture()
def mcp_client(
    _neovim_env: dict[str, Path],
    request: pytest.FixtureRequest,
) -> MCPClient:
    """Per-test client. Re-seeds XDG per scenario phase."""
    seed_config_for_phase(_neovim_env["xdg"], _phase_from_request(request))

    proc = launch_server(
        xdg_dir=_neovim_env["xdg"],
        stub_dir=_neovim_env["stub_dir"],
        taskdata_dir=_neovim_env["taskdata"],
    )
    client = MCPClient(proc)
    client.initialize()
    yield client
    client.close()
