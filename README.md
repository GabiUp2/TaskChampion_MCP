# TaskChampion MCP

**A Model Context Protocol server for Taskwarrior 3.x, TaskChampion, and Timewarrior.**

> *For the bearded Unix jockeys and keyboard cowboys who manage their life from the terminal — and now want their LLM to lend a hand.* 🧔⌨️

<!-- mcp-name: io.github.GabiUp2/taskchampion-mcp -->

[![PyPI version](https://img.shields.io/pypi/v/taskchampion-mcp.svg)](https://pypi.org/project/taskchampion-mcp/)
[![GitHub release](https://img.shields.io/github/v/release/GabiUp2/TaskChampion_MCP.svg)](https://github.com/GabiUp2/TaskChampion_MCP/releases)
[![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.10+-green.svg)](https://python.org)
[![MCP Registry](https://img.shields.io/badge/MCP-Registry-blue)](https://registry.modelcontextprotocol.io/v0/servers?search=io.github.GabiUp2/taskchampion-mcp)
[![Glama](https://glama.ai/mcp/servers/GabiUp2/TaskChampion_MCP/badges/score.svg)](https://glama.ai/mcp/servers/GabiUp2/TaskChampion_MCP)

**Latest release:** [v1.0.2](https://github.com/GabiUp2/TaskChampion_MCP/releases/tag/v1.0.2) — [`pip install taskchampion-mcp`](https://pypi.org/project/taskchampion-mcp/) / `uvx taskchampion-mcp`

---

## What Is This?

TaskChampion MCP is a [Model Context Protocol](https://modelcontextprotocol.io) server that lets LLMs read, create, modify, and manage your Taskwarrior tasks and Timewarrior time entries. It wraps the `task` and `timew` CLI tools and exposes them as structured MCP tools that any compatible AI assistant can call.

**Why?** The author self-hosts [TaskChampion](https://github.com/GothenburgBitFactory/taskchampion-sync-server) on a home server and wanted a clean way for LLMs to cooperate on project planning, task decomposition, and time tracking — without giving up control of the task database.

---

## Supported Platforms

| Platform | Transport | Status |
|---|---|---|
| **Neovim** (via Claude Code CLI) | stdio | v1.0.2 |
| **Cursor** | stdio | v1.0.2 |
| **Windsurf** | stdio | v1.0.2 |
| **VS Code** (Copilot MCP) | stdio | v1.0.2 |
| **Claude Desktop** | stdio | v1.0.2 |
| **HTTP/SSE transports** | HTTP/SSE | Deferred to v1.x |

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

Per-target install guides: [Claude Desktop](docs/manuals/targets/claude_desktop.md) | [Windsurf](docs/manuals/targets/windsurf.md) | [Cursor](docs/manuals/targets/cursor.md) | [Neovim](docs/manuals/targets/neovim.md)

---

## First Run

On a fresh install with no `config.toml`, the server boots in **onboarding mode**. All tools are visible in `tools/list`, but operational tools return structured `schema_unset` errors until onboarding completes (ADR 19). You finish onboarding by persisting two keys in `~/.config/taskchampion-mcp/config.toml`:

- `role` — what the LLM can do (CONTRIBUTOR / GENERATOR / MANAGER)
- `schema` *or* `schema_path` — which task schema the server validates against

Three ways to get there:

1. **Let the LLM walk you through it.** Connect your IDE to the MCP server with no config and ask: *"Help me set up TaskChampion MCP."* The LLM calls `get_runtime_capabilities` first, sees `mode: "onboarding"`, then uses `get_initialization_status` -> `propose_initialization_options` -> `use_preset_schema` (or `save_initial_schema`). The server auto-reloads on success -- **no restart needed**.
2. **Run the CLI wizard:** `./dev.sh init` (interactive) or `./dev.sh init --preset gtd --role CONTRIBUTOR --non-interactive` (scripted).
3. **Edit `config.toml` by hand** -- see [quick_start.md](docs/manuals/quick_start.md). Two keys, then call `reload_configuration` from the LLM (or restart the IDE).

The three paths are interchangeable and produce identical state. Pick by who should be doing the typing -- see [initialization_flows.md](docs/manuals/initialization_flows.md) for the decision guide.

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
| [`docs/manuals/quick_start.md`](docs/manuals/quick_start.md) | Manual `config.toml` setup |
| [`docs/manuals/configuration_reference.md`](docs/manuals/configuration_reference.md) | Full config key reference with precedence rules |
| [`docs/manuals/schema_authoring.md`](docs/manuals/schema_authoring.md) | Writing custom task schemas |
| [`docs/manuals/security_model.md`](docs/manuals/security_model.md) | Security controls for end-users |
| [`docs/manuals/initialization_flows.md`](docs/manuals/initialization_flows.md) | Which init path to use (LLM-driven vs CLI vs hand-edit) |
| [`docs/manuals/targets/`](docs/manuals/targets/) | Per-IDE install guides (Claude Desktop, Windsurf, Cursor, Neovim) |
| [`docs/manuals/logrotate.md`](docs/manuals/logrotate.md) | Audit log rotation |
| [`docs/llm_context/`](docs/llm_context/) | LLM agent guidelines and tracked assumptions |
| [`docs/CONTRIBUTING.md`](docs/CONTRIBUTING.md) | How to contribute (branching, PRs, versioning) |
| [`docs/ROADMAP.md`](docs/ROADMAP.md) | Feature roadmap (v0.1.0 → v1.0.0) |
| [`docs/releases/v1.0.2.md`](docs/releases/v1.0.2.md) | v1.0.2 release notes and install links |
| [`docs/manuals/release_checklist.md`](docs/manuals/release_checklist.md) | Pre-tag publish checklist |
| [`src/taskchampion_mcp/schemas/`](src/taskchampion_mcp/schemas/) | Bundled task schema presets (TOML) |
| [`scripts/setup_remote.sh`](scripts/setup_remote.sh) | One-shot remote-host bootstrap |

---

## Troubleshooting

Common first-run and config issues. Detailed walkthroughs live in [docs/manuals/quick_start.md](docs/manuals/quick_start.md) and [docs/manuals/initialization_flows.md](docs/manuals/initialization_flows.md).

| Symptom | Likely cause | Fix |
|---|---|---|
| Tools return `schema_unset` errors after connecting | `~/.config/taskchampion-mcp/config.toml` is missing either `role` or `schema`/`schema_path` | Add both under `[server]` and call `reload_configuration` (or restart). |
| Linux Claude Desktop install completes but taskchampion never appears | Pre-v0.3.0 lowercase path bug in dev.sh | Update to v0.3.0+. Linux: capital `C` in `~/.config/Claude/`. |
| `set_role("MANAGER")` returns `role_elevation_forbidden` | Self-elevation via MCP is forbidden ([ADR 17](docs/adrs/ADRs.md)) | Hand-edit `config.toml`, then call `reload_configuration`. |
| MCP server fails on startup with `Taskwarrior not found on PATH` | `task` not installed or not on the MCP server's `PATH` | Install Taskwarrior 3.x. Set `task_binary` in config if needed. |
| Cowork / Claude Desktop: install JSON overwritten on quit | Wrote config while Claude Desktop was running | Quit Claude Desktop first, or use `./dev.sh reinstall claude -r`. |
| Tool surface includes neither onboarding nor contributor tools | Server failed to start (check stderr) | Run `taskchampion-mcp-server` from a shell to see the error. |

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
