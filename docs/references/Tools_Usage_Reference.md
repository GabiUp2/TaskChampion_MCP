# Tools Usage Reference

**Purpose:** Consolidated reference for the three upstream tools this MCP integrates with. Used during development and testing to ensure correct CLI interactions, configuration assumptions, and data format handling.

**Sources:** Official project documentation, GitHub/GitLab release pages, and the project author's live Taskwarrior installation. See `deep-research-report.md` in the repository root for full citations.

---

## 1. Tool Overview

| Attribute | Taskserver (taskd) | TaskChampion Sync Server | Timewarrior |
|---|---|---|---|
| **Project** | Gothenburg Bit Factory | Gothenburg Bit Factory | Gothenburg Bit Factory |
| **Homepage** | taskwarrior.org | taskwarrior.org (TaskChampion) | timewarrior.net |
| **Latest Release** | v1.1.0 (2015-05-10) | v0.7.1 (2025-10-11) | v1.9.1 (2025-08-27) |
| **License** | MIT | MIT | MIT |
| **Language** | C++ | Rust | C++ |
| **Status** | **Deprecated** — archived, no active development | Active development | Active development |
| **Taskwarrior Compat** | 2.x only | 3.x only | Both (via hooks) |
| **Sync Protocol** | Custom JSON-over-GnuTLS (TCP) | HTTP+JSON (TaskChampion protocol) | None (local only) |
| **MCP Priority** | Deferred (future) | **Primary target** | Secondary (time tracking) |

---

## 2. Taskserver (taskd) — Deprecated

### Summary
Taskserver is the legacy sync daemon for Taskwarrior 2.x. It uses TLS certificates for authentication and a custom binary protocol. The code repository is archived. **This MCP does not support Taskserver in v0.1.0** (see ADR 8).

### Installation
- Distro packages: `apt install taskd` (Debian), `pacman -S taskd` (Arch)
- Source: CMake build from GitHub (archived)
- No official Docker images

### Configuration
- Data root: `$TASKDDATA` env var or `--data <root>` flag
- Config file: `$TASKDDATA/config` (managed via `taskd config`)
- TLS certificates: stored in `pki/` under data root
- Default server: `localhost:53589`

### Key Commands
```bash
taskd init --data <root>          # Initialize server data store
taskd server [--daemon]           # Start the sync server
taskd add user <org> <user>       # Create a user
taskd remove user <org> <user>    # Remove a user
taskd config <name> [<value>]     # View/modify config
taskd diagnostics                 # System diagnostics
```

### Known Limitations
- No updates since 2015
- Complex PKI setup required
- Only works with Taskwarrior 2.x
- No Docker images, no modern packaging

---

## 3. TaskChampion Sync Server — Primary Target

### Summary
TaskChampion is the modern HTTP-based sync server for Taskwarrior 3.x. It stores encrypted task data (the server never sees plaintext tasks). Clients identify via UUID-based client IDs. Frequent releases during 2024-2025.

### Installation
- **Docker** (recommended for self-hosting):
  ```bash
  docker run -d --name=taskchampion \
      -p 8080:8080 \
      -e RUST_LOG=info \
      -v /path/to/data:/var/lib/taskchampion-sync-server/data \
      ghcr.io/gothenburgbitfactory/taskchampion-sync-server:latest
  ```
- **Binary**: download from GitHub releases (SQLite or Postgres variants)
- **Source**: Rust/Cargo (`cargo build --release`)
- No official distro packages yet

### Configuration
All via CLI flags or environment variables:

| Setting | Env Var | CLI Flag | Default |
|---|---|---|---|
| Listen address | `LISTEN` | `--listen` | `0.0.0.0:8080` |
| SQLite data dir | `DATA_DIR` | `--data-dir` | `/var/lib/taskchampion-sync-server/data` |
| Postgres connection | `CONNECTION` | `--connection` | (none) |
| Allowed client IDs | `CLIENT_ID` | `--allow-client-id` | (all allowed) |
| Auto-create clients | `CREATE_CLIENTS` | `--no-create-clients` | `true` |
| Log level | `RUST_LOG` | — | (none) |

### Taskwarrior Client Config
In `~/.taskrc` or `~/.config/task/taskrc`:
```ini
sync.server.url=http://<YOUR_SERVER_IP>:8080
sync.server.client_id=<YOUR_CLIENT_UUID>
sync.encryption_secret=<YOUR_ENCRYPTION_SECRET>
```

### Key Commands (server-side)
```bash
taskchampion-sync-server --listen 0.0.0.0:8080 --data-dir /srv/taskchampion
```

### Key Commands (client-side — Taskwarrior 3.x)
```bash
task sync                         # Push/pull changes to TaskChampion server
```

### Security Model
- All task data is encrypted client-side with `sync.encryption_secret`
- Server stores only opaque encrypted blobs
- Client IDs (UUIDs) identify replicas; no username/password auth
- TLS termination must be handled by a reverse proxy (server does not do TLS)

### Known Limitations
- Postgres backend requires manual schema setup
- No built-in TLS (needs reverse proxy)
- No built-in authentication beyond client ID trust
- Docker images do not auto-configure HTTPS

---

## 4. Timewarrior — Time Tracking

### Summary
Timewarrior is a CLI time-tracking tool. It is local-only (no sync server). It integrates with Taskwarrior via an `on-modify` hook that automatically starts/stops time tracking when tasks are started/completed.

### Installation
- Distro packages: `apt install timewarrior` (Debian), `pacman -S timew` (Arch), `dnf install timew` (Fedora), `brew install timewarrior` (macOS)
- Source: CMake build

### Configuration (XDG paths since v1.5.0)
| Item | Path |
|---|---|
| Config file | `~/.config/timewarrior/timewarrior.cfg` |
| Data directory | `~/.local/share/timewarrior/data/` |
| Extensions | `~/.config/timewarrior/extensions/` |
| Legacy config | `~/.timewarrior/timewarrior.cfg` |
| Override env var | `TIMEWARRIORDB` |

Data files: monthly `.data` files (text), `tags.data`, `undo.data`.

### Key Commands
```bash
timew start [tags...]             # Start tracking
timew stop                        # Stop current interval
timew resume                      # Resume last interval
timew continue                    # Alias for resume
timew summary [:week] [tags]      # Show time summaries
timew day                         # Today's intervals
timew week                        # This week's intervals
timew month                       # This month's intervals
timew add <duration> [tags]       # Log past time
timew modify start @<id> <time>   # Modify interval start
timew delete @<id>                # Delete an interval
timew tag @<id> <tag>             # Add tag to interval
timew untag @<id> <tag>           # Remove tag from interval
timew cancel                      # Cancel active tracking (no record)
timew gaps                        # Show untracked gaps
timew export                      # JSON export of intervals
timew undo                        # Undo last change
timew config <name> <value>       # Set config option
```

### Taskwarrior Integration (on-modify hook)
The hook script `on-modify.timewarrior` is shipped with Timewarrior. When installed in `~/.task/hooks/` (or `~/.config/task/hooks/`):

```bash
# Install the hook
cp /usr/share/doc/timew/ext/on-modify.timewarrior ~/.config/task/hooks/
chmod +x ~/.config/task/hooks/on-modify.timewarrior
```

**Behavior:**
- `task <id> start` → hook calls `timew start` with task tags
- `task <id> stop` → hook calls `timew stop`
- `task <id> done` → hook calls `timew stop`

### Data Format (JSON export)
```json
[
  {
    "id": 1,
    "start": "20260525T090000Z",
    "end": "20260525T111500Z",
    "tags": ["ProjectA", "work"]
  }
]
```

### Known Limitations
- No sync capability (local only; user must sync via git/rsync)
- Single-user only
- Hook integration depends on correct hook installation and permissions
- Tags in Timewarrior are independent of Taskwarrior tags (hook bridges them)

---

## 5. Taskwarrior CLI — Primary Interface

This is the tool the MCP server wraps directly. Not a server, but the client CLI.

### Data Location
```
~/.local/share/task/              # XDG data (Taskwarrior 3.x default)
~/.task/                          # Legacy data location
~/.taskrc                         # Legacy config (or ~/.config/task/taskrc)
```

### Key Commands for MCP Integration

#### Reading (safe, used by all roles)
```bash
task export                       # All pending tasks as JSON array
task <filter> export              # Filtered JSON export
task <uuid> export                # Single task by UUID
task count                        # Count matching tasks
task <uuid> info                  # Detailed human-readable info
task projects                     # List all projects
task tags                         # List all tags
task udas                         # List defined UDAs
task show                         # Show all config settings
task _version                     # Taskwarrior version string
task diagnostics                  # Full diagnostic info
```

#### Writing (role-gated)
```bash
task add "<description>" [fields] # Create task (GENERATOR+)
task <uuid> modify <field>:<val>  # Modify field (CONTRIBUTOR+)
task <uuid> annotate "<text>"     # Add annotation (CONTRIBUTOR+)
task <uuid> denotate "<text>"     # Remove annotation (CONTRIBUTOR+)
task <uuid> start                 # Start working (CONTRIBUTOR+)
task <uuid> stop                  # Stop working (CONTRIBUTOR+)
task <uuid> done                  # Complete task (MANAGER only)
task <uuid> delete                # Delete task (MANAGER only)
task undo                         # Undo last change (MANAGER only)
task sync                         # Sync with server (MANAGER only)
```

### JSON Export Format
```json
[
  {
    "id": 42,
    "uuid": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    "description": "Set up automated backups on homelab server",
    "status": "pending",
    "project": "personal.infra.myserver.backup",
    "priority": "M",
    "tags": ["linux", "ansible"],
    "entry": "20260520T140000Z",
    "modified": "20260524T090000Z",
    "due": "20260601T000000Z",
    "urgency": 18.8,
    "annotations": [
      {
        "entry": "20260521T100000Z",
        "description": "Researching restic vs borgbackup"
      }
    ],
    "scope": "personal",
    "area": "infra",
    "phase": "research",
    "hypothesis": "restic is faster than borgbackup on Pi 4",
    "versus": "restic vs borgbackup",
    "decides": "backup solution for homelab",
    "effort": "M",
    "confidence": "M",
    "gen_model": "",
    "gen_persona": "",
    "gen_harness": ""
  }
]
```

### UDA Definitions (from author's installation)
Defined in `~/.config/task/meta.taskrc`:

| UDA | Type | Values | Required | Notes |
|---|---|---|---|---|
| `scope` | string | `personal`, `work` | Always | Top-level domain discriminator |
| `client` | string | free | When `scope:work` | Client/org name |
| `area` | string | `infra`, `dev`, `learning`, `ops`, `data`, `security`, `tooling`, `career` | Recommended | Functional domain |
| `phase` | string | `idea`, `research`, `design`, `testing`, `impl`, `validate`, `blocked` | Always | Lifecycle position |
| `hypothesis` | string | free | When `phase:research` or `phase:testing` | Falsifiable claim being investigated |
| `versus` | string | free | When `phase:testing` | Options under comparison |
| `effort` | string | `XS`, `S`, `M`, `L`, `XL` | Recommended | T-shirt size estimate |
| `confidence` | string | `H`, `M`, `L` | Recommended | How well-defined the task is |
| `decides` | string | free | Optional | What decision this task informs |
| `gen_model` | string | free | When LLM-generated | LLM model name |
| `gen_persona` | string | free | When LLM-generated | Persona/system-prompt used |
| `gen_harness` | string | free | When LLM-generated | Tool context (cowork, mcp, etc.) |
| `review` | date | ISO date | Optional | Scheduled review date |

### Custom Reports (from author's installation)
| Report | Filter | Purpose |
|---|---|---|
| `task urgent` | pending, not waiting, top 25 | Daily triage |
| `task work` | `scope:work`, pending | All work tasks |
| `task personal` | `scope:personal`, pending | All personal tasks |
| `task focus` | `phase:impl`, pending, top 15 | What to execute today |
| `task phases` | pending, sorted by phase | Situational overview |
| `task research` | `phase:research,testing` | Research with hypothesis context |
| `task llmgen` | `gen_model.any:`, pending | LLM-generated tasks |
| `task blocked_tasks` | `phase:blocked`, pending | Blocked tasks with review dates |

---

## 6. Integration Map

```
┌─────────────────┐     task sync      ┌──────────────────────┐
│  Taskwarrior 3  │◄──────────────────►│  TaskChampion Server │
│  (task CLI)     │     HTTP+JSON      │  (self-hosted)       │
└────────┬────────┘     (encrypted)    └──────────────────────┘
         │
         │ on-modify hook
         ▼
┌─────────────────┐
│   Timewarrior   │
│   (timew CLI)   │
└─────────────────┘
         ▲
         │
         │  subprocess calls
         │
┌────────┴────────┐
│  TaskChampion   │     stdio          ┌──────────────────────┐
│  MCP Server     │◄──────────────────►│  LLM Client (IDE)    │
│  (this project) │     MCP protocol   │  Cursor/Windsurf/    │
└─────────────────┘                    │  VSC/NVIM/Claude     │
                                       └──────────────────────┘
```

### Data Flow
1. LLM sends MCP tool call (e.g., `create_task`) via stdio
2. MCP server validates input against schema + role permissions
3. MCP server calls `task add ...` via subprocess (sanitized arguments)
4. Taskwarrior processes the command, fires hooks (e.g., Timewarrior)
5. MCP server parses output, returns structured result to LLM
6. Audit log records the operation

### Important: UUID vs ID
- **UUID** — stable across syncs, should be used for all programmatic operations
- **ID** — local sequential number, can change after sync; use only for display
- The MCP server should always use UUIDs when calling `task <uuid> modify/done/delete`

---

## 7. Version Detection

The MCP server should detect the Taskwarrior version at startup:

```bash
task _version    # Returns version string, e.g., "3.1.0" or "2.6.2"
```

- **3.x**: full support (TaskChampion sync, modern CLI output)
- **2.x**: warn user, offer limited support in future release
- **Not found**: error with installation instructions

For Timewarrior:
```bash
timew --version  # Returns version string, e.g., "1.9.1"
```

- **Found**: register Timewarrior MCP tools
- **Not found**: skip Timewarrior tools, log info message
