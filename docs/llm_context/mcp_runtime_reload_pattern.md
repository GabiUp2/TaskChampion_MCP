# MCP Runtime Reload Pattern — IDE Agent Handoff

> **Status:** Superseded by [ADR 19](../adrs/ADRs.md#adr-19-runtime-reload--stable-tool-surface--runtime-state-checks--reload_configuration-tool)
> as of v0.3.2. This document is preserved verbatim because it captures the original
> hands-on framing that the ADR formalises; future contributors should read ADR 19
> first and use this doc only for the worked examples / pseudo-code at the bottom.

## Context

TaskChampion MCP currently has a first-run/onboarding flow where the server exposes onboarding tools until a schema is selected or generated. After selecting a preset such as `authors_custom_example`, the config is written correctly, but the running MCP process may still expose only the onboarding tool surface until the MCP host is restarted.

This is annoying in Windsurf/Cascade and similar IDE clients because the user has to close/reopen or refresh the IDE after running setup commands such as:

```bash
./dev.sh install windsurf
```

The goal is to remove this restart requirement where possible.

## Relevant MCP protocol behaviour

The MCP tools specification supports dynamic tool-list signalling:

- servers declare `capabilities.tools.listChanged = true` when they may emit tool-list change notifications;
- clients discover tools via `tools/list`;
- servers can notify clients using `notifications/tools/list_changed` when the available tool list changes.

Reference: <https://modelcontextprotocol.io/specification/2025-06-18/server/tools>

However, client support for dynamic refresh can vary. Therefore the safest implementation pattern is **not** to rely only on dynamic tool-list refresh.

## Preferred implementation pattern

Use a **stable tool surface with runtime gating**.

Instead of registering only onboarding tools before initialisation and normal tools after initialisation, register the full intended tool surface at server startup:

- onboarding/status/schema-selection tools;
- read/query tools;
- annotation/modification tools;
- creation tools;
- lifecycle/sync tools.

Then each normal task-management tool checks runtime state before doing work:

1. Is the MCP initialised?
2. Does the configured role allow this operation?
3. Is the schema loaded?
4. Are rate-limit, audit, confirmation, and validation rules satisfied?

If the server is not initialised, the tool should return a structured, non-mutating response such as:

```json
{
  "error": true,
  "requires_initialisation": true,
  "safe_to_mutate_tasks": false,
  "message": "TaskChampion MCP is not initialised. Select a preset or save a reviewed schema first.",
  "next_tools": [
    "get_initialization_status",
    "propose_initialization_options",
    "list_preset_schemas",
    "use_preset_schema",
    "save_initial_schema",
    "reload_configuration"
  ]
}
```

This means the IDE does not need to rediscover new tool names after onboarding. The tools are already visible; they simply become operational once runtime state changes.

## Add explicit reload tool

Add a tool named:

```text
reload_configuration
```

Expected behaviour:

1. Read the current config from `~/.config/taskchampion-mcp/config.toml` or the configured path.
2. Reload role, schema name/path, taxonomy path, security settings, and logging settings.
3. Reload the active schema object.
4. Recreate or update rate limiter and audit logger state if configuration changed.
5. Recreate Taskwarrior/Timewarrior CLI wrappers if relevant binary/taskrc settings changed.
6. Return a structured response:

```json
{
  "success": true,
  "reloaded": true,
  "restart_required": false,
  "role": "CONTRIBUTOR",
  "schema_name": "authors_custom_example",
  "schema_version": "1.0.0",
  "initialised": true,
  "message": "Configuration and schema reloaded in the running MCP server."
}
```

## Update onboarding write operations

After successful onboarding writes, reload runtime state immediately.

Affected onboarding tools:

- `use_preset_schema`
- `save_initial_schema`

Current user-facing messages say that the user must restart the MCP server. Replace that with runtime reload behaviour.

Expected successful `use_preset_schema` response should include:

```json
{
  "success": true,
  "preset_name": "authors_custom_example",
  "config_updated": true,
  "runtime_reload": {
    "success": true,
    "reloaded": true,
    "restart_required": false
  },
  "restart_required": false,
  "message": "Preset selected and loaded into the running MCP server."
}
```

## Optional protocol enhancement

If the MCP SDK/server wrapper exposes a safe way to declare and emit dynamic tool-list notifications, also add:

```json
{
  "capabilities": {
    "tools": {
      "listChanged": true
    }
  }
}
```

and emit:

```json
{
  "jsonrpc": "2.0",
  "method": "notifications/tools/list_changed"
}
```

when the effective tool list really changes.

Do **not** make this the only mechanism. Keep the stable tool surface pattern as the primary solution because it is more client-tolerant.

## Likely files to inspect/change

Start with:

- `src/taskchampion_mcp/server.py`
- `src/taskchampion_mcp/onboarding.py`
- `src/taskchampion_mcp/config.py`
- `src/taskchampion_mcp/tools.py`
- `tests/test_onboarding.py`

Potentially add a dedicated test file if cleaner:

- `tests/test_runtime_reload.py`

## Suggested server-side design

Introduce small helper functions in `server.py` or a new runtime-state module:

```text
_load_schema_for_config(config)
_is_initialised(config)
_reload_registry(reg, config_path=None)
_not_initialised_error(reg)
_role_denied_error(config, required_role)
_call_runtime_tool(reg, required_role, fn, *args, **kwargs)
```

Then register all tools at startup and wrap normal task-management calls through `_call_runtime_tool`.

Pseudo-flow:

```text
create_server()
  load config
  load fallback/current schema
  build ToolRegistry
  register onboarding tools
  register contributor tools
  register generator tools
  register manager tools
```

Normal task tool wrapper:

```text
if not initialised:
    return structured requires_initialisation response
if role is insufficient:
    return structured role-denied response
return actual registry method result
```

## Important semantic detail

Named bundled presets should count as initialised.

Currently, logic that only treats `schema_path` or taxonomy files as initialised may incorrectly report named presets such as `authors_custom_example` as not initialised. A config with explicit `[server].schema = "authors_custom_example"` should be treated as initialised.

Recommended initialisation predicate:

```text
initialised = explicit_schema_configured or explicit_taxonomy_configured
```

For status payloads, `safe_to_mutate_tasks` should become `true` only after initialisation and only for operations allowed by role.

## Test cases

Add tests for the following:

1. Before initialisation, normal task tools are registered/visible but return `requires_initialisation` instead of mutating or reading tasks.
2. `use_preset_schema("authors_custom_example")` updates config and triggers runtime reload.
3. After preset selection, `get_initialization_status` reports:
   - `initialised: true`
   - `needs_onboarding: false`
   - `safe_to_mutate_tasks: true`
   - active schema name/version from the selected preset.
4. `reload_configuration` reloads a manually changed config without process restart.
5. Role gating still works:
   - CONTRIBUTOR can read/annotate/modify;
   - GENERATOR can create;
   - MANAGER can perform lifecycle/sync operations.
6. Timewarrior tools should remain visible but return a clear unavailable response if Timewarrior is not installed.
7. Existing onboarding tests still pass.

## Acceptance criteria

The change is done when this flow works without restarting Windsurf/Cascade:

```text
1. Start MCP server with no config.toml.
2. Ask model to call get_initialization_status.
3. Ask model to call list_preset_schemas.
4. Ask model to call use_preset_schema("authors_custom_example").
5. Immediately call get_initialization_status again.
6. Immediately call get_schema_info.
```

Expected outcome:

```json
{
  "initialised": true,
  "needs_onboarding": false,
  "safe_to_mutate_tasks": true,
  "restart_required": false,
  "active_schema_name": "authors_custom_example"
}
```

No IDE close/reopen should be required.

## Non-goals

Do not implement IDE-specific process restarts as the primary solution.

Avoid relying on commands such as:

```bash
pkill -f windsurf
windsurf .
```

Those are acceptable emergency workarounds, not product behaviour.

## Notes for the IDE agent

Prefer a minimal, safe refactor over a broad rewrite. The project already has working onboarding helpers; reuse them. The key architectural shift is:

```text
startup-time tool selection  --->  stable tools + runtime state checks
```

That is the whole point. Do not over-engineer it into a framework unless tests force your hand.
