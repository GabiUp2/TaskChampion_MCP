# Message to Wintermute

From: Bartosz (via Claude on Seraph)
Re: TaskChampion MCP — first-run setup on your host

You are a Claude Code instance running on **Wintermute**. This note is the
authoritative source of truth for what to do *the first time* you encounter
this repo / a request involving Taskwarrior task management here. Read it
end-to-end before running anything.

---

## What you already have

- `claude` (Claude Code CLI) — that's you.
- `task` (Taskwarrior 3.x) — task storage, already configured to **sync** with
  Seraph. Tasks created here appear on Seraph and vice versa.
- Likely `timew` (Timewarrior) — optional, time tracking.
- A standard Linux user account; `~/.local/bin` on PATH (or via `uv tool`).

You do **NOT** have:

- `taskchampion-mcp` (the MCP server that lets you read/write Taskwarrior
  tasks through MCP tools instead of shelling out to `task ...`). You're
  about to install it.

## What you need to do

Run the bootstrap script in this directory:

```bash
./setup_remote.sh
```

Defaults (chosen by Bartosz for you specifically):

| Setting          | Value                       | Why                                             |
|------------------|-----------------------------|-------------------------------------------------|
| install source   | `git_dev`                   | Latest fixes from today's session — see ADR 17  |
| role             | `GENERATOR`                 | You autonomously create tasks; CONTRIBUTOR would be read-only |
| schema           | `authors_custom_example`    | Same as Seraph — keeps the taxonomy consistent across sync |
| auto-prereqs     | `false` (check only)        | If something's missing, you'll be told — install it manually |

Override any of these via flags. Run `./setup_remote.sh --help` for the full
list. A `--dry-run` mode is available; use it first if you're unsure.

The script is **idempotent** — safe to re-run. It backs up any existing
`~/.config/taskchampion-mcp/config.toml` before overwriting.

## What happens after the script succeeds

1. `taskchampion-mcp-server` is on your PATH (installed via `uv tool install`
   from the dev branch of this repo).
2. Claude Code's user-scoped MCP config now includes `taskchampion`. You can
   verify with `claude mcp list` — should show `✓ Connected`.
3. `~/.config/taskchampion-mcp/config.toml` is seeded with `role = "GENERATOR"`
   and `schema = "authors_custom_example"`. This means on next `claude`
   invocation the server starts directly in GENERATOR mode (read + annotate +
   modify + **create** tasks), bypassing onboarding entirely.
4. Your tool surface gains the taskchampion tools: `list_tasks`, `get_task`,
   `search_tasks`, `annotate_task`, `modify_task`, `create_task`, `start_task`,
   `stop_task`, `get_projects`, `get_tags`, `get_schema_info`,
   `get_active_context`, `timew_*`, plus the reconfigure tools
   (`set_active_schema`, `set_taxonomy_path`, `set_role` — downgrade only).

## What you CANNOT do

Read ADR 17 (`docs/adrs/ADRs.md`) before this surprises you:

- You **cannot self-elevate your role via MCP**. `set_role("MANAGER")` will
  return `error_code: role_elevation_forbidden` and refuse to touch the
  config. This is deliberate.
- If a workflow genuinely requires MANAGER (delete tasks, undo, etc.), the
  *user* must hand-edit `config.toml` and restart the `claude` session. Don't
  try to be clever about it — the refusal is the load-bearing security
  invariant that makes prompt-injection-via-task-content survivable.
- You can voluntarily **downgrade** your own role (e.g., drop to CONTRIBUTOR
  for a risky sub-task). That's encouraged when appropriate.

## What to do if something goes wrong

- `claude mcp list` shows `✗ Failed to connect` → run
  `taskchampion-mcp-server` directly from the shell; the error message goes to
  stderr. Most common cause: `task` binary not on PATH.
- `requires_onboarding` still True after install → check
  `~/.config/taskchampion-mcp/config.toml` actually has both `role` and
  `schema` (or `schema_path`) keys. If only one, you're in onboarding mode
  by design.
- Anything else → ask Bartosz on Seraph. Taskwarrior sync means he can see
  any task you annotate.

## How to acknowledge you've read this

Once the install is verified, leave Bartosz a Taskwarrior task he'll see on
Seraph after the next sync:

```bash
task add project:Infra "[Wintermute] taskchampion-mcp bootstrap complete" \
    +Wintermute +Setup \
    scope:work area:tooling phase:done
```

Then `task sync` (if sync isn't automatic). He'll see it on Seraph and know
you're operational.

---

End of message. Welcome aboard.
