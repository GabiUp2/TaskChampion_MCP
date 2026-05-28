#!/usr/bin/env bash
# Pack and publish TaskChampion MCP to Smithery via MCPB bundle.
# Uses one-shot npx only — no global npm installs.
#
# Deployment issues log and next-release checklist:
#   docs/MARKETPLACE_SUBMISSIONS.md §3 (smithery.ai)
#
# Prerequisites:
#   - uv on PATH (Smithery/Claude host manages Python via UV runtime)
#   - Smithery API key from https://smithery.ai/account/api-keys
#
# Usage:
#   export SMITHERY_API_KEY='...'   # or paste when prompted
#   ./scripts/publish_smithery.sh
#
# After publishing, remove system npm if you installed it only for this step:
#   sudo apt remove -y npm

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BUNDLE_DIR="${ROOT}/smithery"
MCPB="${BUNDLE_DIR}/smithery.mcpb"
QUALIFIED_NAME="${SMITHERY_QUALIFIED_NAME:-gabiup2/taskchampion-mcp}"
NAMESPACE="${QUALIFIED_NAME%%/*}"

# Smithery upload needs Node 20+ (global File). Prefer Cursor's bundled Node.
ensure_node20() {
  local major cursor_node
  major="$(node -p 'process.versions.node.split(".")[0]')"
  if (( major >= 20 )); then
    return 0
  fi
  cursor_node="/usr/share/cursor/resources/app/resources/helpers/node"
  if [[ -x "${cursor_node}" ]]; then
    export PATH="$(dirname "${cursor_node}"):${PATH}"
    major="$(node -p 'process.versions.node.split(".")[0]')"
    if (( major >= 20 )); then
      echo "==> Using Node $(node -v) for Smithery CLI"
      return 0
    fi
  fi
  export NODE_OPTIONS="--require ${ROOT}/scripts/node20-file-polyfill.cjs${NODE_OPTIONS:+ ${NODE_OPTIONS}}"
  echo "==> Polyfilling global File for Node $(node -v)"
}
ensure_node20

npx_cmd() {
  npx --yes "$@"
}

cd "${BUNDLE_DIR}"

echo "==> Validating and packing MCPB bundle..."
npx_cmd @anthropic-ai/mcpb@latest pack

if [[ ! -f "${MCPB}" ]]; then
  echo "error: expected ${MCPB} after pack" >&2
  exit 1
fi

if [[ -z "${SMITHERY_API_KEY:-}" ]]; then
  read -rsp "Smithery API key (https://smithery.ai/account/api-keys): " SMITHERY_API_KEY
  echo
fi
export SMITHERY_API_KEY

echo "==> Checking Smithery auth..."
if ! npx_cmd @smithery/cli@latest auth whoami >/dev/null 2>&1; then
  echo "error: SMITHERY_API_KEY not accepted — create a fresh key at https://smithery.ai/account/api-keys" >&2
  exit 1
fi

echo "==> Ensuring Smithery namespace '${NAMESPACE}'..."
if ! npx_cmd @smithery/cli@latest namespace list 2>&1 | rg -q "${NAMESPACE}"; then
  echo "    Namespace not found — creating '${NAMESPACE}'..."
  npx_cmd @smithery/cli@latest namespace create "${NAMESPACE}"
fi
npx_cmd @smithery/cli@latest namespace use "${NAMESPACE}"

# Smithery CLI calls servers.create() with an empty body → 400 "No values to set".
# Register metadata via REST first:
#   PUT  — create: https://smithery.ai/docs/api-reference/servers/create-a-server
#   PATCH — update: https://smithery.ai/docs/api-reference/servers/update-a-server
# Upload release via PUT /releases (bypasses Smithery CLI empty-body create).
# Deploy payload MUST include configSchema (even empty) or deploy fails with
# "No values to set". See docs/MARKETPLACE_SUBMISSIONS.md §3.
#   https://smithery.ai/docs/api-reference/servers/publish-a-server
smithery_urlencode() {
  python3 -c "import urllib.parse, sys; print(urllib.parse.quote(sys.argv[1], safe=''))" "$1"
}

smithery_server_create_json() {
  python3 <<'PY'
import json
print(json.dumps({
    "displayName": "TaskChampion MCP",
    "description": (
        "MCP server for Taskwarrior 3.x, TaskChampion, and Timewarrior. "
        "Schema validation, role-based permissions, 35 tools. uvx taskchampion-mcp."
    ),
}))
PY
}

smithery_server_patch_json() {
  python3 <<'PY'
import json
print(json.dumps({
    "displayName": "TaskChampion MCP",
    "description": (
        "MCP server for Taskwarrior 3.x, TaskChampion, and Timewarrior. "
        "Schema validation, role-based permissions, 35 tools. uvx taskchampion-mcp."
    ),
    "repositoryUrl": "https://github.com/GabiUp2/TaskChampion_MCP",
    "homepage": "https://github.com/GabiUp2/TaskChampion_MCP",
    "license": "Apache-2.0",
    "unlisted": False,
}))
PY
}

smithery_deploy_payload_json() {
  python3 <<'PY'
import json
from pathlib import Path

manifest = json.loads(Path("manifest.json").read_text(encoding="utf-8"))
if not manifest.get("name") or not manifest.get("version"):
    raise SystemExit("manifest.json must include name and version")

server = manifest.get("server") or {}
runtime = "python"
if server.get("type") == "node":
    runtime = "node"
elif server.get("type") == "python":
    runtime = "python"
elif server.get("type") == "binary":
    runtime = "binary"
command = (server.get("mcp_config") or {}).get("command") or ""
if command.rsplit("/", 1)[-1] == "bun":
    runtime = "bun"

payload = {
    "type": "stdio",
    "runtime": runtime,
    "configSchema": {"type": "object", "properties": {}},
    "serverCard": {
        "serverInfo": {
            "name": manifest["name"],
            "version": manifest["version"],
        },
    },
}
if manifest.get("tools"):
    payload["serverCard"]["tools"] = manifest["tools"]
if manifest.get("prompts"):
    payload["serverCard"]["prompts"] = manifest["prompts"]
if manifest.get("resources"):
    payload["serverCard"]["resources"] = manifest["resources"]

print(json.dumps(payload))
PY
}

ensure_smithery_server() {
  local encoded create_body patch_body http_code
  encoded="$(smithery_urlencode "${QUALIFIED_NAME}")"
  create_body="$(smithery_server_create_json)"
  patch_body="$(smithery_server_patch_json)"

  http_code="$(curl -sS -o /tmp/smithery-server-get.json -w '%{http_code}' \
    -H "Authorization: Bearer ${SMITHERY_API_KEY}" \
    "https://api.smithery.ai/servers/${encoded}")"

  if [[ "${http_code}" == "404" ]]; then
    echo "==> Creating server (PUT /servers/${QUALIFIED_NAME})..."
    http_code="$(curl -sS -o /tmp/smithery-server-create.json -w '%{http_code}' \
      -X PUT "https://api.smithery.ai/servers/${encoded}" \
      -H "Authorization: Bearer ${SMITHERY_API_KEY}" \
      -H "Content-Type: application/json" \
      -d "${create_body}")"
    if [[ "${http_code}" != "201" && "${http_code}" != "200" ]]; then
      echo "error: server create failed (HTTP ${http_code}):" >&2
      cat /tmp/smithery-server-create.json >&2
      exit 1
    fi
  elif [[ "${http_code}" != "200" ]]; then
    echo "error: unexpected GET /servers response (HTTP ${http_code}):" >&2
    cat /tmp/smithery-server-get.json >&2
    exit 1
  fi

  echo "==> Updating server metadata (PATCH /servers/${QUALIFIED_NAME})..."
  http_code="$(curl -sS -o /tmp/smithery-server-update.json -w '%{http_code}' \
    -X PATCH "https://api.smithery.ai/servers/${encoded}" \
    -H "Authorization: Bearer ${SMITHERY_API_KEY}" \
    -H "Content-Type: application/json" \
    -d "${patch_body}")"
  if [[ "${http_code}" != "200" ]]; then
    echo "error: server update failed (HTTP ${http_code}):" >&2
    cat /tmp/smithery-server-update.json >&2
    exit 1
  fi
}

poll_smithery_release() {
  local encoded deployment_id http_code status
  encoded="$(smithery_urlencode "${QUALIFIED_NAME}")"
  deployment_id="$1"

  echo "==> Waiting for release ${deployment_id}..."
  for _ in $(seq 1 120); do
    http_code="$(curl -sS -o /tmp/smithery-release.json -w '%{http_code}' \
      -H "Authorization: Bearer ${SMITHERY_API_KEY}" \
      "https://api.smithery.ai/servers/${encoded}/releases/${deployment_id}")"
    if [[ "${http_code}" != "200" ]]; then
      sleep 2
      continue
    fi
    status="$(python3 -c "import json; print(json.load(open('/tmp/smithery-release.json')).get('status',''))")"
    case "${status}" in
      SUCCESS)
        echo "    Release successful."
        python3 -c "import json; d=json.load(open('/tmp/smithery-release.json')); print('    MCP URL:', d.get('mcpUrl',''))"
        return 0
        ;;
      FAILURE|FAILURE_SCAN|INTERNAL_ERROR|CANCELLED)
        echo "error: release failed (${status}):" >&2
        python3 -c "import json; d=json.load(open('/tmp/smithery-release.json')); print('\n'.join(l.get('message','') for l in d.get('logs',[]) if l.get('level')=='error'))" >&2
        exit 1
        ;;
    esac
    sleep 2
  done
  echo "warning: release still in progress — check https://smithery.ai/servers/${QUALIFIED_NAME}/releases"
}

deploy_smithery_release() {
  local encoded payload http_code deployment_id
  encoded="$(smithery_urlencode "${QUALIFIED_NAME}")"
  payload="$(smithery_deploy_payload_json)"

  echo "==> Uploading MCPB release (PUT /servers/${QUALIFIED_NAME}/releases)..."
  echo "    Payload: ${payload}"
  # payload must be a multipart form STRING (JSON text), not a file part — matches SDK FormData.
  http_code="$(curl -sS -o /tmp/smithery-deploy.json -w '%{http_code}' \
    -X PUT "https://api.smithery.ai/servers/${encoded}/releases" \
    -H "Authorization: Bearer ${SMITHERY_API_KEY}" \
    --form-string "payload=${payload}" \
    -F "bundle=@${MCPB};filename=smithery.mcpb;type=application/octet-stream")"

  if [[ "${http_code}" != "202" && "${http_code}" != "200" ]]; then
    echo "error: release upload failed (HTTP ${http_code}):" >&2
    cat /tmp/smithery-deploy.json >&2
    echo >&2
    echo "hint: payload must be sent as a multipart form string (--form-string), not as a file upload." >&2
    echo "      See https://smithery.ai/docs/api-reference/servers/publish-a-server" >&2
    exit 1
  fi

  deployment_id="$(python3 -c "import json; print(json.load(open('/tmp/smithery-deploy.json')).get('deploymentId',''))")"
  echo "    Release accepted: ${deployment_id:-unknown}"
  echo "    Track: https://smithery.ai/servers/${QUALIFIED_NAME}/releases"
  if [[ -n "${deployment_id}" ]]; then
    poll_smithery_release "${deployment_id}"
  fi
}

ensure_smithery_server
deploy_smithery_release

echo "==> Done. Verify with: npx --yes @smithery/cli@latest mcp search taskchampion"
