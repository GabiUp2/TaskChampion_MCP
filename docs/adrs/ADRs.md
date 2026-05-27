# Architecture Decision Records

This file tracks all architecture decisions for the TaskChampion MCP project. Each ADR follows a consistent template and is numbered sequentially. ADRs are append-only — deprecated decisions are marked as such, never deleted.

## ADR Template

```
# ADR <N>: <Title>
**Date:** YYYY-MM-DD
**Status:** Proposed | Accepted | Deprecated | Superseded by ADR <N>
**Author:** <human | LLM model+harness>

## Context
Describe the issue or problem being addressed, including relevant background.

## Decision
Summarize the decision taken.

## Alternatives Considered
List alternatives that were evaluated.

## Consequences
### Pros
- ...
### Cons
- ...
```

---

# ADR 0: ADR Template & Process

**Date:** 2026-05-25
**Status:** Accepted
**Author:** Claude claude-sonnet-4-20250514 / Windsurf Cascade

## Context

We need a structured way to record architecture decisions so that current and future contributors (human or LLM) can understand why the system is built the way it is. Decisions made without documentation tend to be revisited repeatedly, wasting effort.

## Decision

Adopt Architecture Decision Records (ADRs) as the standard format for documenting significant technical decisions. All ADRs live in `docs/adrs/ADRs.md`, are numbered sequentially starting from 0, and follow the template defined above. Each ADR must include a timestamp, status, author attribution (including LLM model if applicable), context, decision, alternatives, and consequences.

## Alternatives Considered

- **Inline code comments** — too scattered, hard to discover
- **Wiki pages** — external dependency, may drift from repo
- **GitHub Discussions** — not version-controlled with the code

## Consequences

### Pros
- Single source of truth for architectural decisions, version-controlled
- Forces explicit reasoning about trade-offs
- LLM contributors can read ADRs to understand project constraints

### Cons
- Requires discipline to maintain
- Single-file format may become long over time (can split per-ADR later)

---

# ADR 1: License — Apache 2.0

**Date:** 2026-05-25
**Status:** Accepted
**Author:** Claude claude-sonnet-4-20250514 / Windsurf Cascade + human decision

## Context

We need an open-source license that:
1. Allows private and commercial use
2. Requires attribution to the original author and repository in all derivative works and publications
3. Provides patent protection for users and contributors
4. Is compatible with upstream MIT-licensed tools (Taskwarrior, TaskChampion, Timewarrior)

The deep research report recommended MIT. However, the project author requires stronger attribution guarantees.

## Decision

Use the **Apache License, Version 2.0**. Include a `NOTICE` file that names the project, author, and upstream dependencies. All derivative works must preserve the NOTICE file contents per Section 4(d) of the license.

## Alternatives Considered

- **MIT License** — simpler, but attribution is limited to preserving the copyright line; no NOTICE mechanism; no patent grant
- **BSD-3-Clause** — similar to MIT plus a non-endorsement clause; still no patent grant or NOTICE file
- **GPLv3** — copyleft would prevent commercial use without source disclosure; too restrictive for our goals
- **Custom license** — maintenance burden, legal ambiguity, poor ecosystem trust

## Consequences

### Pros
- NOTICE file provides a robust, well-understood attribution mechanism
- Patent grant protects users from patent trolling
- Widely recognized and trusted in enterprise and open-source communities
- Fully compatible with MIT-licensed upstream tools

### Cons
- Slightly more complex than MIT (NOTICE file management)
- Some developers perceive Apache 2.0 as "heavier" than MIT

---

# ADR 2: Language — Python with uv

**Date:** 2026-05-25
**Status:** Accepted
**Author:** Claude claude-sonnet-4-20250514 / Windsurf Cascade + human decision

## Context

The MCP server needs to be implemented in a language that:
1. Has a mature, official MCP SDK
2. Installs easily across Linux distributions without a compile step
3. Has a broad contributor base
4. Supports both stdio and HTTP/SSE transports

## Decision

Use **Python** as the implementation language with the official `mcp` Python SDK. Use **uv** as the package manager and virtual environment tool for fast, reproducible dependency management.

## Alternatives Considered

- **TypeScript/Node.js** — good MCP SDK, but adds Node.js as a runtime dependency on systems that may not have it; less natural for CLI-wrapping tools
- **Rust** — matches TaskChampion's ecosystem, excellent performance, but high barrier for contributors; MCP SDK is less mature
- **Go** — fast binaries, but no official MCP SDK at time of writing

## Consequences

### Pros
- Python is pre-installed on virtually all Linux systems
- `uv` provides fast, lockfile-based dependency resolution
- Official `mcp` SDK handles protocol details, transport negotiation
- Easy to write subprocess wrappers for `task` and `timew` CLI
- Largest potential contributor pool

### Cons
- Slower than Rust/Go for compute-heavy operations (irrelevant for our I/O-bound use case)
- Requires Python 3.10+ (reasonable for 2026)

---

# ADR 3: Transport — stdio First, HTTP/SSE Deferred

**Date:** 2026-05-25
**Status:** Superseded by ADR 15 (2026-05-26)
**Author:** Claude claude-sonnet-4-20250514 / Windsurf Cascade

## Context

The MCP protocol supports multiple transports: stdio, SSE (Server-Sent Events), and streamable HTTP. Different platforms require different transports:

| Platform | Required Transport |
|---|---|
| Neovim (nvim-mcp) | stdio |
| Cursor | stdio |
| Windsurf | stdio |
| VS Code (Copilot) | stdio |
| Claude Desktop | stdio |
| ChatGPT / Codex | HTTP/SSE |

## Decision

Implement **stdio transport only** for v0.1.0. This covers all 5 primary target platforms. Defer HTTP/SSE transport to v0.2.0+ for ChatGPT and Codex support.

## Alternatives Considered

- **Both transports from day one** — increases scope and testing surface for v0.1.0
- **HTTP/SSE only** — would exclude all primary IDE targets

## Consequences

### Pros
- Minimal implementation scope for v0.1.0
- Covers 5 of 7 target platforms immediately
- stdio is simpler to secure (no network attack surface)

### Cons
- ChatGPT and Codex support delayed
- Will need a second transport entry point later

---

# ADR 4: CLI-Only Integration — No Direct File/DB Access

**Date:** 2026-05-25
**Status:** Accepted
**Author:** Claude claude-sonnet-4-20250514 / Windsurf Cascade

## Context

Taskwarrior and Timewarrior store data in local files (`.task/`, `~/.local/share/timewarrior/`). We could interact with them by:
1. Calling the CLI tools (`task`, `timew`) via subprocess
2. Reading/writing data files directly
3. Using a library binding (e.g., Taskwarrior's `tasklib` Python package)

## Decision

Interact **exclusively** through the `task` and `timew` command-line interfaces via subprocess calls. Use `task export` (JSON output) as the primary read mechanism. Never read or write Taskwarrior or Timewarrior data files directly.

## Alternatives Considered

- **Direct file access** — faster reads, but bypasses hooks, undo stack, sync state, and internal consistency checks; high risk of data corruption
- **tasklib Python package** — wraps CLI but adds a dependency; not actively maintained for TW3; abstracts away CLI behavior we need to understand
- **TaskChampion Rust bindings via PyO3** — tight coupling to specific TaskChampion version; complex build; overkill for our needs

## Consequences

### Pros
- Respects Taskwarrior's internal consistency (undo stack, hooks, sync)
- Works with any Taskwarrior configuration without assumptions about data format
- Hooks (e.g., Timewarrior on-modify) fire naturally
- Easy to test by mocking subprocess calls

### Cons
- Subprocess overhead per operation (negligible for our use case)
- Must parse CLI output; `task export` JSON is reliable but other commands produce human-readable text
- Depends on `task` and `timew` binaries being installed and in PATH

---

# ADR 5: Role System — CONTRIBUTOR < GENERATOR < MANAGER

**Date:** 2026-05-25
**Status:** Accepted
**Author:** Claude claude-sonnet-4-20250514 / Windsurf Cascade + human decision

## Context

Users need to control what actions an LLM can perform on their task database. Different use cases demand different permission levels:
- A coding assistant that only adds context to existing tasks
- An agent that can create new tasks based on project analysis
- A full project management assistant that can complete, delete, and reorganize tasks

## Decision

Implement three cumulative permission roles. Each higher role includes all permissions of lower roles:

**CONTRIBUTOR** (read + annotate + modify fields):
- List, filter, search, read task details
- Annotate tasks (add comments/links)
- Modify existing fields (description, tags, priority, UDAs)
- Time tracking operations (start/stop/summary via timew)

**GENERATOR** (+ create):
- All CONTRIBUTOR permissions
- Create new tasks
- Create subtasks and dependency relationships

**MANAGER** (+ lifecycle control):
- All GENERATOR permissions
- Complete/done tasks
- Delete tasks
- Archive tasks
- Bulk operations
- Undo last action
- Trigger sync (`task sync`)

The role is set in the MCP server configuration file and determines which MCP tools are registered at startup.

## Alternatives Considered

- **Single role with per-tool toggles** — more granular but complex to configure; error-prone
- **Two roles (read-only / full)** — too coarse; most users want create but not delete
- **No role system** — dangerous; LLMs could delete tasks without guardrails

## Consequences

### Pros
- Simple mental model: three clear levels
- Cumulative design means upgrading is just changing one config value
- Tools are dynamically registered, so the LLM never even sees tools it cannot use
- Matches common organizational patterns (contributor/developer/admin)

### Cons
- May need finer granularity later (e.g., "can complete but not delete")
- Role applies globally, not per-project

---

# ADR 6: Configuration Format — TOML

**Date:** 2026-05-25
**Status:** Accepted
**Author:** Claude claude-sonnet-4-20250514 / Windsurf Cascade + human decision

## Context

The MCP server needs a configuration file for settings like role level, rate limits, audit log path, schema selection, and Taskwarrior binary paths. We need a human-readable, well-supported format.

## Decision

Use **TOML** for all configuration files. The primary config file location is `~/.config/taskchampion-mcp/config.toml`, following the XDG Base Directory specification. Project-level overrides can be placed in `.taskchampion-mcp.toml` in the project root (future feature).

## Alternatives Considered

- **YAML** — widely used but has gotchas (Norway problem, implicit typing, significant whitespace)
- **JSON** — no comments, verbose for configuration
- **INI** — too simple, no nested structures
- **Python file** — powerful but security risk (arbitrary code execution)

## Consequences

### Pros
- Native comment support
- Explicit typing (strings, integers, booleans, dates)
- Well-supported in Python (`tomllib` in stdlib since 3.11, `tomli` for older)
- Matches Rust ecosystem conventions (TaskChampion is Rust-based)
- XDG-compliant path is consistent with Taskwarrior and Timewarrior config locations

### Cons
- Less familiar than YAML to some users
- Nested structures can be slightly verbose

---

# ADR 7: Task Schemas — TOML Presets

**Date:** 2026-05-25
**Status:** Accepted
**Author:** Claude claude-sonnet-4-20250514 / Windsurf Cascade + human decision

## Context

Taskwarrior supports UDAs (User Defined Attributes) and users define their own workflows. The MCP server needs to understand which fields exist, their types, allowed values, and which are required — so that LLMs generate valid tasks. Users should be able to define custom schemas, but sensible defaults must ship with the tool.

## Decision

Ship TOML-based schema preset files in a `schemas/` directory. Each schema defines:
- Field names, types, allowed values, and whether they are required
- Conditional requirements (e.g., `hypothesis` required when `phase:research`)
- Default values
- Field descriptions (for LLM context)

Ship 5 presets:
1. `minimal.toml` — priority, project, tags only
2. `gtd.toml` — Getting Things Done (contexts, next-actions, someday/maybe)
3. `scrum.toml` — sprint-based with story points, sprint ID, acceptance criteria
4. `kanban.toml` — status-board with WIP limits and board columns
5. `authors_custom_example.toml` — full UDA set from the project author's taxonomy (scope, client, area, phase, hypothesis, versus, effort, confidence, decides, gen_*, review)

On first run, if no schema is configured, the MCP prompts the user to select a preset or generate a schema from their existing tasks.

## Alternatives Considered

- **JSON Schema** — more formal validation, but verbose and less human-editable
- **YAML schemas** — same issues as YAML config (see ADR 6)
- **No schemas, freeform** — LLMs would generate inconsistent tasks; no validation possible

## Consequences

### Pros
- Users can customize without code changes
- LLMs receive structured field definitions, improving task quality
- Presets lower the barrier to entry
- Author's custom example serves as a real-world reference for advanced setups

### Cons
- Schema validation logic must be implemented in the MCP server
- Users with very unusual setups may need to write schemas manually

---

# ADR 8: Target Taskwarrior 3.x First

**Date:** 2026-05-25
**Status:** Accepted
**Author:** Claude claude-sonnet-4-20250514 / Windsurf Cascade + human decision

## Context

Taskwarrior 3.x uses TaskChampion for sync (HTTP-based, encrypted). Taskwarrior 2.x uses Taskserver (taskd) for sync (GnuTLS-based, deprecated since 2015). The two versions have different sync protocols, different configuration keys, and some behavioral differences in CLI output.

## Decision

Target **Taskwarrior 3.x with TaskChampion** as the primary and only supported configuration for v0.1.0. Taskwarrior 2.x / Taskserver support will be added in a future release, clearly documented as a secondary target. The MCP server should detect the Taskwarrior version at startup and warn if 2.x is found.

## Alternatives Considered

- **Support both from v0.1.0** — doubles testing surface; Taskserver is deprecated and complex
- **Support 2.x only** — would ignore the modern ecosystem; most new users are on 3.x
- **Version-agnostic (CLI only, no version check)** — risky; subtle behavioral differences could cause silent data issues

## Consequences

### Pros
- Focused development and testing effort
- Aligns with upstream direction (Taskserver is archived)
- TaskChampion's HTTP sync is simpler and more modern
- Clear documentation prevents user confusion

### Cons
- Excludes users still on Taskwarrior 2.x (likely a shrinking population)
- Must implement version detection and clear error messaging

---

# ADR 9: Security Baseline for v0.1.0

**Date:** 2026-05-25
**Status:** Accepted
**Author:** Claude claude-sonnet-4-20250514 / Windsurf Cascade + human decision

## Context

An MCP server that wraps CLI tools gives an LLM indirect shell access scoped to task management. This creates several attack surfaces:
1. **Command injection** — malicious task descriptions passed to shell
2. **Unbounded operations** — LLM creating thousands of tasks in a loop
3. **Unaudited mutations** — no record of what the LLM changed
4. **Destructive actions** — accidental deletion or completion
5. **Data exposure** — task descriptions sent to LLM may contain sensitive information

## Decision

Implement the following security features as **required for v0.1.0** (not optional/deferred):

1. **Subprocess argument lists** — all CLI calls use `subprocess.run()` with argument lists, never `shell=True`. This is the primary command injection defense.
2. **Input sanitization** — validate all inputs (descriptions, tags, UDA values) against allowlist patterns before passing to subprocess. Reject shell metacharacters.
3. **Rate limiting** — configurable per-minute and per-hour caps on operations. Defaults: 30 ops/min, 200 ops/hour. Separate limits for create operations.
4. **Audit logging** — every MCP tool invocation logged with timestamp, tool name, parameters, result, and session ID. Default log location: `~/.local/share/taskchampion-mcp/audit.log`.
5. **Dry-run mode** — every write operation supports a `dry_run` parameter that returns what would happen without executing. Enabled by default for MANAGER-level destructive operations.
6. **Confirmation mode** — configurable flag (`require_confirmation = true`) for destructive operations (delete, done, bulk). When enabled, the tool returns a pending state requiring explicit user confirmation.
7. **Sensitive field redaction** — configurable list of UDA fields to redact from LLM responses (e.g., fields containing credentials or personal data).

## Alternatives Considered

- **Defer security to v0.2.0** — unacceptable; an insecure MCP server should not be released
- **Rely on LLM guardrails only** — LLMs can be jailbroken or make mistakes; defense-in-depth required
- **Sandboxing via containers** — the MCP server needs host CLI access; containerization breaks the use case

## Consequences

### Pros
- Defense-in-depth: multiple layers protect against different attack vectors
- Audit log enables post-incident review and debugging
- Rate limiting prevents runaway LLM loops
- Dry-run and confirmation give users control over destructive actions
- Sensitive field redaction addresses data exposure concerns

### Cons
- Adds implementation complexity to v0.1.0
- Rate limiting may frustrate legitimate bulk operations (configurable to mitigate)
- Audit log requires rotation/cleanup strategy

---

# ADR 10: Distribution — PyPI First

**Date:** 2026-05-25
**Status:** Accepted
**Author:** Claude claude-sonnet-4-20250514 / Windsurf Cascade + human decision

## Context

The MCP server needs to be distributable across multiple platforms (Linux primarily, macOS secondarily). Installation should be as simple as possible for users who may not be developers.

## Decision

Distribute primarily via **PyPI** as `taskchampion-mcp`. Users install with:
```
pip install taskchampion-mcp
# or
uv add taskchampion-mcp
# or
uvx taskchampion-mcp
```

The package provides a `taskchampion-mcp-server` entry point that IDE MCP configurations can reference directly. Platform-specific packaging (AUR, Homebrew, .deb) will be added in later releases based on demand.

## Alternatives Considered

- **Homebrew-first** — macOS-centric; our primary audience is Linux
- **AUR-first** — Arch-only; too narrow
- **Docker image** — MCP server needs host CLI access to `task` and `timew`; Docker breaks this unless using host networking and volume mounts, which defeats the purpose
- **Standalone binary (PyInstaller/Nuitka)** — removes Python dependency but adds build complexity and binary size

## Consequences

### Pros
- Single command installation on any system with Python 3.10+
- `uvx` enables zero-install execution (downloads and runs in temp env)
- PyPI is the standard Python distribution channel
- Entry point pattern works directly with MCP client configurations in all target IDEs

### Cons
- Requires Python to be installed (almost always true on Linux)
- PyPI package naming must be claimed early
- Platform-specific packages (AUR, Homebrew) offer better system integration but are deferred

---

# ADR 11: TOML Field Name Handling — Quoted Keys for Special Characters

**Date:** 2026-05-25
**Status:** Accepted
**Author:** gabiup2

## Context

Taskwarrior UDA field names can contain spaces, dots, and other special characters (e.g., "client name", "field.with.dots"). When generating schema TOML files, these field names must be represented as TOML table keys. TOML has strict rules about bare keys (alphanumeric, underscores, dashes only), but supports quoted keys for arbitrary strings.

A previous implementation replaced invalid characters with underscores, causing field name collisions:
- `"field name"` → `"field_name"`
- `"field-name"` → `"field_name"`

This resulted in silent data loss when different field names collided after sanitization.

## Decision

Use **quoted TOML keys** for field names that contain special characters. The `_sanitize_toml_key()` function in `schema_gen.py` checks if a field name matches the bare key pattern `[a-zA-Z0-9_-]+`. If it does, the key is used as-is. If it contains other characters, the field name is wrapped in double quotes to preserve the original name and avoid collisions.

Example:
- `"scope"` → `[fields.scope]`
- `"field name"` → `[fields."field name"]`
- `"field.with.dots"` → `[fields."field.with.dots"]`

The schema loader (`schema.py`) already handles quoted keys correctly via the standard TOML parser.

## Alternatives Considered

- **Replace invalid characters with underscores** — causes field name collisions, silent data loss
- **Reject field names with special characters** — breaks existing Taskwarrior setups, user-hostile
- **Use a different escaping mechanism (e.g., URL encoding)** — non-standard, harder to read

## Consequences

### Pros
- Preserves original field names exactly
- No risk of name collisions
- TOML-standard approach
- Backward compatible with existing schema loader

### Cons
- Quoted keys are slightly less readable in raw TOML files
- Requires documentation for users editing schemas manually

---

# ADR 12: Testing Strategy — Three-Layer Pyramid with Per-Target E2E Matrix

**Date:** 2026-05-26
**Status:** Proposed
**Author:** gabiup2 / Claude Opus 4.7 (1M context) via Cowork

## Context

The server already has unit tests for `sanitizer`, `schema`, `schema_gen`, `config`, `rate_limiter`, and `onboarding` (see `tests/`). What is missing is (a) a documented strategy that defines what each layer covers, (b) integration tests that exercise the real `task` and `timew` binaries against an ephemeral data directory, and (c) a per-target end-to-end matrix that verifies feature symmetry across the seven IDE/host targets enumerated in ADR 15. Without that matrix the v1.0 promise of "same UX across all targets" cannot be enforced — only asserted.

A second pressure is the subprocess boundary: most bugs in a CLI-wrapping MCP server live in argument construction and output parsing, neither of which is exercised by unit tests that mock `subprocess.run`. We need a layer that runs the real binaries.

## Decision

Adopt a three-layer test pyramid plus a per-target compatibility matrix:

1. **Unit tests** (`tests/`, fast, run on every commit). Mock `subprocess.run` and the filesystem where helpful. Cover sanitizer rules, schema validation, rate limiter, config loading, audit log entry shape, role gating logic, and every branch in `tools.py` that does not require a real CLI. Coverage gate: 85% line coverage for `src/taskchampion_mcp/`.

2. **Integration tests** (`tests/integration/`, run on every PR). Spin up an ephemeral Taskwarrior data directory by setting `TASKDATA` and `TASKRC` env vars to a pytest `tmp_path`. Use the real `task` and `timew` binaries from the test container. Cover every MCP tool against this real backend, including the dry-run and confirmation flows. Matrix: Python 3.10/3.11/3.12 × Taskwarrior 3.0 / 3.x-latest.

3. **End-to-end target compatibility tests** (`tests/targets/`, run nightly and on every release tag). One subdirectory per target IDE (`neovim/`, `cursor/`, `windsurf/`, `vscode/`, `claude_desktop/`, `chatgpt/`, `codex/`). Each contains a script that drives the MCP server through the v1.0 acceptance matrix defined in `ROADMAP.md` and reports pass/fail per feature. Targets that cannot be automated headlessly (e.g. Claude Desktop) get a checklist runbook plus a recorded transcript.

4. **Security regression tests** (`tests/security/`, run on every PR). A frozen corpus of problematic inputs (shell metacharacters, oversized payloads, malformed UUIDs, schema bypass attempts) verified against the sanitizer + tool layer. New CVE-like findings get added to the corpus; entries are never deleted.

5. **Fixtures**: a gold dataset (`tests/fixtures/tasks/`) of representative task JSON exports — minimal, gtd, scrum, kanban, and the author's custom example — used by integration and e2e tests. Updated only when schema semantics change.

CI configuration: GitHub Actions runs unit + integration + security on every PR. E2E target tests run on a nightly cron and on every `v*` tag push. A target that fails an e2e run blocks the release.

## Alternatives Considered

- **Two-layer (unit + e2e only)** — skipping integration tests pushes too much risk to e2e, which is slow and harder to debug. Integration catches subprocess argument bugs cheaply.
- **Run real binaries in unit tests** — slows the inner loop and creates flakiness from binary version drift. Mocking at the unit layer keeps the loop fast.
- **No per-target matrix, document parity instead** — the whole point of v1.0 is symmetric UX. Documentation drifts; tests don't.
- **Single Python version in CI** — `uv`'s lockfile pins versions, but the project supports 3.10+. We catch typing/stdlib drift only by running the matrix.

## Consequences

### Pros
- Subprocess argument and parsing bugs are caught at integration before they reach a target IDE
- Per-target matrix makes v1.0 release gates objective and re-runnable
- Security corpus grows over time as a regression net
- Coverage gate keeps `tools.py` honest as it grows

### Cons
- Integration tests require `task` and `timew` binaries in the CI image — adds container build complexity
- Some targets (Claude Desktop) cannot be driven headlessly and need manual runbooks — partial automation only
- Nightly e2e cron incurs CI minute cost

---

# ADR 13: Observability — Two Streams, Structured Logs, Audit Log as Source of Truth

**Date:** 2026-05-26
**Status:** Proposed
**Author:** gabiup2 / Claude Opus 4.7 (1M context) via Cowork

## Context

ADR 9 mandates an audit log. The current implementation (`audit.py`) writes JSON lines to `~/.local/share/taskchampion-mcp/audit.log` and logs operational events via the standard `logging` module. Two questions are unresolved:

1. What is the canonical shape of an audit entry, and is it stable enough for downstream tooling (KQL queries, log shippers, dashboards) to depend on?
2. Where do operational logs go, given that stdio transport reserves stdout for the MCP protocol?

A third concern: distributed tracing (OpenTelemetry, etc.) is increasingly expected in modern services. The MCP server is a single process per host, but spans across the LLM → MCP → CLI boundary have diagnostic value when something goes wrong.

## Decision

Maintain **two independent log streams** with strict separation:

1. **Operational log** (process diagnostics) — written to **stderr only**. Never stdout (reserved for MCP protocol on stdio transport). Format: JSON Lines when stderr is not a TTY (machine-readable), human-readable text when stderr is a TTY (developer ergonomics). Level controlled by `TC_MCP_LOG_LEVEL` env var (defaults to `INFO`). Used for startup banners, CLI version detection, schema load notices, exceptions before a tool returns.

2. **Audit log** (every tool invocation) — append-only JSON Lines to a file path resolved per ADR 16's config precedence. **Stable schema** (this ADR formalizes it):

```json
{
  "timestamp": "2026-05-26T12:34:56.789Z",
  "session_id": "abc123def456",
  "tool": "create_task",
  "parameters": { "...": "..." },
  "result": "short summary string (≤500 chars)",
  "result_code": "ok | dry_run | confirmation_required | rate_limit | validation_error | not_found | cli_error | internal_error",
  "success": true,
  "duration_ms": 12.3,
  "pid": 12345,
  "error": "optional error message (≤500 chars)"
}
```

The `result_code` field is added (currently missing) and aligned with ADR 14's error taxonomy so audit logs are queryable by category.

3. **Correlation**: each server process generates one `session_id` at startup. All entries within that process share it. This is sufficient for v1.0; cross-process correlation is deferred.

4. **Tracing**: OpenTelemetry integration is **deferred**. If/when added, span context will be attached to the audit entry as an optional `trace_id` / `span_id` pair. No work in v1.0.

5. **Log rotation**: not built into the server. Document a `logrotate` snippet in `docs/manuals/`. Re-evaluate native rotation in a future ADR if user feedback demands it.

6. **Sensitive parameter handling**: the existing `_redact_long_values` truncates at 200 chars. Add field-name-based redaction matching `config.redacted_fields` so that sensitive UDA values never land in the audit log even if the LLM passes them.

## Alternatives Considered

- **Single combined log stream** — conflates "what the process is doing" with "what the LLM asked the process to do"; harder to query, harder to ship to SIEM
- **stdout for operational logs** — breaks the MCP stdio protocol immediately
- **Build native OpenTelemetry support in v1.0** — adds a dependency and configuration surface for marginal benefit at a single-process scale
- **Native log rotation** — duplicates a solved problem (`logrotate`); adds dependency or careful file-locking code

## Consequences

### Pros
- Audit log is the queryable source of truth for "what did the LLM do" — KQL, jq, log shippers all work against a stable schema
- Stderr-only operational logs preserve the stdio protocol invariant
- Adding `result_code` aligns audit log with the error model (ADR 14) — single source of truth for categorization
- Deferring tracing keeps v1.0 dependency footprint small

### Cons
- Two destinations to configure and document
- Schema change (`result_code`) is a minor breaking change for anyone already parsing the audit log — call it out in CHANGELOG
- `logrotate` dependency is a Linux assumption; macOS users need an equivalent

---

# ADR 14: Error Model — Stable Envelope, Code-Tagged Categories, Explicit Retry Semantics

**Date:** 2026-05-26
**Status:** Proposed
**Author:** gabiup2 / Claude Opus 4.7 (1M context) via Cowork

## Context

Every tool in `tools.py` already returns either `_make_success(message, **extra)` or `_make_error(message)`. The envelope shape is consistent, but the error variant carries only a freeform `message` string. An LLM seeing `"error": true, "message": "Failed: Task abc not found"` cannot reliably distinguish a missing-resource error from a rate-limit error from a CLI failure without parsing English. That coupling is fragile.

There is also no documented contract for what counts as "destructive" and therefore requires `dry_run` / confirmation. Today only `complete_task` and `delete_task` implement the dry-run/confirmation flow. `modify_task`, `undo`, `sync`, and future bulk operations are inconsistent.

## Decision

Define a single error model with three parts:

### 1. Stable envelope

Every MCP tool MUST return one of these two shapes. Exceptions are never propagated to the transport layer.

```json
// Success
{ "success": true, "message": "...", "code": "ok | dry_run | confirmation_required", "<extra>": "..." }

// Error
{ "error": true, "message": "...", "code": "<category>", "details": { "<optional>": "..." } }
```

The `code` field is **new** and is added to both success and error envelopes. Existing callers that only check `success` / `error` continue to work; new callers can branch on `code` without parsing English.

### 2. Error categories (closed set)

| code | Meaning | Retryable? |
|---|---|---|
| `validation_error` | Sanitizer or schema validation rejected the input | No — fix args first |
| `not_found` | Referenced UUID / project / preset does not exist | No |
| `rate_limit` | Sliding-window cap exceeded | Yes, after wait (`details.retry_after_s` provided) |
| `cli_error` | `task` or `timew` returned non-zero | Sometimes — depends on stderr |
| `schema_unset` | First-run onboarding required before this tool can run | No — run onboarding flow |
| `confirmation_required` | Destructive op needs second call | No — re-call with explicit confirm |
| `dry_run` | Preview only, no execution occurred | N/A — not an error |
| `role_elevation_forbidden` | `set_role` was asked to raise role above current; refused by design per ADR 17 | **Not retryable via MCP.** User must elevate out-of-band: `./dev.sh init --role <ROLE>` or hand-edit `~/.config/taskchampion-mcp/config.toml`, then restart the MCP server. |
| `internal_error` | Unhandled exception caught at the tool boundary | Yes, with backoff |

Codes are stable identifiers. Adding a new code is a MINOR version bump (ADR 15). Removing or repurposing a code is a MAJOR version bump.

`role_elevation_forbidden` was added in v0.3.2 to inventory the refusal class introduced by ADR 17 (Role-Elevation Asymmetry). It is structurally a refusal, not a validation error: the input was well-formed and the request well-understood — only the security policy refuses to execute it. Keeping it as a distinct code lets dashboards / SIEM queries count self-elevation attempts cleanly.

### 3. Dry-run and confirmation contract

A tool is **destructive** if it mutates Taskwarrior or Timewarrior state. By that definition, destructive tools are: `create_task`, `modify_task`, `annotate_task`, `complete_task`, `delete_task`, `start_task`, `stop_task`, `undo`, `sync`, and future `bulk_modify` / `batch_create_tasks`. (`save_initial_schema` mutates config and schema files — also destructive.)

Every destructive tool MUST accept an optional `dry_run: bool` parameter (default resolved from `config.dry_run_default`, currently `false`). When `dry_run=true`, the tool returns `{success: true, code: "dry_run", message: "Would do X", preview: {...}}` and performs no mutation.

`require_confirmation` (config) gates an additional confirmation step on **MANAGER-level lifecycle tools only** (`complete_task`, `delete_task`, `undo`, `bulk_modify`). When enabled and `dry_run=false`, the tool returns `{success: true, code: "confirmation_required", message: "..."}` on first call, expecting a second call with an explicit confirmation token in `details`.

## Alternatives Considered

- **Keep freeform messages only** — what we have today; LLMs cannot reliably branch on category without English parsing
- **HTTP-style numeric codes (400, 404, 429, 500)** — familiar but the mapping to MCP semantics is lossy and adds translation work for both server and client
- **Per-tool error enums** — proliferation of types; harder for the LLM to learn; harder to grep across the codebase
- **Apply confirmation to all destructive tools** — would force confirmation on `modify_task` and `annotate_task`, which would be annoying for high-volume edits. Restricting to lifecycle keeps the friction proportional to the blast radius

## Consequences

### Pros
- LLMs can branch on `code` without natural-language parsing
- Adding tools is mechanical — pick a code, write the message
- Aligns audit log (`result_code` per ADR 13) and tool output — one taxonomy
- Dry-run becomes universal for destructive ops; predictable behavior across the surface

### Cons
- Adding `dry_run` to tools that currently lack it is a breaking parameter change — schedule for v1.0 alongside other breaking renames
- Forces discipline: every new tool must declare its error codes
- `cli_error` is broad — may need sub-codes later if Taskwarrior failure modes diversify

---

# ADR 15: Versioning and v1.0 Release — Multi-Transport, All-Targets Milestone (Supersedes ADR 3)

**Date:** 2026-05-26
**Status:** Proposed
**Author:** gabiup2 / Claude Opus 4.7 (1M context) via Cowork

## Context

ADR 3 deferred HTTP/SSE transport past v0.1.0 to focus on the five IDE targets that use stdio. With the project now committing to v1.0 = symmetric UX across all seven targets (Neovim, Cursor, Windsurf, VS Code, Claude Desktop, ChatGPT, Codex), the deferred transport must be in scope. ADR 3 is superseded.

Beyond transport, we need an explicit SemVer policy, a deprecation policy for tools (since ADR 14 introduces several breaking renames), and a clear definition of what "v1.0" means as a release gate.

## Decision

### SemVer policy

The MCP server follows strict SemVer:

- **MAJOR** — any of: removed/renamed MCP tool, removed/renamed parameter, removed error code, removed config key, changed default role-permission semantics
- **MINOR** — added MCP tool, added optional parameter, added error code, added schema preset, added config key with a safe default, added transport
- **PATCH** — bug fix with no API contract change

Schema preset versions (`[meta].version` in TOML) are independent of the server version.

### MCP protocol pinning

`server.json` records the MCP protocol version range the server supports. The Python `mcp` SDK dependency is pinned to a `~=` minor range. Upgrading SDK minor versions requires a PATCH release minimum and a CI run of the integration matrix.

### Deprecation policy

A tool, parameter, or error code marked Deprecated:

1. Stays present and functional for at least one MINOR release after the Deprecated label appears in its docstring
2. Emits a structured deprecation notice to the operational log (ADR 13) on first use per session
3. Is removed only in the next MAJOR release
4. Is documented in CHANGELOG.md under "Deprecated" with the replacement called out

### v1.0 release gates

v1.0 ships when ALL of the following are true:

1. **Both transports supported**: stdio (existing) and Streamable HTTP / SSE (per the upstream MCP SDK)
2. **All seven targets pass the v1.0 acceptance matrix** in `ROADMAP.md` (per ADR 12's e2e tests). Manual checklists are acceptable for targets that cannot be driven headlessly
3. **HTTP/SSE auth story documented**: token-based auth with config-driven secret rotation; no auth required for stdio (process-bound)
4. **Tool surface normalized**: naming inconsistencies from the design-system audit resolved (American spelling, dropped `timew_` prefix conflicts, JSON-string params replaced with native types)
5. **Error model implemented**: ADR 14's `code` field present on every tool return; audit log `result_code` populated (ADR 13)
6. **Config precedence implemented**: layer order per ADR 16; `--config-dump` flag available
7. **Distribution**: published to PyPI and Official MCP Registry; install instructions verified for each target IDE
8. **Security**: all ADR 9 features verified; security regression corpus (ADR 12) green
9. **Documentation**: per-target installation guide, configuration reference, schema authoring guide, security model
10. **CHANGELOG**: spans 0.x → 1.0 with explicit migration notes for every breaking change

### Pre-v1.0 numbering

Versions 0.x.y leading up to v1.0 follow normal SemVer with the relaxed convention that 0.x bumps may include breaking changes (per upstream SemVer guidance for 0.y.z series). The first stable contract is v1.0.0.

## Alternatives Considered

- **Keep ADR 3 and ship HTTP/SSE in v2.0** — punts the all-targets promise; ChatGPT/Codex users wait a major version
- **Loose SemVer (move-fast-break-things in 1.x)** — destroys downstream trust; LLM tooling assumes stable contracts
- **Per-target version numbers** — proliferates complexity; one server, one version
- **Skip the v1.0 release gate matrix; ship when "ready"** — "ready" is unmeasurable; gates make the milestone concrete

## Consequences

### Pros
- v1.0 is a measurable, gated milestone instead of a vibe
- Strict SemVer protects downstream MCP clients
- Deprecation policy creates a safe path to evolve the tool surface
- Supersedes ADR 3 cleanly without leaving stale guidance in the registry

### Cons
- HTTP/SSE work pulled forward — increases v1.0 scope
- Tool-renaming breaking changes must be coordinated into a single MAJOR boundary
- Auth model for HTTP/SSE is its own design problem (likely future ADR)

---

# ADR 16: Configuration Precedence — Five Layers, Last Wins, Explicit Provenance

**Date:** 2026-05-26
**Status:** Proposed
**Author:** gabiup2 / Claude Opus 4.7 (1M context) via Cowork

> **Note on numbering:** ADR 18 (Installation Strategy) was originally drafted as a
> second ADR 16 due to a merge-time collision and renumbered in v0.3.2 to remove
> the ambiguity. Every "ADR 16" reference in the codebase now unambiguously means
> *this* document — Configuration Precedence.

## Context

Today `load_config()` reads a single TOML file at `~/.config/taskchampion-mcp/config.toml` (per ADR 6) and falls back to dataclass defaults. The roadmap calls for project-scoped configuration (`.taskchampion-mcp.toml` in the project root) and CI/automation users need a way to override settings without editing files. Without a documented precedence order, behavior becomes "wherever the developer happened to read first," which is exactly the class of bug ADR documentation is meant to prevent.

A secondary concern: secrets. Auth tokens for the HTTP/SSE transport (per ADR 15) should never be required in a checked-in config file. Environment variables are the conventional answer, but only if precedence puts them above project config.

## Decision

Five layers, evaluated in order. Each later layer overrides earlier layers per key.

1. **Hard-coded defaults** — `ServerConfig` dataclass values in `config.py`
2. **User config** — `~/.config/taskchampion-mcp/config.toml` (XDG Base Dir, per ADR 6)
3. **Project config** — `.taskchampion-mcp.toml` in the current working directory or the first ancestor containing a `.git/` directory (whichever comes first). Optional; missing file is not an error
4. **Environment variables** — `TC_MCP_*` (e.g. `TC_MCP_ROLE`, `TC_MCP_SCHEMA`, `TC_MCP_AUDIT_LOG`, `TC_MCP_AUTH_TOKEN`). Snake-case env var → dotted config key (`TC_MCP_RATE_LIMIT_PER_MINUTE` → `security.rate_limit_per_minute`)
5. **CLI flags** — passed to `taskchampion-mcp-server` (e.g. `--role MANAGER`, `--schema gtd`, `--config-dump`)

### Merge semantics

- **Scalar fields** (strings, ints, bools) — later layer replaces earlier
- **List fields** (e.g. `redacted_fields`) — later layer **replaces** earlier (no merge). Predictability beats clever; users who want to extend can re-list values
- **Unknown keys** — ignored with a WARNING in operational logs; never fail to start

### Secret handling

Sensitive values (HTTP/SSE auth tokens, future webhook secrets) MUST be settable via env var or CLI flag. They MAY appear in TOML config files but the documentation discourages it and the `--config-dump` output redacts them.

### Provenance debugging

A `--config-dump` CLI flag prints the effective config as JSON, annotated with the source layer per key:

```json
{
  "server.role": { "value": "MANAGER", "source": "env:TC_MCP_ROLE" },
  "server.schema": { "value": "gtd", "source": "file:~/.config/taskchampion-mcp/config.toml" },
  "security.rate_limit_per_minute": { "value": 30, "source": "default" }
}
```

This is the diagnostic tool of first resort when a user reports "I changed the config but nothing happened."

## Alternatives Considered

- **Single layer (user config only)** — what we have today; doesn't scale to multi-project users or CI
- **Three layers (defaults / user / env)** — skips project config, which is on the v0.2.0 roadmap regardless
- **Deep-merge lists** — clever, hard to debug, hides intent
- **Read project config from a `pyproject.toml` table** — couples our config to Python packaging tools and to projects that don't have a `pyproject.toml`
- **Use environment variables as primary, files as fallback** — flips the usual ergonomics; most users edit files, not env

## Consequences

### Pros
- One documented order makes "where does this value come from" answerable
- Env vars + CLI flags make CI and ephemeral overrides clean
- `--config-dump` turns a class of support questions into a single command
- Project config (roadmap item) slots in cleanly without re-litigating precedence
- Secret handling story is consistent

### Cons
- Five layers is more surface than one — onboarding doc must explain it
- Env var naming convention adds a translation step (`TC_MCP_RATE_LIMIT_PER_MINUTE` ↔ `[security] rate_limit_per_minute`)
- CLI flag implementation requires wiring through `argparse` or `click` — small new dependency or stdlib effort

---

# ADR 18: Installation Strategy — dev.sh vs Published Distribution

**Date:** 2026-05-26
**Status:** Accepted
**Author:** Claude Sonnet 4.6 / Cowork (bartosz.wichowski@dxc.com)

> **Note on numbering:** Originally drafted as a second ADR 16 due to a
> merge-time collision with the Configuration Precedence ADR. Renumbered to
> ADR 18 in v0.3.2 to remove the ambiguity. Historical commits prior to v0.3.2
> may reference "ADR 16: Installation Strategy" — those references mean *this*
> document.

## Context

During development of the `feature_claude_desktop_init_process` branch, we discovered
that `dev.sh install claude` is structurally unsuited for end-user distribution, for
several compounding reasons:

**1. Claude Desktop owns its config file.**
`%APPDATA%\Claude\claude_desktop_config.json` is written back by Claude Desktop on
every clean exit. If the script writes `mcpServers` while the app is running, the app
overwrites the file on quit and the entry is lost. This is not a race condition that
can be fixed with retries — it is a deliberate ownership boundary.

**2. `$APPDATA` is never available inside WSL.**
When a bash process runs inside WSL (whether launched interactively or via
`wsl.exe -e`), Windows environment variables including `$APPDATA` are not inherited.
The correct config path can only be resolved by shelling out to `cmd.exe` from within
an interactive WSL session. This works for a developer running `./dev.sh` in a
terminal; it is not reliable in non-interactive or CI contexts.

**3. `wsl.exe -e <binary>` does not load the login profile.**
When Claude Desktop launches the MCP server via `wsl.exe -e <binary>`, the WSL
process starts without a login shell. `~/.local/bin` (where `uv` and `uvx` live) is
not on PATH. Only binaries with absolute paths or those in `/usr/bin` are reachable.
`wsl.exe bash -lc <cmd>` is required to get a full environment.

**4. dev.sh requires the repo to be cloned first.**
An end user should not need to clone a development repository to install an MCP
server. The install should work from a published package.

## Decision

We formally separate two distinct workflows with different audiences, tools, and
contracts:

### Path A — Developer convenience (`dev.sh install claude`)

**Audience:** contributors hacking on the server locally.
**Purpose:** point Claude Desktop at the local dev build instead of the published package.
**Behaviour:**
- Writes the MCP config entry using the local venv Python (via `wsl.exe bash -lc`)
- **Refuses to run if Claude Desktop is currently running** (hard exit with clear error)
- User must either quit Claude Desktop first, or use `./dev.sh reinstall claude -r`
  which manages the full stop→write→start lifecycle

**What it is not:** an installer for end users. No distribution, no versioning, no
update path. The `install` action header comment must say this explicitly.

### Path B — Published distribution (`./dev.sh publish` → end user)

**Audience:** anyone who wants to use TaskChampion MCP without contributing to it.
**Steps:**
1. `./dev.sh publish` pushes to PyPI as `taskchampion-mcp`
2. The MCP Registry entry (`server.json`) is updated to reference the PyPI package
3. End users add one entry to their `claude_desktop_config.json` (or Claude Desktop
   installs it via the registry):

**Native Linux / macOS:**
```json
{ "command": "uvx", "args": ["taskchampion-mcp"] }
```

**WSL (Taskwarrior lives inside WSL):**
```json
{
  "command": "wsl.exe",
  "args": ["bash", "-lc", "uvx taskchampion-mcp"]
}
```
`bash -lc` is mandatory — it loads `~/.profile` / `~/.bashrc`, putting
`~/.local/bin` on PATH where `uvx` (installed via `uv`) lives. `wsl.exe -e uvx`
fails silently because `uvx` is not in the non-login PATH.

**Cowork plugin (future):** bundle the MCP config entry + existing skills into a
`.plugin` file for one-click install from the Cowork marketplace.

### Testing the published path

Manual end-to-end testing of the full publish → install → connect cycle is not
acceptable as a merge gate. The automated test strategy is:

1. **MCP protocol smoke test** (`./dev.sh smoke-test`, wired into CI):
   Start the server as a subprocess, send `initialize` + `tools/list` over stdio,
   assert the response contains the expected tool names and counts. This validates
   the published package is protocol-correct without requiring a running Claude Desktop.

2. **Install unit tests** (`tests/test_install.py`):
   Test config-path resolution per platform (mock `uname` + `wslpath`), test that
   `_upsert_mcp_entry` produces valid JSON with correct structure, test that
   `_remove_mcp_entry` is idempotent and does not corrupt other keys.

3. **TestPyPI pre-release gate** (`.github/workflows/publish.yml`):
   Publish to TestPyPI first, run `uvx --index-url https://test.pypi.org/simple/
   taskchampion-mcp --help` to confirm the package is importable and the entry point
   resolves. Only promote to PyPI if this passes.

## Alternatives Considered

- **Fix `dev.sh install` to work while Claude Desktop is running** — not possible
  without root access to pause the app's config flush; the ownership model is correct.
- **Write to a separate JSON file that Claude Desktop imports** — Claude Desktop has
  no such import mechanism.
- **Use a PowerShell wrapper script** — avoids the WSL/bash complexity but adds a
  new dependency for Windows users and still fights the config ownership problem.
- **Ship a standalone installer binary (Go/Rust)** — correct long-term for a polished
  product; premature at v0.3.0 alpha.

## Consequences

### Pros
- dev.sh `install` becomes honest about what it is and refuses silently-broken states
- End users get a one-line install that works across restarts without script intervention
- `uvx` handles versioning, updates, and venv lifecycle transparently
- The smoke test catches protocol regressions before they reach users
- TestPyPI gate prevents broken packages from hitting the public registry

### Cons
- `uvx taskchampion-mcp` requires `uv` to be installed (near-universal for Python
  developers; slightly more friction for non-Python users)
- WSL users need to know to use `bash -lc` variant — must be prominent in docs
- Full publish path cannot be tested locally without a TestPyPI account

---

# ADR 17: Role-Elevation Asymmetry — LLM-Driven Reconfiguration Is One-Way Downward

**Date:** 2026-05-27
**Status:** Accepted
**Author:** gabiup2 / Claude Opus 4.7 (1M context) via Cowork

## Context

ADR 5 introduced three cumulative roles (CONTRIBUTOR < GENERATOR < MANAGER) and the v0.3.0 onboarding refactor moved role/schema persistence into `config.toml`. Once onboarding completes, the only way to change the persisted role or schema is to hand-edit `config.toml` and restart the IDE. This works but creates a real UX gap: switching schemas during a session — a routine workflow change, not a permission decision — requires the user to leave the LLM-driven flow.

The natural fix is to expose configuration mutators (`set_active_schema`, `set_taxonomy_path`, `set_role`) as MCP tools. Doing so without care, however, would let the LLM grant itself privileges the user explicitly chose not to grant — a self-elevation path that defeats the entire role model.

The threat model that motivates the role gate has three layers, all increasingly relevant:

1. **Prompt injection via task content.** Task descriptions, annotations, project names, and the user's TAXONOMY.md are all model-readable text. A malicious or accidental instruction buried in any of those (a captured email turned into a task, a colleague's PR description, a shared taxonomy) becomes executable intent the moment the LLM has the matching capability. The role gate bounds the blast radius of such injections.
2. **Misaligned tool selection.** Even without adversarial input, LLMs over-reach when "helpful" — "I'll clean up these duplicates for you" eagerly invokes `delete_task`. CONTRIBUTOR functioning as a ceiling, not just a default, is what makes "ask before destructive ops" enforceable.
3. **Compromise upstream of the MCP.** If the IDE plugin, MCP server bundle, or model provider ever ships a bug or a tampered update, an unprivileged MCP role limits the damage that bug can do.

If the LLM can self-elevate, all three protections collapse to "the LLM was honest about needing the privilege" — exactly what the gate was built to avoid relying on.

## Decision

Expose configuration mutators as CONTRIBUTOR-level MCP tools, but enforce a strict asymmetry between schema/taxonomy mutation, role downgrade, and role upgrade:

| Operation | Exposed via MCP? | Rationale |
|---|---|---|
| `set_active_schema(schema_name OR schema_path)` | Yes, CONTRIBUTOR | Changes the validation lens, not capabilities. The LLM at CONTRIBUTOR can already modify tasks; picking the semantics under which it modifies them is a horizontal move, not an escalation. |
| `set_taxonomy_path(path)` | Yes, CONTRIBUTOR | Same as above — informational input to the LLM, no capability change. |
| `set_role(target)` where `level(target) ≤ level(current)` | Yes, CONTRIBUTOR | Voluntary de-privileging is always safe. Lets an LLM drop to CONTRIBUTOR for a risky sub-task or honour a user instruction to "be careful". |
| `set_role(target)` where `level(target) > level(current)` | **No** | Self-elevation. Forbidden by design. The tool returns a structured error pointing the user at the CLI wizard or hand-edit + restart. |

The asymmetry mirrors POSIX `setuid` semantics and the broader capability-systems convention: dropping privileges is unprivileged; raising them requires authorization that the current principal cannot grant itself.

Privilege elevation paths that **remain** available, by design, all require out-of-band human action:

- `./dev.sh init --role MANAGER` (CLI wizard) — explicitly invoked by the user from a shell, outside the LLM's tool surface.
- Hand-edit `~/.config/taskchampion-mcp/config.toml` — the user owns the file.
- Re-running `save_initial_schema` / `use_preset_schema` with an explicit `role=` argument, but only when the server is in onboarding mode (i.e., `requires_onboarding == True`). The onboarding tools are not registered post-completion, so an LLM cannot re-trigger them.

Every successful configuration mutation MUST emit one audit log entry per ADR 13, capturing tool name, parameters, role before/after, and timestamp. Silent self-mutation is the failure mode this ADR exists to prevent; auditability is the second line of defence.

## Alternatives Considered

- **Expose symmetric `set_role` that allows upgrade.** Maximally convenient; defeats the entire purpose of having a role system. Rejected.
- **Require user confirmation prompts in the LLM client for role upgrade.** Relies on the client honouring the prompt; many MCP clients today do not have a confirmation primitive, and prompt-injection-driven uplift can fabricate the "I confirm" follow-up. Insufficient.
- **No reconfiguration tools at all; keep config edits hand-only.** Preserves the model rigidly but accepts the UX cost: every schema swap requires leaving the LLM flow. Rejected because schema switching is a frequent workflow change, not a privilege decision.
- **Make role downgrade also out-of-band.** Symmetric but unnecessarily restrictive; voluntary de-privileging is harmless by construction.

## Consequences

### Pros
- The role model retains its meaning: a CONTRIBUTOR can never become MANAGER without explicit, out-of-band human action.
- Schema/taxonomy swap becomes a single LLM tool call — the workflow gap that motivated this ADR is closed.
- Voluntary downgrade gives careful LLMs (or careful users) a way to ratchet down trust during risky sub-tasks.
- Audit log makes every config mutation traceable; "what did the LLM change about my server" is queryable.
- The forbidden-upgrade path is a structured error code (`role_elevation_forbidden`), discoverable in logs and dashboards.

### Cons
- Genuine "I want to give Claude MANAGER for this one task" workflows require leaving the chat for one CLI command. Acceptable friction — it's the feature.
- Two ways now exist to change role (CLI wizard / hand-edit + restart, vs. downgrade-only MCP tool). Document both prominently in `docs/manuals/`.
- Reconfiguration tools take effect on next IDE restart (runtime reload not yet implemented; see the runtime reload handoff doc on `dev`). Until that lands, the "restart required" hint is non-negotiable in every tool response.
- The schema/taxonomy mutators technically affect what fields the LLM treats as valid for subsequent operations. A confused-deputy variant exists where a malicious task description tricks the LLM into pointing taxonomy at a forged file. Mitigation: validate the file exists before persisting, and audit-log the path change so a human review can catch it.

