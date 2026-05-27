# Quick start — manual `config.toml` setup

For users who'd rather hand-edit one file than run an onboarding wizard.

The TaskChampion MCP server needs exactly two things in its config to leave
onboarding mode and register the real tool surface:

1. A **role** (CONTRIBUTOR / GENERATOR / MANAGER) — see [ADR 5][adr5]
2. A **schema** (either a bundled preset name OR a path to a custom schema TOML)

That's it. Everything else has sensible defaults.

[adr5]: ../adrs/ADRs.md

---

## TL;DR — three lines + one restart

```bash
mkdir -p ~/.config/taskchampion-mcp
cat > ~/.config/taskchampion-mcp/config.toml <<'EOF'
[server]
role = "CONTRIBUTOR"
schema = "minimal"
EOF
```

Restart your IDE (so the MCP server reloads `config.toml`). Done.

If you want to verify before restarting:

```bash
taskchampion-mcp-server --help >/dev/null && echo "binary OK"
python3 -c "
from taskchampion_mcp.config import load_config
c = load_config()
print('role:', c.role, '(explicit:', c.explicit_role_configured, ')')
print('schema:', c.schema_name, '/', c.schema_path)
print('requires_onboarding:', not (c.explicit_role_configured and c.explicit_schema_configured))
"
```

You want `requires_onboarding: False`.

---

## Picking a role

Choose deliberately — this is what bounds what the LLM can do to your task
database. The role is hierarchical (each higher role includes the lower).

| Role | Reads | Annotates / modifies | Creates | Completes / deletes / syncs | Pick if… |
|---|:-:|:-:|:-:|:-:|---|
| **CONTRIBUTOR** | ✓ | ✓ | — | — | You want the LLM as a careful assistant: read context, add notes, fix small fields. Safe default. |
| **GENERATOR** | ✓ | ✓ | ✓ | — | You want the LLM to actively populate the backlog from meeting notes, PRs, etc. |
| **MANAGER** | ✓ | ✓ | ✓ | ✓ | Full lifecycle. Pick deliberately. |

You can always change role later — but **only downward** through the MCP. To
raise the role you must hand-edit this file or run the CLI wizard. See
[ADR 17][adr17] for why.

[adr17]: ../adrs/ADRs.md

---

## Picking a schema

Five presets ship in `schemas/` — list them at runtime via the MCP tool
`list_preset_schemas`, or look directly:

| Preset | Use when |
|---|---|
| `minimal` | You don't use UDAs. Built-in Taskwarrior fields only. |
| `gtd` | You manage tasks GTD-style (contexts, energy, next-actions). |
| `kanban` | You think in board columns, WIP limits, classes of service. |
| `scrum` | Sprints, story points, acceptance criteria. |
| `authors_custom_example` | Heavy real-world taxonomy with lifecycle phases, hypothesis-driven research, LLM provenance. |

Reference a preset by name:

```toml
[server]
role = "CONTRIBUTOR"
schema = "gtd"
```

…or point at a custom TOML file (e.g. one you generated from your existing
tasks via the wizard):

```toml
[server]
role = "CONTRIBUTOR"
schema_path = "/home/you/.config/taskchampion-mcp/generated_schema.toml"
```

If both `schema` and `schema_path` are set, `schema_path` wins.

---

## Optional but useful keys

```toml
[server]
role = "CONTRIBUTOR"
schema = "gtd"

# Tell the LLM where your taxonomy notes live (informational; does not affect
# validation). Helps Claude understand the semantics behind UDAs in your schema.
taxonomy_path = "/home/you/notes/TAXONOMY.md"

# Override the Taskwarrior binary if it's not on the default PATH.
# task_binary = "/usr/local/bin/task"
# timew_binary = "/usr/local/bin/timew"

# Custom Taskwarrior rc file (e.g. for an isolated test database).
# taskrc = "/home/you/.config/taskchampion-mcp/test.taskrc"

[security]
rate_limit_per_minute = 30      # ops/min cap
rate_limit_per_hour = 200       # ops/hour cap
create_limit_per_hour = 50      # creates/hour cap (GENERATOR+ only)
require_confirmation = true     # MANAGER lifecycle ops ask twice
dry_run_default = false         # if true, mutations are previewed by default
redacted_fields = ["secret_uda_1", "internal_link"]   # hidden from LLM + audit log

[logging]
# audit_log = "/custom/path/to/audit.log"   # defaults to $XDG_DATA_HOME/taskchampion-mcp/audit.log
```

All of these have sensible defaults — you only need the two `[server]` keys at
the top.

---

## How to know it worked

After the IDE restart, from inside Claude (or whichever client is wired to the
MCP), ask `get_schema_info` (or "what schema is taskchampion-mcp using?"). You
should see the schema you picked. If you see `Schema 'minimal' loaded` and you
didn't pick minimal, the server is using a fallback — re-check that the file
is at `~/.config/taskchampion-mcp/config.toml` (XDG default), not somewhere
else, and that the `[server]` section is correctly formatted.

If the tool surface still looks like onboarding tools (`get_initialization_status`,
`save_initial_schema`, etc.), your config is missing either `role` or
`schema`/`schema_path`. See [Troubleshooting](#troubleshooting) below.

---

## Changing role or schema later

Two routes:

1. **From the LLM (no shell needed):** use the post-onboarding reconfigure
   tools — `set_active_schema(...)`, `set_taxonomy_path(...)`,
   `set_role(...)`. The role tool will refuse to raise your role above the
   currently-loaded value (ADR 17). After the call, restart the IDE so the
   new config is loaded.
2. **By hand:** edit this file again, restart the IDE. The role-raise
   restriction does not apply to direct file edits — you own the file.

---

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| Tool surface shows `get_initialization_status` etc. after restart | `role` or `schema` missing | Add both to `[server]` and restart |
| `Schema 'minimal' loaded` but you picked `gtd` | Config file in wrong location | Confirm path is `~/.config/taskchampion-mcp/config.toml` |
| `set_role` returns `role_elevation_forbidden` | You tried to upgrade via MCP | Hand-edit this file (ADR 17) |
| MCP server crashes on startup, `Taskwarrior not found` | `task` binary not on `PATH` | Install Taskwarrior 3.x or set `task_binary` |
| Schema looks loaded but `get_schema_info` shows different fields | Two configs interfering (e.g. `XDG_CONFIG_HOME` overridden) | Run `env \| grep XDG`; remove rogue override |
| Linux Claude Desktop install completes but nothing happens | Pre-v0.3.0 lowercase path bug | Use latest `dev` branch; config must live in `~/.config/Claude/`, capital C |

For MCP tool failures, the per-tool envelope's `error_code` field gives the
machine-readable category (`validation_error`, `not_found`, `rate_limit`,
`cli_error`, etc. — see [ADR 14][adr14]). Audit log entries
(`~/.local/share/taskchampion-mcp/audit.log` by default) record every call
with a stable JSON schema (see [ADR 13][adr13]).

[adr14]: ../adrs/ADRs.md
[adr13]: ../adrs/ADRs.md
