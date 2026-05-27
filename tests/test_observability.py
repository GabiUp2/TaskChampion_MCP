from __future__ import annotations

import json
import logging
from pathlib import Path

from taskchampion_mcp.audit import AuditLogger
from taskchampion_mcp.server import _configure_logging


class _FakeStream:
    def __init__(self, tty: bool) -> None:
        self._tty = tty
        self._parts: list[str] = []

    def write(self, data: str) -> int:
        self._parts.append(data)
        return len(data)

    def flush(self) -> None:
        return None

    def isatty(self) -> bool:
        return self._tty

    def text(self) -> str:
        return "".join(self._parts)


def _read_last_json_line(path: Path) -> dict:
    lines = [ln for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip()]
    return json.loads(lines[-1])


def test_audit_entry_includes_result_code_and_redacts_configured_fields(tmp_path: Path) -> None:
    log_path = tmp_path / "audit.log"
    logger = AuditLogger(str(log_path), redacted_fields=["token"])
    logger.log(
        tool_name="list_tasks",
        parameters={"token": "super-secret-token", "query": "status:pending"},
        result="failed",
        result_code="rate_limit",
        success=False,
        duration_ms=3.7,
        error="rate limited",
    )

    entry = _read_last_json_line(log_path)
    assert entry["result_code"] == "rate_limit"
    assert entry["parameters"]["token"].startswith("***")
    assert entry["parameters"]["token"].endswith("***")


def test_operational_logs_are_json_lines_when_stderr_is_not_tty(monkeypatch) -> None:
    stream = _FakeStream(tty=False)
    _configure_logging(stream=stream)
    logger = logging.getLogger("taskchampion_mcp.test")
    logger.info("json mode works")
    payload = json.loads(stream.text().splitlines()[-1])
    assert payload["message"] == "json mode works"
    assert payload["level"] == "INFO"


def test_operational_logs_are_human_readable_when_stderr_is_tty(monkeypatch) -> None:
    stream = _FakeStream(tty=True)
    _configure_logging(stream=stream)
    logger = logging.getLogger("taskchampion_mcp.test")
    logger.info("tty mode works")
    line = stream.text().splitlines()[-1]
    assert "INFO" in line
    assert "tty mode works" in line


def test_log_level_can_be_overridden_with_environment_variable(monkeypatch) -> None:
    monkeypatch.setenv("TC_MCP_LOG_LEVEL", "DEBUG")
    stream = _FakeStream(tty=False)
    _configure_logging(stream=stream)
    logger = logging.getLogger("taskchampion_mcp.test")
    logger.debug("debug mode active")
    payload = json.loads(stream.text().splitlines()[-1])
    assert payload["level"] == "DEBUG"
    assert payload["message"] == "debug mode active"
