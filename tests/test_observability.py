from __future__ import annotations

import json
import logging
from pathlib import Path

from taskchampion_mcp.audit import AuditLogger
from taskchampion_mcp.rate_limiter import RateLimiter
from taskchampion_mcp.server import _audit_call, _configure_logging


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


# ---------------------------------------------------------------------------
# _audit_call helper (server.py) — wraps onboarding + reconfigure tools so
# they leave an audit trail equivalent to the role-tier tools.  v0.3.2 audit
# finding #3.
# ---------------------------------------------------------------------------


class _ToolRegistryStub:
    """Just enough surface for _audit_call: ``.audit`` + ``.limiter`` attributes."""

    def __init__(
        self,
        audit: AuditLogger,
        limiter: RateLimiter | None = None,
    ) -> None:
        self.audit = audit
        # Generous defaults so most tests don't trip the rate limiter.
        self.limiter = limiter or RateLimiter(
            ops_per_minute=10_000,
            ops_per_hour=10_000,
            creates_per_hour=10_000,
        )


def _fresh_audit_logger(log_path: Path) -> AuditLogger:
    """Build an AuditLogger pointing at ``log_path`` with no carry-over handlers.

    ``AuditLogger`` reuses a process-global ``logging.getLogger`` named
    ``taskchampion_mcp.audit`` and only attaches a handler on first init.
    In a multi-test process the second-and-later loggers would silently
    write to whichever path the first test picked, so we clear handlers
    here before each test.
    """
    parent = logging.getLogger("taskchampion_mcp.audit")
    for handler in list(parent.handlers):
        try:
            handler.close()
        finally:
            parent.removeHandler(handler)
    return AuditLogger(str(log_path))


def test_audit_call_logs_successful_onboarding_result(tmp_path: Path) -> None:
    """A successful onboarding-style call lands in the audit log with
    success=True, the result's ``code`` propagated to ``result_code``, and
    only curated summary keys in ``result`` (no large blobs)."""
    log_path = tmp_path / "audit.log"
    reg = _ToolRegistryStub(_fresh_audit_logger(log_path))

    def _fake_save() -> dict:
        return {
            "success": True,
            "code": "ok",
            "schema_path": "/tmp/generated_schema.toml",
            "role": "CONTRIBUTOR",
            "config_file": "/tmp/config.toml",
            "restart_required": True,
            "message": "Initial schema saved.",
            # Large field that MUST NOT land in the audit summary:
            "schema_toml": "[meta]\nname = 'x'\n" + "# pad\n" * 5000,
        }

    result = _audit_call(reg, "save_initial_schema", {"role": "CONTRIBUTOR"}, _fake_save)
    assert result["success"] is True

    entry = _read_last_json_line(log_path)
    assert entry["tool"] == "save_initial_schema"
    assert entry["success"] is True
    assert entry["result_code"] == "ok"
    # ``result`` is the JSON-encoded summary; assert key facts present
    assert '"role": "CONTRIBUTOR"' in entry["result"]
    assert '"restart_required": true' in entry["result"]
    # The schema_toml blob MUST NOT have leaked into the audit summary
    assert "schema_toml" not in entry["result"]


def test_audit_call_propagates_error_code_for_refusal(tmp_path: Path) -> None:
    """A role_elevation_forbidden refusal is logged with success=False and
    the structured error_code surfaced as result_code (ADR 14 + ADR 17)."""
    log_path = tmp_path / "audit.log"
    reg = _ToolRegistryStub(_fresh_audit_logger(log_path))

    def _fake_set_role() -> dict:
        return {
            "error": True,
            "error_code": "role_elevation_forbidden",
            "current_role": "CONTRIBUTOR",
            "requested_role": "MANAGER",
            "message": "Self-elevation forbidden",
        }

    _audit_call(reg, "set_role", {"target_role": "MANAGER"}, _fake_set_role)

    entry = _read_last_json_line(log_path)
    assert entry["success"] is False
    assert entry["result_code"] == "role_elevation_forbidden"
    assert entry["error"] == "Self-elevation forbidden"
    assert '"requested_role": "MANAGER"' in entry["result"]


def test_audit_call_records_exception_path(tmp_path: Path) -> None:
    """If the wrapped callable raises, the audit log still gets exactly one
    entry capturing the exception, and the exception re-propagates."""
    log_path = tmp_path / "audit.log"
    reg = _ToolRegistryStub(_fresh_audit_logger(log_path))

    def _boom() -> dict:
        raise RuntimeError("disk on fire")

    import pytest

    with pytest.raises(RuntimeError, match="disk on fire"):
        _audit_call(reg, "list_preset_schemas", {}, _boom)

    entry = _read_last_json_line(log_path)
    assert entry["tool"] == "list_preset_schemas"
    assert entry["success"] is False
    # AuditLogger defaults result_code to "internal_error" when no code given
    assert entry["result_code"] == "internal_error"
    assert "RuntimeError" in entry["error"]
    assert "disk on fire" in entry["error"]


def test_audit_call_emits_duration_ms(tmp_path: Path) -> None:
    """duration_ms is recorded so audit consumers can flag slow calls."""
    log_path = tmp_path / "audit.log"
    reg = _ToolRegistryStub(_fresh_audit_logger(log_path))

    def _quick() -> dict:
        return {"success": True, "code": "ok"}

    _audit_call(reg, "get_initialization_status", {}, _quick)
    entry = _read_last_json_line(log_path)
    assert "duration_ms" in entry
    assert entry["duration_ms"] >= 0


def test_audit_call_curates_only_known_summary_keys(tmp_path: Path) -> None:
    """The audit summary contains keys from the curated allow-list; unknown
    keys do not leak through (the helper is a query target, not a result
    store)."""
    log_path = tmp_path / "audit.log"
    reg = _ToolRegistryStub(_fresh_audit_logger(log_path))

    def _fake() -> dict:
        return {
            "success": True,
            "code": "ok",
            "schema_name": "minimal",          # in allow-list
            "task_count": 7,                   # in allow-list
            "secret_internal_field": "shhh",   # NOT in allow-list
            "internal_debug_state": [1, 2, 3], # NOT in allow-list
        }

    _audit_call(reg, "get_initialization_status", {}, _fake)
    entry = _read_last_json_line(log_path)
    result = entry["result"]
    assert "schema_name" in result
    assert "task_count" in result
    assert "secret_internal_field" not in result
    assert "internal_debug_state" not in result


def test_audit_call_returns_rate_limit_refusal_without_running_fn(tmp_path: Path) -> None:
    """When the per-minute bucket is full, ``_audit_call`` short-circuits with a
    structured rate_limit envelope (ADR 14) and never invokes the wrapped fn.
    The refusal is audit-logged so attempts are visible (ADR 13)."""
    log_path = tmp_path / "audit.log"
    # Tiny limiter — 2 ops per minute. We'll burn both then trip on the third.
    tiny = RateLimiter(ops_per_minute=2, ops_per_hour=10_000, creates_per_hour=10_000)
    reg = _ToolRegistryStub(_fresh_audit_logger(log_path), limiter=tiny)

    call_count = {"n": 0}

    def _counted() -> dict:
        call_count["n"] += 1
        return {"success": True, "code": "ok"}

    # First two calls succeed
    r1 = _audit_call(reg, "get_initialization_status", {}, _counted)
    r2 = _audit_call(reg, "get_initialization_status", {}, _counted)
    assert r1["success"] and r2["success"]
    assert call_count["n"] == 2

    # Third call must be refused without invoking _counted
    r3 = _audit_call(reg, "get_initialization_status", {}, _counted)
    assert r3["error"] is True
    assert r3["code"] == "rate_limit"
    assert r3["details"]["bucket"] == "ops_per_minute"
    assert r3["details"]["limit"] == 2
    assert r3["details"]["retry_after_s"] == 60
    # Critical: wrapped fn must NOT have been called
    assert call_count["n"] == 2

    # And the refusal is audit-logged with result_code="rate_limit"
    entry = _read_last_json_line(log_path)
    assert entry["tool"] == "get_initialization_status"
    assert entry["result_code"] == "rate_limit"
    assert entry["success"] is False


def test_audit_call_rate_limit_independent_of_tool_name(tmp_path: Path) -> None:
    """The limiter counts across all tools, not per-tool — exhausting the
    budget on one tool blocks any other onboarding/reconfigure tool too.
    This is what makes the rate limit useful against runaway loops that
    rotate between tools."""
    log_path = tmp_path / "audit.log"
    tiny = RateLimiter(ops_per_minute=1, ops_per_hour=10_000, creates_per_hour=10_000)
    reg = _ToolRegistryStub(_fresh_audit_logger(log_path), limiter=tiny)

    def _ok() -> dict:
        return {"success": True, "code": "ok"}

    # First tool burns the budget
    _audit_call(reg, "get_initialization_status", {}, _ok)
    # Second tool, different name, must be refused
    r2 = _audit_call(reg, "set_active_schema", {}, _ok)
    assert r2["error"] is True
    assert r2["code"] == "rate_limit"
