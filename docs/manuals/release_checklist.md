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

---

*Added after v1.0.0-rc1 publish debugging, May 2026.*
