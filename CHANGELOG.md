# Changelog

All notable changes to this project are documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2026-05-28

### Summary

First stable release. Ships the four primary stdio targets (Claude Desktop, Windsurf, Cursor, Neovim via Claude Code CLI) with a 26-scenario per-target acceptance matrix. HTTP/SSE transport and ChatGPT/Codex targets are deferred to v1.x.

**Published:** PyPI `taskchampion-mcp==1.0.0`, MCP Registry `io.github.GabiUp2/taskchampion-mcp`, git tag [`v1.0.0`](https://github.com/GabiUp2/TaskChampion_MCP/releases/tag/v1.0.0). Pre-release: `v1.0.0-rc1` / `1.0.0rc1`. Release notes: [`docs/releases/v1.0.0.md`](docs/releases/v1.0.0.md).

### Added

- **ADR 19 — Runtime reload.** All MCP tools are registered unconditionally at startup; operational tools are gated at runtime by initialisation state and role. Config changes via MCP tools (`set_active_schema`, `set_taxonomy_path`, `set_role`, `use_preset_schema`, `save_initial_schema`) trigger in-process reload — no IDE restart needed. New `reload_configuration` tool for explicit reload after hand-editing `config.toml`.
- **ADR 21a — Runtime capability introspection.** New `get_runtime_capabilities` tool returns `mode`, `role`, `schema`, `integrations`, `callable_tool_groups`, and `uncallable_tool_groups` with reason codes. Recommended as the LLM's first tool call.
- **Per-target acceptance test harness** (`tests/targets/`) with 26 parametrised scenarios covering onboarding, post-onboarding, generator, manager, role-gating, and schema-unset flows. Per-target runners for Windsurf, Cursor, Neovim (headless), Claude Desktop (manual checklist).
- **Per-target install guides:** `docs/manuals/targets/{claude_desktop,windsurf,cursor,neovim}.md`.
- **Configuration reference:** `docs/manuals/configuration_reference.md` — all config keys, env vars, CLI flags, runtime reconfiguration tools, precedence rules.
- **Schema authoring guide:** `docs/manuals/schema_authoring.md` — TOML structure, field properties, conditional requirements, generate-from-taxonomy and generate-from-tasks workflows.
- **Security model document:** `docs/manuals/security_model.md` — sanitisation, rate limiting, audit logging, dry-run, confirmation tokens, field redaction, RBAC, runtime reload security.
- CI `acceptance` job running headless targets (Windsurf, Cursor, Neovim) as a matrix after unit tests.

### Changed

- **Stable tool surface (ADR 19).** `tools/list` now returns all tools in both onboarding and operational modes. The mutual-exclusivity model (onboarding OR operational tools) is replaced by runtime gating. Tools return structured `schema_unset` or `role_insufficient` errors when preconditions are unmet.
- **`restart_required` responses.** Onboarding and reconfigure tools now return `restart_required: false` (was `true` pre-v1.0).
- Smoke tests (`tests/smoke_test_mcp.py`) updated: both scenarios assert the same full tool set.
- Server registration tests refactored to assert all tool groups are registered regardless of init state.
- README updated: stale "not yet published" text removed; per-target install links added; troubleshooting table reflects ADR 19 behaviour.
- `server.json` tool list expanded to include all 35 registered tools.
- Supported platforms table: Neovim via Claude Code CLI; HTTP/SSE deferred to v1.x.

### Breaking changes from 0.3.x

- **Tool surface semantics.** Tools that were previously unregistered (and thus invisible) when preconditions were unmet now appear in `tools/list` but return error envelopes. Clients that assumed "tool in list = tool is callable" must handle `schema_unset` and `role_insufficient` error codes.
- **`restart_required` field.** Code that checked for `restart_required: true` to prompt an IDE restart should now check `restart_required: false` — the server reloads in place.

### Migration notes

- **From v0.3.x LLM-driven flows:** No action needed. The LLM should call `get_runtime_capabilities` first and route based on `mode`. Tools self-report their gatedness via structured errors.
- **From v0.3.x hand-edit flows:** After editing `config.toml`, call `reload_configuration` instead of restarting. Restart still works but is no longer required.
- **From v0.3.x CI/automation:** Update tool-surface assertions to expect all tools in `tools/list` regardless of config state. Check for error codes in tool responses rather than tool presence/absence.

## [0.3.2] - 2026-05-27

### State Described

- Closes the 12 actionable items from the post-v0.3.1 design-system audit. No new protocol surface; v1.0 gates remain unchanged.
- Onboarding and post-onboarding reconfigure tools now have full audit-log, sliding-window rate-limit, and `dry_run` coverage on par with MANAGER lifecycle tools (closes audit findings #3, #4, #6). A shared `_audit_call` helper in `server.py` consolidates the bespoke `_audit_reconfigure` side channel into the standard ADR-13 audit envelope.
- ADR cleanup: duplicate ADR 16 renumbered to ADR 18 (Installation Strategy); ADR 14's closed-set `code` inventory amended to include `role_elevation_forbidden` so the v0.3.0 refusal class is part of the stable error model. New: ADR 19 (Runtime Reload — stable tool surface + per-tool runtime state checks + `reload_configuration` tool, Status: Proposed) and ADR 20 (`scripts/setup_remote.sh` remote-host bootstrap design, Status: Accepted).
- Codebase hygiene: British → American identifier rename completed inside `taskchampion_mcp.onboarding` and its tests. `grep -rnE '\banalyse|initialisation' src/ tests/` returns zero. MCP tool names were already American at v0.3.0; this completes the symmetry inside the source.
- Smoke test gains a second scenario (`post_onboarding`) that seeds an XDG with `role + schema` and asserts the CONTRIBUTOR + reconfigure tool surface, with mutually-exclusive invariants pinned (onboarding tools must NOT register when initialised, and vice versa). Both scenarios run in CI under `pytest tests/smoke_test_mcp.py`.
- CI stabilisation: matrix jobs bootstrap a non-interactive Taskwarrior `.taskrc` so first-run prompts no longer hang `task _version` calls; `ruff` lint gate cleaned across `src/` and `tests/` (about 200 lines of formatting/style adjustments in `server.py` alone, with smaller cleanups in `onboarding.py`, `schema.py`, and eight test files).
- Coverage gate held at ≥ 85 % per ADR 12 (current: 85.59 % on `src/taskchampion_mcp/`).

## [0.3.1] - 2026-05-27

### State Described

- Development hardening state on `dev` after v0.3.0 baseline.
- CI developer extras fixed for lint tooling consistency.
- Documentation consolidated for onboarding and troubleshooting clarity.
- New tooling additions landed: task reports and batch task creation support.
- No new transport surface or release-gate scope change; v1.0 gates remain unchanged.

## [0.3.0] - 2026-05-26

### State Described

- Tool surface normalisation and contract hardening baseline.
- Onboarding completion and reconfiguration flows stabilised.
- Config precedence, observability, and error envelope contracts formalised.

[1.0.0]: https://github.com/GabiUp2/TaskChampion_MCP/releases/tag/v1.0.0
[0.3.2]: https://github.com/GabiUp2/TaskChampion_MCP/releases/tag/v0.3.2
[0.3.1]: https://github.com/GabiUp2/TaskChampion_MCP/releases/tag/v0.3.1
[0.3.0]: https://github.com/GabiUp2/TaskChampion_MCP/releases/tag/v0.3.0
