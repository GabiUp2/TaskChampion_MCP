"""First-run schema initialization wizard (IDEA-003) — thin CLI layer.

Invoked via ``./dev.sh init`` or ``python -m taskchampion_mcp.init_schema``.

This module is *intentionally thin*: it adds interactive prompts and coloured
terminal output, but every decision and every file mutation goes through the
public API in :mod:`taskchampion_mcp.onboarding`.  That keeps the CLI wizard
and the runtime MCP onboarding tools behaviourally identical.

The wizard supports three branches, mirroring the options proposed by
:func:`onboarding.propose_initialization_options`:

1. Generate a schema from existing tasks and/or a taxonomy file.
2. Pick a bundled preset (``--preset <name>`` or interactive list).
3. Abort, leaving the server on the default minimal schema.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from taskchampion_mcp.cli import TaskwarriorCLI
from taskchampion_mcp.config import Role, load_config
from taskchampion_mcp.onboarding import (
    _default_schema_path,
    analyze_existing_tasks,
    default_schema_name_for_source,
    generate_schema_preview,
    get_initialization_status,
    list_preset_schemas,
    resolve_taxonomy_path,
    save_initial_schema,
    use_preset_schema,
)

# ---------------------------------------------------------------------------
# Output helpers
# ---------------------------------------------------------------------------

_CYAN = "\033[0;36m"
_GREEN = "\033[0;32m"
_YELLOW = "\033[1;33m"
_RED = "\033[0;31m"
_NC = "\033[0m"


def _info(msg: str) -> None:
    print(f"{_CYAN}[INFO]{_NC}  {msg}")


def _ok(msg: str) -> None:
    print(f"{_GREEN}[OK]{_NC}    {msg}")


def _warn(msg: str) -> None:
    print(f"{_YELLOW}[WARN]{_NC}  {msg}")


def _fail(msg: str) -> None:
    print(f"{_RED}[FAIL]{_NC}  {msg}")


def _prompt(question: str, default: str = "") -> str:
    suffix = f" [{default}]" if default else ""
    answer = input(f"  {question}{suffix}: ").strip()
    return answer or default


def _confirm(question: str, default_yes: bool = False) -> bool:
    suffix = "[Y/n]" if default_yes else "[y/N]"
    answer = input(f"  {question} {suffix}: ").strip().lower()
    if not answer:
        return default_yes
    return answer in ("y", "yes")


def _resolve_role(
    requested: str | None,
    *,
    non_interactive: bool,
    already_configured: bool,
) -> str | None:
    """Resolve which role to persist via onboarding.

    - ``requested`` (e.g. from ``--role``): validated and returned.
    - non-interactive without a request: returns None so onboarding picks its
      CONTRIBUTOR default.
    - interactive without a request: prompt the user, defaulting to
      CONTRIBUTOR (or the already-configured role, when one exists).
    """
    if requested:
        try:
            return Role.validate(requested)
        except ValueError as exc:
            _fail(str(exc))
            raise SystemExit(2) from exc

    if non_interactive:
        return None

    options = Role._HIERARCHY
    default = Role.CONTRIBUTOR
    if already_configured:
        _info("Role is already set in config.toml; keep current unless you want to change it.")
    _info("Select MCP permission level (role):")
    for idx, name in enumerate(options, start=1):
        marker = " (default)" if name == default else ""
        print(f"    {idx}. {name}{marker}")
    answer = _prompt("Enter role name or number", default=default)
    if answer.isdigit():
        idx = int(answer) - 1
        if not 0 <= idx < len(options):
            _fail(f"Invalid selection: {answer}")
            raise SystemExit(2)
        return options[idx]
    try:
        return Role.validate(answer)
    except ValueError as exc:
        _fail(str(exc))
        raise SystemExit(2) from exc


# ---------------------------------------------------------------------------
# Generated-schema branch
# ---------------------------------------------------------------------------


def _run_generate_branch(
    *,
    task_cli: TaskwarriorCLI,
    project_dir: str | None,
    taxonomy_path: str | None,
    output_path: str | None,
    schema_name: str | None,
    role: str | None,
    non_interactive: bool,
) -> bool:
    """Generate-and-save flow that delegates entirely to onboarding.*."""
    config = load_config()

    resolved_taxonomy = resolve_taxonomy_path(
        config=config,
        taxonomy_path=taxonomy_path,
        project_dir=project_dir,
    )

    # Confirm taxonomy choice interactively
    if not taxonomy_path and resolved_taxonomy is not None and not non_interactive:
        _ok(f"Detected taxonomy file: {resolved_taxonomy}")
        if not _confirm("Use this file?", default_yes=True):
            alt = _prompt("Enter path to taxonomy file (or Enter to skip)")
            if alt:
                candidate = Path(alt).expanduser().resolve()
                if not candidate.exists():
                    _warn(f"File not found: {candidate}. Skipping taxonomy.")
                    resolved_taxonomy = None
                else:
                    resolved_taxonomy = candidate
            else:
                resolved_taxonomy = None
    elif resolved_taxonomy is None and not non_interactive:
        _warn("No taxonomy file detected.")
        alt = _prompt("Enter path to taxonomy file (or Enter to skip)")
        if alt:
            candidate = Path(alt).expanduser().resolve()
            if not candidate.exists():
                _warn(f"File not found: {candidate}. Skipping taxonomy.")
            else:
                resolved_taxonomy = candidate

    if resolved_taxonomy:
        _info(f"Using taxonomy: {resolved_taxonomy}")
    else:
        _info("Proceeding without taxonomy file.")

    # Sanity check: warn early if neither tasks nor taxonomy are available.
    task_report = analyze_existing_tasks(task_cli)
    task_count = int(task_report.get("task_count") or 0)
    if task_report.get("error"):
        _warn(f"Task export failed: {task_report.get('message')}")
    elif task_count:
        _ok(f"Found {task_count} tasks.")
    else:
        _warn("No existing tasks found. Schema will be based on taxonomy only.")

    if task_count == 0 and resolved_taxonomy is None:
        _fail("No tasks and no taxonomy file. Cannot generate a schema.")
        _info("Re-run with --preset <name> to install a bundled preset instead.")
        return False

    # Generate preview via the shared onboarding API.
    effective_name = schema_name or default_schema_name_for_source(
        has_taxonomy=resolved_taxonomy is not None,
        has_tasks=task_count > 0,
    )
    _info("Generating schema...")
    preview = generate_schema_preview(
        config=config,
        task_cli=task_cli,
        taxonomy_path=str(resolved_taxonomy) if resolved_taxonomy else None,
        project_dir=project_dir,
        schema_name=effective_name,
    )
    if not preview.get("success"):
        _fail(preview.get("message", "Schema preview failed."))
        return False

    # Resolve output target and confirm overwrite.
    out_path: Path | None = Path(output_path).expanduser() if output_path else None
    overwrite = False
    if out_path is None:
        out_path = _default_schema_path()

    if out_path.exists():
        if non_interactive:
            overwrite = True
        else:
            if not _confirm(f"Schema file exists: {out_path}\n  Overwrite?", default_yes=False):
                _info("Aborted. Existing schema kept.")
                return False
            overwrite = True

    save_result = save_initial_schema(
        schema_toml=preview["schema_toml"],
        taxonomy_path=str(resolved_taxonomy) if resolved_taxonomy else None,
        output_path=str(out_path),
        role=role,
        overwrite=overwrite,
        update_config=True,
    )
    if not save_result.get("success"):
        _fail(save_result.get("message", "Saving schema failed."))
        return False

    _ok(f"Schema saved to: {save_result['schema_path']}")
    _ok(f"Config updated: {save_result['config_file']}")
    print()
    _ok("Initialisation complete!")
    print(f"  Schema:   {save_result['schema_path']}")
    if resolved_taxonomy:
        print(f"  Taxonomy: {resolved_taxonomy}")
    print(f"  Config:   {save_result['config_file']}")
    if save_result.get("role"):
        print(f"  Role:     {save_result['role']}")
    print()
    _info("Restart your MCP server to use the new schema.")
    return True


# ---------------------------------------------------------------------------
# Preset branch
# ---------------------------------------------------------------------------


def _run_preset_branch(
    *,
    preset_name: str | None,
    taxonomy_path: str | None,
    copy: bool,
    output_path: str | None,
    role: str | None,
    non_interactive: bool,
) -> bool:
    """Preset-selection flow that delegates entirely to onboarding.*."""
    listing = list_preset_schemas()
    presets = listing.get("presets") or []
    if not presets:
        _fail("No bundled preset schemas found.")
        return False

    if preset_name is None:
        if non_interactive:
            _fail("Preset branch requires --preset <name> in non-interactive mode.")
            return False
        _info("Available preset schemas:")
        for idx, item in enumerate(presets, start=1):
            description = item.get("description") or "(no description)"
            print(f"    {idx}. {item['name']:<24} {description}")
        choice = _prompt("Enter preset name (or number)", default=presets[0]["name"])
        if choice.isdigit():
            idx = int(choice) - 1
            if not 0 <= idx < len(presets):
                _fail(f"Invalid selection: {choice}")
                return False
            preset_name = presets[idx]["name"]
        else:
            preset_name = choice

    overwrite = False
    if copy and output_path:
        target = Path(output_path).expanduser()
        if target.exists():
            if non_interactive:
                overwrite = True
            else:
                if not _confirm(
                    f"Target file exists: {target}\n  Overwrite?",
                    default_yes=False,
                ):
                    _info("Aborted. Existing file kept.")
                    return False
                overwrite = True

    result = use_preset_schema(
        preset_name=preset_name,
        taxonomy_path=taxonomy_path,
        output_path=output_path,
        role=role,
        copy=copy,
        overwrite=overwrite,
        update_config=True,
    )
    if not result.get("success"):
        _fail(result.get("message", "Preset selection failed."))
        return False

    _ok(f"Preset '{result['preset_name']}' selected.")
    if result.get("copied_to"):
        _ok(f"Copied preset to: {result['copied_to']}")
    _ok(f"Config updated: {result['config_file']}")
    if result.get("role"):
        _ok(f"Role persisted: {result['role']}")
    print()
    _info("Restart your MCP server to use the new schema.")
    return True


# ---------------------------------------------------------------------------
# Main wizard
# ---------------------------------------------------------------------------


def run_init(
    project_dir: str | None = None,
    taxonomy_path: str | None = None,
    output_path: str | None = None,
    schema_name: str | None = None,
    preset: str | None = None,
    role: str | None = None,
    list_presets: bool = False,
    copy_preset: bool = False,
    non_interactive: bool = False,
) -> bool:
    """Run the first-time schema initialization wizard.

    Returns True if a schema was successfully selected/generated and the
    config updated.
    """
    print()
    _info("TaskChampion MCP — First-Run Schema Initialisation")
    print()

    # --list-presets short-circuits everything else.
    if list_presets:
        return _print_presets()

    config = load_config()

    # Read-only status snapshot via the shared API.
    task_cli = TaskwarriorCLI(
        binary=config.task_binary,
        override_rc=config.taskwarrior_override_rc,
    )
    status = get_initialization_status(
        config=config,
        task_cli=task_cli,
        project_dir=project_dir,
    )

    if not status["needs_onboarding"]:
        _warn(
            "A custom schema or taxonomy is already configured: "
            f"{status.get('custom_schema_path') or status.get('taxonomy_path')}"
        )
        if non_interactive:
            _info("Non-interactive mode: skipping (already initialised).")
            return False
        if not _confirm("Overwrite?", default_yes=False):
            _info("Keeping existing configuration. Nothing to do.")
            return False

    # Resolve role once, up front, so both branches persist it.
    resolved_role = _resolve_role(
        role,
        non_interactive=non_interactive,
        already_configured=bool(status.get("role_configured")),
    )

    # Explicit preset selection wins.
    if preset is not None:
        return _run_preset_branch(
            preset_name=preset,
            taxonomy_path=taxonomy_path,
            copy=copy_preset,
            output_path=output_path,
            role=resolved_role,
            non_interactive=non_interactive,
        )

    # Otherwise, generate from tasks/taxonomy (matching the legacy behaviour).
    return _run_generate_branch(
        task_cli=task_cli,
        project_dir=project_dir,
        taxonomy_path=taxonomy_path,
        output_path=output_path,
        schema_name=schema_name,
        role=resolved_role,
        non_interactive=non_interactive,
    )


def _print_presets() -> bool:
    listing = list_preset_schemas()
    presets = listing.get("presets") or []
    if not presets:
        _warn("No bundled preset schemas found.")
        return False
    _info(f"Bundled schemas in {listing.get('schema_dir')}:")
    for item in presets:
        description = item.get("description") or "(no description)"
        print(f"    {item['name']:<24} {description}")
    return True


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def _build_parser() -> Any:
    import argparse

    parser = argparse.ArgumentParser(
        description="TaskChampion MCP — First-run schema initialization",
    )
    parser.add_argument(
        "--project-dir",
        default=None,
        help="Project directory to search for taxonomy files",
    )
    parser.add_argument(
        "--taxonomy",
        default=None,
        help="Path to taxonomy markdown file",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Output path for the generated schema TOML (or preset copy target)",
    )
    parser.add_argument(
        "--name",
        default=None,
        help="Schema name (default: source-aware, e.g. auto_generated_from_taxonomy)",
    )
    parser.add_argument(
        "--preset",
        default=None,
        help="Name of a bundled preset schema to install (e.g. minimal, gtd, kanban, scrum)",
    )
    parser.add_argument(
        "--role",
        default=None,
        help=(
            "MCP permission level to persist in config.toml "
            "(CONTRIBUTOR / GENERATOR / MANAGER). "
            "When omitted in non-interactive mode, defaults to CONTRIBUTOR."
        ),
    )
    parser.add_argument(
        "--list-presets",
        action="store_true",
        help="List bundled preset schemas and exit",
    )
    parser.add_argument(
        "--copy-preset",
        action="store_true",
        help=(
            "When used with --preset, copy the preset into the user config dir "
            "and point schema_path at the copy instead of referencing the bundled file."
        ),
    )
    parser.add_argument(
        "--non-interactive",
        action="store_true",
        help="Run without prompts (use defaults)",
    )
    return parser


def main() -> None:
    args = _build_parser().parse_args()

    success = run_init(
        project_dir=args.project_dir,
        taxonomy_path=args.taxonomy,
        output_path=args.output,
        schema_name=args.name,
        preset=args.preset,
        role=args.role,
        list_presets=args.list_presets,
        copy_preset=args.copy_preset,
        non_interactive=args.non_interactive,
    )
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
