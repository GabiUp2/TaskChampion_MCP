# Security Model

This document summarises the security features implemented per
[ADR 9](../adrs/ADRs.md) (Security Baseline). All features are required —
none are optional or deferred.

---

## Input sanitisation

All user and LLM input is sanitised before reaching the Taskwarrior CLI.

- CLI calls use `subprocess.run()` with **argument lists** — never
  `shell=True`. This is the primary command injection defence.
- All inputs (descriptions, tags, UDA values) are validated against
  allowlist patterns before being passed to subprocess. Shell
  metacharacters are rejected.
- Field values are checked against the loaded schema's type constraints and
  allowed-value enumerations. Invalid values produce a structured
  `code: "validation_error"` response ([ADR 14](../adrs/ADRs.md)).

---

## Rate limiting

Sliding-window rate limits prevent unbounded operations — including runaway
LLM loops.

| Limit | Default | Config key |
|---|---|---|
| Operations per minute | 30 | `security.rate_limit_per_minute` |
| Operations per hour | 200 | `security.rate_limit_per_hour` |
| Creates per hour | 50 | `security.create_limit_per_hour` |

When a limit is exceeded, the tool returns `code: "rate_limit"` with a
`details.retry_after_s` value indicating when the next call will be
accepted. The tool body never executes — the refusal happens in the shared
`_audit_call` wrapper before any work is done.

All limits are configurable via `config.toml`, environment variables, or CLI
flags. See the [configuration reference](configuration_reference.md).

---

## Audit logging

Every MCP tool invocation is recorded in an append-only JSON Lines audit
log ([ADR 13](../adrs/ADRs.md)).

**Default path:** `~/.local/share/taskchampion-mcp/audit.log`

Each entry contains:

| Field | Description |
|---|---|
| `timestamp` | ISO 8601 UTC |
| `session_id` | Unique per server process |
| `tool` | MCP tool name |
| `parameters` | Call parameters (sensitive fields redacted) |
| `result` | Short summary (max 500 chars) |
| `result_code` | Stable code from the ADR 14 taxonomy |
| `success` | Boolean |
| `duration_ms` | Wall-clock execution time |
| `pid` | Server process ID |
| `error` | Error message if applicable (max 500 chars) |

The log is the queryable source of truth for "what did the LLM do to my
task database". Entries are parseable with `jq`, log shippers, or KQL.

The server does not implement log rotation. See
[`logrotate.md`](logrotate.md) for a recommended configuration.

---

## Dry-run mode

Every destructive tool accepts an optional `dry_run: bool` parameter. When
`true`, the tool returns a preview of what would happen without executing
any mutation.

```json
{
  "success": true,
  "code": "dry_run",
  "message": "Would complete task abc123",
  "preview": { ... }
}
```

The `dry_run_default` config key (`security.dry_run_default`) controls
whether destructive operations default to dry-run mode. Default: `false`.

Destructive tools include: `create_task`, `modify_task`, `annotate_task`,
`complete_task`, `delete_task`, `start_task`, `stop_task`,
`undo_last_action`, `sync_tasks`, `bulk_modify`, `batch_create_tasks`,
`save_initial_schema`, `set_active_schema`, `set_taxonomy_path`, `set_role`.

---

## Confirmation tokens for destructive operations

When `require_confirmation = true` (the default), MANAGER-level lifecycle
tools require a two-step confirmation flow:

1. **First call** — the tool validates inputs and returns
   `code: "confirmation_required"` with a summary of the pending action.
2. **Second call** — the caller re-invokes the tool with an explicit
   confirmation token. Only then does the mutation execute.

This applies to: `complete_task`, `delete_task`, `undo_last_action`,
`bulk_modify`.

The confirmation requirement is proportional to blast radius — high-volume
tools like `modify_task` and `annotate_task` do not require confirmation,
keeping friction proportional to risk ([ADR 14](../adrs/ADRs.md)).

---

## Field redaction

The `security.redacted_fields` config key accepts a list of UDA field names
to hide from the LLM and from the audit log.

```toml
[security]
redacted_fields = ["client_secret", "internal_link"]
```

Redacted fields are stripped from:

- Task data returned to the LLM via any tool (`list_tasks`, `get_task`,
  `search_tasks`, etc.)
- The `parameters` dict in audit log entries

This addresses data exposure concerns when task UDAs contain sensitive
information (credentials, internal URLs, personal data) that should not
reach the LLM or persist in logs.

---

## Role-based access control

Three cumulative permission roles bound what the LLM can do
([ADR 5](../adrs/ADRs.md)):

| Role | Capabilities |
|---|---|
| **CONTRIBUTOR** | Read, annotate, modify existing tasks, time tracking, reconfigure |
| **GENERATOR** | All CONTRIBUTOR capabilities + create new tasks |
| **MANAGER** | All GENERATOR capabilities + complete, delete, undo, sync, bulk operations |

The role is set in `config.toml` and enforced at runtime per tool call. The
LLM can **downgrade** its role via `set_role` but cannot self-elevate —
raising the role requires out-of-band human action (hand-edit the config
file or use the CLI wizard). This asymmetry is by design
([ADR 17](../adrs/ADRs.md)) and mirrors POSIX `setuid` semantics: dropping
privileges is unprivileged; raising them requires authorisation the current
principal cannot grant itself.

Attempted self-elevation returns `code: "role_elevation_forbidden"`.

---

## Runtime reload security

Configuration can be reloaded at runtime without restarting the IDE
([ADR 19](../adrs/ADRs.md)). The reload mechanism does **not** bypass role
constraints:

- `reload_configuration` re-reads `config.toml` and refreshes schema,
  rate limiter, and audit logger — but the role gating remains enforced.
- If a hand-edit raises the role in `config.toml`, the reload picks up the
  new role. This is an explicit out-of-band human action, not an LLM
  self-elevation.
- The reconfigure tools (`set_active_schema`, `set_taxonomy_path`,
  `set_role`) trigger in-process reloads on success. `set_role` still
  refuses upgrades even during a reload cycle.
- Every configuration mutation is audit-logged with the tool name,
  parameters, and role before/after values.
