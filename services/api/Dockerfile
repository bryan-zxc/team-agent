FROM python:3.13-slim

RUN apt-get update && apt-get install -y git curl && \
    # GitHub CLI
    mkdir -p /etc/apt/keyrings && \
    curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg -o /etc/apt/keyrings/githubcli-archive-keyring.gpg && \
    chmod go+r /etc/apt/keyrings/githubcli-archive-keyring.gpg && \
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" > /etc/apt/sources.list.d/github-cli.list && \
    apt-get update && apt-get install -y gh && \
    rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Non-root user (UID 1000) shared with ai-service for project_data volume
RUN useradd -m -u 1000 -s /bin/bash agent

WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

COPY . .

RUN git config --system credential.helper '!/usr/bin/gh auth git-credential' && \
    git config --system user.email "agent@team-agent.local" && \
    git config --system user.name "Team Agent"

RUN chown -R agent:agent /app && \
    mkdir -p /data/projects && chown agent:agent /data/projects && \
    mkdir -p /home/agent/.config/gh && chown agent:agent /home/agent/.config/gh

USER agent

EXPOSE 8000

CMD ["uv", "run", "uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
