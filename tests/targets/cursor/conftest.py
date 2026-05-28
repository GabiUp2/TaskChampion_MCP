"""Cursor acceptance target — stdio subprocess runner."""

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
def _cursor_env(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Path]:
    """Session-scoped sandbox: stub ``task`` binary + isolated XDG + taskdata.

    The XDG is *not* seeded here — the per-test ``mcp_client`` fixture seeds it
    fresh based on each scenario's declared ``phase``. That gives us per-test
    onboarding / CONTRIBUTOR / GENERATOR / MANAGER state without a
    session-scoped config baked in.
    """
    base = tmp_path_factory.mktemp("cursor")
    stub_dir = make_task_stub(base / "bin")
    xdg = base / "xdg"
    taskdata = base / "taskdata"
    taskdata.mkdir()
    return {"stub_dir": stub_dir, "xdg": xdg, "taskdata": taskdata}


def _phase_from_request(request: pytest.FixtureRequest) -> str:
    """Pull the scenario phase off the parametrised test, defaulting to
    ``post_onboarding`` for non-parametrised callers."""
    callspec = getattr(request.node, "callspec", None)
    if callspec is None:
        return "post_onboarding"
    spec = callspec.params.get("spec")
    if not isinstance(spec, dict):
        return "post_onboarding"
    return spec.get("phase", "post_onboarding")


@pytest.fixture()
def mcp_client(
    _cursor_env: dict[str, Path],
    request: pytest.FixtureRequest,
) -> MCPClient:
    """Per-test MCP client. Re-seeds the XDG config for the scenario's
    ``phase`` (onboarding / post_onboarding / generator / manager / …) before
    launching a fresh server subprocess. This is what makes the 26-scenario
    matrix actually exercise role + initialisation states correctly."""
    seed_config_for_phase(_cursor_env["xdg"], _phase_from_request(request))

    proc = launch_server(
        xdg_dir=_cursor_env["xdg"],
        stub_dir=_cursor_env["stub_dir"],
        taskdata_dir=_cursor_env["taskdata"],
    )
    client = MCPClient(proc)
    client.initialize()
    yield client
    client.close()
