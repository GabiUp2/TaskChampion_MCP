# Feature Roadmap

> **North-star milestone — v1.0**: TaskChampion MCP is installed and feature-symmetric across all seven target IDEs/hosts (Neovim, Cursor, Windsurf, VS Code, Claude Desktop, ChatGPT, Codex). Both stdio and HTTP/SSE transports supported. Per ADR 15.

This roadmap is organized around three release tracks:

- **v0.x (Foundation)** — ship a usable stdio MCP server and feedback-driven iterations
- **v1.0 (Multi-target Release)** — symmetric UX on all seven targets, both transports, all release gates met
- **v1.x+ (Post-release)** — workflow features, ecosystem integrations, second-class targets

---

## v0.2.0 — Released

This is the current release. It established the security baseline (ADR 9), the role system (ADR 5), schema presets (ADR 7), and the onboarding flow.

**Initialization status:** Manual configuration completed (config.toml + schema preset selection). Full onboarding flow tools implemented but UX clarity needs improvement for first-time users.

### Core MCP tools

**CONTRIBUTOR** (read + annotate + modify):
- [x] `get_initialization_status` — inspect schema/taxonomy readiness before task mutations
- [x] `propose_initialization_options` — first-run choices: taxonomy, inference, hybrid, or preset
- [x] `analyze_existing_tasks_for_schema` — read-only field/value analysis from `task export`
- [x] `analyze_taxonomy_file` — parse taxonomy Markdown for field semantics
- [x] `generate_initial_schema_preview` — reviewable schema TOML without writes
- [x] `save_initial_schema` — persist approved schema, optionally update `config.toml`
- [x] `list_preset_schemas` / `use_preset_schema`
- [x] `list_tasks` / `get_task` / `search_tasks`
- [x] `annotate_task` / `modify_task`
- [x] `start_task` / `stop_task`
- [x] `get_projects` / `get_tags` / `get_active_context` / `get_schema_info`
- [x] `get_time_summary` / `get_time_status` (registered only if Timewarrior present)

**GENERATOR** (+ create):
- [x] `create_task`

**MANAGER** (+ lifecycle):
- [x] `complete_task` (dry-run + confirmation)
- [x] `delete_task` (dry-run + confirmation)
- [x] `undo_last_action` / `sync_tasks`

### Foundation

- [x] Schema preset system (minimal, gtd, scrum, kanban, authors_custom_example)
- [x] Security baseline per ADR 9 (sanitization, rate limits, audit log, dry-run, confirmation, redaction)
- [x] XDG-compliant config + audit log paths
- [x] Role-based dynamic tool registration
- [x] Taskwarrior 3.x version detection, 2.x warning
- [x] `server.json` for the Official MCP Registry
- [x] GitHub Actions CI + publish workflow
- [x] `dev.sh` developer ergonomics script

---

## v0.3.0 — Tool surface normalization and contract hardening

**Theme**: Make the tool surface internally consistent before we promise stability at v1.0. Most items are intentionally breaking — better now than after v1.0.

### Tool surface refactor (breaking)

Resolves design-system audit findings (see commit history / changelog for full list).

- [x] Standardize on American spelling: `analyze_*`, `initialization`, `propose_initialization_options`
- [x] Drop JSON-string params: `modify_task.fields` → `dict`, `create_task.extra_fields` → `dict`, `create_task.tags` → `list[str]`
- [x] Lifecycle verb parallelism: `undo` → `undo_last_action`, `sync` → `sync_tasks`
- [x] Choose namespacing convention (dropped `timew_` prefix; use `get_time_*` names)
- [x] Rewrite `_build_instructions` role descriptions to acknowledge CONTRIBUTOR write surface (modify/annotate/start/stop)

### Error model (ADR 14)

- [x] Add `code` field to every success and error envelope
- [x] Implement closed-set error categories: `validation_error`, `not_found`, `rate_limit`, `cli_error`, `schema_unset`, `confirmation_required`, `dry_run`, `internal_error`
- [x] Add `dry_run: bool` to every destructive tool (currently only on `complete_task`, `delete_task`)
- [x] Restrict `require_confirmation` to MANAGER lifecycle tools per ADR 14

### Observability (ADR 13)

- [x] Add `result_code` to audit log entries
- [x] JSON Lines vs human stderr based on TTY detection
- [x] `TC_MCP_LOG_LEVEL` env var
- [x] Document `logrotate` snippet in `docs/manuals/`
- [x] Redact `config.redacted_fields` from audit log parameter dict

### Config precedence (ADR 16)

- [x] Project config: `.taskchampion-mcp.toml` lookup (cwd → first ancestor with `.git/`)
- [x] Env var layer: `TC_MCP_*` → dotted config keys
- [x] CLI flags via `argparse`: `--role`, `--schema`, `--config-dump`
- [x] `--config-dump` prints effective config with source provenance per key

### Testing (ADR 12)

- [x] Integration test layer (`tests/integration/`) using real `task` and `timew` against ephemeral `TASKDATA`
- [x] Security regression corpus (`tests/security/`)
- [x] Gold dataset fixtures per schema preset
- [x] CI matrix: Python 3.10/3.11/3.12 × TW 3.0/3.x-latest
- [x] Coverage gate at 85% for `src/taskchampion_mcp/`

### Tooling additions

- [x] `create_subtask` (GENERATOR) — task with `depends:` linking to parent
- [x] `batch_create_tasks` (GENERATOR) — bulk create with rate-limit awareness
- [x] `bulk_modify` (MANAGER) — filter-based bulk modify with dry-run + count confirmation
- [x] `get_task_report` (CONTRIBUTOR) — named Taskwarrior reports

### Initialization UX improvements

- [x] Improve clarity of required initialization steps for first-time users
      — README `## First Run` section walks through the three paths (LLM-driven,
      CLI wizard, hand-edit) with the two-key requirement (`role` + `schema`)
      stated up front
- [x] Add explicit "quick start" guide for manual config.toml editing
      ([`docs/manuals/quick_start.md`](manuals/quick_start.md))
- [x] Document when to use full onboarding flow vs manual preset selection
      ([`docs/manuals/initialization_flows.md`](manuals/initialization_flows.md))
- [x] Add initialization troubleshooting section to README
      (10-row symptom/cause/fix table covering the common gotchas)

### Onboarding completion + reconfiguration (ADR 17)

Closes the original "schema persisted but role never set → server stuck in
onboarding forever" regression and adds the LLM-driven reconfigure surface
that lets users change schema/taxonomy/role mid-flight (downgrade only).

- [x] `upsert_server_config` accepts `role`; validates against `Role` enum
      before any disk write
- [x] `save_initial_schema` / `use_preset_schema` accept `role` and default to
      `CONTRIBUTOR` when `update_config=True`, so onboarding completion
      always satisfies `requires_onboarding == False`
- [x] CLI wizard (`./dev.sh init`) accepts `--role` flag + interactive prompt
- [x] `get_initialization_status` surfaces `active_role`, `role_configured`,
      `needs_role_selection`, `available_roles`
- [x] `propose_initialization_options` returns a self-describing `roles` block
      alongside schema options
- [x] New MCP tools at CONTRIBUTOR level: `set_active_schema`,
      `set_taxonomy_path`, `set_role` — all audit-logged
- [x] Role asymmetry enforced: `set_role` accepts downgrade and same-level
      no-op; rejects upgrade with `error_code = "role_elevation_forbidden"`
      and refuses to touch disk
- [x] ADR 17 — full threat model (prompt injection via task content,
      misaligned tool selection, upstream compromise) + POSIX setuid analogy

### Install path coverage

- [x] Fix Linux Claude Desktop config path casing (`~/.config/claude/` →
      `~/.config/Claude/`) — was a silent install failure on case-sensitive
      Linux filesystems
- [x] Tighten `test_linux_returns_xdg_path` to assert exact capitalisation
      so a future lowercase regression fails CI
- [x] Add `claude-code` install target to `dev.sh` (uses `claude mcp add`
      CLI, not JSON file rewriting) — install/uninstall/reinstall/clean all
      wired up
- [x] `scripts/setup_remote.sh` — portable, idempotent, dry-run-able
      bootstrap for remote Linux hosts. Uses `uv tool install` from PyPI or
      a pinned git ref; seeds `config.toml` with role + schema preset
- [x] Isolate XDG_CONFIG_HOME in `tests/smoke_test_mcp.py` so the smoke test
      no longer depends on the local developer's onboarding state

---

## v0.3.1 — Released (stabilisation checkpoint)

**State described by this release:** The post-v0.3.0 stabilisation snapshot on `dev`, focused on delivery reliability and operator clarity rather than new protocol surface.

- [x] CI developer extras corrected so lint/test toolchain dependencies install consistently
- [x] Onboarding and troubleshooting documentation tightened for faster first-run recovery
- [x] Reporting and batch task creation capabilities integrated into the tool surface
- [x] Version metadata remains in the v0.3 line; no release-gate changes for v1.0

---

## v0.3.2 — Released (audit follow-ups + CI hardening)

**State described by this release:** Closes the 12 actionable items from the post-v0.3.1 design-system audit. No new protocol surface; v1.0 gates remain unchanged. PR #3 (`feature/v0.3.2_audit_followups`) merged the audit work; PR #4 (`ci-debug`) stabilised the GitHub Actions matrix on top.

### Security-baseline parity for onboarding and reconfigure tools

- [x] Audit-log coverage extended to all 8 onboarding tools and the 3 reconfigure tools via a shared `_audit_call` helper in `server.py` — replaces the bespoke `_audit_reconfigure` side channel with the standard ADR-13 envelope (audit finding #3)
- [x] Sliding-window rate-limiting applied uniformly through the same `_audit_call` helper; refusals return `code: "rate_limit"` and the wrapped tool body never runs (audit finding #4)
- [x] `dry_run=True` added to `set_active_schema`, `set_taxonomy_path`, `set_role` — validates inputs, returns a `code: "dry_run"` preview, leaves `config.toml` untouched. ADR-17 invariant pinned by test: a forbidden elevation stays forbidden even when `dry_run=True` (audit finding #6)

### ADR and inventory cleanup

- [x] Duplicate ADR 16 renumbered to **ADR 18** (Installation Strategy); both former-16s carry cross-reference headers so prior commit messages remain readable (audit finding #1)
- [x] ADR 14's closed-set `code` inventory amended to include `role_elevation_forbidden`, restoring the "stable envelope" promise broken when ADR 17 added the code in v0.3.0 (audit finding #2)
- [x] **ADR 19** added — Runtime Reload via stable tool surface + per-tool runtime state checks + `reload_configuration` tool. Status: Proposed (implementation pending). Supersedes `docs/llm_context/mcp_runtime_reload_pattern.md`. (audit finding #11)
- [x] **ADR 20** added — Remote-host bootstrap (`scripts/setup_remote.sh`) design captured: `uv tool install` delivery, `claude mcp add` user scope, idempotent config seeding, check-only prereq policy, intentional Linux-only / Claude-Code-only scope. Status: Accepted. (audit finding #12)

### Codebase hygiene

- [x] British → American identifier rename completed inside `taskchampion_mcp.onboarding` and its tests — the v0.3.0 rename had stopped at the MCP-tool layer. `grep -rnE '\banalyse|initialisation' src/ tests/` now returns zero hits (audit finding #5)
- [x] Aliased imports in `server.py` simplified now that source identifiers match MCP tool names

### Test coverage

- [x] Smoke test gains a second scenario (`post_onboarding`) seeding an XDG with `role + schema` and asserting the CONTRIBUTOR + reconfigure tool surface. Mutually-exclusive invariants asserted: onboarding tools MUST NOT register when the server is initialised, and vice versa (audit finding #8)
- [x] Coverage gate held at ≥ 85 % per ADR 12 (current: 85.59 % on `src/taskchampion_mcp/`)

### CI hardening (post-PR #3)

- [x] Matrix jobs bootstrap a non-interactive Taskwarrior `.taskrc` (`confirmation=no`, fixed `data.location`) before any `task` invocation — prevents `task _version` from hanging on first-run prompts in clean runners
- [x] `ruff` lint gate cleaned across `src/` and `tests/` — about 200 lines of formatting/style adjustments in `server.py`, plus smaller cleanups in `onboarding.py`, `schema.py`, and eight test files
- [x] CI workflow now passes end-to-end on the Linux matrix

### Carried over to a later release (not blocking v0.3.2 tag)

- [ ] **ADR 19 implementation.** The stable-tool-surface refactor and `reload_configuration` tool are scoped as their own future PR — ADR 19 is `Proposed`, not `Accepted`.
- [ ] Confirmation flow for `set_role` downgrades (audit finding #7) — design decision deferred; tracked in the audit's medium-priority bucket.
- [ ] v1.0 acceptance-test items for `get_task_report` / `batch_create_tasks` / `bulk_modify` (audit finding #9) — applies at the v1.0 gate review, not v0.3.x.
- [ ] `config.example.toml` mention of the post-onboarding reconfigure tool surface (audit finding #10) — doc-only follow-up.

---

## v0.4.0 — HTTP/SSE transport and auth

**Theme**: Add the second transport so ChatGPT and Codex become reachable. Stays pre-1.0 until target compatibility is verified.

- [ ] Streamable HTTP transport via the upstream `mcp` SDK
- [ ] SSE transport for real-time progress events
- [ ] Token-based auth (`TC_MCP_AUTH_TOKEN`); rotation guide
- [ ] Optional CIDR allowlist for HTTP transport
- [ ] Health endpoint (`GET /health`) for orchestration
- [ ] Hosted deployment guide (`docs/manuals/hosted-deployment.md`)
- [ ] OpenAPI spec generated from tool registry for ChatGPT plugin compatibility
- [ ] Codex MCP support documented

---

## v1.0.0 — Multi-target release

**Theme**: Per ADR 15, this is the gated release. All ten v1.0 gates must be green.

### v1.0 release gates

1. [ ] Both transports supported (stdio + HTTP/SSE)
2. [ ] All seven targets pass the v1.0 acceptance matrix (below)
3. [ ] HTTP/SSE auth story documented and verified
4. [ ] Tool surface normalized (v0.3.0 breaking changes complete)
5. [ ] Error model implemented (ADR 14)
6. [ ] Config precedence implemented (ADR 16)
7. [ ] Published to PyPI and Official MCP Registry
8. [ ] All ADR 9 security features verified; security regression corpus green
9. [ ] Per-target installation guide, configuration reference, schema authoring guide, security model
10. [ ] CHANGELOG spans 0.x → 1.0 with migration notes for every breaking change

### Target compatibility matrix

Each target must support the same feature set ("symmetric UX"). Cells marked `✓` are required for v1.0; `~` means partial / manual; `✗` means deferred to v1.x.

| Feature | Neovim | Cursor | Windsurf | VS Code | Claude Desktop | ChatGPT | Codex |
|---|:-:|:-:|:-:|:-:|:-:|:-:|:-:|
| Transport: stdio | ✓ | ✓ | ✓ | ✓ | ✓ | — | — |
| Transport: HTTP/SSE | — | — | — | — | — | ✓ | ✓ |
| All CONTRIBUTOR tools | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| All GENERATOR tools | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| All MANAGER tools | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| Schema preset loading | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| Onboarding flow (`get_initialization_status` → `save_initial_schema`) | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| Timewarrior tools (if installed) | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| Rate limiting | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| Audit log written | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| Dry-run / confirmation flow | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| Sensitive field redaction | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| Per-target install guide | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| Headless e2e automation | ✓ | ✓ | ✓ | ✓ | ~ | ✓ | ✓ |
| Per-target deprecation warnings surfaced to user | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |

> `~` for Claude Desktop e2e because it cannot be driven headlessly today. The v1.0 gate accepts a manual checklist plus a recorded transcript as evidence.

### Per-target acceptance test (ADR 12, layer 3)

Each target's `tests/targets/<target>/` runs the same script and reports per-feature pass/fail. The acceptance suite — identical across targets — is:

1. Server starts, advertises the expected role's tool set
2. `get_initialization_status` returns valid JSON
3. `list_preset_schemas` returns at least the five bundled presets
4. Onboarding round-trip: `analyze_existing_tasks_for_schema` → `generate_initial_schema_preview` → `save_initial_schema` (using a temp output path)
5. `list_tasks` with empty and non-empty filters
6. `get_task` for a known UUID
7. `search_tasks` across `description`, `project`, `tags`, UDA
8. `annotate_task` against a real task; verify via `get_task`
9. `modify_task` of one built-in and one UDA field; verify
10. `start_task` → `stop_task`; verify Timewarrior status if available
11. `get_projects`, `get_tags`, `get_active_context`, `get_schema_info`
12. GENERATOR-only: `create_task` minimal; `create_task` with full UDA payload
13. MANAGER-only: `complete_task` with `dry_run=true` (expect `code: "dry_run"`)
14. MANAGER-only: `delete_task` with `dry_run=true` (expect `code: "dry_run"`)
15. MANAGER-only: `undo_last_action` after a real modification
16. MANAGER-only: `sync_tasks` against a configured TaskChampion sync server (skipped if unconfigured)
17. Rate limiter triggers at configured threshold; returns `code: "rate_limit"`
18. Audit log entry written for every call above; entries parseable as JSON Lines with stable schema (ADR 13)
19. Confirmation flow on a MANAGER lifecycle tool: first call → `code: "confirmation_required"`, second call → success
20. Sensitive field in `config.redacted_fields` is absent from both tool return and audit log entry

A target that fails any of items 1–20 blocks the v1.0 release for that target. Failure of items 1–18 across any target blocks the v1.0 release globally.

---

## v1.1.0 and beyond

### Workflow features (post-v1.0)

- [ ] `get_phase_distribution` — aggregate phase counts for a project/scope
- [ ] `get_decisions_in_flight` — list unique `decides:` values with current phases
- [ ] `promote_task` — phase transition with field prompting (e.g. idea→research adds hypothesis)
- [ ] `diff_after_sync` — compare task state before/after sync
- [ ] `timew_start` / `timew_stop` / `timew_tag` / `timew_untag` — direct Timewarrior control
- [ ] Burndown data via `task burndown`
- [ ] Velocity metrics (completed-per-week, project-level)

### Per-project configuration

- [ ] Per-project role overrides via `.taskchampion-mcp.toml`
- [ ] Auto-detect project from working directory (already a precedence layer per ADR 16; this is the UX layer)
- [ ] Project-scoped audit log paths

### Task templates

- [ ] Predefined task structures (bug report, feature request, research spike)
- [ ] Template selection in `create_task`
- [ ] User-defined templates in config

### Second-class targets

- [ ] Taskwarrior 2.x support (CLI parsing differences, Taskserver/taskd sync)
- [ ] Platform packages (AUR, Homebrew, .deb) per demand
- [ ] Standalone binary via PyInstaller for Python-less environments

### Observability extensions

- [ ] OpenTelemetry tracing (deferred from ADR 13)
- [ ] Native log rotation if `logrotate` proves insufficient
- [ ] Optional Prometheus metrics endpoint (HTTP transport only)
