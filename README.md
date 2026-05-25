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
- **Audit logging** — every operation logged with timestamp, tool, parameters, and result
- **Dry-run mode** — preview changes before executing
- **Confirmation mode** — destructive operations (delete, done) require explicit confirmation
- **Sensitive field redaction** — configurable fields hidden from LLM responses

See [ADR 9](docs/adrs/ADRs.md) for the full security design.

---

## Taskwarrior Compatibility

| Version | Status |
|---|---|
| **Taskwarrior 3.x** (TaskChampion) | ✅ Fully supported |
| **Taskwarrior 2.x** (Taskserver/taskd) | ⏳ Planned for future release |

We focus on the modern Taskwarrior 3.x + TaskChampion stack. Taskserver (taskd) is deprecated and will receive limited support in a future version. See [ADR 8](docs/adrs/ADRs.md).

---

## Documentation

| Folder | Contents |
|---|---|
| [`docs/adrs/`](docs/adrs/) | Architecture Decision Records |
| [`docs/references/`](docs/references/) | Upstream tool reference (Taskd, TaskChampion, Timewarrior) |
| [`docs/manuals/`](docs/manuals/) | User and technical manuals (coming soon) |
| [`docs/llm_context/`](docs/llm_context/) | LLM agent guidelines and tracked assumptions |
| [`docs/CONTRIBUTING.md`](docs/CONTRIBUTING.md) | How to contribute (branching, PRs, versioning) |
| [`docs/ROADMAP.md`](docs/ROADMAP.md) | Feature roadmap (v0.1.0 → v1.0.0) |
| [`schemas/`](schemas/) | Task schema presets (TOML) |

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
