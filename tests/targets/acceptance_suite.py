"""Target-agnostic acceptance test — 26 parametrised scenarios.

Imported by each per-target ``test_acceptance.py``.  The ``mcp_client``
fixture is resolved from the per-target conftest.
"""

from __future__ import annotations

import json
from typing import Any

import pytest

from tests.targets.conftest import ACCEPTANCE_SCENARIOS, MCPClient


@pytest.mark.acceptance
@pytest.mark.parametrize(
    "scenario_id,description,spec",
    ACCEPTANCE_SCENARIOS,
    ids=[s[0] for s in ACCEPTANCE_SCENARIOS],
)
def test_acceptance(
    mcp_client: MCPClient,
    scenario_id: str,
    description: str,
    spec: dict[str, Any],
) -> None:
    """Run a single acceptance scenario against the target's MCP server."""
    tool = spec["tool"]
    params = spec.get("params", {})
    expect_error = spec.get("expect_error")

    result = mcp_client.send_tool_call(tool, params)

    if expect_error:
        _assert_structured_error(result, expect_error, scenario_id)
    else:
        _assert_success(result, spec, scenario_id)


def _assert_structured_error(result: dict, expected_code: str, scenario_id: str) -> None:
    content = _extract_content_text(result)
    assert expected_code in content, (
        f"[{scenario_id}] Expected error code {expected_code!r} in response. "
        f"Got: {content[:300]}"
    )


def _assert_success(result: dict, spec: dict[str, Any], scenario_id: str) -> None:
    content = _extract_content_text(result)

    error_codes = ("role_insufficient", "schema_unset", "not_available")
    for code in error_codes:
        assert code not in content, (
            f"[{scenario_id}] Unexpected error {code!r} in successful response. "
            f"Got: {content[:300]}"
        )

    tool = spec["tool"]
    if tool == "get_initialization_status":
        assert "needs_onboarding" in content or "true" in content.lower(), (
            f"[{scenario_id}] Expected needs_onboarding indicator. Got: {content[:300]}"
        )
    elif tool == "list_preset_schemas":
        assert "minimal" in content.lower(), (
            f"[{scenario_id}] Expected 'minimal' preset in response. Got: {content[:300]}"
        )
    elif tool == "get_runtime_capabilities":
        assert "operational" in content.lower() or "mode" in content.lower(), (
            f"[{scenario_id}] Expected operational mode. Got: {content[:300]}"
        )
    elif tool == "use_preset_schema":
        assert "restart_required" in content.lower() or "success" in content.lower(), (
            f"[{scenario_id}] Expected schema activation confirmation. Got: {content[:300]}"
        )


def _extract_content_text(result: dict) -> str:
    if isinstance(result, dict):
        content_list = result.get("content", [])
        if isinstance(content_list, list):
            texts = []
            for item in content_list:
                if isinstance(item, dict) and item.get("type") == "text":
                    texts.append(item.get("text", ""))
            if texts:
                return "\n".join(texts)
        return json.dumps(result)
    return str(result)
