# Configuration Reference

All configuration lives in TOML files ([ADR 6](../adrs/ADRs.md)). The
primary user config path is:

```
~/.config/taskchampion-mcp/config.toml
```

A complete annotated example ships as `config.example.toml` in the
repository root.

---

## Config precedence

Five layers, evaluated in order. Each later layer overrides earlier layers
per key ([ADR 16](../adrs/ADRs.md)):

| Priority | Source | Notes |
|---|---|---|
| 1 (lowest) | Hard-coded defaults | `ServerConfig` dataclass values |
| 2 | User config | `~/.config/taskchampion-mcp/config.toml` (XDG) |
| 3 | Project config | `.taskchampion-mcp.toml` in cwd or first ancestor with `.git/` |
| 4 | Environment variables | `TC_MCP_*` prefix (see below) |
| 5 (highest) | CLI flags | `--role`, `--schema`, `--config-dump`, etc. |

**Merge semantics:**

- Scalar fields (strings, ints, bools) — later layer replaces earlier.
- List fields (e.g. `redacted_fields`) — later layer **replaces** earlier
  (no merge). Re-list all values if extending.
- Unknown keys — ignored with a WARNING in operational logs.

Use `--config-dump` to inspect the effective config with per-key source
provenance.

---

## `[server]` section

| Key | Type | Default | Description |
|---|---|---|---|
| `role` | string | *(none)* | Permission tier: `CONTRIBUTOR`, `GENERATOR`, or `MANAGER`. Required for the server to leave onboarding mode. See [ADR 5](../adrs/ADRs.md). |
| `schema` | string | *(none)* | Bundled preset name (`minimal`, `gtd`, `scrum`, `kanban`, `authors_custom_example`). Mutually exclusive with `schema_path`; if both are set, `schema_path` wins. |
| `schema_path` | string | *(none)* | Absolute path to a custom schema TOML file. Takes precedence over `schema`. |
| `taxonomy_path` | string | *(none)* | Path to a taxonomy Markdown file. Informational — used by schema auto-generation and by the LLM for field-semantics context. |
| `task_binary` | string | `"task"` | Path to the Taskwarrior binary. Override if `task` is not on the default `PATH`. |
| `timew_binary` | string | `"timew"` | Path to the Timewarrior binary. Override if `timew` is not on the default `PATH`. |
| `taskrc` | string | *(none)* | Path to a custom Taskwarrior rc file. Useful for isolated test databases. |

**Minimum viable config** (the two keys needed to leave onboarding mode):

```toml
[server]
role = "CONTRIBUTOR"
schema = "minimal"
```

---

## `[security]` section

| Key | Type | Default | Description |
|---|---|---|---|
| `rate_limit_per_minute` | int | `30` | Maximum MCP operations per minute (sliding window). |
| `rate_limit_per_hour` | int | `200` | Maximum MCP operations per hour (sliding window). |
| `create_limit_per_hour` | int | `50` | Maximum task creation operations per hour (GENERATOR+ only). |
| `require_confirmation` | bool | `true` | When enabled, MANAGER lifecycle tools (`complete_task`, `delete_task`, `undo_last_action`, `bulk_modify`) return `code: "confirmation_required"` on first call, expecting a second call with a confirmation token. See [ADR 14](../adrs/ADRs.md). |
| `dry_run_default` | bool | `false` | When `true`, all destructive operations default to dry-run mode (preview without executing). |
| `redacted_fields` | list of strings | `[]` | UDA field names to strip from task data before returning to the LLM and from audit log entries. |

---

## `[logging]` section

| Key | Type | Default | Description |
|---|---|---|---|
| `audit_log` | string | `~/.local/share/taskchampion-mcp/audit.log` | Path to the append-only JSON Lines audit log. Every MCP tool call is recorded with timestamp, tool name, parameters, result, and duration ([ADR 13](../adrs/ADRs.md)). |

The server does not implement log rotation. See
[`logrotate.md`](logrotate.md) for a recommended `logrotate` configuration.

---

## Environment variables

All environment variables use the `TC_MCP_` prefix. The mapping from env var
to config key replaces `TC_MCP_` and converts the remainder to lowercase
with dots separating sections:

| Environment variable | Config key |
|---|---|
| `TC_MCP_ROLE` | `server.role` |
| `TC_MCP_SCHEMA` | `server.schema` |
| `TC_MCP_SCHEMA_PATH` | `server.schema_path` |
| `TC_MCP_TAXONOMY_PATH` | `server.taxonomy_path` |
| `TC_MCP_TASK_BINARY` | `server.task_binary` |
| `TC_MCP_TIMEW_BINARY` | `server.timew_binary` |
| `TC_MCP_TASKRC` | `server.taskrc` |
| `TC_MCP_RATE_LIMIT_PER_MINUTE` | `security.rate_limit_per_minute` |
| `TC_MCP_RATE_LIMIT_PER_HOUR` | `security.rate_limit_per_hour` |
| `TC_MCP_CREATE_LIMIT_PER_HOUR` | `security.create_limit_per_hour` |
| `TC_MCP_REQUIRE_CONFIRMATION` | `security.require_confirmation` |
| `TC_MCP_DRY_RUN_DEFAULT` | `security.dry_run_default` |
| `TC_MCP_AUDIT_LOG` | `logging.audit_log` |
| `TC_MCP_LOG_LEVEL` | Operational log level (`DEBUG`, `INFO`, `WARNING`, `ERROR`) |

Environment variables sit above user and project config in precedence but
below CLI flags. They are the recommended mechanism for CI/automation
overrides and for secrets that should not appear in checked-in files.

---

## Runtime reconfiguration via MCP tools

Three MCP tools allow mid-session reconfiguration without editing files or
restarting the IDE ([ADR 17](../adrs/ADRs.md),
[ADR 19](../adrs/ADRs.md)):

| Tool | Effect |
|---|---|
| `set_active_schema(schema_name=... OR schema_path=...)` | Changes the validation schema. Horizontal move — does not affect capabilities. |
| `set_taxonomy_path(path=...)` | Changes the taxonomy reference. Informational only. |
| `set_role(target=...)` | Changes the role. **Downgrade only** — upgrading via MCP is forbidden by design. To raise the role, hand-edit `config.toml` or use the CLI wizard. |

All three persist their changes to `config.toml` and trigger an in-process
reload (ADR 19). The LLM can also call `reload_configuration` explicitly
after hand-editing the config file.

---

## CLI flags

| Flag | Effect |
|---|---|
| `--role <ROLE>` | Override the role for this process |
| `--schema <NAME>` | Override the schema preset for this process |
| `--config-dump` | Print the effective config as JSON with per-key source provenance, then exit |

CLI flags take the highest precedence — they override everything, including
environment variables.
