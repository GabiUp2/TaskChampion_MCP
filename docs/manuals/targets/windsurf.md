# Windsurf — Install Guide

## Config path

```
~/.codeium/windsurf/mcp_config.json
```

---

## Developer install (local checkout)

```bash
./dev.sh install windsurf
```

This points Windsurf at the `.venv` Python from your working copy. It is a
developer convenience tool, not an end-user installer
([ADR 18](../../adrs/ADRs.md)).

### Flags

| Flag | Effect |
|---|---|
| `-r` / `--restart` | Restart Windsurf after writing the config |

Equivalent one-liner for stop, write, start:

```bash
./dev.sh reinstall windsurf -r
```

---

## End-user install (published package)

Add the following entry to `~/.codeium/windsurf/mcp_config.json`. Create the
file if it does not exist.

```json
{
  "mcpServers": {
    "taskchampion": {
      "command": "uvx",
      "args": ["taskchampion-mcp"]
    }
  }
}
```

Restart Windsurf to pick up the new server.

---

## Verification

After restart, ask the LLM:

> What schema is taskchampion-mcp using?

Or call `get_runtime_capabilities`. If the tool surface still shows only
onboarding tools, the server config is missing `role` or `schema`. See
the [quick start guide](../quick_start.md) and
[configuration reference](../configuration_reference.md).
