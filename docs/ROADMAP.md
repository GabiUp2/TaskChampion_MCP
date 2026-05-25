# Feature Roadmap

## v0.1.0 — Foundation (Current Target)

The minimum viable MCP server: read, write, and manage tasks via LLM with security guardrails.

### Core MCP Tools

**CONTRIBUTOR level** (read + annotate + modify):
- [ ] `list_tasks` — list/filter tasks via `task export` with optional filters
- [ ] `get_task` — get a single task by UUID with full field detail
- [ ] `search_tasks` — search tasks by description, project, tags, or UDA values
- [ ] `annotate_task` — add annotation to a task by UUID
- [ ] `modify_task` — modify fields on an existing task (description, tags, priority, UDAs)
- [ ] `start_task` / `stop_task` — toggle active time tracking on a task
- [ ] `get_projects` — list all projects in the task database
- [ ] `get_tags` — list all tags
- [ ] `get_active_context` — show current Taskwarrior context
- [ ] `timew_summary` — get Timewarrior time summary (today/week/month)
- [ ] `timew_status` — check if Timewarrior is currently tracking

**GENERATOR level** (+ create):
- [ ] `create_task` — create a new task with schema validation
- [ ] `create_subtask` — create a task with `depends:` linking to a parent
- [ ] `batch_create_tasks` — create multiple related tasks in one call (with rate limiting)

**MANAGER level** (+ lifecycle):
- [ ] `complete_task` — mark task as done (with confirmation mode)
- [ ] `delete_task` — delete a task (with confirmation mode)
- [ ] `undo` — undo last Taskwarrior operation
- [ ] `sync` — trigger `task sync`
- [ ] `bulk_modify` — modify multiple tasks matching a filter (with dry-run + count confirmation)

### Schema System
- [ ] Load and validate TOML schema presets
- [ ] Schema selection in config (`config.toml`)
- [ ] Conditional field requirement validation
- [ ] First-run wizard: detect existing tasks, propose schema, or guide creation

### Security (ADR 9 — all required)
- [ ] Subprocess argument list enforcement (no `shell=True`)
- [ ] Input sanitization layer with allowlist patterns
- [ ] Rate limiting (configurable ops/min, creates/hour)
- [ ] Audit logging to `~/.local/share/taskchampion-mcp/audit.log`
- [ ] Dry-run mode for all write operations
- [ ] Confirmation mode for destructive operations (delete, done, bulk)
- [ ] Sensitive field redaction (configurable)

### Infrastructure
- [ ] Python package with `pyproject.toml` (uv-compatible)
- [ ] `taskchampion-mcp-server` entry point (stdio transport)
- [ ] TOML configuration at `~/.config/taskchampion-mcp/config.toml`
- [ ] Taskwarrior version detection (3.x required, 2.x warns)
- [ ] Timewarrior detection (optional, tools register only if found)
- [ ] Role-based dynamic tool registration

### Testing
- [ ] Unit tests for input sanitization
- [ ] Unit tests for schema validation
- [ ] Unit tests for role-based tool filtering
- [ ] Integration tests using gold dataset fixtures
- [ ] Security tests using problematic input fixtures

### Documentation
- [ ] Installation guide for each supported IDE (NVIM, Cursor, Windsurf, VSC, Claude Desktop)
- [ ] Configuration reference
- [ ] Schema authoring guide
- [ ] Security model documentation

---

## v0.2.0 — Enhanced Workflows

### New Tools
- [ ] `get_task_report` — run named Taskwarrior reports (`task urgent`, `task focus`, etc.)
- [ ] `get_phase_distribution` — aggregate phase counts for a project/scope
- [ ] `get_decisions_in_flight` — list unique `decides:` values with current phases
- [ ] `promote_task` — phase transition with automatic field prompting (e.g., idea→research adds hypothesis)
- [ ] `timew_start` / `timew_stop` — direct Timewarrior control independent of tasks
- [ ] `timew_tag` / `timew_untag` — manage Timewarrior interval tags
- [ ] `diff_after_sync` — compare task state before/after sync, report changes

### Project-Scoped Configuration
- [ ] `.taskchampion-mcp.toml` in project root for scoping visible tasks
- [ ] Auto-detect project from working directory
- [ ] Per-project role overrides

### Task Templates
- [ ] Predefined task structures (bug report, feature request, research spike)
- [ ] Template selection in `create_task`
- [ ] User-defined templates in config

### Reporting
- [ ] Burndown data via `task burndown`
- [ ] Time-spent summaries per project via Timewarrior
- [ ] Task velocity metrics (completed per week)

---

## v0.3.0 — Platform Expansion

### HTTP/SSE Transport
- [ ] Streamable HTTP transport for remote MCP clients
- [ ] SSE transport for real-time updates
- [ ] Authentication for HTTP transport (API key or token-based)

### ChatGPT / Codex Integration
- [ ] OpenAPI spec generation for ChatGPT plugin compatibility
- [ ] Codex MCP support verification and documentation
- [ ] Hosted deployment guide (self-hosted HTTP server)

### Taskwarrior 2.x Support
- [ ] Detect TW 2.x and adjust CLI parsing
- [ ] Taskserver (taskd) sync compatibility
- [ ] Document 2.x limitations and differences

### Advanced Features
- [ ] Natural language → Taskwarrior filter translation
- [ ] Task dependency graph visualization (text-based)
- [ ] Webhook notifications on sync changes
- [ ] Multi-schema support (different schemas per project)

---

## v1.0.0 — Stable Release

- [ ] All v0.1–v0.3 features stabilized
- [ ] Comprehensive test coverage (>90% for core modules)
- [ ] Published on PyPI with stable API
- [ ] Platform-specific packages (AUR, Homebrew, .deb)
- [ ] Full documentation site
- [ ] Security audit completed

---

## Non-Goals (Explicitly Out of Scope)

- **GUI or web interface** — this is a CLI/MCP tool
- **Replacing Taskwarrior** — we wrap it, not reimplement it
- **Direct database access** — all operations go through CLI (ADR 4)
- **Multi-tenant server** — this is a single-user MCP server
- **Task data storage** — Taskwarrior owns the data; we never persist task state

---

*This document was initially generated by Claude claude-sonnet-4-20250514 via Windsurf Cascade. Reviewed by gabiup2, 2026-05-25.*
