# Claude Desktop — Install Guide

## Config path

| Platform | Path |
|---|---|
| Linux | `~/.config/Claude/claude_desktop_config.json` |
| macOS | `~/Library/Application Support/Claude/claude_desktop_config.json` |
| WSL | `/mnt/c/Users/<user>/AppData/Roaming/Claude/claude_desktop_config.json` |
| Windows (Git Bash) | `%APPDATA%\Claude\claude_desktop_config.json` |

> **Linux caveat:** the directory is `Claude` with a capital **C**. Linux
> filesystems are case-sensitive; a lowercase `claude` path silently breaks
> the install — the file is created but Claude Desktop never reads it.

---

## Developer install (local checkout)

```bash
./dev.sh install claude
```

This points Claude Desktop at the `.venv` Python from your working copy.
It is a developer convenience tool, not an end-user installer
([ADR 18](../../adrs/ADRs.md)).

### Flags

| Flag | Effect |
|---|---|
| `-r` / `--restart` | Restart Claude Desktop after writing the config |

Equivalent one-liner for stop, write, start:

```bash
./dev.sh reinstall claude -r
```

---

## End-user install (published package)

Add the following entry to `claude_desktop_config.json` manually. **Claude
Desktop must not be running** when you edit this file — the application
overwrites the config on exit, discarding your changes.

### Linux / macOS

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

### WSL

When Taskwarrior lives inside WSL, the server must be launched through
`wsl.exe` with a login shell so that `~/.local/bin` (where `uvx` lives) is
on `PATH`:

```json
{
  "mcpServers": {
    "taskchampion": {
      "command": "wsl.exe",
      "args": ["bash", "-lc", "uvx taskchampion-mcp"]
    }
  }
}
```

`wsl.exe -e uvx` will fail silently because `uvx` is not in the non-login
`PATH`. Always use `bash -lc`.

---

## Caveats

1. **Do not edit the config while Claude Desktop is running.** The
   application owns `claude_desktop_config.json` and flushes its in-memory
   state to disk on exit — any `mcpServers` entry written while the app is
   open will be silently overwritten when the user quits.

2. **WSL `$APPDATA` is not inherited.** Inside WSL, Windows environment
   variables are not available. The config path must be resolved by shelling
   out to `cmd.exe` or by using the known `/mnt/c/Users/<user>/AppData/Roaming/`
   path directly.

3. **WSL login shell is required.** `wsl.exe -e <binary>` does not load the
   login profile, so `~/.local/bin` is not on `PATH`. Use `bash -lc` as
   shown above.

---

## Verification

After restarting Claude Desktop, ask the LLM:

> What schema is taskchampion-mcp using?

Or call `get_runtime_capabilities` — it should return the current mode,
role, and schema state. If the tool surface still shows only onboarding
tools, the config is missing `role` or `schema`. See the
[quick start guide](../quick_start.md) and [configuration reference](../configuration_reference.md).
