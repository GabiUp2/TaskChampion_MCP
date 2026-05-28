# Schema Authoring Guide

TaskChampion MCP uses TOML schema files to define which fields exist, their
types, allowed values, and whether they are required
([ADR 7](../adrs/ADRs.md)). Five presets ship in the `schemas/` directory.
This guide covers writing custom schemas beyond those presets.

---

## TOML structure

A schema file has three sections: `[meta]`, `[fields.*]`, and optionally
`[llm_provenance]`.

### `[meta]`

```toml
[meta]
name = "my_custom_schema"
version = "1.0.0"
description = "Short description of the workflow this schema supports"
taskwarrior_version = "3.x"
```

| Key | Required | Description |
|---|---|---|
| `name` | yes | Unique identifier for the schema |
| `version` | yes | SemVer version string |
| `description` | yes | One-line summary for LLM and human context |
| `taskwarrior_version` | no | Target Taskwarrior version (informational) |

### `[fields.*]`

Each field is a TOML table under `fields`. The key is the Taskwarrior field
name (or UDA name).

```toml
[fields.priority]
type = "string"
required = false
values = ["H", "M", "L"]
description = "Task priority. H=high, M=medium, L=low."

[fields.scope]
type = "string"
required = true
allowed_values = ["personal", "work", "community"]
description = "Top-level organisational scope."
```

#### Field properties

| Property | Type | Default | Description |
|---|---|---|---|
| `type` | string | *(required)* | `"string"`, `"list"`, `"date"`, `"numeric"`, or `"duration"` |
| `required` | bool | `false` | Whether the field must be present when creating a task |
| `description` | string | `""` | Semantic description shown to the LLM for context |
| `values` | list | *(none)* | Enumerated allowed values (shorthand for `allowed_values`) |
| `allowed_values` | list | *(none)* | Enumerated allowed values. Alias of `values`; if both are present, `allowed_values` takes precedence |
| `default` | varies | *(none)* | Default value applied when the field is omitted |
| `conditions` | table | *(none)* | Conditional requirements (see below) |

#### Conditional requirements

A field can be conditionally required based on the value of another field.
Use the `conditions` sub-table:

```toml
[fields.hypothesis]
type = "string"
required = false
description = "What this research task is trying to prove or disprove."

[fields.hypothesis.conditions]
required_when = { field = "phase", value = "research" }
```

When `phase` is `"research"`, the `hypothesis` field becomes required. The
server enforces this at validation time and surfaces the requirement to the
LLM via `get_schema_info`.

#### Quoted keys for special characters

Taskwarrior UDA names can contain spaces or dots. Use quoted TOML keys to
preserve the original name ([ADR 11](../adrs/ADRs.md)):

```toml
[fields."field name"]
type = "string"
required = false

[fields."field.with.dots"]
type = "string"
required = false
```

Bare keys (alphanumeric, underscores, dashes) do not need quoting.

---

## Worked example: a minimal custom schema

```toml
[meta]
name = "freelance"
version = "1.0.0"
description = "Freelance project tracking with client and billing fields"
taskwarrior_version = "3.x"

[fields.description]
type = "string"
required = true
description = "Imperative sentence describing the deliverable."

[fields.project]
type = "string"
required = true
description = "Client.project hierarchy (e.g., 'acme.website-redesign')."

[fields.priority]
type = "string"
required = false
values = ["H", "M", "L"]

[fields.tags]
type = "list"
required = false

[fields.due]
type = "date"
required = false

[fields.client]
type = "string"
required = true
description = "Client name. Must match a known client identifier."

[fields.billable]
type = "string"
required = false
values = ["yes", "no"]
default = "yes"
description = "Whether this task is billable to the client."

[fields.rate_type]
type = "string"
required = false
values = ["hourly", "fixed", "retainer"]
description = "Billing rate classification."
```

Save this as (e.g.) `~/.config/taskchampion-mcp/freelance_schema.toml` and
reference it in your config:

```toml
[server]
role = "CONTRIBUTOR"
schema_path = "/home/you/.config/taskchampion-mcp/freelance_schema.toml"
```

Or call `set_active_schema(schema_path="/home/you/.config/taskchampion-mcp/freelance_schema.toml")`
from the LLM to switch at runtime without restart.

---

## Bundled presets as reference

The five presets in `schemas/` cover common workflows and serve as
real-world examples:

| Preset | File | Use when |
|---|---|---|
| `minimal` | `schemas/minimal.toml` | No UDAs; built-in Taskwarrior fields only |
| `gtd` | `schemas/gtd.toml` | GTD contexts, energy levels, next-actions |
| `kanban` | `schemas/kanban.toml` | Board columns, WIP limits, classes of service |
| `scrum` | `schemas/scrum.toml` | Sprints, story points, acceptance criteria |
| `authors_custom_example` | `schemas/authors_custom_example.toml` | Heavy real-world taxonomy with lifecycle phases, hypothesis-driven research, LLM provenance |

Browse these files directly for patterns — conditional requirements,
enumerated values, nested UDA semantics.

---

## Generate-from-taxonomy workflow

If you maintain a taxonomy Markdown file describing your field semantics,
lifecycle phases, and conditional rules, the server can generate a schema
from it:

1. Set the taxonomy path in config or via the LLM:
   `set_taxonomy_path("/path/to/TAXONOMY.md")`
2. Call `analyze_taxonomy_file` — the server parses the Markdown and
   extracts field definitions, allowed values, and conditional rules.
3. Call `generate_initial_schema_preview` — produces a reviewable TOML
   schema without writing anything to disk.
4. Review and adjust. Call `save_initial_schema` to persist.

---

## Generate-from-tasks workflow

If you already have tasks in Taskwarrior with UDAs populated, the server
can infer a schema from your existing data:

1. Call `analyze_existing_tasks_for_schema` — reads `task export` and
   analyses field names, types, and value distributions.
2. Call `generate_initial_schema_preview` — produces a reviewable TOML
   schema based on the analysis.
3. Review the generated schema. Adjust field descriptions, add conditions,
   and tighten allowed values as needed.
4. Call `save_initial_schema` to persist.

Both workflows produce a standard TOML schema file. The
`generate_initial_schema_preview` tool returns the schema as text for
review; `save_initial_schema` writes it to disk and optionally updates
`config.toml` to reference it.

---

## LLM provenance fields

All schemas can optionally include an `[llm_provenance]` section for
tracking LLM-generated tasks:

```toml
[llm_provenance]
description = "Fields for tracking LLM-generated tasks."

[llm_provenance.gen_model]
type = "string"
required = false
description = "LLM model that generated this task."

[llm_provenance.gen_persona]
type = "string"
required = false
description = "Persona or system prompt used during generation."

[llm_provenance.gen_harness]
type = "string"
required = false
description = "Tool that produced this task (e.g., 'mcp', 'claude-code')."
```

These fields are recommended but never enforced. They provide an audit
trail for tasks created by an LLM.
