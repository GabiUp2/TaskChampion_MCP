# TaskChampion MCP — Dockerfile
#
# Used by Glama (https://glama.ai/mcp/servers/GabiUp2/TaskChampion_MCP)
# for server scoring and capability introspection.
#
# The server communicates exclusively over stdio (MCP JSON-RPC).
# No ports are exposed.
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

# Install uv then use it to install taskchampion-mcp from PyPI
RUN pip3 install --break-system-packages uv \
    && uv pip install --system taskchampion-mcp

# Create a minimal Taskwarrior data dir and config so the server
# starts cleanly without prompting for first-run initialisation
RUN mkdir -p /root/.task \
    && printf 'data.location=/root/.task\nconfirmation=no\n' > /root/.taskrc

# The MCP server speaks JSON-RPC over stdio — no ports needed
CMD ["taskchampion-mcp"]
