"""Audit logging for all MCP tool invocations (ADR 9)."""

from __future__ import annotations

import json
import logging
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class AuditLogger:
    """Structured append-only audit log for MCP operations."""

    def __init__(
        self,
        log_path: str,
        session_id: str | None = None,
        redacted_fields: list[str] | None = None,
    ) -> None:
        self._path = Path(log_path)
        self._session_id = session_id or uuid.uuid4().hex[:12]
        self._redacted_fields = {f.strip() for f in (redacted_fields or []) if f and f.strip()}
        self._logger = logging.getLogger("taskchampion_mcp.audit")
        self._ensure_directory()
        self._setup_file_handler()

    def _ensure_directory(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)

    def _setup_file_handler(self) -> None:
        if not self._logger.handlers:
            handler = logging.FileHandler(self._path, mode="a", encoding="utf-8")
            handler.setFormatter(logging.Formatter("%(message)s"))
            self._logger.addHandler(handler)
            self._logger.setLevel(logging.INFO)
            self._logger.propagate = False

    @property
    def session_id(self) -> str:
        return self._session_id

    def log(
        self,
        tool_name: str,
        parameters: dict[str, Any],
        result: str,
        result_code: str | None,
        success: bool,
        duration_ms: float | None = None,
        error: str | None = None,
    ) -> None:
        """Write a single audit entry."""
        redacted_params = _redact_configured_fields(parameters, self._redacted_fields)
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "session_id": self._session_id,
            "tool": tool_name,
            "parameters": _redact_long_values(redacted_params),
            "result": result[:500] if result else "",
            "result_code": result_code or ("ok" if success else "internal_error"),
            "success": success,
            "pid": os.getpid(),
        }
        if duration_ms is not None:
            entry["duration_ms"] = round(duration_ms, 2)
        if error:
            entry["error"] = error[:500]
        self._logger.info(json.dumps(entry, default=str))

    def log_startup(self, role: str, schema: str, tw_version: str | None) -> None:
        """Log server startup event."""
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "session_id": self._session_id,
            "event": "server_start",
            "role": role,
            "schema": schema,
            "taskwarrior_version": tw_version or "unknown",
            "pid": os.getpid(),
        }
        self._logger.info(json.dumps(entry, default=str))


def _redact_long_values(params: dict[str, Any], max_len: int = 200) -> dict[str, Any]:
    """Truncate overly long parameter values for audit legibility."""
    result: dict[str, Any] = {}
    for k, v in params.items():
        if isinstance(v, str) and len(v) > max_len:
            result[k] = v[:max_len] + "...<truncated>"
        else:
            result[k] = v
    return result


def _redact_configured_fields(data: Any, redacted_fields: set[str]) -> Any:
    """Recursively redact configured sensitive fields from parameters."""
    if not redacted_fields:
        return data
    if isinstance(data, dict):
        result: dict[str, Any] = {}
        for key, value in data.items():
            if key in redacted_fields:
                result[key] = "***REDACTED***"
            else:
                result[key] = _redact_configured_fields(value, redacted_fields)
        return result
    if isinstance(data, list):
        return [_redact_configured_fields(item, redacted_fields) for item in data]
    return data
