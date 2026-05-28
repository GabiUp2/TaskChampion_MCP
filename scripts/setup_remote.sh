#!/usr/bin/env bash
# -----------------------------------------------------------------------------
# TaskChampion MCP — Remote-host bootstrap
#
# One-shot installer for a Linux box that already has Taskwarrior, Timewarrior,
# and Claude Code (the `claude` CLI), but no prior taskchampion-mcp setup.
# Designed to run idempotently — re-running on a configured host is safe.
#
# Default behaviour matches the choices captured in the session widget:
#   INSTALL_SOURCE=git_dev      (uv tool install from this repo's dev branch)
#   SEED_ROLE=GENERATOR         (an autonomous remote agent creates tasks)
#   SEED_SCHEMA=authors_custom_example
#   AUTO_PREREQS=false          (check-and-report; never installs uv/task itself)
#
# Override any of these via flags or env vars:
#   ./setup_remote.sh --source git_main --role CONTRIBUTOR --schema gtd
#   INSTALL_SOURCE=pypi ./setup_remote.sh --dry-run
#
# After successful run:
#   - taskchampion-mcp-server is on PATH (uv tool install)
#   - Claude Code (`claude mcp list`) shows the `taskchampion` server, Connected
#   - ~/.config/taskchampion-mcp/config.toml seeded with role + schema
#   - The next `claude` invocation picks up the new MCP server automatically
# -----------------------------------------------------------------------------

set -euo pipefail

# === Defaults (overridable via flags/env) ===================================

INSTALL_SOURCE="${INSTALL_SOURCE:-git_dev}"     # git_dev | git_main | pypi
SEED_ROLE="${SEED_ROLE:-GENERATOR}"
SEED_SCHEMA="${SEED_SCHEMA:-authors_custom_example}"
GIT_URL="${GIT_URL:-https://github.com/GabiUp2/TaskChampion_MCP}"
DRY_RUN="${DRY_RUN:-false}"
AUTO_PREREQS="${AUTO_PREREQS:-false}"            # check-only by default

# === Colours (ANSI) ========================================================

CYAN="\033[0;36m"
GREEN="\033[0;32m"
YELLOW="\033[1;33m"
RED="\033[0;31m"
NC="\033[0m"

info() { printf "${CYAN}[INFO]${NC}  %s\n" "$*"; }
ok()   { printf "${GREEN}[OK]${NC}    %s\n" "$*"; }
warn() { printf "${YELLOW}[WARN]${NC}  %s\n" "$*"; }
fail() { printf "${RED}[FAIL]${NC}  %s\n" "$*" >&2; }

# === Argument parsing ======================================================

usage() {
    cat <<EOF
TaskChampion MCP — Remote-host bootstrap

Usage:
  $(basename "$0") [options]

Options:
  --source <SRC>     Install source: git_dev | git_main | pypi (default: ${INSTALL_SOURCE})
  --role <ROLE>      Role to seed in config.toml: CONTRIBUTOR | GENERATOR | MANAGER
                     (default: ${SEED_ROLE})
  --schema <NAME>    Schema preset to seed: any bundled schema name
                     (default: ${SEED_SCHEMA})
  --auto-prereqs     Auto-install missing prereqs (uv, taskwarrior) where possible
  --dry-run          Show what would happen without making changes
  -h, --help         Show this help

Environment overrides: INSTALL_SOURCE, SEED_ROLE, SEED_SCHEMA, GIT_URL, DRY_RUN,
AUTO_PREREQS — all take precedence over the defaults but are overridden by flags.

Idempotent: re-running on a configured host replaces the existing install and
backs up the old config.toml before overwriting.
EOF
}

while [ $# -gt 0 ]; do
    case "$1" in
        --source)        INSTALL_SOURCE="$2"; shift 2 ;;
        --role)          SEED_ROLE="$2"; shift 2 ;;
        --schema)        SEED_SCHEMA="$2"; shift 2 ;;
        --auto-prereqs)  AUTO_PREREQS=true; shift ;;
        --dry-run)       DRY_RUN=true; shift ;;
        -h|--help)       usage; exit 0 ;;
        *)               fail "Unknown argument: $1"; usage; exit 1 ;;
    esac
done

case "${INSTALL_SOURCE}" in
    git_dev|git_main|pypi) ;;
    *) fail "Invalid --source: ${INSTALL_SOURCE}. Use git_dev | git_main | pypi."; exit 1 ;;
esac

case "${SEED_ROLE}" in
    CONTRIBUTOR|GENERATOR|MANAGER) ;;
    *) fail "Invalid --role: ${SEED_ROLE}. Use CONTRIBUTOR | GENERATOR | MANAGER."; exit 1 ;;
esac

# === Step 1: Prereq check =================================================

check_prereqs() {
    info "Checking prerequisites..."
    local all_ok=true

    # uv (required for `uv tool install`)
    if command -v uv &>/dev/null; then
        ok "uv: $(uv --version 2>&1 | head -1)"
    else
        fail "uv NOT FOUND."
        if [ "$AUTO_PREREQS" = "true" ]; then
            info "Auto-installing uv via the official installer..."
            [ "$DRY_RUN" = "true" ] || curl -LsSf https://astral.sh/uv/install.sh | sh
        else
            echo "  Install: curl -LsSf https://astral.sh/uv/install.sh | sh"
            echo "          (or your package manager equivalent)"
            all_ok=false
        fi
    fi

    # claude CLI (Claude Code)
    if command -v claude &>/dev/null && claude mcp --help &>/dev/null; then
        ok "claude (Claude Code): $(claude --version 2>&1 | head -1)"
    else
        fail "claude (Claude Code) NOT FOUND or missing 'mcp' subcommand."
        echo "  Install: https://docs.anthropic.com/en/docs/claude-code"
        all_ok=false
    fi

    # Taskwarrior
    if command -v task &>/dev/null; then
        local tw_ver
        tw_ver="$(task _version 2>/dev/null || echo '?')"
        ok "task (Taskwarrior): v${tw_ver}"
        local major="${tw_ver%%.*}"
        if [ "$major" = "2" ]; then
            warn "Taskwarrior 2.x detected — this MCP targets 3.x. Some tools may not work."
        fi
    else
        fail "task (Taskwarrior) NOT FOUND."
        echo "  Install (Debian/Ubuntu): sudo apt install taskwarrior"
        echo "          (or build 3.x from https://taskwarrior.org/download/)"
        all_ok=false
    fi

    # Timewarrior (optional)
    if command -v timew &>/dev/null; then
        ok "timew (Timewarrior, optional): $(timew --version 2>&1 | head -1)"
    else
        info "timew (Timewarrior) not found — time tracking tools will be disabled, otherwise harmless."
    fi

    if [ "$all_ok" != "true" ]; then
        fail "Missing prerequisites above. Install them and re-run."
        exit 1
    fi
    echo ""
}

# === Step 2: Install taskchampion-mcp via uv tool install =================

install_taskchampion() {
    local source_arg
    case "${INSTALL_SOURCE}" in
        git_dev)   source_arg=(--from "git+${GIT_URL}@dev" taskchampion-mcp) ;;
        git_main)  source_arg=(--from "git+${GIT_URL}@main" taskchampion-mcp) ;;
        pypi)      source_arg=(taskchampion-mcp) ;;
    esac

    info "Installing taskchampion-mcp (source=${INSTALL_SOURCE}) via uv tool install..."
    info "  Command: uv tool install --force ${source_arg[*]}"

    if [ "$DRY_RUN" = "true" ]; then
        echo "  (dry-run) skipping actual install"
        return
    fi

    # --force makes re-runs idempotent: replaces existing install instead of erroring.
    uv tool install --force "${source_arg[@]}"

    if command -v taskchampion-mcp-server &>/dev/null; then
        ok "taskchampion-mcp-server installed at: $(command -v taskchampion-mcp-server)"
    else
        fail "Install reported success but taskchampion-mcp-server is not on PATH."
        echo "  Check 'uv tool list' and confirm ~/.local/bin (or uv's bin) is on PATH."
        exit 1
    fi
    echo ""
}

# === Step 3: Wire Claude Code (user scope) ================================

wire_claude_code() {
    info "Wiring taskchampion into Claude Code (scope=user)..."

    if [ "$DRY_RUN" = "true" ]; then
        echo "  (dry-run) claude mcp add taskchampion -s user -- $(command -v taskchampion-mcp-server 2>/dev/null || echo '<not yet installed>')"
        return
    fi

    # Idempotent: remove any existing entry first so `add` doesn't fail on dup.
    if claude mcp list 2>/dev/null | grep -qE '^taskchampion[: ]'; then
        info "Removing existing 'taskchampion' Claude Code entry (idempotent)..."
        claude mcp remove taskchampion 2>/dev/null || true
    fi

    claude mcp add taskchampion -s user -- "$(command -v taskchampion-mcp-server)"
    ok "Claude Code: taskchampion registered at user scope."
    echo ""
}

# === Step 4: Seed config.toml =============================================

seed_config() {
    local cfg_dir="${XDG_CONFIG_HOME:-$HOME/.config}/taskchampion-mcp"
    local cfg_path="${cfg_dir}/config.toml"

    info "Seeding config.toml (role=${SEED_ROLE}, schema=${SEED_SCHEMA})..."
    info "  Target: ${cfg_path}"

    if [ "$DRY_RUN" = "true" ]; then
        echo "  (dry-run) would write [server] with role + schema"
        return
    fi

    mkdir -p "$cfg_dir"

    if [ -f "$cfg_path" ]; then
        local backup="${cfg_path}.bak-$(date +%Y%m%d-%H%M%S)"
        warn "Existing config.toml found — backing up to ${backup}"
        cp "$cfg_path" "$backup"
    fi

    cat > "$cfg_path" <<EOF
# TaskChampion MCP — seeded by scripts/setup_remote.sh on $(date -Iseconds)
# Role + schema are the two keys that flip the server out of onboarding mode
# (see ADR 17). Edit freely; the MCP also exposes set_active_schema /
# set_taxonomy_path / set_role (downgrade-only) tools after onboarding.
[server]
role = "${SEED_ROLE}"
schema = "${SEED_SCHEMA}"
EOF
    ok "config.toml seeded: ${cfg_path}"
    echo ""
}

# === Step 5: Verification ==================================================

verify_install() {
    info "Verifying install end-to-end..."

    if [ "$DRY_RUN" = "true" ]; then
        echo "  (dry-run) skipping verification"
        return
    fi

    # 1. Binary is on PATH
    if command -v taskchampion-mcp-server &>/dev/null; then
        ok "Binary on PATH: $(command -v taskchampion-mcp-server)"
    else
        fail "taskchampion-mcp-server not on PATH after install."
        exit 1
    fi

    # 2. Claude Code lists it as Connected
    info "Asking Claude Code to health-check the server..."
    if claude mcp list 2>&1 | grep -qE '^taskchampion.*Connected'; then
        ok "Claude Code: taskchampion ✓ Connected"
    else
        warn "Claude Code health check did not report Connected — output below:"
        claude mcp list 2>&1 | sed 's/^/    /'
    fi

    # 3. Config parses and exits onboarding mode
    info "Loading config.toml as the server would on startup..."
    taskchampion-mcp-server --help &>/dev/null || true   # warm imports

    # Use python from the uv tool env to introspect the loaded config.
    local uv_python
    uv_python="$(uv tool dir 2>/dev/null)/taskchampion-mcp/bin/python"
    if [ -x "$uv_python" ]; then
        "$uv_python" - <<'PY'
from taskchampion_mcp.config import load_config
cfg = load_config()
needs = not (cfg.explicit_role_configured and cfg.explicit_schema_configured)
print(f"  role:                 {cfg.role!r}")
print(f"  schema:               {cfg.schema_name!r}")
print(f"  schema_path:          {cfg.schema_path!r}")
print(f"  explicit_role:        {cfg.explicit_role_configured}")
print(f"  explicit_schema:      {cfg.explicit_schema_configured}")
print(f"  requires_onboarding:  {needs}")
PY
    else
        info "(skipping config introspection — uv tool python not located)"
    fi
    echo ""
}

# === Step 6: Summary =======================================================

print_summary() {
    local cfg_path="${XDG_CONFIG_HOME:-$HOME/.config}/taskchampion-mcp/config.toml"
    cat <<EOF
========================================================
  TaskChampion MCP bootstrap complete on $(hostname)
========================================================

  Install source:    ${INSTALL_SOURCE}
  Server binary:     $(command -v taskchampion-mcp-server 2>/dev/null || echo '<unknown>')
  Claude Code:       user scope (verify: claude mcp list)
  Seeded role:       ${SEED_ROLE}
  Seeded schema:     ${SEED_SCHEMA}
  Config file:       ${cfg_path}

  Taskwarrior:       $(task _version 2>/dev/null || echo '<missing>')
  Timewarrior:       $(timew --version 2>/dev/null | head -1 || echo '<missing>')

Next steps:
  1. Run \`claude\` from your NVIM terminal (or anywhere).
  2. Ask Claude something task-related to confirm the MCP wired up,
     e.g. "list my pending tasks".
  3. To inspect or change the role/schema later from inside Claude:
       set_active_schema(schema_name="gtd")
       set_role("CONTRIBUTOR")          # downgrade only (ADR 17)
       set_taxonomy_path("/path/...")
  4. To elevate role (e.g. promote to MANAGER) you must hand-edit
     ${cfg_path} and restart the claude session — self-elevation via
     MCP is intentionally forbidden (see ADR 17).

========================================================
EOF
}

# === Main ==================================================================

main() {
    echo ""
    info "TaskChampion MCP — Remote-host bootstrap"
    info "Source=${INSTALL_SOURCE}  Role=${SEED_ROLE}  Schema=${SEED_SCHEMA}  Dry-run=${DRY_RUN}"
    echo ""

    check_prereqs
    install_taskchampion
    wire_claude_code
    seed_config
    verify_install
    print_summary
}

main "$@"
