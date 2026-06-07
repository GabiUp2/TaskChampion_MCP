# Release checklist — PyPI and MCP Registry

Use this checklist **before tagging** and again **after any publish workflow failure**.
Lessons captured from the `v1.0.0-rc1` release (May 2026).

Related: [`.github/workflows/publish.yml`](../../.github/workflows/publish.yml), [`server.json`](../../server.json), [MCP Registries reference](../references/MCP_Registries.md).

---

## 1. Version alignment

| Location | Format | Example |
|----------|--------|---------|
| `pyproject.toml` → `version` | PEP 440 | `1.0.0rc1` |
| `src/taskchampion_mcp/__init__.py` → `__version__` | Same as PyPI | `1.0.0rc1` |
| `server.json` → top-level `version` | Same as PyPI | `1.0.0rc1` |
| `server.json` → `packages[].version` | Same as PyPI | `1.0.0rc1` |
| Git tag | SemVer with `v` prefix | `v1.0.0-rc1` |

Git tags and PyPI versions **may differ in punctuation** (`v1.0.0-rc1` vs `1.0.0rc1`) — that is normal. The **package metadata must match what you intend to publish**, not just the tag name.

Schema TOML files under `src/taskchampion_mcp/schemas/` have their **own** version fields — do not change those unless the schema itself changed.

---

## 2. Branch promotion (before tagging)

Publish workflow runs on **tag push to `main`**. Promote in order:

1. `dev` → `qa` (PR)
2. `qa` → `main` (PR)
3. Tag on `main`, then `git push origin <tag>`

Branch policy requires `qa ← dev` and `main ← qa`. See [branch-policy workflow](../../.github/workflows/branch-policy.yml).

---

## 3. GitHub `pypi` environment

**Settings → Environments → `pypi`** (name must match `publish.yml`).

| Setting | Required value |
|---------|----------------|
| Deployment branches | `main` |
| Deployment tags | `v*` |
| Secrets | None (Trusted Publishing uses OIDC) |
| `id-token: write` | Set in workflow (already present) |

Verify:

```bash
gh api repos/GabiUp2/TaskChampion_MCP/environments/pypi --jq .name
```

---

## 4. PyPI Trusted Publishing

Configure **before the first publish** at:
https://pypi.org/manage/project/taskchampion-mcp/settings/publishing/

| Field | Value |
|-------|-------|
| PyPI project | `taskchampion-mcp` |
| Owner | `GabiUp2` |
| Repository | `TaskChampion_MCP` |
| Workflow filename | `publish.yml` |
| Environment | `pypi` |

Check project exists:

```bash
curl -sS -o /dev/null -w "%{http_code}\n" https://pypi.org/pypi/taskchampion-mcp/json
```

(`404` until first successful publish.)

---

## 5. `server.json` (MCP Registry)

Validate against the current schema before tagging. Common failures from `v1.0.0-rc1`:

| Error | Cause | Fix |
|-------|-------|-----|
| `expected length <= 100` on `description` | Description too long | Keep ≤ 100 characters |
| `expected length >= 1` on `packages[0].registryType` | Snake_case field names | Use camelCase (see below) |
| `invalid audience … got [mcp-registry]` | Old `mcp-publisher` binary | Use latest CLI + `--registry` URL (workflow handles this) |

**Field naming:** the registry expects **camelCase** (not snake_case):

| Old (invalid) | Current |
|---------------|---------|
| `registry_type` | `registryType` |
| `registry_base_url` | `registryBaseUrl` |
| `runtime_arguments` | removed — use `transport` |
| `environment_variables` | `environmentVariables` |
| `supported_platforms` | not used in current PyPI examples |

**PyPI package block (minimum):**

```json
{
  "registryType": "pypi",
  "registryBaseUrl": "https://pypi.org",
  "identifier": "taskchampion-mcp",
  "version": "1.0.0rc1",
  "runtimeHint": "uvx",
  "transport": { "type": "stdio" },
  "environmentVariables": []
}
```

Use a current `$schema` URL from [MCP registry docs](https://modelcontextprotocol.io/registry/package-types).

Local dry-run (install latest `mcp-publisher`):

```bash
mcp-publisher login github
mcp-publisher publish --dry-run   # if supported; otherwise validate via CI
```

---

## 6. Publish workflow behaviour

Trigger: push any tag matching `v*` (see `publish.yml`).

Job order:

1. `test` — lint, pytest, wheel smoke test
2. `pypi` — build + upload (Trusted Publishing)
3. `mcp-registry` — OIDC login + `mcp-publisher publish`

Notes:

- **`skip-existing: true`** on PyPI upload allows re-pushing a tag when the version is already on PyPI (registry-only retry).
- **`mcp-registry` depends on `test`**, not `pypi`, so a registry retry is not blocked when PyPI already has the artefact.
- Install **`mcp-publisher` from `releases/latest`**, not a pinned old version. Registry v1.7.6+ requires OIDC audience `https://registry.modelcontextprotocol.io`.
- Auth command: `mcp-publisher login github-oidc --registry=https://registry.modelcontextprotocol.io`

---

## 7. Retrying a failed publish — do not rerun the old job

`gh run rerun --failed` re-executes the workflow file **frozen at the original tag commit**. If the tag pointed at an older `publish.yml` (wrong `mcp-publisher`, wrong `server.json`), the rerun **will fail the same way**.

**Correct retry:**

1. Merge fixes to `main` (via `dev` → `qa` → `main`).
2. Move the tag to current `main`:

```bash
git fetch origin main
git tag -fa v1.0.0-rc1 origin/main -m "v1.0.0 release candidate 1"
git push -f origin v1.0.0-rc1
```

3. Watch **Actions → Publish** for the new run triggered by the tag push.

---

## 8. Pre-tag command checklist

Run locally on the commit you intend to tag:

```bash
# Version consistency
grep '^version' pyproject.toml
grep '__version__' src/taskchampion_mcp/__init__.py
python3 -c "import json; s=json.load(open('server.json')); print(s['version'], s['packages'][0]['version'])"

# server.json description length
python3 -c "import json; d=json.load(open('server.json'))['description']; assert len(d)<=100, len(d); print('description ok:', len(d))"

# Build artefact
uv build && ls dist/

# Tests (publish gate subset)
uv run pytest tests/ --ignore=tests/targets -q
```

---

## 9. Post-tag verification

| Check | Command / URL |
|-------|----------------|
| Publish workflow green | `gh run list --workflow=publish.yml --limit 1` |
| PyPI package | https://pypi.org/project/taskchampion-mcp/ |
| MCP Registry listing | https://registry.modelcontextprotocol.io/v0/servers?search=io.github.GabiUp2/taskchampion-mcp |
| Install smoke test | `uvx taskchampion-mcp --help` |

---

## 10. Error quick reference

| Symptom | Likely cause |
|---------|----------------|
| `invalid audience: expected https://registry.modelcontextprotocol.io, got [mcp-registry]` | Old `mcp-publisher` or rerun of old workflow at tag |
| `Activity must belong to an allowed branch or tag` | `pypi` environment missing `v*` tag rule |
| PyPI 403 / trusted publishing error | Trusted publisher not configured or wrong environment name |
| PyPI “file already exists” on retag | Expected without `skip-existing: true` |
| MCP Registry 422 on `description` | Description > 100 chars |
| MCP Registry 422 on `registryType` | Snake_case `server.json` fields |
| Workflow still runs old steps after merge | Tag not moved to `main`; used `gh run rerun` instead |
| README PyPI badge red (“package or version not found”) | Tag pushed before PyPI publish finished, or shields.io cache; verify https://pypi.org/pypi/taskchampion-mcp/json shows the version |
| GitHub release badge red | Tag exists but no GitHub Release object — run `gh release create vX.Y.Z` |
| PyPI project page missing links | Add `[project.urls]` in `pyproject.toml` (published on next release) |

---

## 11. README badges and GitHub Releases

After tagging:

1. Confirm PyPI lists the version: `curl -sS https://pypi.org/pypi/taskchampion-mcp/json | jq -r .info.version`
2. Create a **GitHub Release** (not just a tag) so the release badge works:
   ```bash
   gh release create v1.0.0 --title "v1.0.0" --notes-file docs/releases/v1.0.0.md
   ```
3. Ensure `pyproject.toml` includes `[project.urls]` (Homepage, Repository, Changelog) so PyPI shows correct links on the next publish.
4. If shields.io badges stay red briefly, hard-refresh the README or wait a few minutes for cache expiry.

---

*Added after v1.0.0-rc1 publish debugging, May 2026.*


---

## 12. Feature release checklist (patch or minor with new functionality)

Run this section in addition to sections 1–11 whenever the release adds a new
tool, a new public API, a new config key, or changes observable server
behaviour — even if the semver bump is a patch.

### 12a. Behaviour and API surface

- [ ] Every new or changed MCP tool is listed in `server.json` → `tools[]`
      with an accurate description (≤ 100 chars per entry).
- [ ] Every new public symbol in `src/` (function, constant, class) has a
      docstring and is covered by at least one unit test.
- [ ] New config keys are documented in
      `docs/manuals/configuration_reference.md` with type, default, env var
      override, and example.
- [ ] New schema fields or constraints are documented in
      `docs/manuals/schema_authoring.md`.
- [ ] If the feature changes tool response envelopes or error codes, the
      `docs/references/Tools_Usage_Reference.md` is updated.

### 12b. Documentation

- [ ] `CHANGELOG.md` entry explains the user-visible change in plain language,
      not just "fixed a bug". Link the PR number.
- [ ] `docs/releases/vX.Y.Z.md` release notes written (see `v1.0.0.md` and
      `v1.0.2.md` for format).
- [ ] `pyproject.toml` `[project.urls]` `"Release Notes"` points to the new
      release notes file.
- [ ] `README.md` updated if the feature changes setup steps, usage examples,
      or the supported-platforms table.
- [ ] `docs/llm_context/AGENTS.md` updated if the feature changes what an LLM
      agent should know about server behaviour.

### 12c. Tests

- [ ] New behaviour covered by unit tests (happy path + at least one error
      path).
- [ ] If the feature touches a tool: `tests/test_tools.py` or
      `tests/test_tools_coverage.py` has at least one test for the new
      behaviour.
- [ ] Coverage gate still passes: `uv run pytest tests/ -m "not integration"
      --cov=src/taskchampion_mcp --cov-fail-under=85`.
- [ ] Acceptance suite still passes (all three headless targets):
      `uv run pytest tests/targets/ -m acceptance`.
- [ ] `tests/smoke_test_mcp.py` still passes (MCP protocol integrity).

### 12d. Assumptions and ADRs

- [ ] If the feature required a non-obvious design decision, an ADR was written
      or an existing ADR was amended (append-only per `.cursor/rules/`).
- [ ] If the feature was prototyped or involved AI-assisted reasoning, relevant
      assumptions are logged in `docs/llm_context/assumptions_and_ideas.md`
      with status `unverified` or `accepted`.

### 12e. Pre-tag command additions for feature releases

```bash
# server.json tool list completeness
python3 -c "
import json
s = json.load(open('server.json'))
print('Tools in server.json:', len(s['tools']))
"

# Release notes file exists
test -f docs/releases/vX.Y.Z.md && echo 'Release notes: OK' || echo 'MISSING'

# Coverage
uv run pytest tests/ -m 'not integration' --cov=src/taskchampion_mcp \
  --cov-report=term-missing --cov-fail-under=85 -q

# Acceptance
uv run pytest tests/targets/ -m acceptance -q
```

---

## 13. Major version release checklist (X.0.0)

Run this section in addition to all of sections 1–12 whenever the major version
number changes. A major release signals breaking changes to the public API,
tool surface, config schema, or behaviour contracts.

### 13a. Breaking change inventory

- [ ] Every breaking change is listed in `CHANGELOG.md` under a
      `### Breaking changes` heading with a migration path for each.
- [ ] A `### Migration notes` section explains the minimum steps to upgrade
      from the previous major version.
- [ ] ADRs recording the reasons for each breaking change exist or are updated.

### 13b. MCP tool surface audit

This is the endpoint check for major releases. Every tool must be deliberately
reviewed — not assumed to be unchanged.

**For each tool in `server.json` → `tools[]`:**

- [ ] Tool name is stable and intentional (renames are breaking).
- [ ] Tool description accurately describes current behaviour (≤ 100 chars).
- [ ] Tool input schema (parameter names, types, required/optional) is
      intentional. Any removed or renamed parameter is documented as breaking.
- [ ] Tool response envelope fields (`success`, `error`, `code`, `message`,
      plus tool-specific fields) are documented and stable.
- [ ] Error codes the tool can return are listed in
      `docs/references/Tools_Usage_Reference.md`.
- [ ] Role gating (CONTRIBUTOR / GENERATOR / MANAGER) is correct and
      intentional for each tool.

**Tool surface diff against the previous major version:**

```bash
# Compare tool names between tags
git show vPREV.0.0:server.json | python3 -c   "import sys,json; [print(t['name']) for t in json.load(sys.stdin)['tools']]"   > /tmp/tools_prev.txt

python3 -c   "import json; [print(t['name']) for t in json.load(open('server.json'))['tools']]"   > /tmp/tools_curr.txt

diff /tmp/tools_prev.txt /tmp/tools_curr.txt
```

- [ ] Diff reviewed and every addition, removal, and rename is intentional.
- [ ] Removed tools have a documented migration path to their replacement.

### 13c. Config and schema surface audit

- [ ] Every config key in `docs/manuals/configuration_reference.md` is
      reviewed for correctness.
- [ ] Any removed or renamed config key is documented as breaking with a
      migration path.
- [ ] `config.example.toml` reflects the current config surface.
- [ ] Bundled preset schemas (`src/taskchampion_mcp/schemas/*.toml`) have been
      reviewed; if changed, their own `version` fields are bumped.

### 13d. Error envelope audit

- [ ] The closed set of `code` values in the error envelope is reviewed and
      accurate (see ADR 14).
- [ ] Any new error code is added to ADR 14 and to
      `docs/references/Tools_Usage_Reference.md`.
- [ ] Any removed error code is documented as breaking.

### 13e. Acceptance suite scope review

- [ ] The 26-scenario acceptance matrix covers the new major version's feature
      set. Add new scenarios for any new tool or mode introduced.
- [ ] Per-target install guides
      (`docs/manuals/targets/{claude_desktop,windsurf,cursor,neovim}.md`) are
      updated for any changed install steps, config format, or binary names.

### 13f. MCP Registry re-submission

A major version requires re-submission to the MCP Registry (the registry does
not auto-update on patch/minor bumps).

- [ ] `server.json` fully updated: version, tool list, description.
- [ ] `mcp-publisher publish` dry-run passes locally.
- [ ] After tagging, confirm the publish workflow's `mcp-registry` job
      completes successfully.
- [ ] Registry listing visible:
      `https://registry.modelcontextprotocol.io/v0/servers?search=io.github.GabiUp2/taskchampion-mcp`

### 13g. GitHub Release

For major versions, the GitHub Release body should be more than a link to
release notes:

- [ ] Release title: `vX.0.0 — <one-line summary>`.
- [ ] Release body includes: summary paragraph, link to release notes, link to
      migration guide, list of breaking changes (short).
- [ ] Pre-release checkbox is NOT set (major stable releases are not
      pre-releases).

```bash
gh release create vX.0.0 \
  --title "vX.0.0 — <summary>" \
  --notes-file docs/releases/vX.0.0.md
```

### 13h. Pre-tag command additions for major releases

```bash
# Tool surface diff
git show vPREV.0.0:server.json | python3 -c \
  "import sys,json; [print(t['name']) for t in json.load(sys.stdin)['tools']]" \
  > /tmp/tools_prev.txt
python3 -c \
  "import json; [print(t['name']) for t in json.load(open('server.json'))['tools']]" \
  > /tmp/tools_curr.txt
diff /tmp/tools_prev.txt /tmp/tools_curr.txt

# Config surface diff
git diff vPREV.0.0..HEAD -- docs/manuals/configuration_reference.md

# Breaking change section present in CHANGELOG
grep '### Breaking changes' CHANGELOG.md

# Migration notes present
grep '### Migration notes' CHANGELOG.md

# All acceptance targets pass
uv run pytest tests/targets/ -m acceptance -v
```

---

*Sections 12–13 added 2026-06-07 after v1.0.2 patch release.*
