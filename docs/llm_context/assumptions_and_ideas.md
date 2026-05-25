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

### IDEA-003: Schema auto-generation from existing tasks
- **Date:** 2026-05-25
- **Author:** Human (gabiup2) — stated in initial requirements
- **Description:** On first run, if no schema is configured, the MCP can analyze existing tasks (`task export`) to infer which UDAs are in use, their value distributions, and generate a draft schema TOML. User reviews and approves.
- **Status:** Required for v0.1.0 (first-run wizard)

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

### ASM-013: MCP tool return values should be JSON strings
- **Date:** 2026-05-25
- **Author:** Claude claude-sonnet-4-20250514 / Windsurf Cascade
- **Status:** Unverified — based on MCP SDK examples
- **Source:** MCP SDK tool functions return strings. We serialize tool results as JSON strings for structured data.
- **Impact:** If the SDK expects different return types, tools would fail. Low risk given SDK documentation examples.
