"""Target-agnostic acceptance test — 26 parametrised scenarios.

Imported by each per-target ``test_acceptance.py``.  The ``mcp_client``
fixture is resolved from the per-target conftest.
"""

from __future__ import annotations

import json
import re
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


# Match structured error codes inside a JSON response — either as the
# response's top-level ``code`` field or the refusal-class ``error_code``
# (per ADR 14 + ADR 17). A raw substring check is too lax: it produces false
# positives when a successful response legitimately *mentions* an error code
# in its data payload (e.g. ``get_runtime_capabilities`` listing
# ``uncallable_tool_groups`` with their ``uncallable_reason`` codes).
_CODE_FIELD = re.compile(r'"(?:error_)?code"\s*:\s*"(?P<code>[a-z_]+)"')


def _structured_codes(content: str) -> set[str]:
    """Return the set of error codes asserted in JSON ``code`` / ``error_code``
    fields anywhere in ``content``. Used by both the error-expected and
    success-expected paths."""
    return {m.group("code") for m in _CODE_FIELD.finditer(content)}


def _assert_structured_error(result: dict, expected_code: str, scenario_id: str) -> None:
    """Scenario declared ``expect_error: "<code>"`` — verify the response
    carries that code via a structured field (not a bare substring)."""
    content = _extract_content_text(result)
    codes = _structured_codes(content)
    if expected_code not in codes:
        raise AssertionError(
            f"[{scenario_id}] Expected structured error code {expected_code!r} "
            f"in response (looked for `\"code\": \"{expected_code}\"` or "
            f"`\"error_code\": \"{expected_code}\"`). "
            f"Saw codes: {sorted(codes) or '(none)'}. "
            f"Got: {content[:300]}"
        )


def _assert_success(result: dict, spec: dict[str, Any], scenario_id: str) -> None:
    """Scenario expects success — verify the response does not carry a
    refusal-class structured code, and run a tool-specific shape check."""
    content = _extract_content_text(result)
    codes = _structured_codes(content)

    # A successful response must not be *the* refusal — a substring match
    # would also flag introspection-style responses that legitimately list
    # uncallable reasons in their data. Match only on the top-level/envelope
    # code, which we detect by checking the *first* structured code occurrence
    # in the response. If the first occurrence is a refusal, we fail; if a
    # later occurrence is (e.g. inside an ``uncallable_tool_groups`` array),
    # we tolerate it.
    first_code_match = _CODE_FIELD.search(content)
    refusal_codes = {"role_insufficient", "schema_unset", "not_available"}
    if first_code_match and first_code_match.group("code") in refusal_codes:
        raise AssertionError(
            f"[{scenario_id}] Unexpected refusal code "
            f"{first_code_match.group('code')!r} as the envelope's primary "
            f"code in a successful-scenario response. "
            f"All codes seen: {sorted(codes)}. Got: {content[:300]}"
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
