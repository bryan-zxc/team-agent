FROM python:3.13

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Install Node.js (required for Claude CLI) and GitHub CLI
RUN apt-get update && \
    apt-get install -y --no-install-recommends ca-certificates curl gnupg && \
    # Node.js 22.x via nodesource
    mkdir -p /etc/apt/keyrings && \
    curl -fsSL https://deb.nodesource.com/gpgkey/nodesource-repo.gpg.key | gpg --dearmor -o /etc/apt/keyrings/nodesource.gpg && \
    echo "deb [signed-by=/etc/apt/keyrings/nodesource.gpg] https://deb.nodesource.com/node_22.x nodistro main" > /etc/apt/sources.list.d/nodesource.list && \
    # GitHub CLI
    mkdir -p -m 755 /etc/apt/keyrings && \
    curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg -o /etc/apt/keyrings/githubcli-archive-keyring.gpg && \
    chmod go+r /etc/apt/keyrings/githubcli-archive-keyring.gpg && \
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" > /etc/apt/sources.list.d/github-cli.list && \
    apt-get update && \
    apt-get install -y --no-install-recommends nodejs gh && \
    rm -rf /var/lib/apt/lists/*

# Install Claude CLI
RUN npm install -g @anthropic-ai/claude-code

# Non-root user (UID 1000) shared with api service for project_data volume
RUN useradd -m -u 1000 -s /bin/bash agent && \
    mkdir -p /home/agent/.claude /home/agent/.config/gh && \
    chown -R agent:agent /home/agent/.claude /home/agent/.config && \
    git config --system credential.helper '!/usr/bin/gh auth git-credential'

WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

COPY . .

RUN chown -R agent:agent /app && \
    mkdir -p /data/projects && chown agent:agent /data/projects

USER agent

CMD ["uv", "run", "uvicorn", "src.ai.main:app", "--host", "0.0.0.0", "--port", "8001"]
