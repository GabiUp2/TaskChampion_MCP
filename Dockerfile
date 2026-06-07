# TaskChampion MCP — Dockerfile
#
# Used by Glama (https://glama.ai/mcp/servers/GabiUp2/TaskChampion_MCP)
# for server scoring and capability introspection.
#
# The server communicates exclusively over stdio (MCP JSON-RPC).
# No ports are exposed.
#
# NOTE: Glama auto-detects a uv-based build spec from pyproject.toml and
# may bypass this Dockerfile. If so, the equivalent Glama build spec is:
#   buildSteps: ["uv sync",
#                "ln -s $(pwd)/.venv/bin/taskchampion-mcp-server /usr/local/bin/taskchampion-mcp-server"]
#   cmdArguments: ["mcp-proxy", "--", "taskchampion-mcp-server"]
#
# Requires: Taskwarrior 3.x — available in Ubuntu 24.04 (noble) via apt.

FROM ubuntu:24.04

# Suppress interactive prompts during package installation
ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Install system dependencies:
#   python3 / pip  — runtime
#   taskwarrior    — Taskwarrior 3.x (noble ships 3.0.x)
#   timewarrior    — optional time-tracking integration
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        python3 \
        python3-pip \
        taskwarrior \
        timewarrior \
    && rm -rf /var/lib/apt/lists/*

# Install uv, sync the project, then symlink both entry-point binaries onto
# system PATH so they are findable regardless of invocation method
# (uv pip install --system, uv run, or direct spawn by mcp-proxy).
RUN pip3 install --break-system-packages uv

WORKDIR /app
COPY . .

RUN uv sync --no-dev \
    && ln -s /app/.venv/bin/taskchampion-mcp-server /usr/local/bin/taskchampion-mcp-server \
    && ln -s /app/.venv/bin/taskchampion-mcp /usr/local/bin/taskchampion-mcp

# Create a minimal Taskwarrior data dir and config so the server
# starts cleanly without prompting for first-run initialisation
RUN mkdir -p /root/.task \
    && printf 'data.location=/root/.task\nconfirmation=no\n' > /root/.taskrc

# The MCP server speaks JSON-RPC over stdio — no ports needed
CMD ["taskchampion-mcp-server"]
