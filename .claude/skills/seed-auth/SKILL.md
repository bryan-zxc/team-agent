---
name: seed-auth
description: "Seed the claude_auth and gh_auth Docker volumes so the production AI service can authenticate with Claude CLI (subscription) and GitHub CLI. Use this skill whenever the user mentions seeding auth, reseeding credentials, fixing Claude or GitHub auth in the container, or after a docker compose down -v that wiped the volumes. Also use when the user reports that Claude Code inside the AI service can't authenticate or that gh commands are failing in the container."
---

# Seed Auth

Populate the `claude_auth` and `gh_auth` Docker named volumes with credentials
so the AI service's Claude Code subprocesses and GitHub CLI work in production.

## Usage

```
/seed-auth [claude|gh|all]
```

Default is `all`. The argument selects which credential to seed.

## Compose command

Every `docker compose` invocation in this skill uses:

```bash
docker compose --env-file .env.prod -f docker-compose.yml -f docker-compose.prod.yml
```

Abbreviated as `$COMPOSE` below for readability.

## Prerequisite

The production stack must be running. If it isn't:

```bash
$COMPOSE up -d
```

## Claude auth

Claude Code on macOS stores subscription credentials in the macOS keychain.
The service name is `Claude Code-credentials` (with a space and capital C).
The value is a JSON blob containing OAuth tokens.

Inside the Linux container there is no system keychain, so Claude Code falls
back to reading `/home/agent/.claude/.credentials.json`.

### Steps

1. Extract the credential from the host keychain into a temp file:

```bash
security find-generic-password -s "Claude Code-credentials" -w > /tmp/claude-cred.tmp
```

2. Pipe it into the container's `claude_auth` volume:

```bash
cat /tmp/claude-cred.tmp | $COMPOSE exec -T ai-service \
  bash -c 'cat > /home/agent/.claude/.credentials.json && chmod 600 /home/agent/.claude/.credentials.json'
```

3. Clean up the temp file:

```bash
rm -f /tmp/claude-cred.tmp
```

4. If the container has a missing `.claude.json` warning, restore from backup:

```bash
$COMPOSE exec ai-service bash -c '
  BACKUP=$(ls -t /home/agent/.claude/backups/.claude.json.backup.* 2>/dev/null | head -1)
  if [ -n "$BACKUP" ]; then
    cp "$BACKUP" /home/agent/.claude.json
    echo "Restored .claude.json from backup"
  fi
'
```

5. Verify:

```bash
$COMPOSE exec ai-service bash -c 'claude auth status 2>&1'
```

Expected output must include:
- `"authMethod": "claude.ai"`
- `"subscriptionType": "max"`

If it shows `"authMethod": "api_key"` instead, the `ANTHROPIC_API_KEY`
environment variable is set and taking precedence. Remove it from `.env.prod`
and restart the ai-service:

```bash
$COMPOSE up -d ai-service
```

## GitHub auth

GitHub CLI requires an interactive browser-based login.

### Steps

1. Run the login flow inside the container:

```bash
$COMPOSE exec -it ai-service gh auth login --web --git-protocol https
```

This prints a one-time code and a URL. Open the URL in a browser, enter the
code, and authorise. Wait for the CLI to confirm `Logged in as <username>`.

2. Verify:

```bash
$COMPOSE exec ai-service gh auth status
```

## Volume persistence

Credentials are stored in Docker named volumes (`claude_auth`, `gh_auth`).
They survive container rebuilds, restarts, image updates, and `docker compose
down`. They are only deleted by `docker compose down -v` (the `-v` flag
explicitly removes volumes). After a `-v` teardown, re-run `/seed-auth` to
restore credentials.
