# Cursor — Install Guide

## Config path

```
~/.cursor/mcp.json
```

---

## Developer install (local checkout)

```bash
./dev.sh install cursor
```

This points Cursor at the `.venv` Python from your working copy. It is a
developer convenience tool, not an end-user installer
([ADR 18](../../adrs/ADRs.md)).

### Flags

| Flag | Effect |
|---|---|
| `-r` / `--restart` | Restart Cursor after writing the config |

Equivalent one-liner for stop, write, start:

```bash
./dev.sh reinstall cursor -r
```

---

## End-user install (published package)

Add the following entry to `~/.cursor/mcp.json`. Create the file if it does
not exist.

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

Restart Cursor to pick up the new server.

---

## Verification

After restart, ask the LLM:

> What schema is taskchampion-mcp using?

Or call `get_runtime_capabilities`. If the tool surface still shows only
onboarding tools, the server config is missing `role` or `schema`. See
the [quick start guide](../quick_start.md) and
[configuration reference](../configuration_reference.md).
