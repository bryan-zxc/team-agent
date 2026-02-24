FROM python:3.13-slim

RUN apt-get update && apt-get install -y git && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Non-root user (UID 1000) shared with ai-service for project_data volume
RUN useradd -m -u 1000 -s /bin/bash agent

WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

COPY . .

RUN chown -R agent:agent /app && \
    mkdir -p /data/projects && chown agent:agent /data/projects

USER agent

EXPOSE 8000

CMD ["uv", "run", "uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
