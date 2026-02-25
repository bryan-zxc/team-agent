#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# ---------- Defaults ----------
BUILD=false
SKIP_CERTS=false
ENV_FILE=".env.prod"

# ---------- Usage ----------
usage() {
    echo "Usage: $0 [--build] [--skip-certs] [--env-file FILE]"
    echo
    echo "Options:"
    echo "  --build       Build images locally instead of pulling from GHCR"
    echo "  --skip-certs  Skip TLS certificate provisioning (certs already exist)"
    echo "  --env-file    Path to env file (default: .env.prod)"
    echo "  --help        Show this help message"
    exit 0
}

# ---------- Parse arguments ----------
while [[ $# -gt 0 ]]; do
    case $1 in
        --build) BUILD=true; shift ;;
        --skip-certs) SKIP_CERTS=true; shift ;;
        --env-file) ENV_FILE="$2"; shift 2 ;;
        --help) usage ;;
        *) echo "Unknown option: $1"; usage ;;
    esac
done

# ---------- Validate ----------
if [[ ! -f "$ENV_FILE" ]]; then
    echo "Error: $ENV_FILE not found."
    echo "Copy .env.prod.template to .env.prod and fill in your values:"
    echo "  cp .env.prod.template .env.prod"
    exit 1
fi

# Read SITE_ADDRESS from env file
SITE_ADDRESS=$(grep -E '^SITE_ADDRESS=' "$ENV_FILE" | cut -d= -f2-)
if [[ -z "$SITE_ADDRESS" ]]; then
    echo "Error: SITE_ADDRESS not set in $ENV_FILE"
    exit 1
fi

# ---------- Docker credential workaround ----------
# Docker Desktop's credential helper requires keychain access, which fails in
# non-interactive SSH sessions. Copy the real Docker config but strip the
# credential store so base image pulls work without the keychain.
if [[ -z "${DOCKER_CONFIG:-}" && ! -t 0 ]]; then
    export DOCKER_CONFIG="$SCRIPT_DIR/.docker-ci"
    mkdir -p "$DOCKER_CONFIG"
    cp -r ~/.docker/* "$DOCKER_CONFIG/" 2>/dev/null || true
    if command -v python3 &>/dev/null; then
        python3 -c "
import json, pathlib
p = pathlib.Path('$DOCKER_CONFIG/config.json')
c = json.loads(p.read_text()) if p.exists() else {}
c.pop('credsStore', None)
p.write_text(json.dumps(c))
"
    fi
fi

echo "==> Deploying for $SITE_ADDRESS"

# ---------- Provision TLS certificates ----------
if [[ "$SKIP_CERTS" == true ]]; then
    echo "==> Skipping TLS certificate provisioning"
else
    echo "==> Provisioning Tailscale TLS certificates..."
    mkdir -p certs
    tailscale cert \
        --cert-file "certs/${SITE_ADDRESS}.crt" \
        --key-file "certs/${SITE_ADDRESS}.key" \
        "$SITE_ADDRESS"
    echo "    Certificates written to certs/"
fi

# ---------- Build or pull ----------
COMPOSE_CMD="docker compose --env-file $ENV_FILE -f docker-compose.yml -f docker-compose.prod.yml"

if [[ "$BUILD" == true ]]; then
    echo "==> Building images locally..."
    $COMPOSE_CMD build
else
    echo "==> Pulling images..."
    $COMPOSE_CMD pull --ignore-buildable
fi

# ---------- Start services ----------
echo "==> Starting services..."
$COMPOSE_CMD up -d

# ---------- Wait for health ----------
echo "==> Waiting for services to become healthy..."
MAX_WAIT=60
ELAPSED=0

while [[ $ELAPSED -lt $MAX_WAIT ]]; do
    HEALTHY=$(docker compose --env-file "$ENV_FILE" -f docker-compose.yml -f docker-compose.prod.yml ps --format json 2>/dev/null \
        | jq -r 'select(.Health == "healthy") | .Service' 2>/dev/null \
        | sort | tr '\n' ' ' || true)

    if echo "$HEALTHY" | grep -q "postgres" && echo "$HEALTHY" | grep -q "redis"; then
        echo "    postgres and redis are healthy"
        break
    fi

    sleep 2
    ELAPSED=$((ELAPSED + 2))
done

if [[ $ELAPSED -ge $MAX_WAIT ]]; then
    echo "Warning: timed out waiting for postgres/redis health checks"
fi

# Give application services a moment to start after DB is ready
sleep 5

# ---------- Verify endpoints ----------
echo "==> Verifying endpoints..."
FAILURES=0

# API health
API_STATUS=$(curl -sf "https://${SITE_ADDRESS}/api/health" 2>/dev/null | jq -r '.status' 2>/dev/null || echo "unreachable")
if [[ "$API_STATUS" == "ok" || "$API_STATUS" == "degraded" ]]; then
    echo "    API health: $API_STATUS"
else
    echo "    API health: FAILED ($API_STATUS)"
    FAILURES=$((FAILURES + 1))
fi

# Frontend
FRONTEND_STATUS=$(curl -sf -o /dev/null -w "%{http_code}" "https://${SITE_ADDRESS}/" 2>/dev/null || echo "000")
if [[ "$FRONTEND_STATUS" == "200" ]]; then
    echo "    Frontend: OK (HTTP $FRONTEND_STATUS)"
else
    echo "    Frontend: FAILED (HTTP $FRONTEND_STATUS)"
    FAILURES=$((FAILURES + 1))
fi

# ---------- Summary ----------
echo
if [[ $FAILURES -eq 0 ]]; then
    echo "Deployment successful! App is live at https://${SITE_ADDRESS}/"
else
    echo "Deployment completed with $FAILURES verification failure(s)."
    echo "Check logs with: docker compose --env-file $ENV_FILE -f docker-compose.yml -f docker-compose.prod.yml logs"
    exit 1
fi
