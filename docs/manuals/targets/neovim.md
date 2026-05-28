# Neovim — Install Guide

Neovim uses **Claude Code CLI** (`claude`) as the MCP runner
([ADR 18](../../adrs/ADRs.md)). There is no JSON config file to edit —
registration happens through the `claude mcp add` command.

This is the recommended path for terminal-first users.

---

## Developer install (local checkout)

```bash
./dev.sh install claude-code
```

This wires the local `.venv` Python into Claude Code's user-scoped MCP
config via `claude mcp add`. No IDE restart is needed — the next `claude`
invocation picks up the new server automatically.

---

## End-user install (published package)

### Prerequisites

1. **Claude Code CLI** — install from
   <https://docs.anthropic.com/en/docs/claude-code>
2. **uv** — install from <https://docs.astral.sh/uv/getting-started/installation/>

### Register the MCP server

```bash
claude mcp add taskchampion -- uvx taskchampion-mcp
```

This registers `taskchampion` at user scope. The entry persists across
sessions — every subsequent `claude` invocation spawns the MCP server and
exposes the tool surface.

### Verify the registration

```bash
claude mcp list
```

You should see a `taskchampion` entry with the `uvx taskchampion-mcp`
command.

---

## Scope

By default, `claude mcp add` uses **user scope** — the server is available
in every directory and every `claude` session. This is the correct scope for
TaskChampion MCP because it manages a user-level task database, not a
per-project one.

To restrict to a specific project instead:

```bash
claude mcp add taskchampion -s project -- uvx taskchampion-mcp
```

---

## Updating

To update to a newer version:

```bash
claude mcp remove taskchampion
claude mcp add taskchampion -- uvx taskchampion-mcp
```

`uvx` fetches the latest published version from PyPI on each invocation, so
the `remove` + `add` cycle is primarily to refresh the registration metadata.

---

## Verification

Inside a `claude` session, ask:

> What schema is taskchampion-mcp using?

Or call `get_runtime_capabilities`. If the tool surface still shows only
onboarding tools, the server config is missing `role` or `schema`. See
the [quick start guide](../quick_start.md) and
[configuration reference](../configuration_reference.md).
