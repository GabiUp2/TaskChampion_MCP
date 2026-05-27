# Changelog

All notable changes to this project are documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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

[0.3.2]: https://github.com/GabiUp2/TaskChampion_MCP/releases/tag/v0.3.2
[0.3.1]: https://github.com/GabiUp2/TaskChampion_MCP/releases/tag/v0.3.1
[0.3.0]: https://github.com/GabiUp2/TaskChampion_MCP/releases/tag/v0.3.0
