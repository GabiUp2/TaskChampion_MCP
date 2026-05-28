from __future__ import annotations

import json

from taskchampion_mcp.server import _build_parser


def test_parser_accepts_config_precedence_flags() -> None:
    parser = _build_parser()
    args = parser.parse_args(["--role", "MANAGER", "--schema", "gtd", "--config-dump"])
    assert args.role == "MANAGER"
    assert args.schema == "gtd"
    assert args.config_dump is True


def test_config_dump_payload_shape() -> None:
    sample = {
        "server.role": {"value": "MANAGER", "source": "env:TC_MCP_ROLE"},
        "security.rate_limit_per_minute": {"value": 30, "source": "default"},
    }
    rendered = json.dumps(sample)
    parsed = json.loads(rendered)
    assert parsed["server.role"]["source"] == "env:TC_MCP_ROLE"
