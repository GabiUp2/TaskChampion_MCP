# LLM Agent Guide — Taskwarrior Operations
**Schema v1.0.0** | Full taxonomy: `~/.config/task/TAXONOMY.md`

This document defines how an LLM agent should interact with this Taskwarrior installation. It covers reading, creating, modifying, completing, and querying tasks. Follow these rules precisely — they encode the operator's preferences, not just conventions.

---

## 0. Before You Do Anything

1. **Read `TAXONOMY.md`** if you haven't in this session. It defines all UDA semantics.
2. **Never modify tasks without explicit operator intent.** Reading and querying are always safe. Mutations require either a direct instruction or a clearly implied workflow step.
3. **Always export first, then act.** Read current state before proposing any change.
4. **Run `task sync` before and after any batch mutations** if the operator is on a multi-machine setup.

```bash
task sync                         # sync before reading if state freshness matters
task export | python3 -c "..."   # always read before proposing modifications
```

---

## 1. Reading Tasks

### Get all pending tasks as structured JSON
```bash
task export
```
Filter in Python or with Taskwarrior native filters:
```bash
task scope:work export
task phase:impl export
task project:personal.infra.<homelab> export
```

### Key fields to read per task
```
uuid          — stable identifier, use for all modify/done commands
id            — local sequential id, can shift after sync — prefer uuid for scripts
description   — the task text
project       — dot-notation namespace (see TAXONOMY.md §1)
status        — pending | completed | deleted | waiting
phase         — idea|research|design|testing|impl|validate|blocked
scope         — personal | work
area          — infra|dev|learning|ops|data|security|tooling|career
client        — work tasks only
hypothesis    — what is being investigated (research/testing)
versus        — options under comparison (testing only)
decides       — what decision this feeds
effort        — XS|S|M|L|XL
confidence    — H|M|L
priority      — H|M|L (built-in Taskwarrior)
urgency       — computed float — do not set manually
due           — ISO date string
gen_model     — LLM model that authored this task
gen_persona   — persona/system-prompt used
gen_harness   — tool context (cowork|claude-code|api|mcp|human)
annotations   — list of {entry, description} — free notes and links
tags          — list of strings
```

### Interpreting urgency
Do not interpret raw urgency numbers as absolute priority. Use them for relative ordering within a filtered set. High urgency from `phase:blocked` tasks is suppressed by a -5.0 coefficient — blocked tasks appearing high in urgency despite that coefficient indicates the underlying task has extreme age or due-date pressure.

---

## 2. Adding Tasks

### Required fields on every new task
```
description   — imperative sentence, specific and actionable
project       — must follow the namespace hierarchy in TAXONOMY.md §1
scope         — personal | work
area          — from the controlled vocabulary
phase         — never omit; assign honestly based on where the task sits in lifecycle
```

### Conditionally required
```
hypothesis    — REQUIRED when phase:research or phase:testing
versus        — REQUIRED when phase:testing
client        — REQUIRED when scope:work
gen_model     — REQUIRED when you (an LLM) create this task
gen_persona   — REQUIRED when you create this task
gen_harness   — REQUIRED when you create this task
```

### Add task command pattern
```bash
task add "Description here" \
  project:<namespace> \
  scope:<personal|work> \
  area:<domain> \
  phase:<stage> \
  effort:<XS|S|M|L|XL> \
  confidence:<H|M|L> \
  [client:<name>] \
  [priority:<H|M|L>] \
  [due:<date>] \
  [hypothesis:"..."] \
  [versus:"..."] \
  [decides:"..."] \
  [+tag1] [+tag2] \
  gen_model:<model-string> \
  gen_persona:<persona-name> \
  gen_harness:<harness-name>
```

### Concrete example — LLM generating a task during a debug session
```bash
task add "Add idempotent client registration on taskchampion-sync-server startup"
  project:personal.infra.<homelab>.services \
  scope:personal \
  area:infra \
  phase:impl \
  effort:M \
  confidence:H \
  decides:"taskchampion sync reliability" \
  +rust +taskwarrior \
  gen_model:claude-sonnet-4-6 \
  gen_persona:DSSD \
  gen_harness:cowork
```

### Adding multiple related tasks (research + impl pair)
When breaking a problem into a research task and a downstream impl task, create both and link them with `depends`:

```bash
# Step 1 — create the research task and capture its uuid
task add "Research borgbackup vs restic for Pi 4 incremental backups" \
  project:personal.infra.<homelab>.backup \
  scope:personal area:infra \
  phase:research \
  hypothesis:"restic is faster and simpler to configure than borgbackup on aarch64" \
  versus:"restic vs borgbackup" \
  decides:"backup solution for homelab" \
  effort:S confidence:M \
  gen_model:claude-sonnet-4-6 gen_persona:DSSD gen_harness:cowork

# Capture uuid of the above task
RESEARCH_UUID=$(task project:personal.infra.<homelab>.backup phase:research \
  description:"Research borgbackup" _uuid 2>/dev/null | head -1)

# Step 2 — create the impl task that depends on research
task add "Implement borgbackup/restic with daily cron and retention policy on homelab" \
  project:personal.infra.<homelab>.backup \
  scope:personal area:infra \
  phase:impl \
  effort:M confidence:L \
  decides:"backup solution for homelab" \
  depends:$RESEARCH_UUID \
  gen_model:claude-sonnet-4-6 gen_persona:DSSD gen_harness:cowork
```

---

## 3. Modifying Tasks

### Always use UUID for modifications in scripts
```bash
task <uuid> modify <field>:<value>
```
Use local `id` only for one-off interactive modifications where sync hasn't happened mid-session.

### Phase promotion — the primary modification workflow
Each promotion may require adding or clearing fields:

```bash
# idea → research
task <uuid> modify \
  phase:research \
  hypothesis:"<falsifiable claim about what you're investigating>"

# research → testing
task <uuid> modify \
  phase:testing \
  versus:"<option A> vs <option B>"

# testing → impl (commit to a direction)
task <uuid> modify phase:impl
task <uuid> annotate "Decision: chose <option> — <brief reason>"
# Optionally clear hypothesis/versus (Taskwarrior doesn't clear on modify,
# but they become noise; annotate the decision and leave them for audit trail)

# impl → validate
task <uuid> modify phase:validate

# validate → done
task <uuid> done
```

### Adding context mid-flight
```bash
# Add a decision link
task <uuid> modify decides:"remote access method for homelab"

# Add a due date
task <uuid> modify due:2024-06-30

# Add tags
task <uuid> modify +python +azure

# Bump priority
task <uuid> modify priority:H

# Set review date on a blocked task
task <uuid> modify phase:blocked review:2024-03-01
task <uuid> annotate "Blocked: waiting for SSD delivery before encrypting"

# Improve confidence once scope is clearer
task <uuid> modify confidence:H effort:M
```

### Bulk modify (with care)
```bash
# Promote all personal.learning.certs tasks to research phase
task project:personal.learning.certs phase:idea modify phase:research
# WARNING: confirm count first:
task project:personal.learning.certs phase:idea count
```

---

## 4. Completing Tasks

```bash
task <uuid> done
```

Before marking done:
- Verify `phase` is `review` or `impl` — completing from `idea` or `research` is a signal that scope changed, which may warrant an annotation.
- If the task was part of a `decides:` decision tree, annotate the outcome so the record is useful:
  ```bash
  task <uuid> annotate "Outcome: <what was decided and why>"
  task <uuid> done
  ```

### Deleting (not completing)
Only delete tasks that were created in error or are true duplicates. Completed tasks are history — don't delete them.
```bash
task <uuid> delete
```

---

## 5. Querying for Context

### What is the operator working on right now?
```bash
task +ACTIVE export                          # started (task start <id>)
task phase:impl +next export                 # marked for today
task focus                                   # impl tasks, urgency-sorted
```

### What decisions are currently being researched?
```bash
task phase:research,testing export | python3 -c "
import sys, json
tasks = json.load(sys.stdin)
for t in tasks:
    print(t.get('decides','(no decides)'), '|', t.get('versus',''), '|', t['description'][:60])
"
```

### What is blocked and when does it need review?
```bash
task phase:blocked export
task review.before:today export              # overdue for review
```

### What tasks belong to a specific decision?
```bash
task decides:"backup solution for homelab" export
```

### What work tasks have no phase set?
```bash
task scope:work phase: export               # missing phase
```

### What is the current project-level state of a domain?
```bash
task project:personal.infra.<homelab> export | python3 -c "
import sys, json
from collections import Counter
tasks = json.load(sys.stdin)
pending = [t for t in tasks if t['status'] == 'pending']
print('Phase distribution:', dict(Counter(t.get('phase','-') for t in pending)))
print('Effort distribution:', dict(Counter(t.get('effort','-') for t in pending)))
"
```

---

## 6. Creating New Projects

When the operator describes work that doesn't fit any existing project namespace:

1. Determine `scope` (personal or work) and `area` first.
2. Build the project name following the hierarchy rules in TAXONOMY.md §1.
3. Do not create more than 4 levels deep.
4. Announce the new project name before creating tasks, so the operator can correct it.

```
# Example reasoning
# Operator: "I want to set up a Grafana dashboard on the homelab"
# → scope:personal, area:infra, host:<homelab>, subsystem:monitoring
# → project:personal.infra.<homelab>.monitoring
# → New project. Announce: "I'll use personal.infra.<homelab>.monitoring — confirm?"
```

---

## 7. Constraints and Rules

### Never do these without explicit operator instruction
- `task <uuid> delete` — deletion is irreversible
- `task <filter> modify phase:idea` — demoting tasks loses urgency context
- `task <filter> done` — bulk completion
- Any modification to `sync.*` settings in `.taskrc`
- Any modification to tasks on a filter broader than a single project without a dry-run count first

### Be explicit about uncertainty
If you infer a `project`, `phase`, or `decides` value from context, say so and ask for confirmation before applying.

### Prefer annotation over field mutation for narrative context
Fields are for structured data that gets filtered and reported. Rationale, links, decisions, and observations go in annotations:
```bash
task <uuid> annotate "https://restic.readthedocs.io — see §3.2 for aarch64 notes"
task <uuid> annotate "Decision: restic chosen over borgbackup — simpler retention DSL"
```

### gen_* fields are immutable after creation
Do not modify `gen_model`, `gen_persona`, or `gen_harness` on existing tasks. They record provenance at the time of creation. If a task is substantially rewritten by a different agent, create a new task and delete the old one.

### hypothesis and versus are additive, not replacements
If a task's hypothesis is refined during research, annotate the refinement rather than overwriting:
```bash
task <uuid> annotate "Hypothesis refined: original assumed aarch64 parity — benchmarks show 15% gap, see notes"
task <uuid> modify hypothesis:"restic is faster than borgbackup for incremental backups on Pi 4, despite 15% base overhead"
```

---

## 8. Reporting Back to the Operator

When summarising task state for the operator, structure it as:

1. **Phase distribution** — how many tasks in each phase for the relevant project/scope
2. **Top urgency items** — the 3-5 highest urgency `impl` tasks
3. **Decisions in flight** — unique `decides:` values with their current phase
4. **Blocked items** — count and nearest review dates
5. **Provenance note** — if you created tasks in this session, list them explicitly with UUIDs

Example summary format:
```
personal.infra.myserver — 10 pending
  impl: 7   research: 2   blocked: 1

Top urgency:
  [58] Set up automated backups (borgbackup/restic)  urg:20.9  effort:M
  [59] Deploy Taskwarrior server in Docker            urg:18.8  effort:L
  [63] Conduct security audit                         urg:16.8  effort:?

Decisions in flight:
  "backup solution for homelab" — phase:research (1 task)
  "remote access method for homelab" — phase:research (1 task)

Blocked: 0

Tasks created this session: none
```
