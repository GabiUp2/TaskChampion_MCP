# Taskwarrior Taxonomy Reference
**Schema version:** 1.0.0  
**Config file:** `~/.config/task/meta.taskrc`  
**For:** Human operators and LLM agents consuming tasks via MCP or `task export`

---

## Purpose

This document is the authoritative reference for interpreting Taskwarrior tasks in this installation. LLMs should read this before querying, creating, or modifying tasks. It defines project naming conventions, UDA semantics, phase lifecycle, tag usage, urgency tuning, and query patterns.

---

## 1. Project Namespace

Projects use dot-notation hierarchies. Always lowercase. Maximum depth: 4 levels.

### Personal projects
```
personal.dev.<machine-or-domain>         # dev environment, machine setup, tooling
personal.infra.<host>.<subsystem>        # homelab / self-hosted infrastructure
personal.learning.<domain>              # courses, certs, reading
personal.tooling.<tool>.<subsystem>     # meta-tooling (taskwarrior, nvim, etc.)
```

### Work projects
```
work.<org>.<client>.<domain>            # client engagement work
work.<org>.internal.<domain>            # internal/org work without a named client
```

### Current project map (as of schema v1.0.0)
| Project prefix | Meaning |
|---|---|
| `personal.dev.<workstation>` | Primary workstation (Arch Linux) setup & customization |
| `personal.dev` | Miscellaneous personal dev reading/exploration |
| `personal.infra.<homelab>` | Homelab server (Raspberry Pi, Debian Bookworm) |
| `personal.infra.<homelab>.backup` | Homelab backup system |
| `personal.infra.<homelab>.security` | Homelab security hardening |
| `personal.infra.<homelab>.services` | Services deployed on homelab |
| `personal.infra.<homelab>.automation` | CI/CD and automation for homelab |
| `personal.infra.<homelab>.configuration` | Repeatable config management (Ansible) |
| `personal.infra.<homelab>.documentation` | Homelab setup documentation |
| `personal.learning.certs` | Certifications (Databricks, AWS, Terraform, NVIDIA) |
| `personal.tooling.taskwarrior` | Taskwarrior mastery, config, integration |
| `personal.tooling.taskwarrior.addons` | Taskwarrior ecosystem addon research |
| `personal.tooling.taskwarrior.cheatsheet` | Taskwarrior cheatsheet creation |
| `work.<org>.<client>.monitoring` | Org/Client — monitoring and observability |
| `work.<org>.internal.configmgmt` | Org internal config management demo |

---

## 2. UDA Reference

All UDAs are defined in `~/.config/task/meta.taskrc`. Below is the full semantics reference.

### 2.1 `scope` — `personal | work`
**Required on all tasks.** Top-level discriminator. Use `scope:work` or `scope:personal` in every filter when you need to isolate one domain.

```bash
task scope:work                  # all work tasks
task scope:personal phase:impl   # personal tasks ready to execute
```

### 2.2 `client` — free string (lowercase)
Work tasks only. Names the client or org. Examples: `acme`, `globex`. For internal work without a named client, use the org name. Omit on personal tasks.

```bash
task client:acme                 # all Acme tasks
task client:globex phase:impl    # Globex implementation tasks
```

### 2.3 `area` — `infra | dev | learning | ops | data | security | tooling | career`
Functional domain. Enables cross-project clustering independent of the project name hierarchy.

| Value | Meaning |
|---|---|
| `infra` | Infrastructure, servers, networking, storage |
| `dev` | Software development, coding, machine setup |
| `learning` | Reading, courses, certifications, research consumption |
| `ops` | Operational tasks, monitoring, CI/CD, deployment |
| `data` | Data engineering, pipelines, analytics |
| `security` | Security hardening, auditing, access management |
| `tooling` | Developer tooling, workflow, productivity systems |
| `career` | Career development, networking, professional positioning |

### 2.4 `phase` — lifecycle position
**The most important UDA for situational awareness.** Every task should have a phase.

| Value | Meaning | Use `hypothesis`? | Use `versus`? |
|---|---|---|---|
| `idea` | Captured but unevaluated. Parking lot. | No | No |
| `research` | Actively gathering info to make a decision | Yes | No |
| `design` | Translating research into concrete plans | No | No |
| `testing` | Running experiments, A/B evaluation, validation | Yes | Yes |
| `impl` | Committed direction, executing | No | No |
| `validate` | Work done, needs validation or retro | No | No |
| `blocked` | Cannot proceed — external dependency | No | No |

**Phase progression (typical):**
```
idea → research → design → testing → impl → validate → done
                         ↘ (skip testing if no alternatives) ↗
```

```bash
task phase:impl                  # what to work on today
task phase:research              # what decisions are being researched
task phase:blocked               # what is stalled
```

### 2.5 `hypothesis` — free string
State the question or assumption being investigated as a falsifiable claim. Required when `phase:research` or `phase:testing`.

Examples:
- `"restic is faster than borgbackup for incremental backups on Pi 4 hardware"`
- `"Tailscale is sufficient for homelab remote access without Cloudflare Tunnel"`
- `"ncspot is a viable terminal Spotify client for daily use"`

### 2.6 `versus` — free string
Names the options under comparison. Required when `phase:testing`. Format: `"Option A vs Option B"`.

Examples:
- `"restic vs borgbackup"`
- `"Tailscale vs Cloudflare Tunnel vs WireGuard"`
- `"Backblaze vs rsync.net vs Hetzner Storage Box"`

### 2.7 `effort` — `XS | S | M | L | XL`
T-shirt size estimate. Not hours — order of magnitude only.

| Value | Rough time |
|---|---|
| `XS` | < 30 minutes |
| `S` | < 2 hours |
| `M` | Half a day |
| `L` | 1–2 days |
| `XL` | Multi-day or architectural scope |

### 2.8 `confidence` — `H | M | L`
How well-defined this task is. High confidence = clear scope, clear done criteria. Low confidence = fuzzy, needs decomposition before execution.

Affects urgency: `H` adds +1.0, `L` subtracts -1.5. Fuzzy tasks should not surface over clear ones.

### 2.9 `decides` — free string
What architectural or design decision this task informs or resolves. Primarily for LLM consumption — enables clustering related research/testing tasks by the decision they feed into. If software project follows/have 'ADRs' (Architectural Design Registry) add relevant ADR index to the decides.

Examples:
- `"backup solution for homelab"`
- `"remote access method for homelab"`
- `"LLM plugin choice for nvim, , ADR 19"`
- `"CI/CD approach for homelab services, , ADR 20"`

### 2.10 `gen_model` — free string
LLM model that generated or substantially contributed to this task's definition. Leave empty for human-authored tasks. Use the canonical model string.

Examples: `claude-sonnet-4-6`, `claude-opus-4-6`, `gpt-4o`, `gemini-2.5-pro`

### 2.11 `gen_persona` — free string
Named persona or system-prompt context used during generation. This captures *which role the LLM was playing* when it produced the task.

Examples: `DSSD` (Distributed Systems Sync Debugger), `default`, `senior-sre`, `data-engineer`

### 2.12 `gen_harness` — free string
Tool or integration that produced this task. Captures the *how* of generation.

| Value | Meaning |
|---|---|
| `human` | Human-authored (or leave empty) |
| `cowork` | Generated in Cowork mode |
| `claude-code` | Generated via Claude Code CLI |
| `api` | Generated via direct API call |
| `mcp` | Generated by an LLM via MCP tools |

```bash
task gen_harness:cowork gen_model:claude-sonnet-4-6   # tasks from this session
task gen_model.any:                                    # all LLM-generated tasks
```

### 2.13 `review` — date
When to revisit this task. Use on `phase:blocked` and `phase:idea` tasks to prevent them from becoming invisible.

```bash
task review.before:today                               # overdue for review
task phase:blocked review.any:                        # blocked with scheduled review
```

---

## 3. Tags

Tags capture **cross-cutting concerns that UDAs don't cover** — primarily technology stack. Keep them lowercase when possible for consistency.

### Technology tags (use freely)
`+linux`, `+python`, `+rust`, `+terraform`, `+databricks`, `+docker`, `+ansible`, `+nvim`, `+tmux`, `+spark`, `+kubernetes`, `+azure`, `+aws`

### Operational tags (reserved meanings)
| Tag | Meaning |
|---|---|
| `+next` | Selected for the current session/day's focus |
| `+waiting` | Blocked on someone else (use with `wait:` date) |
| `+ops` | Operational/on-call relevance |

### Avoid
- Using tags as a second project system (use project hierarchy instead)
- Capitalized tags (legacy — normalize to lowercase over time)
- Using tags for things that are now UDAs (scope, phase, area, client)
- Usage of Emoticons and out of keyboard characters.

---

## 4. Urgency Model

Default Taskwarrior urgency plus UDA coefficients:

| Factor | Coefficient | Notes |
|---|---|---|
| `scope:work` | +1.5 | Work tasks surface higher by default |
| `phase:impl` | +2.0 | Ready to execute = should be visible |
| `phase:testing` | +1.5 | Active experiments need attention |
| `phase:design` | +1.0 | Planning phase — moderate visibility |
| `phase:validate` | +1.0 | Needs validation — don't lose it |
| `phase:research` | +0.5 | Ongoing, not urgent day-to-day |
| `phase:idea` | -2.0 | Ideas recede until promoted |
| `phase:blocked` | -5.0 | Blocked tasks should not clutter queues |
| `confidence:H` | +1.0 | Clear tasks surface over fuzzy ones |
| `confidence:L` | -1.5 | Fuzzy tasks should not dominate |
| `effort:XS` | +0.3 | Quick wins get slight boost |
| `effort:XL` | -0.5 | Large tasks recede slightly |

---

## 5. Custom Reports

| Command | Description |
|---|---|
| `task urgent` | Cross-project top-25 by urgency — daily triage |
| `task work` | All work tasks by urgency |
| `task personal` | All personal tasks by urgency |
| `task focus` | `phase:impl` tasks only — what to execute today |
| `task phases` | All pending grouped by phase — situational overview |
| `task research` | Research/testing tasks with hypothesis/versus context |
| `task llmgen` | All LLM-generated tasks by entry date |
| `task blocked_tasks` | Blocked tasks with review dates |

---

## 6. Contexts

Predefined contexts for switching focus:

```bash
task context work       # scope:work filter on all reports
task context personal   # scope:personal filter on all reports
task context acme       # client:acme filter
task context none       # clear context
```

---

## 7. LLM Agent Query Patterns

When an LLM agent accesses tasks via MCP or `task export`, use these patterns:

### Get current work for a specific decision
```bash
task decides:"backup solution for homelab" export
```

### Identify what phase a project area is in
```bash
task project:personal.infra.<homelab> export | jq '[.[] | {description, phase, hypothesis, versus}]'
```

### Find all tasks blocking progress on an area
```bash
task scope:personal area:infra phase:blocked export
```

### Assess total research workload vs execution workload
```bash
task phase:research count
task phase:impl count
```

### Create a task with full provenance (from LLM/MCP)
```bash
task add "Description here" \
  project:personal.infra.<homelab>.backup \
  scope:personal area:infra \
  phase:research \
  hypothesis:"restic is faster than borgbackup on Pi hardware" \
  versus:"restic vs borgbackup" \
  decides:"backup solution for homelab" \
  effort:M confidence:M \
  gen_model:claude-sonnet-4-6 \
  gen_persona:DSSD \
  gen_harness:cowork
```

### Check LLM-generated task quality
```bash
task gen_model.any: confidence:L export   # LLM tasks that are still fuzzy
```

---

## 8. Maintenance

- **When promoting a task from `idea` → `research`:** Add `hypothesis:` describing what you're trying to answer.
- **When promoting from `research` → `testing`:** Add `versus:` naming the options. Keep `hypothesis:`.
- **When promoting from `testing` → `impl`:** Clear `hypothesis` and `versus`. Update description with chosen direction.
- **When creating tasks via LLM:** Always set `gen_model`, `gen_persona`, `gen_harness`.
- **Review `phase:idea` tasks** monthly. Promote or delete.
- **Review `phase:blocked` tasks** per their `review:` date.
