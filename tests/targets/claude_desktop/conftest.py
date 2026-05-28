"""Claude Desktop acceptance target — manual checklist runner.

Claude Desktop cannot be driven headlessly. This conftest provides a stub
``mcp_client`` fixture that unconditionally skips, directing the tester to
the manual checklist at docs/manuals/targets/claude_desktop.md.
"""

from __future__ import annotations

import pytest

from tests.targets.conftest import MCPClient


@pytest.fixture()
def mcp_client() -> MCPClient:
    pytest.skip(
        "Claude Desktop requires manual testing — "
        "see docs/manuals/targets/claude_desktop.md for the checklist."
    )
