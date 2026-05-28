# Initialization flows — which path to use

There are three ways to get TaskChampion MCP from a fresh install to a usable
state. They produce the same end result (a `config.toml` with `role` +
`schema`/`schema_path`) but differ in how much hand-holding the LLM does and
how much you do yourself.

## At a glance

| Path | Who drives | Best for | Cost |
|---|---|---|---|
| **A. LLM-driven onboarding** | Your AI assistant via MCP tools | First-time users; users who'd rather describe their workflow than learn the schema TOML format | One conversation + one IDE restart |
| **B. CLI wizard (`./dev.sh init`)** | You, from a shell | Contributors iterating on the dev build; non-interactive bootstrapping; scripted setups | One shell session + one IDE restart |
| **C. Manual `config.toml` edit** | You, in `$EDITOR` | You already know which role + preset you want; you're recreating a known-good config; you're scripting deployments | One file edit + one IDE restart |

All three paths are interchangeable. There is no "right" one — pick by who
should be doing the typing.

---

## Path A — LLM-driven onboarding (from inside your IDE)

You connect your IDE (Windsurf / Cursor / VS Code / Claude Desktop / Claude
Code via Neovim) to the MCP server with no config file. The server boots in
**onboarding mode**, registers only the onboarding tools, and tells the model
to walk you through setup.

The conversation flow the LLM is steered through:

1. **Status check** — `get_initialization_status` reports what already exists
   (taxonomy file, existing tasks, configured schema). Surfaces both
   `needs_onboarding` (schema state) and `needs_role_selection`.
2. **Option proposal** — `propose_initialization_options` returns a menu:
   - `use_taxonomy` — best if you have a `TAXONOMY.md`.
   - `infer_from_tasks` — schema heuristics from `task export`.
   - `hybrid_taxonomy_plus_tasks` — taxonomy semantics + empirical checks.
   - `use_builtin_preset` — pick from `minimal`/`gtd`/`kanban`/`scrum`/`authors_custom_example`.
   - Plus a `roles` block listing CONTRIBUTOR/GENERATOR/MANAGER with
     descriptions. The model presents this to you alongside the schema choice.
3. **Generate or pick**:
   - For generation paths: `analyze_existing_tasks_for_schema` and/or
     `analyze_taxonomy_file` → `generate_initial_schema_preview` → review the
     TOML the model shows you → `save_initial_schema(role=..., ...)`.
   - For preset paths: `list_preset_schemas` → `use_preset_schema(preset_name=..., role=...)`.
4. **Restart the IDE** — `requires_onboarding` will now return `False`.
   The server registers the role-tier tool surface (CONTRIBUTOR /
   GENERATOR / MANAGER tools, plus the reconfigure tools).

**When path A works well:**

- You don't know exactly what schema you want yet — the LLM can show you
  options.
- You have a taxonomy file (`user/TAXONOMY.md` or similar) and want it
  parsed into a schema you can review.
- You want the role choice surfaced and explained (CONTRIBUTOR vs
  GENERATOR vs MANAGER) before you commit.

**When path A is the wrong tool:**

- You're bootstrapping a fleet of remote hosts. Use path B (with `--non-interactive`).
- You already know exactly what you want. Use path C — it's one file edit.

---

## Path B — CLI wizard (`./dev.sh init`)

From a shell in the repo checkout:

```bash
./dev.sh init                                  # interactive; prompts for everything
./dev.sh init --preset gtd --role CONTRIBUTOR  # non-interactive preset path
./dev.sh init --preset minimal --role CONTRIBUTOR --non-interactive
./dev.sh init --taxonomy ~/notes/TAXONOMY.md   # generate schema from a taxonomy file
./dev.sh init --list-presets                   # discover preset names
```

The wizard calls into the same `taskchampion_mcp.onboarding` functions the
MCP tools use, so the end state is byte-identical to what path A produces.
Difference: you drive it from the shell, not the LLM. Useful when:

- You're writing a setup script (e.g. `scripts/setup_remote.sh` does this).
- You don't have the LLM connected yet (chicken-and-egg avoidance).
- You want non-interactive defaults: pass `--preset` + `--role` +
  `--non-interactive` and the wizard runs end-to-end without prompts.

The `--role` flag accepts `CONTRIBUTOR` / `GENERATOR` / `MANAGER`. Omitting it
interactively prompts (defaults to CONTRIBUTOR); omitting it
non-interactively defaults to CONTRIBUTOR silently.

---

## Path C — Manual `config.toml` edit

See [quick_start.md](quick_start.md) — full walkthrough including a TL;DR
heredoc and a verification snippet.

In short: write two keys (`role` and `schema`-or-`schema_path`) under
`[server]` in `~/.config/taskchampion-mcp/config.toml`, restart the IDE. Done.

**When path C is right:**

- You're recreating a known-good config from another machine.
- You're deploying via configuration management (Ansible / Nix / dotfiles
  repo). The config is small and TOML; no wizard needed.
- You're confident you know what you want and don't need the LLM's options
  menu.

---

## Changing your mind later

Once `requires_onboarding == False`, the onboarding tools disappear from the
MCP surface. The post-onboarding equivalents are:

- `set_active_schema(schema_name="...")` or `set_active_schema(schema_path="...")`
- `set_taxonomy_path("/path/to/TAXONOMY.md")`
- `set_role("CONTRIBUTOR")` — **downgrade only**. Will return
  `error_code: "role_elevation_forbidden"` if you ask for a higher level.

To raise the role you must use path B (`./dev.sh init --role MANAGER`) or
path C (hand-edit). This is intentional — see [ADR 17][adr17].

[adr17]: ../adrs/ADRs.md

---

## "Which one should I use" decision tree

```
Are you on a fresh box with no config and your LLM is already connected?
├── Yes  → Path A (let the LLM walk you through it)
└── No
    ├── Do you already know which role + schema you want?
    │   ├── Yes  → Path C (edit ~/.config/taskchampion-mcp/config.toml)
    │   └── No   → Path B with no flags (interactive wizard) or Path A
    │
    └── Are you scripting / bootstrapping a remote host?
        └── Path B with --preset --role --non-interactive
            (or copy a known-good config.toml — path C in script form)
```
