# TaskChampion MCP

**A Model Context Protocol server for Taskwarrior 3.x, TaskChampion, and Timewarrior.**

> *For the bearded Unix jockeys and keyboard cowboys who manage their life from the terminal — and now want their LLM to lend a hand.* 🧔⌨️

<!-- mcp-name: io.github.GabiUp2/taskchampion-mcp -->

[![PyPI](https://img.shields.io/pypi/v/taskchampion-mcp)](https://pypi.org/project/taskchampion-mcp/)
[![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.10+-green.svg)](https://python.org)
[![MCP Registry](https://img.shields.io/badge/MCP-Registry-blue)](https://registry.modelcontextprotocol.io)

---

## What Is This?

TaskChampion MCP is a [Model Context Protocol](https://modelcontextprotocol.io) server that lets LLMs read, create, modify, and manage your Taskwarrior tasks and Timewarrior time entries. It wraps the `task` and `timew` CLI tools and exposes them as structured MCP tools that any compatible AI assistant can call.

**Why?** The author self-hosts [TaskChampion](https://github.com/GothenburgBitFactory/taskchampion-sync-server) on a home server and wanted a clean way for LLMs to cooperate on project planning, task decomposition, and time tracking — without giving up control of the task database.

---

## Supported Platforms

| Platform | Transport | Status |
|---|---|---|
| **Neovim** (nvim-mcp) | stdio | v0.1.0 |
| **Cursor** | stdio | v0.1.0 |
| **Windsurf** | stdio | v0.1.0 |
| **VS Code** (Copilot MCP) | stdio | v0.1.0 |
| **Claude Desktop** | stdio | v0.1.0 |
| **ChatGPT** | HTTP/SSE | Planned (v0.3.0) |
| **Codex** | stdio/HTTP | Planned (v0.3.0) |

**Requirements:**
- Python 3.10+
- Taskwarrior 3.x (TaskChampion sync)
- Timewarrior (optional, for time tracking features)

---

## Quick Install

```bash
# With uv (recommended)
uv tool install taskchampion-mcp

# With pip
pip install taskchampion-mcp
```

Then configure your IDE's MCP settings to use:
```json
{
  "mcpServers": {
    "taskchampion": {
      "command": "taskchampion-mcp-server",
      "args": []
    }
  }
}
```

> **Note:** The package is not yet published. See [ROADMAP](docs/ROADMAP.md) for current status.

---

## First Run

On a fresh install with no `config.toml`, the server boots in **onboarding mode** and exposes a small set of setup tools. You finish onboarding by persisting two keys in `~/.config/taskchampion-mcp/config.toml`:

- `role` — what the LLM can do (CONTRIBUTOR / GENERATOR / MANAGER)
- `schema` *or* `schema_path` — which task schema the server validates against

Three ways to get there:

1. **Let the LLM walk you through it.** Connect your IDE to the MCP server with no config and ask: *"Help me set up TaskChampion MCP."* The LLM uses `get_initialization_status` → `propose_initialization_options` → `save_initial_schema` (or `use_preset_schema`) to do the work, including asking you which role to use. **One IDE restart afterwards** so the new config is loaded.
2. **Run the CLI wizard:** `./dev.sh init` (interactive) or `./dev.sh init --preset gtd --role CONTRIBUTOR --non-interactive` (scripted).
3. **Edit `config.toml` by hand** — see [quick_start.md](docs/manuals/quick_start.md). Two keys, one restart, done.

The three paths are interchangeable and produce identical state. Pick by who should be doing the typing — see [initialization_flows.md](docs/manuals/initialization_flows.md) for the decision guide.

If the tool surface in your IDE still shows `get_initialization_status` / `save_initial_schema` after a restart, your config is missing either `role` or `schema`. That's the most common first-run gotcha and it's covered in [Troubleshooting](#troubleshooting) below.

---

## Permission Levels

Control what the LLM can do with your tasks via three cumulative roles:

| Role | Can Read | Can Annotate/Modify | Can Create | Can Complete/Delete |
|---|---|---|---|---|
| **CONTRIBUTOR** | ✅ | ✅ | ❌ | ❌ |
| **GENERATOR** | ✅ | ✅ | ✅ | ❌ |
| **MANAGER** | ✅ | ✅ | ✅ | ✅ |

Set the role in `~/.config/taskchampion-mcp/config.toml`:
```toml
[server]
role = "GENERATOR"  # CONTRIBUTOR | GENERATOR | MANAGER
```

---

## Task Schemas

Taskwarrior supports custom workflows via UDAs (User Defined Attributes). TaskChampion MCP ships with schema presets that teach the LLM your task structure:

| Schema | Description |
|---|---|
| `minimal` | Built-in fields only (priority, project, tags) |
| `gtd` | Getting Things Done (contexts, energy, next-actions) |
| `scrum` | Sprint-based (story points, sprint IDs, acceptance criteria) |
| `kanban` | Board columns, WIP limits, classes of service |
| `authors_custom_example` | Advanced real-world example with lifecycle phases, hypothesis-driven research, and LLM provenance tracking |

On first run, the MCP will prompt you to select a schema or auto-generate one from your existing tasks.

---

## Security

This tool gives an LLM indirect access to your task management CLI. Security is not optional:

- **No shell execution** — all CLI calls use subprocess argument lists, never `shell=True`
- **Input sanitization** — all LLM inputs validated against allowlists before passing to CLI
- **Rate limiting** — configurable per-minute/per-hour caps prevent runaway loops
- **Audit logging** — every operation logged with timestamp, tool, parameters, result, and `result_code`
- **Code-tagged envelopes** — every tool response includes a stable `code` field for machine-safe branching
- **Dry-run mode** — every destructive operation supports `dry_run` preview without mutation
- **Confirmation mode** — lifecycle operations use explicit confirmation tokens when confirmation is enabled
- **Sensitive field redaction** — configurable fields hidden from LLM responses

See [ADR 9](docs/adrs/ADRs.md), [ADR 13](docs/adrs/ADRs.md), and [ADR 14](docs/adrs/ADRs.md) for the full security and observability design.

---

## Taskwarrior Compatibility

| Version | Status |
|---|---|
| **Taskwarrior 3.x** (TaskChampion) | ✅ Fully supported |
| **Taskwarrior 2.x** (Taskserver/taskd) | ⏳ Planned for future release |

We focus on the modern Taskwarrior 3.x + TaskChampion stack. Taskserver (taskd) is deprecated and will receive limited support in a future version. See [ADR 8](docs/adrs/ADRs.md).

---

## Documentation

| Folder / file | Contents |
|---|---|
| [`docs/adrs/`](docs/adrs/) | Architecture Decision Records |
| [`docs/references/`](docs/references/) | Upstream tool reference (Taskd, TaskChampion, Timewarrior) |
| [`docs/manuals/quick_start.md`](docs/manuals/quick_start.md) | Manual `config.toml` setup — three lines + one restart |
| [`docs/manuals/initialization_flows.md`](docs/manuals/initialization_flows.md) | Which init path to use (LLM-driven vs CLI vs hand-edit) |
| [`docs/manuals/logrotate.md`](docs/manuals/logrotate.md) | Audit log rotation |
| [`docs/manuals/`](docs/manuals/) | Other operational manuals |
| [`docs/llm_context/`](docs/llm_context/) | LLM agent guidelines and tracked assumptions |
| [`docs/CONTRIBUTING.md`](docs/CONTRIBUTING.md) | How to contribute (branching, PRs, versioning) |
| [`docs/ROADMAP.md`](docs/ROADMAP.md) | Feature roadmap (v0.1.0 → v1.0.0) |
| [`schemas/`](schemas/) | Task schema presets (TOML) |
| [`scripts/setup_remote.sh`](scripts/setup_remote.sh) | One-shot remote-host bootstrap (Wintermute and friends) |

---

## Troubleshooting

Common first-run and config issues. Detailed walkthroughs live in [docs/manuals/quick_start.md](docs/manuals/quick_start.md) and [docs/manuals/initialization_flows.md](docs/manuals/initialization_flows.md).

| Symptom | Likely cause | Fix |
|---|---|---|
| Tool surface in your IDE shows `get_initialization_status` / `save_initial_schema` after restart | `~/.config/taskchampion-mcp/config.toml` is missing either `role` or `schema`/`schema_path` | Add both under `[server]` and restart the IDE. The server treats either missing as "still onboarding". |
| Linux Claude Desktop install completes but taskchampion never appears | Pre-v0.3.0 lowercase path bug in dev.sh — wrote to `~/.config/claude/` instead of `~/.config/Claude/` | Update to v0.3.0+ or pull from `dev`. Linux filesystems are case-sensitive; capital `C` is the correct directory. |
| `set_role("MANAGER")` returns `error_code: "role_elevation_forbidden"` | You're trying to raise role via MCP — intentionally forbidden ([ADR 17](docs/adrs/ADRs.md)) | Hand-edit `config.toml` or run `./dev.sh init --role MANAGER`, then restart the IDE. |
| MCP server fails on startup with `Taskwarrior not found on PATH` | `task` not installed or not on the MCP server's `PATH` | Install Taskwarrior 3.x. If installed elsewhere, set `task_binary = "/usr/local/bin/task"` under `[server]`. |
| Schema change via `set_active_schema` returned success but `get_schema_info` still shows the old schema | Server hasn't reloaded — runtime reload isn't implemented yet | Restart the IDE so the MCP server re-reads `config.toml`. (See `docs/llm_context/mcp_runtime_reload_pattern.md`.) |
| Cowork / Claude Desktop: install JSON written but Claude Desktop overwrites it on quit | Wrote config while Claude Desktop was running | Quit Claude Desktop first, or use `./dev.sh reinstall claude -r` which terminates and restarts it cleanly. |
| `requires_onboarding` still True after `./dev.sh init` succeeded | Wizard wrote schema but not role (pre-v0.3.0 bug) | Update to v0.3.0+. The wizard now defaults to `role = "CONTRIBUTOR"` when no `--role` is passed. |
| Tool surface includes neither onboarding nor contributor tools | Server failed to start (check stderr) | Run `taskchampion-mcp-server` directly from a shell — the startup error goes to stderr and tells you exactly what's missing. |
| Want to switch schemas without restart | Not yet supported — runtime reload is open work | Restart the IDE after `set_active_schema(...)` or after hand-editing `config.toml`. |

For deeper failure modes, every MCP tool returns a stable `error_code` field ([ADR 14](docs/adrs/ADRs.md)) and every call is audit-logged ([ADR 13](docs/adrs/ADRs.md)) at `~/.local/share/taskchampion-mcp/audit.log` by default.

---

## Contributing

See [`docs/CONTRIBUTING.md`](docs/CONTRIBUTING.md) for the full guide. Key points:

- Branch from `dev`, PR to `qa`, release from `qa` to `main`
- Semantic versioning (`vMAJOR.MINOR.PATCH`)
- LLM-assisted contributions must be attributed (see [`docs/llm_context/AGENTS.md`](docs/llm_context/AGENTS.md))
- All unverified assumptions must be logged in [`docs/llm_context/assumptions_and_ideas.md`](docs/llm_context/assumptions_and_ideas.md)

---

## License

[Apache License 2.0](LICENSE) — use freely for private and commercial purposes. Attribution required via the [NOTICE](NOTICE) file.

Copyright 2026 gabiup2

---

*This project was bootstrapped with assistance from Claude claude-sonnet-4-20250514 via Windsurf Cascade.*
