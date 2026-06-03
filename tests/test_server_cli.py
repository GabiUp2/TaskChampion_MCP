from __future__ import annotations

import json

from taskchampion_mcp.server import _build_parser, _interactive_terminal_guidance


def test_parser_accepts_config_precedence_flags() -> None:
    parser = _build_parser()
    args = parser.parse_args(["--role", "MANAGER", "--schema", "gtd", "--config-dump"])
    assert args.role == "MANAGER"
    assert args.schema == "gtd"
    assert args.config_dump is True


def test_parser_force_defaults_false_and_accepts_flag() -> None:
    parser = _build_parser()
    assert parser.parse_args([]).force is False
    assert parser.parse_args(["--force"]).force is True


def test_no_guidance_when_stdin_is_piped() -> None:
    # stdin wired to an MCP client (not a TTY): start normally.
    assert _interactive_terminal_guidance(is_tty=False, force=False) is None


def test_no_guidance_when_forced_even_on_tty() -> None:
    # --force escape hatch: run anyway despite interactive terminal.
    assert _interactive_terminal_guidance(is_tty=True, force=True) is None


def test_guidance_returned_on_interactive_terminal() -> None:
    guidance = _interactive_terminal_guidance(is_tty=True, force=False)
    assert guidance is not None
    # Tells the user what kind of process this is and how to run it.
    assert "stdio" in guidance.lower()
    assert "--force" in guidance


def test_config_dump_payload_shape() -> None:
    sample = {
        "server.role": {"value": "MANAGER", "source": "env:TC_MCP_ROLE"},
        "security.rate_limit_per_minute": {"value": 30, "source": "default"},
    }
    rendered = json.dumps(sample)
    parsed = json.loads(rendered)
    assert parsed["server.role"]["source"] == "env:TC_MCP_ROLE"
