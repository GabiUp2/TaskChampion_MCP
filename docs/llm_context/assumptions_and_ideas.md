# Assumptions and Ideas

**Purpose:** This file records all assumptions made during development — especially those not verified against a primary source. It also captures ideas and early-stage thinking that may inform future decisions.

**Rules:**
1. Every assumption must include a **date**, **author** (human or `LLM model/harness`), and **verification status** (`verified`, `unverified`, `disproven`).
2. If an assumption is later verified or disproven, update the status and add the source.
3. LLM contributors: if you make any claim that is not directly backed by documentation you have read in this session, log it here **before** acting on it.
4. Ideas are not commitments. They are captured for later evaluation.

---

## Assumptions

### ASM-001: TaskChampion is the primary sync server for Taskwarrior 3.x
- **Date:** 2026-05-25
- **Author:** Claude claude-sonnet-4-20250514 / Windsurf Cascade
- **Status:** Verified
- **Source:** Taskwarrior documentation confirms TaskChampion replaced Taskserver for TW3. See `deep-research-report.md` citations [26†L35-L43].
- **Impact:** We target TaskChampion exclusively for v0.1.0. Taskserver (taskd) support is deferred.

### ASM-002: Taskwarrior's `task export` outputs valid JSON array for all pending tasks
- **Date:** 2026-05-25
- **Author:** Claude claude-sonnet-4-20250514 / Windsurf Cascade
- **Status:** Verified
- **Source:** Taskwarrior documentation; confirmed in author's live installation. `task export` produces a JSON array of task objects.
- **Impact:** We use `task export` as the primary read mechanism for the MCP server, avoiding direct file access.

### ASM-003: The `mcp` Python SDK supports stdio transport out of the box
- **Date:** 2026-05-25
- **Author:** Claude claude-sonnet-4-20250514 / Windsurf Cascade
- **Status:** Unverified — assumed based on MCP specification and SDK documentation in training data
- **Source:** MCP specification (modelcontextprotocol.io); Python SDK docs. To be verified during implementation.
- **Impact:** If the SDK does not support stdio natively, we would need to implement the transport layer ourselves.

### ASM-004: `subprocess.run()` with list arguments prevents shell injection
- **Date:** 2026-05-25
- **Author:** Claude claude-sonnet-4-20250514 / Windsurf Cascade
- **Status:** Verified
- **Source:** Python documentation for `subprocess` module. When `shell=False` (default) and arguments are passed as a list, no shell interpretation occurs.
- **Impact:** Core security design relies on this behavior. Additional input sanitization is defense-in-depth.

### ASM-005: Taskwarrior 3.x is widely adopted among active Taskwarrior users by mid-2026
- **Date:** 2026-05-25
- **Author:** Claude claude-sonnet-4-20250514 / Windsurf Cascade
- **Status:** Unverified — no adoption statistics available
- **Source:** None. Assumed based on 3.x being the current mainline and active development since 2024.
- **Impact:** Targeting 3.x first may exclude users on older distros shipping TW 2.x. Mitigated by version detection and clear messaging.

### ASM-006: Demographics skew toward experienced Linux/Unix users
- **Date:** 2026-05-25
- **Author:** Human + Claude claude-sonnet-4-20250514 / Windsurf Cascade
- **Status:** Unverified — no formal demographic data exists for Taskwarrior users
- **Source:** Inferred from the tool's CLI-only nature, configuration complexity, and community forums. The "bearded Unix jockey" angle is a deliberate marketing nod, not a data-driven claim.
- **Impact:** Documentation and UX should assume CLI literacy. Marketing can lean into the power-user identity without alienating newcomers.

### ASM-007: ChatGPT and Codex can be supported via HTTP/SSE transport
- **Date:** 2026-05-25
- **Author:** Claude claude-sonnet-4-20250514 / Windsurf Cascade
- **Status:** Unverified — ChatGPT plugin architecture may require OpenAPI spec rather than MCP
- **Source:** Based on training data about OpenAI's platform. Codex reportedly supports MCP. ChatGPT may need a different integration pattern.
- **Impact:** HTTP/SSE transport is deferred to v0.2.0+. Needs research before implementation.

### ASM-008: `timew --version` is the correct way to detect Timewarrior version
- **Date:** 2026-05-25
- **Author:** Claude claude-sonnet-4-20250514 / Windsurf Cascade
- **Status:** Unverified — needs testing on actual installation
- **Source:** Assumed based on common CLI conventions. May be `timew version` or parsed from `timew diagnostics`.
- **Impact:** Minor — affects version detection logic only. Easy to fix during implementation.

---

## Ideas

### IDEA-001: Natural language → Taskwarrior filter translation
- **Date:** 2026-05-25
- **Author:** Claude claude-sonnet-4-20250514 / Windsurf Cascade
- **Description:** The LLM could translate natural language queries ("what am I blocked on?") into Taskwarrior filter expressions (`phase:blocked`). This leverages the LLM's strength without adding complexity to the MCP server.
- **Status:** Captured for v0.3.0+ consideration

### IDEA-002: Task diff reporting after sync
- **Date:** 2026-05-25
- **Author:** Claude claude-sonnet-4-20250514 / Windsurf Cascade
- **Description:** After `task sync`, compare before/after exports to report what changed from other replicas. Useful for multi-machine setups.
- **Status:** Captured for v0.2.0+ consideration

### IDEA-003: Schema auto-generation from existing tasks + taxonomy file
- **Date:** 2026-05-25 (extended 2026-05-25)
- **Author:** Human (gabiup2) — stated in initial requirements; extended by human request
- **Description:** On first run, if no schema is configured, the MCP can analyze existing tasks (`task export`) to infer which UDAs are in use, their value distributions, and generate a draft schema TOML. Extended to also accept a taxonomy markdown file (like `user/TAXONOMY.md`) that describes field semantics, lifecycle processes, conditional requirements, and phase transitions. The taxonomy enriches the generated schema with descriptions and rules beyond what raw task data can infer. User reviews and approves.
- **Status:** Implemented — `src/taskchampion_mcp/schema_gen.py` with 41 tests. Config support via `taxonomy_path` in `config.toml`.

### IDEA-004: Project-scoped MCP configs
- **Date:** 2026-05-25
- **Author:** Claude claude-sonnet-4-20250514 / Windsurf Cascade
- **Description:** A `.taskchampion-mcp.toml` in the project root could scope which tasks the LLM sees (e.g., only `project:personal.tooling.taskwarrior`). This prevents the LLM from seeing unrelated tasks.
- **Status:** Captured for v0.2.0 consideration

### ASM-009: MCP Python SDK FastMCP supports stdio transport by default
- **Date:** 2026-05-25
- **Author:** Claude claude-sonnet-4-20250514 / Windsurf Cascade
- **Status:** Verified
- **Source:** Confirmed via PyPI mcp 1.8.0+ documentation. `mcp.run()` defaults to stdio; `mcp.run(transport="stdio")` is explicit.
- **Impact:** If wrong, the server entry point would fail to start.

### ASM-010: Taskwarrior rc.confirmation:off suppresses interactive prompts
- **Date:** 2026-05-25
- **Author:** Claude claude-sonnet-4-20250514 / Windsurf Cascade
- **Status:** Unverified — based on Taskwarrior documentation patterns
- **Source:** Taskwarrior docs indicate `rc.confirmation:off` disables confirmation prompts. Also set `rc.bulk:0` and `rc.verbose:nothing` for non-interactive subprocess usage.
- **Impact:** If wrong, subprocess calls could hang waiting for user input, causing timeouts.

### ASM-011: Taskwarrior _version command returns version string
- **Date:** 2026-05-25
- **Author:** Claude claude-sonnet-4-20250514 / Windsurf Cascade
- **Status:** Unverified — based on Tools_Usage_Reference.md
- **Source:** `task _version` is documented as returning just the version number. Used for version detection.
- **Impact:** Version detection would fail gracefully (returns None), server still starts with a warning.

### ASM-012: URL-encoded shell metacharacters should be blocked
- **Date:** 2026-05-25
- **Author:** Claude claude-sonnet-4-20250514 / Windsurf Cascade
- **Status:** Unverified — defense-in-depth decision
- **Source:** Since subprocess argument lists prevent shell injection, URL-encoded metacharacters like `%26` are not directly dangerous. However, blocking them prevents potential double-decode attacks if any downstream component URL-decodes values.
- **Impact:** False positive rejections of legitimate values containing `%26` etc. Unlikely in task descriptions.

### ASM-014: Taxonomy markdown files follow a parseable heading structure
- **Date:** 2026-05-25
- **Author:** Claude claude-sonnet-4-20250514 / Windsurf Cascade
- **Status:** Unverified — based on the project author's `user/TAXONOMY.md` format
- **Source:** The parser expects `### N.N field_name — values` headings, markdown tables for enum values, and "Required when" phrases for conditions. Other taxonomy formats may not parse correctly.
- **Impact:** Users with differently structured taxonomy files would get incomplete schema enrichment. Mitigated: analysis-only mode still works; taxonomy is optional.

### ASM-013: MCP tool return values should be JSON strings
- **Date:** 2026-05-25
- **Author:** Claude claude-sonnet-4-20250514 / Windsurf Cascade
- **Status:** Unverified — based on MCP SDK examples
- **Source:** MCP SDK tool functions return strings. We serialize tool results as JSON strings for structured data.
- **Impact:** If the SDK expects different return types, tools would fail. Low risk given SDK documentation examples.

### IDEA-005: Differentiate schema names by generation source
- **Date:** 2026-05-25
- **Author:** gabiup2
- **Description:** The schema name should reflect whether it was generated from a provided taxonomy file vs. from analyzing existing tasks alone. Current implementation uses a single "auto_generated" name. Should differentiate:
  - `auto_generated_from_taxonomy` — when taxonomy file is provided
  - `auto_generated_from_tasks` — when only tasks are analyzed
  This helps users understand the source and quality of the generated schema.
- **Status:** Captured for v0.1.0 implementation

### IDEA-006: Web platform connector gateway for lower-cost LLM access
- **Date:** 2026-06-08
- **Author:** Human (gabiup2) + GPT-5.5 Thinking / ChatGPT web
- **Description:** Add support for web LLM platforms on the path to TaskChampionMCP 2.0 so users are not limited to desktop IDEs or local clients. The target direction is an Athena/self-hosted remote gateway that can expose TaskChampionMCP safely to web platforms. Where remote MCP is supported, the gateway should provide an MCP-compatible endpoint. Where MCP is not available or is restricted by plan/platform, it should offer an OpenAPI/REST fallback suitable for Custom GPT Actions-style integrations.
- **Security notes:** Do not expose raw Taskwarrior, raw TaskChampion data, or unrestricted MCP directly to the internet. The gateway should require HTTPS, bearer-token/OAuth-style authentication, read-only default mode, explicit confirmation for destructive writes, audit logging, and preferably VPN/IP restrictions or a tunnel provider.
- **Candidate shape:** `taskchampion-remote-gateway` with endpoints such as `/mcp`, `/openapi`, and a narrow REST surface (`GET /tasks`, `GET /tasks/{uuid}`, `POST /tasks`, `PATCH /tasks/{uuid}`, `POST /tasks/{uuid}/done`).
- **Status:** Captured for v2.0 consideration
