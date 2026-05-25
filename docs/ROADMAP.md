# Feature Roadmap

## v0.1.0 — Foundation (Released v0.2.0)

The minimum viable MCP server: read, write, and manage tasks via LLM with security guardrails.

### Core MCP Tools

**CONTRIBUTOR level** (read + annotate + modify):
- [x] `get_initialisation_status` — inspect schema/taxonomy readiness before task mutations
- [x] `propose_initialisation_options` — offer first-run choices: taxonomy, inference, hybrid, or preset
- [x] `analyse_existing_tasks_for_schema` — read-only field/value analysis from `task export`
- [x] `analyse_taxonomy_file` — parse taxonomy Markdown for field semantics and lifecycle rules
- [x] `generate_initial_schema_preview` — generate reviewable schema TOML without writing files
- [x] `save_initial_schema` — persist an approved schema and optionally update `config.toml`
- [x] `list_tasks` — list/filter tasks via `task export` with optional filters
- [x] `get_task` — get a single task by UUID with full field detail
- [x] `search_tasks` — search tasks by description, project, tags, or UDA values
- [x] `annotate_task` — add annotation to a task by UUID
- [x] `modify_task` — modify fields on an existing task (description, tags, priority, UDAs)
- [x] `start_task` / `stop_task` — toggle active time tracking on a task
- [x] `get_projects` — list all projects in the task database
- [x] `get_tags` — list all tags
- [x] `get_active_context` — show current Taskwarrior context
- [x] `timew_summary` — get Timewarrior time summary (today/week/month)
- [x] `timew_status` — check if Timewarrior is currently tracking

**GENERATOR level** (+ create):
- [x] `create_task` — create a new task with schema validation
- [ ] `create_subtask` — create a task with `depends:` linking to a parent
- [ ] `batch_create_tasks` — create multiple related tasks in one call (with rate limiting)

**MANAGER level** (+ lifecycle):
- [x] `complete_task` — mark task as done (with confirmation mode)
- [x] `delete_task` — delete a task (with confirmation mode)
- [x] `undo` — undo last Taskwarrior operation
- [x] `sync` — trigger `task sync`
- [ ] `bulk_modify` — modify multiple tasks matching a filter (with dry-run + count confirmation)

### Schema System
- [x] Load and validate TOML schema presets
- [x] Schema selection in config (`config.toml`)
- [x] Conditional field requirement validation
- [x] Schema auto-generation from existing tasks (`schema_gen.analyze_tasks`)
- [x] Taxonomy file parsing for field descriptions and process rules (`schema_gen.parse_taxonomy`)
- [x] Combined TOML schema generation from tasks + taxonomy (`schema_gen.generate_schema_toml`)
- [x] `taxonomy_path` config option for taxonomy file location
- [x] Runtime first-run onboarding tools for schema/taxonomy discovery and preview
- [x] First-run wizard: detect existing tasks, propose schema, or guide creation

### Security (ADR 9 — all required)
- [x] Subprocess argument list enforcement (no `shell=True`)
- [x] Input sanitization layer with allowlist patterns
- [x] Rate limiting (configurable ops/min, creates/hour)
- [x] Audit logging to `~/.local/share/taskchampion-mcp/audit.log`
- [x] Dry-run mode for all write operations
- [x] Confirmation mode for destructive operations (delete, done, bulk)
- [x] Sensitive field redaction (configurable)

### Infrastructure
- [x] Python package with `pyproject.toml` (uv-compatible)
- [x] `taskchampion-mcp-server` entry point (stdio transport)
- [x] TOML configuration at `~/.config/taskchampion-mcp/config.toml`
- [x] Taskwarrior version detection (3.x required, 2.x warns)
- [x] Timewarrior detection (optional, tools register only if found)
- [x] Role-based dynamic tool registration

### Distribution & Publishing
- [x] `server.json` for Official MCP Registry
- [x] `mcp-name` marker in README for PyPI validation
- [x] GitHub Actions CI workflow (`.github/workflows/ci.yml`)
- [x] GitHub Actions publish workflow — PyPI + MCP Registry (`.github/workflows/publish.yml`)
- [x] `./dev.sh publish` command for local publishing
- [x] Community submission templates (`.github/MARKETPLACE_SUBMISSIONS.md`)
- [ ] First PyPI release
- [ ] First Official MCP Registry publication
- [ ] mcp.so listing
- [ ] awesome-mcp-servers PR

### Testing
- [x] Unit tests for input sanitization
- [x] Unit tests for schema validation
- [x] Unit tests for runtime onboarding and first-run schema preview/save flow
- [ ] Unit tests for role-based tool filtering
- [ ] Integration tests using gold dataset fixtures
- [ ] Security tests using problematic input fixtures

### Documentation
- [ ] Installation guide for each supported IDE (NVIM, Cursor, Windsurf, VSC, Claude Desktop)
- [ ] Configuration reference
- [ ] Schema authoring guide
- [ ] Security model documentation

---

## v0.2.0 — Enhanced Workflows (Released v0.3.0)

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