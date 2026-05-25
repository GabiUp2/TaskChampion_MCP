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
**Status:** Accepted
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
