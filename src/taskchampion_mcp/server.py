"""TaskChampion MCP Server — entry point.

Registers MCP tools based on the configured role level (ADR 5)
and starts the stdio transport (ADR 3).
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Callable

from mcp.server.fastmcp import FastMCP

from taskchampion_mcp.audit import AuditLogger
from taskchampion_mcp.cli import TaskwarriorCLI, TimewarriorCLI
from taskchampion_mcp.config import (
    Role,
    ServerConfig,
    dump_effective_config,
    load_config,
    load_config_with_sources,
)
from taskchampion_mcp.onboarding import (
    analyze_existing_tasks as onboarding_analyze_existing_tasks,
)
from taskchampion_mcp.onboarding import (
    analyze_taxonomy_file as onboarding_analyze_taxonomy_file,
)
from taskchampion_mcp.onboarding import (
    generate_schema_preview as onboarding_generate_schema_preview,
)
from taskchampion_mcp.onboarding import (
    get_initialization_status as onboarding_get_initialization_status,
)
from taskchampion_mcp.onboarding import (
    list_preset_schemas as onboarding_list_preset_schemas,
)
from taskchampion_mcp.onboarding import (
    propose_initialization_options as onboarding_propose_initialization_options,
)
from taskchampion_mcp.onboarding import (
    reconfigure_active_schema as onboarding_reconfigure_active_schema,
)
from taskchampion_mcp.onboarding import (
    reconfigure_role as onboarding_reconfigure_role,
)
from taskchampion_mcp.onboarding import (
    reconfigure_taxonomy_path as onboarding_reconfigure_taxonomy_path,
)
from taskchampion_mcp.onboarding import (
    save_initial_schema as onboarding_save_initial_schema,
)
from taskchampion_mcp.onboarding import (
    use_preset_schema as onboarding_use_preset_schema,
)
from taskchampion_mcp.rate_limiter import RateLimiter, RateLimitError
from taskchampion_mcp.schema import TaskSchema, load_schema
from taskchampion_mcp.tools import ToolRegistry

logger = logging.getLogger("taskchampion_mcp")


class _JsonLineFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "logger": record.name,
            "level": record.levelname,
            "message": record.getMessage(),
        }
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


def _resolve_log_level(level_name: str) -> tuple[int, bool]:
    requested = (level_name or "INFO").upper()
    if requested in logging._nameToLevel and logging._nameToLevel[requested]:
        return logging._nameToLevel[requested], False
    return logging.INFO, True


def _configure_logging(stream: Any | None = None) -> None:
    stderr_stream = stream if stream is not None else sys.stderr
    level_name = os.environ.get("TC_MCP_LOG_LEVEL", "INFO")
    level, invalid_level = _resolve_log_level(level_name)

    is_tty = bool(getattr(stderr_stream, "isatty", lambda: False)())
    formatter: logging.Formatter
    if is_tty:
        formatter = logging.Formatter("%(asctime)s [%(name)s] %(levelname)s: %(message)s")
    else:
        formatter = _JsonLineFormatter()

    logging.basicConfig(level=level, stream=stderr_stream, format="%(message)s", force=True)
    for handler in logging.getLogger().handlers:
        handler.setFormatter(formatter)

    if invalid_level:
        logger.warning(
            "Invalid TC_MCP_LOG_LEVEL '%s'; falling back to INFO.",
            level_name,
        )


# ---------------------------------------------------------------------------
# Server factory
# ---------------------------------------------------------------------------


def create_server(
    config: ServerConfig | None = None,
    config_path: Path | None = None,
) -> FastMCP:
    """Build and configure the MCP server with the full tool surface.

    Per ADR 19, ALL tools register unconditionally at startup.  Runtime
    gates inside each handler check initialisation state and role level
    before executing, returning structured ADR-14 error envelopes when
    the tool is not currently callable.
    """

    if config is None:
        config = load_config(config_path)

    # --- Detect tools -------------------------------------------------------
    task_cli = TaskwarriorCLI(
        binary=config.task_binary,
        override_rc=config.taskwarrior_override_rc,
    )
    tw_version = task_cli.version()
    if tw_version is None:
        logger.error(
            "Taskwarrior not found on PATH (%s). "
            "Install Taskwarrior 3.x and ensure 'task' is available.",
            config.task_binary,
        )
        sys.exit(1)

    major = tw_version.split(".")[0] if tw_version else "0"
    if major == "2":
        logger.warning(
            "Taskwarrior 2.x detected (%s). This MCP targets 3.x. "
            "Some features may not work correctly.",
            tw_version,
        )
    elif major not in ("3",):
        logger.warning("Unexpected Taskwarrior version: %s", tw_version)

    timew_cli: TimewarriorCLI | None = None
    timew_instance = TimewarriorCLI(binary=config.timew_binary)
    if timew_instance.available():
        timew_cli = timew_instance
        logger.info(
            "Timewarrior detected: %s",
            timew_instance.version(),
        )
    else:
        logger.info("Timewarrior not found. Time tracking tools disabled.")

    # --- Load schema --------------------------------------------------------
    schema: TaskSchema
    if config.schema_path:
        schema = load_schema(config.schema_path)
    else:
        schema = load_schema(config.schema_name)
    logger.info("Schema loaded: %s v%s", schema.name, schema.version)

    # --- Build shared state -------------------------------------------------
    rate_limiter = RateLimiter(
        ops_per_minute=config.rate_limit_per_minute,
        ops_per_hour=config.rate_limit_per_hour,
        creates_per_hour=config.create_limit_per_hour,
    )

    audit = AuditLogger(
        config.audit_log_path,
        redacted_fields=config.redacted_fields,
    )
    audit.log_startup(config.role, schema.name, tw_version)

    registry = ToolRegistry(
        config=config,
        task_cli=task_cli,
        timew_cli=timew_cli,
        schema=schema,
        rate_limiter=rate_limiter,
        audit=audit,
        config_path=config_path,
    )

    # --- Create FastMCP server ----------------------------------------------
    mcp = FastMCP(
        "TaskChampion MCP",
        instructions=_build_instructions(
            config,
            schema,
            tw_version,
            onboarding_required=not registry.initialized,
        ),
    )

    # --- Register ALL tools unconditionally (ADR 19) ------------------------
    _register_onboarding_tools(mcp, registry)
    _register_contributor_tools(mcp, registry)
    _register_generator_tools(mcp, registry)
    _register_manager_tools(mcp, registry)
    _register_reload_tool(mcp, registry)

    logger.info(
        "Server ready. Role=%s, Schema=%s, TW=%s, Initialized=%s",
        config.role,
        schema.name,
        tw_version,
        registry.initialized,
    )

    return mcp


# ---------------------------------------------------------------------------
# Runtime gates (ADR 19)
# ---------------------------------------------------------------------------


def _gate_initialized(reg: ToolRegistry) -> str | None:
    """Return a JSON error string if the server is not initialised, else None."""
    if reg.initialized:
        return None
    return json.dumps({
        "error": True,
        "code": "schema_unset",
        "message": (
            "Server is not initialised. Complete onboarding first: call "
            "get_initialization_status, then save_initial_schema or "
            "use_preset_schema to persist a schema and role."
        ),
    })


def _gate_role(reg: ToolRegistry, required_role: str) -> str | None:
    """Return a JSON error string if init or role is insufficient, else None."""
    init_err = _gate_initialized(reg)
    if init_err:
        return init_err
    if not Role.has_permission(reg.config.role, required_role):
        return json.dumps({
            "error": True,
            "code": "role_insufficient",
            "message": (
                f"This tool requires role {required_role} or higher; "
                f"current role is {reg.config.role}."
            ),
        })
    return None


# ---------------------------------------------------------------------------
# Audit-log helper for onboarding + reconfigure tools
# ---------------------------------------------------------------------------
#
# Onboarding and reconfigure tools call onboarding.* functions directly rather
# than going through ToolRegistry, so they don't get audit logging "for free"
# the way contributor/generator/manager tools do.  ``_audit_call`` is the
# missing piece — wrap any callable that returns a result-dict and it emits
# exactly one audit entry per invocation (success, refusal, or exception).
#
# Per ADR 13 the audit log is the queryable source of truth for "what did the
# LLM do".  ADR 17 specifically requires every config-mutating reconfigure
# call to leave a trail.  v0.3.2 closes audit finding #3 by extending the
# trail to onboarding tools as well, including the two mutating ones
# (save_initial_schema, use_preset_schema) which had no record before.

# Curated set of small result-dict keys safe to copy into the audit log's
# ``result`` summary field.  Excludes large structures (schema_toml, fields,
# options, presets array) that would blow past the audit log's 500-char
# truncation and offer no query value.
_AUDIT_SUMMARY_KEYS = (
    "active_role",
    "config_file",
    "config_updated",
    "copied_to",
    "current_role",
    "custom_schema_configured",
    "custom_schema_exists",
    "error_code",
    "field_count",
    "initialised",
    "needs_onboarding",
    "needs_role_selection",
    "new_role",
    "preset_count",
    "preset_name",
    "previous_role",
    "recommended_next_action",
    "requested_role",
    "restart_required",
    "role",
    "role_configured",
    "schema_name",
    "schema_path",
    "task_count",
    "taxonomy_configured",
    "taxonomy_exists",
    "taxonomy_path",
)


def _audit_call(
    reg: ToolRegistry,
    tool_name: str,
    params: dict[str, Any],
    fn: Callable[[], dict[str, Any]],
) -> dict[str, Any]:
    """Rate-limit + run ``fn`` + audit-log the call.

    Returns ``fn``'s result dict (or re-raises any exception).  Emits exactly
    one ``audit.log`` entry per invocation with:

    * ``tool_name`` and curated ``parameters`` (long string values truncated;
      configured ``redacted_fields`` masked by AuditLogger)
    * ``result`` — a JSON object built from ``_AUDIT_SUMMARY_KEYS``, dropping
      large nested payloads that have no query value
    * ``result_code`` — taken from ``result["code"]`` or
      ``result["error_code"]``; defaults to ``"ok"`` / ``"internal_error"``
    * ``success`` and ``duration_ms``
    * ``error`` — exception message or, on a logical failure, the result's
      ``message`` field

    Rate limiting (ADR 9, audit finding #4 / v0.3.2):  the configured
    sliding-window limits apply uniformly to every onboarding and reconfigure
    tool call, the same way they do to role-tier tools via
    ToolRegistry._guard_rate.  Without this, a misbehaving LLM in a loop
    could rewrite config.toml or call status repeatedly at disk-I/O speed.
    On limit-exceeded, returns a structured ``{"error": True, "code":
    "rate_limit", ...}`` envelope (per ADR 14) and audit-logs the refusal —
    the wrapped ``fn`` is never executed.
    """
    t0 = time.monotonic()

    # --- Rate-limit check (returns a structured envelope on refusal) -------
    try:
        reg.limiter.check_and_record(is_create=False)
    except RateLimitError as exc:
        refusal: dict[str, Any] = {
            "error": True,
            "code": "rate_limit",
            "message": str(exc),
            "details": {
                "bucket": exc.bucket,
                "limit": exc.limit,
                "retry_after_s": exc.window_seconds,
            },
        }
        reg.audit.log(
            tool_name=tool_name,
            parameters=params,
            result=json.dumps(
                {"bucket": exc.bucket, "limit": exc.limit},
                default=str,
            ),
            result_code="rate_limit",
            success=False,
            duration_ms=(time.monotonic() - t0) * 1000.0,
            error=str(exc),
        )
        return refusal

    # --- Normal path -------------------------------------------------------
    result: dict[str, Any] | None = None
    error_msg: str | None = None
    try:
        result = fn()
        return result
    except Exception as exc:  # noqa: BLE001 — re-raised after audit
        error_msg = f"{type(exc).__name__}: {exc}"
        raise
    finally:
        duration_ms = (time.monotonic() - t0) * 1000.0
        ok = bool(isinstance(result, dict) and result.get("success"))
        summary: dict[str, Any] = {}
        result_code: str | None = None
        if isinstance(result, dict):
            summary = {k: result.get(k) for k in _AUDIT_SUMMARY_KEYS if k in result}
            # Prefer an explicit `code` field; fall back to `error_code` for
            # refusal-class results (role_elevation_forbidden etc).
            result_code = result.get("code") or result.get("error_code")
            if not ok and error_msg is None:
                error_msg = result.get("message") or "unknown error"
        reg.audit.log(
            tool_name=tool_name,
            parameters=params,
            result=json.dumps(summary, default=str) if summary else "",
            result_code=result_code,
            success=ok and error_msg is None,
            duration_ms=duration_ms,
            error=error_msg,
        )


# ---------------------------------------------------------------------------
# Tool registration
# ---------------------------------------------------------------------------


def _register_onboarding_tools(mcp: FastMCP, reg: ToolRegistry) -> None:
    """Register first-run onboarding tools.

    Every tool wraps its onboarding.* call with ``_audit_call`` so the audit
    trail captures schema/role choices and parse errors equally — closes
    audit finding #3 (v0.3.2).
    """

    @mcp.tool()
    def get_initialization_status(project_dir: str = "") -> str:
        """Inspect first-run onboarding state without mutating tasks or config.

        Use this before task creation/modification if the active schema may be
        the bundled minimal default rather than a user-specific taxonomy.
        """
        params = {"project_dir": project_dir or None}
        return json.dumps(
            _audit_call(
                reg,
                "get_initialization_status",
                params,
                lambda: onboarding_get_initialization_status(
                    config=reg.config,
                    task_cli=reg.task,
                    timew_cli=reg.timew,
                    project_dir=project_dir or None,
                ),
            )
        )

    @mcp.tool()
    def propose_initialization_options(project_dir: str = "") -> str:
        """Return onboarding choices for the user/model to discuss.

        Options include using a taxonomy file, inferring from existing tasks,
        combining both, or selecting a bundled preset.
        """
        params = {"project_dir": project_dir or None}

        def _run() -> dict[str, Any]:
            status = onboarding_get_initialization_status(
                config=reg.config,
                task_cli=reg.task,
                timew_cli=reg.timew,
                project_dir=project_dir or None,
            )
            return onboarding_propose_initialization_options(status)

        return json.dumps(_audit_call(reg, "propose_initialization_options", params, _run))

    @mcp.tool()
    def analyze_existing_tasks_for_schema() -> str:
        """Analyse existing Taskwarrior tasks for field/schema inference.

        This is read-only. It returns field occurrence ratios, likely enum
        values, likely required fields, projects, tags, and detected UDAs.
        """
        return json.dumps(
            _audit_call(
                reg,
                "analyze_existing_tasks_for_schema",
                {},
                lambda: onboarding_analyze_existing_tasks(reg.task),
            )
        )

    @mcp.tool()
    def analyze_taxonomy_file(path: str) -> str:
        """Parse a taxonomy Markdown file and return extracted semantics.

        This is read-only. It extracts fields, descriptions, allowed values,
        conditional requirements, and phase transitions when possible.
        """
        return json.dumps(
            _audit_call(
                reg,
                "analyze_taxonomy_file",
                {"path": path},
                lambda: onboarding_analyze_taxonomy_file(path),
            )
        )

    @mcp.tool()
    def generate_initial_schema_preview(
        taxonomy_path: str = "",
        project_dir: str = "",
        schema_name: str = "",
    ) -> str:
        """Generate a reviewable schema TOML preview without writing files.

        The preview combines existing task analysis and, when available, a
        taxonomy Markdown file. The returned schema_toml should be reviewed by
        the user before calling save_initial_schema.
        """
        params = {
            "taxonomy_path": taxonomy_path or None,
            "project_dir": project_dir or None,
            "schema_name": schema_name or None,
        }
        return json.dumps(
            _audit_call(
                reg,
                "generate_initial_schema_preview",
                params,
                lambda: onboarding_generate_schema_preview(
                    config=reg.config,
                    task_cli=reg.task,
                    taxonomy_path=taxonomy_path or None,
                    project_dir=project_dir or None,
                    schema_name=schema_name or None,
                ),
            )
        )

    @mcp.tool()
    def save_initial_schema(
        schema_toml: str,
        taxonomy_path: str = "",
        output_path: str = "",
        role: str = "",
        overwrite: bool = False,
        update_config: bool = True,
    ) -> str:
        """Persist an approved generated schema and optionally update config.toml.

        This writes schema/config files but does not mutate Taskwarrior tasks.
        Call generate_initial_schema_preview first and show the user a summary
        before saving.

        ``role`` is the MCP permission level to persist in config.toml. Pass
        one of CONTRIBUTOR / GENERATOR / MANAGER (see propose_initialization_options
        for descriptions). When omitted, CONTRIBUTOR is persisted so the server
        leaves onboarding mode on next restart. Without persisting a role the
        server stays stuck on the onboarding tool surface.
        """
        # Don't audit-log the full schema_toml blob — it can be many KB.
        params = {
            "schema_toml_length": len(schema_toml),
            "taxonomy_path": taxonomy_path or None,
            "output_path": output_path or None,
            "role": role or None,
            "overwrite": overwrite,
            "update_config": update_config,
        }
        result = _audit_call(
            reg,
            "save_initial_schema",
            params,
            lambda: onboarding_save_initial_schema(
                schema_toml=schema_toml,
                taxonomy_path=taxonomy_path or None,
                output_path=output_path or None,
                role=role or None,
                overwrite=overwrite,
                update_config=update_config,
            ),
        )
        if isinstance(result, dict) and result.get("success"):
            reg.reload()
            result["restart_required"] = False
        return json.dumps(result)

    @mcp.tool()
    def list_preset_schemas() -> str:
        """List bundled preset schemas (minimal, gtd, kanban, scrum, ...).

        Read-only. Returns each preset's name, file path, version and
        description as parsed from the schema's [meta] block. Use this
        before calling use_preset_schema so the user can see what is
        available without you guessing the preset names.
        """
        return json.dumps(
            _audit_call(
                reg,
                "list_preset_schemas",
                {},
                lambda: onboarding_list_preset_schemas(),
            )
        )

    @mcp.tool()
    def use_preset_schema(
        preset_name: str,
        taxonomy_path: str = "",
        output_path: str = "",
        role: str = "",
        copy: bool = False,
        overwrite: bool = False,
        update_config: bool = True,
    ) -> str:
        """Wire a bundled preset schema into the user's config.toml.

        By default this just sets ``schema = "<preset_name>"`` in config.toml
        (lowest friction; keeps using the version-controlled bundled file).
        Pass copy=true to copy the preset into output_path (or the user
        config dir) and reference that copy via schema_path — use this when
        the user wants a personal, editable copy.

        Refuses to overwrite an existing target file when copy=true unless
        overwrite=true.

        ``role`` is the MCP permission level to persist in config.toml. Pass
        one of CONTRIBUTOR / GENERATOR / MANAGER (see propose_initialization_options
        for descriptions). When omitted, CONTRIBUTOR is persisted so the server
        leaves onboarding mode on next restart. Without persisting a role the
        server stays stuck on the onboarding tool surface.
        """
        params = {
            "preset_name": preset_name,
            "taxonomy_path": taxonomy_path or None,
            "output_path": output_path or None,
            "role": role or None,
            "copy": copy,
            "overwrite": overwrite,
            "update_config": update_config,
        }
        result = _audit_call(
            reg,
            "use_preset_schema",
            params,
            lambda: onboarding_use_preset_schema(
                preset_name=preset_name,
                taxonomy_path=taxonomy_path or None,
                output_path=output_path or None,
                role=role or None,
                copy=copy,
                overwrite=overwrite,
                update_config=update_config,
            ),
        )
        if isinstance(result, dict) and result.get("success"):
            reg.reload()
            result["restart_required"] = False
        return json.dumps(result)


def _register_contributor_tools(mcp: FastMCP, reg: ToolRegistry) -> None:
    """Register CONTRIBUTOR-level tools (read + annotate + modify).

    Per ADR 19, tools are always registered; runtime gates check
    initialisation and role before executing.
    """

    @mcp.tool()
    def list_tasks(
        filters: str = "",
    ) -> str:
        """List and filter Taskwarrior tasks.

        Returns tasks as JSON. Use Taskwarrior filter syntax:
        - 'status:pending' — pending tasks
        - 'project:work' — tasks in project 'work'
        - 'phase:impl' — tasks in implementation phase
        - '+python' — tasks tagged 'python'
        Combine filters: 'status:pending project:work phase:impl'
        """
        gate = _gate_initialized(reg)
        if gate:
            return gate
        return json.dumps(reg.list_tasks(filters))

    @mcp.tool()
    def get_task(uuid: str) -> str:
        """Get a single task by its UUID.

        Returns full task details including all fields and annotations.
        Always use UUID (not local ID) for reliable identification.
        """
        gate = _gate_initialized(reg)
        if gate:
            return gate
        return json.dumps(reg.get_task(uuid))

    @mcp.tool()
    def search_tasks(
        query: str,
        field: str = "description",
    ) -> str:
        """Search tasks by a specific field.

        Args:
            query: The search term.
            field: Field to search in. Options: 'description',
                   'project', 'tags', or any UDA name.
        """
        gate = _gate_initialized(reg)
        if gate:
            return gate
        return json.dumps(reg.search_tasks(query, field))

    @mcp.tool()
    def annotate_task(uuid: str, annotation: str, dry_run: bool | None = None) -> str:
        """Add an annotation (note, link, or context) to a task.

        Annotations are the preferred way to add narrative context,
        rationale, and reference links to tasks.
        """
        gate = _gate_initialized(reg)
        if gate:
            return gate
        return json.dumps(reg.annotate_task(uuid, annotation, dry_run))

    @mcp.tool()
    def modify_task(
        uuid: str,
        fields: dict[str, str | list[str]],
        dry_run: bool | None = None,
    ) -> str:
        """Modify fields on an existing task.

        Args:
            uuid: Task UUID.
            fields: Field:value pairs to modify.
                    Example: {"priority": "H", "phase": "impl"}
                    For adding tags: {"tags_add": ["python"]}
                    For removing tags: {"tags_remove": ["old"]}
        """
        gate = _gate_initialized(reg)
        if gate:
            return gate
        return json.dumps(reg.modify_task(uuid, fields, dry_run))

    @mcp.tool()
    def start_task(uuid: str, dry_run: bool | None = None) -> str:
        """Start working on a task.

        If Timewarrior hook is installed, this also starts
        time tracking with the task's tags.
        """
        gate = _gate_initialized(reg)
        if gate:
            return gate
        return json.dumps(reg.start_task(uuid, dry_run))

    @mcp.tool()
    def stop_task(uuid: str, dry_run: bool | None = None) -> str:
        """Stop working on a task.

        If Timewarrior hook is installed, this also stops
        time tracking for the task.
        """
        gate = _gate_initialized(reg)
        if gate:
            return gate
        return json.dumps(reg.stop_task(uuid, dry_run))

    @mcp.tool()
    def get_projects() -> str:
        """List all project names in the Taskwarrior database."""
        gate = _gate_initialized(reg)
        if gate:
            return gate
        return json.dumps(reg.get_projects())

    @mcp.tool()
    def get_tags() -> str:
        """List all tags used in the Taskwarrior database."""
        gate = _gate_initialized(reg)
        if gate:
            return gate
        return json.dumps(reg.get_tags())

    @mcp.tool()
    def get_active_context() -> str:
        """Show the currently active Taskwarrior context filter."""
        gate = _gate_initialized(reg)
        if gate:
            return gate
        return json.dumps(reg.get_active_context())

    @mcp.tool()
    def get_schema_info() -> str:
        """Get the active task schema definition.

        Returns field definitions, required fields, allowed values,
        and conditional requirements. Use this to understand what
        fields are available before creating or modifying tasks.
        """
        gate = _gate_initialized(reg)
        if gate:
            return gate
        return json.dumps(reg.get_schema_info())

    @mcp.tool()
    def get_task_report(report_name: str, filters: str = "") -> str:
        """Run a named Taskwarrior report with optional filters.

        Examples:
        - report_name='next'
        - report_name='blocked', filters='project:work'
        """
        gate = _gate_initialized(reg)
        if gate:
            return gate
        return json.dumps(reg.get_task_report(report_name, filters))

    @mcp.tool()
    def get_time_summary(period: str = ":day") -> str:
        """Get Timewarrior time tracking summary.

        Args:
            period: Time period — ':day', ':week', ':month',
                    or a date range like '2026-05-01 - 2026-05-25'.
        """
        gate = _gate_initialized(reg)
        if gate:
            return gate
        return json.dumps(reg.timew_summary(period))

    @mcp.tool()
    def get_time_status() -> str:
        """Check if Timewarrior is currently tracking time."""
        gate = _gate_initialized(reg)
        if gate:
            return gate
        return json.dumps(reg.timew_status())

    # -----------------------------------------------------------------------
    # Post-onboarding reconfiguration (ADR 17)
    #
    # Schema / taxonomy mutation: allowed at any role (changes the lens,
    # not the capabilities).  Role change: downgrade only — self-elevation
    # is forbidden by design.  All three audit-log every successful and
    # every failed call so the trail of LLM-driven config mutations is
    # queryable.  See ADR 17 for the threat model.
    #
    # Uses the shared ``_audit_call`` helper (consolidated in v0.3.2 — the
    # bespoke ``_audit_reconfigure`` that lived here was retired so reconfigure
    # tools and onboarding tools share one audit envelope).
    # -----------------------------------------------------------------------

    @mcp.tool()
    def set_active_schema(
        schema_name: str = "",
        schema_path: str = "",
        dry_run: bool = False,
    ) -> str:
        """Switch the active task schema.

        Exactly one of ``schema_name`` (a bundled preset such as
        'minimal' / 'gtd' / 'kanban' / 'scrum') or ``schema_path``
        (an absolute path to a custom TOML schema) must be provided.

        Set ``dry_run=true`` to validate the inputs and preview the
        config write without touching ``config.toml`` — useful for
        confirming a preset name spells correctly or a schema_path
        exists before committing. Returns code="dry_run" per ADR 14.

        Updates config.toml and triggers an in-process reload so the
        change takes effect immediately (ADR 19). Does not mutate any
        Taskwarrior tasks. Available at CONTRIBUTOR level and above —
        switching the validation lens is a horizontal move, not a
        privilege change (ADR 17).
        """
        gate = _gate_initialized(reg)
        if gate:
            return gate
        params = {
            "schema_name": schema_name or None,
            "schema_path": schema_path or None,
            "dry_run": dry_run,
        }
        result = _audit_call(
            reg,
            "set_active_schema",
            params,
            lambda: onboarding_reconfigure_active_schema(
                schema_name=schema_name or None,
                schema_path=schema_path or None,
                dry_run=dry_run,
            ),
        )
        if not dry_run and isinstance(result, dict) and result.get("success"):
            reg.reload()
            result["restart_required"] = False
        return json.dumps(result)

    @mcp.tool()
    def set_taxonomy_path(path: str, dry_run: bool = False) -> str:
        """Update the taxonomy file path persisted in config.toml.

        The taxonomy informs the model's interpretation of task
        semantics. The target path must exist and be a regular file;
        the tool refuses non-existent or directory targets to prevent
        silently disabling taxonomy awareness.

        Set ``dry_run=true`` to validate the path and preview the
        config write without touching ``config.toml``. Returns
        code="dry_run" per ADR 14.

        Takes effect on next MCP server restart. Available at
        CONTRIBUTOR level (informational input, not a capability).
        """
        gate = _gate_initialized(reg)
        if gate:
            return gate
        result = _audit_call(
            reg,
            "set_taxonomy_path",
            {"path": path, "dry_run": dry_run},
            lambda: onboarding_reconfigure_taxonomy_path(path, dry_run=dry_run),
        )
        if not dry_run and isinstance(result, dict) and result.get("success"):
            reg.reload()
            result["restart_required"] = False
        return json.dumps(result)

    @mcp.tool()
    def set_role(target_role: str, dry_run: bool = False) -> str:
        """Change the persisted MCP role — DOWNGRADE ONLY.

        Valid roles: CONTRIBUTOR, GENERATOR, MANAGER (cumulative;
        see ADR 5). This tool will set the persisted role to
        ``target_role`` IF AND ONLY IF its level is less than or
        equal to the currently-loaded role.

        Set ``dry_run=true`` to validate inputs (including the
        elevation refusal check) and preview the config write without
        touching ``config.toml``. Refusal-class errors
        (role_elevation_forbidden) trigger regardless of dry_run — a
        forbidden elevation is forbidden whether or not the LLM was
        just "asking". Returns code="dry_run" on legitimate previews.

        Self-elevation via MCP is forbidden by design (ADR 17).
        Attempts to elevate return a structured error with
        error_code='role_elevation_forbidden'. To elevate, run
        './dev.sh init --role <ROLE>' from a shell or hand-edit
        ~/.config/taskchampion-mcp/config.toml and restart the
        MCP server.

        Takes effect on next MCP server restart.
        """
        gate = _gate_initialized(reg)
        if gate:
            return gate
        params = {
            "target_role": target_role,
            "current_role": reg.config.role,
            "dry_run": dry_run,
        }
        result = _audit_call(
            reg,
            "set_role",
            params,
            lambda: onboarding_reconfigure_role(
                current_role=reg.config.role,
                target_role=target_role,
                dry_run=dry_run,
            ),
        )
        if not dry_run and isinstance(result, dict) and result.get("success"):
            reg.reload()
            result["restart_required"] = False
        return json.dumps(result)


def _register_generator_tools(mcp: FastMCP, reg: ToolRegistry) -> None:
    """Register GENERATOR-level tools (create).

    Per ADR 19, always registered; runtime gate checks GENERATOR role.
    """

    @mcp.tool()
    def create_task(
        description: str,
        project: str = "",
        priority: str = "",
        tags: list[str] | None = None,
        due: str = "",
        extra_fields: dict[str, str] | None = None,
        dry_run: bool | None = None,
    ) -> str:
        """Create a new Taskwarrior task with schema validation.

        Args:
            description: Task description (imperative, actionable).
            project: Project name in dot-notation (e.g. 'work.acme').
            priority: H, M, or L.
            tags: List of tags (e.g. ["python", "docker"]).
            due: Due date (ISO format or Taskwarrior relative like 'eow').
            extra_fields: Additional UDA fields.
                Example: {"scope": "personal", "phase": "impl"}

        Call get_schema_info first to see required and available fields.
        """
        gate = _gate_role(reg, Role.GENERATOR)
        if gate:
            return gate
        tag_list = [t.strip() for t in tags if t and t.strip()] if tags else None
        udas: dict[str, str] = dict(extra_fields or {})
        return json.dumps(
            reg.create_task(
                description=description,
                project=project,
                priority=priority,
                tags=tag_list,
                due=due,
                dry_run=dry_run,
                **udas,
            )
        )

    @mcp.tool()
    def create_subtask(
        parent_uuid: str,
        description: str,
        project: str = "",
        priority: str = "",
        tags: list[str] | None = None,
        due: str = "",
        extra_fields: dict[str, str] | None = None,
        dry_run: bool | None = None,
    ) -> str:
        """Create a subtask with depends: linking to a parent task.

        Args:
            parent_uuid: UUID of the parent task this subtask depends on.
            description: Task description (imperative, actionable).
            project: Project name in dot-notation (e.g. 'work.acme').
            priority: H, M, or L.
            tags: List of tags (e.g. ["python", "docker"]).
            due: Due date (ISO format or Taskwarrior relative like 'eow').
            extra_fields: Additional UDA fields.
                Example: {"scope": "personal", "phase": "impl"}

        The subtask will have a 'depends' field set to the parent UUID.
        Call get_schema_info first to see required and available fields.
        """
        gate = _gate_role(reg, Role.GENERATOR)
        if gate:
            return gate
        tag_list = [t.strip() for t in tags if t and t.strip()] if tags else None
        udas: dict[str, str] = dict(extra_fields or {})
        return json.dumps(
            reg.create_subtask(
                parent_uuid=parent_uuid,
                description=description,
                project=project,
                priority=priority,
                tags=tag_list,
                due=due,
                dry_run=dry_run,
                **udas,
            )
        )

    @mcp.tool()
    def batch_create_tasks(
        tasks: list[dict[str, object]],
        dry_run: bool | None = None,
    ) -> str:
        """Create multiple tasks in a single call with per-task result reporting.

        Prefer this over repeated create_task calls when creating several
        independent tasks at once. Use create_subtask instead when tasks must
        be linked to a parent via depends. Requires GENERATOR role.

        NON-ATOMIC: tasks are created sequentially. If task N fails, tasks
        0..N-1 are already committed — there is no rollback. A rate-limit
        hit stops the batch early; partial results are returned with the
        stopping index and created/failed counts.

        dry_run=true previews all entries without writing to Taskwarrior.
        Each preview entry confirms field validation without mutation.

        Each entry in `tasks` accepts:
          description (str, required), project (str), priority (H/M/L),
          tags (list[str] or comma-separated str), due (ISO or TW relative
          e.g. eow/eom), extra_fields (dict of UDA key/value pairs).

        Call get_schema_info first to confirm required and available fields.
        """
        gate = _gate_role(reg, Role.GENERATOR)
        if gate:
            return gate
        return json.dumps(reg.batch_create_tasks(tasks=tasks, dry_run=dry_run))


def _register_manager_tools(mcp: FastMCP, reg: ToolRegistry) -> None:
    """Register MANAGER-level tools (lifecycle control).

    Per ADR 19, always registered; runtime gate checks MANAGER role.
    """

    @mcp.tool()
    def complete_task(
        uuid: str,
        dry_run: bool | None = None,
        confirm_token: str = "",
    ) -> str:
        """Mark a task as done (completed).

        Args:
            uuid: Task UUID.
            dry_run: If true, preview the action without executing.

        Destructive operation — may require confirmation depending
        on server configuration.
        """
        gate = _gate_role(reg, Role.MANAGER)
        if gate:
            return gate
        return json.dumps(reg.complete_task(uuid, dry_run, confirm_token))

    @mcp.tool()
    def delete_task(
        uuid: str,
        dry_run: bool | None = None,
        confirm_token: str = "",
    ) -> str:
        """Delete a task from Taskwarrior.

        Args:
            uuid: Task UUID.
            dry_run: If true, preview the action without executing.

        Destructive operation — may require confirmation depending
        on server configuration. Prefer completing over deleting.
        """
        gate = _gate_role(reg, Role.MANAGER)
        if gate:
            return gate
        return json.dumps(reg.delete_task(uuid, dry_run, confirm_token))

    @mcp.tool()
    def undo_last_action(dry_run: bool | None = None, confirm_token: str = "") -> str:
        """Undo the last Taskwarrior operation.

        Reverts the most recent change. Use with caution.
        """
        gate = _gate_role(reg, Role.MANAGER)
        if gate:
            return gate
        return json.dumps(reg.undo(dry_run=dry_run, confirm_token=confirm_token))

    @mcp.tool()
    def sync_tasks(dry_run: bool | None = None) -> str:
        """Trigger task sync with the TaskChampion sync server.

        Pushes local changes and pulls remote changes.
        """
        gate = _gate_role(reg, Role.MANAGER)
        if gate:
            return gate
        return json.dumps(reg.sync(dry_run=dry_run))

    @mcp.tool()
    def bulk_modify(
        filters: str,
        fields: dict[str, str | list[str]],
        dry_run: bool | None = None,
        confirm_token: str = "",
    ) -> str:
        """Modify all tasks matching filters.

        Supports dry-run previews and confirmation for high-impact changes.
        """
        gate = _gate_role(reg, Role.MANAGER)
        if gate:
            return gate
        return json.dumps(
            reg.bulk_modify(
                filters=filters,
                fields=fields,
                dry_run=dry_run,
                confirm_token=confirm_token,
            )
        )


# ---------------------------------------------------------------------------
# Runtime reload + capability introspection (ADR 19 / ADR 21a)
# ---------------------------------------------------------------------------


def _register_reload_tool(mcp: FastMCP, reg: ToolRegistry) -> None:
    """Register the reload_configuration and get_runtime_capabilities tools."""

    @mcp.tool()
    def reload_configuration() -> str:
        """Re-read config.toml from disk and refresh all runtime state.

        Use this after hand-editing config.toml to pick up changes without
        restarting the IDE.  Reloads: config, schema, rate limiter, audit
        logger, Taskwarrior/Timewarrior CLI wrappers.

        Onboarding write tools (save_initial_schema, use_preset_schema) and
        reconfigure tools (set_active_schema, set_taxonomy_path, set_role)
        auto-reload on success, so you rarely need to call this directly.
        """
        params: dict[str, Any] = {}
        return json.dumps(
            _audit_call(
                reg,
                "reload_configuration",
                params,
                lambda: _do_reload(reg),
            )
        )

    @mcp.tool()
    def get_runtime_capabilities() -> str:
        """Return the server's current mode, role, schema, and callable tool groups.

        Call this first to understand what the server can do right now.
        The response tells you which tool groups are callable and which
        are blocked (with the reason code).
        """
        params: dict[str, Any] = {}
        return json.dumps(
            _audit_call(
                reg,
                "get_runtime_capabilities",
                params,
                lambda: _build_capabilities(reg),
            )
        )


def _do_reload(reg: ToolRegistry) -> dict[str, Any]:
    """Execute the reload and return a structured result."""
    reloaded = reg.reload()
    return {
        "success": True,
        "code": "ok",
        "reloaded": reloaded,
        "restart_required": False,
        "initialized": reg.initialized,
        "role": reg.config.role,
        "schema_name": reg.schema.name,
        "message": f"Configuration reloaded ({len(reloaded)} subsystems refreshed).",
    }


def _build_capabilities(reg: ToolRegistry) -> dict[str, Any]:
    """Build the ADR 21a runtime capabilities payload."""
    mode = "operational" if reg.initialized else "onboarding"
    role = reg.config.role if reg.initialized else None

    callable_groups: list[dict[str, Any]] = []
    uncallable_groups: list[dict[str, Any]] = []

    # Onboarding tools are always callable
    callable_groups.append({
        "group": "onboarding",
        "tools": [
            "get_initialization_status",
            "propose_initialization_options",
            "analyze_existing_tasks_for_schema",
            "analyze_taxonomy_file",
            "generate_initial_schema_preview",
            "save_initial_schema",
            "list_preset_schemas",
            "use_preset_schema",
        ],
    })

    # Introspection tools are always callable
    callable_groups.append({
        "group": "introspection",
        "tools": ["reload_configuration", "get_runtime_capabilities"],
    })

    if reg.initialized:
        callable_groups.append({
            "group": "contributor",
            "tools": [
                "list_tasks", "get_task", "search_tasks", "annotate_task",
                "modify_task", "start_task", "stop_task", "get_projects",
                "get_tags", "get_active_context", "get_schema_info",
                "get_task_report", "get_time_summary", "get_time_status",
            ],
        })
        callable_groups.append({
            "group": "reconfigure",
            "tools": ["set_active_schema", "set_taxonomy_path", "set_role"],
        })

        if Role.has_permission(reg.config.role, Role.GENERATOR):
            callable_groups.append({
                "group": "generator",
                "tools": ["create_task", "create_subtask", "batch_create_tasks"],
            })
        else:
            uncallable_groups.append({
                "group": "generator",
                "tools": ["create_task", "create_subtask", "batch_create_tasks"],
                "uncallable_reason": "role_insufficient",
                "detail": f"Requires GENERATOR; current role is {reg.config.role}.",
            })

        if Role.has_permission(reg.config.role, Role.MANAGER):
            callable_groups.append({
                "group": "manager",
                "tools": [
                    "complete_task", "delete_task", "undo_last_action",
                    "sync_tasks", "bulk_modify",
                ],
            })
        else:
            uncallable_groups.append({
                "group": "manager",
                "tools": [
                    "complete_task", "delete_task", "undo_last_action",
                    "sync_tasks", "bulk_modify",
                ],
                "uncallable_reason": "role_insufficient",
                "detail": f"Requires MANAGER; current role is {reg.config.role}.",
            })
    else:
        for group_name, tools, reason in [
            ("contributor", [
                "list_tasks", "get_task", "search_tasks", "annotate_task",
                "modify_task", "start_task", "stop_task", "get_projects",
                "get_tags", "get_active_context", "get_schema_info",
                "get_task_report", "get_time_summary", "get_time_status",
            ], "schema_unset"),
            ("reconfigure", [
                "set_active_schema", "set_taxonomy_path", "set_role",
            ], "schema_unset"),
            ("generator", [
                "create_task", "create_subtask", "batch_create_tasks",
            ], "schema_unset"),
            ("manager", [
                "complete_task", "delete_task", "undo_last_action",
                "sync_tasks", "bulk_modify",
            ], "schema_unset"),
        ]:
            uncallable_groups.append({
                "group": group_name,
                "tools": tools,
                "uncallable_reason": reason,
                "detail": "Server is not initialised; complete onboarding first.",
            })

    return {
        "success": True,
        "mode": mode,
        "role": role,
        "schema": {
            "name": reg.schema.name,
            "version": reg.schema.version,
        } if reg.initialized else None,
        "integrations": {
            "timewarrior": reg.timew is not None,
        },
        "callable_tool_groups": callable_groups,
        "uncallable_tool_groups": uncallable_groups,
    }


# ---------------------------------------------------------------------------
# Instructions for LLM
# ---------------------------------------------------------------------------


def _build_instructions(
    config: ServerConfig,
    schema: TaskSchema,
    tw_version: str | None,
    *,
    onboarding_required: bool,
) -> str:

    if onboarding_required:
        return "\n".join(
            [
                (
                    "You are interacting with a Taskwarrior 3.x task database via the "
                    "TaskChampion MCP server."
                ),
                "",
                "This MCP installation is visible, but it is not initialised yet.",
                "",
                "The current role and schema are safe runtime fallbacks only:",
                f"- fallback role: {config.role}",
                f"- fallback schema: {schema.name} (v{schema.version})",
                f"- Taskwarrior version: {tw_version or 'unknown'}",
                "",
                (
                    "Do not present the fallback role or fallback schema as "
                    "user-selected configuration."
                ),
                "Do not claim normal task-management capabilities yet.",
                (
                    "Do not read, modify, annotate, create, complete, delete, "
                    "undo, or sync tasks until onboarding is complete."
                ),
                "",
                "Your first task is to help the user initialise the MCP configuration.",
                "",
                "Initialisation decisions to guide:",
                "1. MCP role scope: CONTRIBUTOR, GENERATOR, or MANAGER.",
                (
                    "2. Schema source: generated from taxonomy, inferred from "
                    "existing tasks, hybrid, or bundled preset."
                ),
                "3. Optional taxonomy path / workflow taxonomy.",
                "",
                "Available onboarding flow:",
                "- call get_initialization_status first",
                "- then call propose_initialization_options",
                (
                    "- for taxonomy or task inference: "
                    "generate_initial_schema_preview, show the user a summary, "
                    "then save_initial_schema only after approval"
                ),
                (
                    "- for preset selection: list_preset_schemas, "
                    "let the user choose, then use_preset_schema"
                ),
                "",
                "Never silently invent workflow semantics.",
                "Never save a schema the user has not approved.",
                "",
                "MANDATORY UNINITIALISED RESPONSE RULE:",
                (
                    "If onboarding_required is true, every user-facing answer "
                    "about this server's availability MUST include:"
                ),
                "1. that the server is visible but not initialised;",
                "2. that fallback role/schema are not user-selected;",
                "3. a concrete onboarding menu with role and schema-source choices;",
                "4. a request for the user's first choice.",
            ]
        )

    lines = [
        "You are interacting with a Taskwarrior 3.x task database via the TaskChampion MCP server.",
        "",
        f"Your role: {config.role}",
        f"Schema: {schema.name} (v{schema.version})",
        f"Taskwarrior version: {tw_version or 'unknown'}",
        "",
    ]

    if config.role == Role.CONTRIBUTOR:
        lines.append(
            "You can READ, ANNOTATE, MODIFY, START, and STOP existing tasks. "
            "You CANNOT create new tasks or complete/delete them."
        )
    elif config.role == Role.GENERATOR:
        lines.append(
            "You can READ, ANNOTATE, MODIFY, START, STOP, and CREATE tasks. "
            "You CANNOT complete or delete tasks."
        )
    elif config.role == Role.MANAGER:
        lines.append(
            "You have FULL ACCESS: read, annotate, modify, create, "
            "complete, delete, undo_last_action, and sync_tasks."
        )

    lines += [
        "",
        "FIRST-RUN / TAXONOMY RULES:",
        "- If task semantics are unclear, call get_initialization_status first.",
        (
            "- If onboarding is needed, call propose_initialization_options "
            "and present the choices to the user."
        ),
        (
            "- For taxonomy / task-inference flows: generate_initial_schema_preview, "
            "show the TOML to the user, then save_initial_schema."
        ),
        (
            "- For preset selection: list_preset_schemas, let the user pick a name, "
            "then use_preset_schema."
        ),
        (
            "- Never silently invent workflow semantics. "
            "Never save a schema the user has not approved."
        ),
        "",
        "IMPORTANT RULES:",
        "- Always use task UUIDs, never local IDs.",
        "- Call get_schema_info before creating tasks to see required fields.",
        "- Prefer annotations for narrative context.",
        "- Do not modify gen_model/gen_persona/gen_harness on existing tasks.",
    ]

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    """CLI entry point for taskchampion-mcp-server."""
    _configure_logging()
    parser = _build_parser()
    args = parser.parse_args()

    cli_overrides: dict[str, tuple[Any, str]] = {}
    if args.role:
        cli_overrides["server.role"] = (args.role, "cli:--role")
    if args.schema:
        cli_overrides["server.schema"] = (args.schema, "cli:--schema")

    config_path = Path(args.config).expanduser() if args.config else None
    cfg, sources = load_config_with_sources(
        path=config_path,
        cwd=Path.cwd(),
        cli_overrides=cli_overrides,
    )

    if args.config_dump:
        print(json.dumps(dump_effective_config(cfg, sources), indent=2, sort_keys=True))
        return

    guidance = _interactive_terminal_guidance(
        is_tty=sys.stdin.isatty(), force=args.force
    )
    if guidance is not None:
        print(guidance, file=sys.stderr)
        raise SystemExit(2)

    mcp = create_server(config=cfg, config_path=config_path)
    mcp.run(transport="stdio")


def _interactive_terminal_guidance(*, is_tty: bool, force: bool) -> str | None:
    """Return guidance text when the server is started in an interactive shell.

    This is a stdio MCP server: it expects JSON-RPC messages on stdin from an
    MCP client. When stdin is an interactive terminal, the process otherwise
    appears to hang (blocked reading stdin) and then emits a confusing
    ``1 validation error for JSONRPCMessage`` from the MCP SDK on the first
    keystroke. Detect that case and return actionable guidance instead.

    Returns ``None`` when stdin is wired to a client (not a TTY) or when
    ``--force`` is set, meaning the server should start normally.
    """
    if force or not is_tty:
        return None
    return (
        "taskchampion-mcp is a stdio MCP server; it does not run interactively.\n"
        "It expects JSON-RPC messages on stdin from an MCP client, so launching\n"
        "it directly in a terminal will appear to hang and then report\n"
        "'1 validation error for JSONRPCMessage' on the first keystroke.\n\n"
        "Configure it in your MCP client instead, e.g. (Claude Desktop / Code):\n"
        '  {"command": "uvx", "args": ["taskchampion-mcp"]}\n\n'
        "To start the server anyway (for debugging), pass --force."
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="TaskChampion MCP server")
    parser.add_argument(
        "--config",
        default="",
        help="Path to user config TOML (defaults to XDG path).",
    )
    parser.add_argument(
        "--role",
        choices=Role._HIERARCHY,
        help="Override effective role for this process.",
    )
    parser.add_argument(
        "--schema",
        default="",
        help="Override effective schema name for this process.",
    )
    parser.add_argument(
        "--config-dump",
        action="store_true",
        help="Print effective config with provenance as JSON and exit.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Start the stdio server even when stdin is an interactive terminal.",
    )
    return parser


if __name__ == "__main__":
    main()
