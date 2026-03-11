---
name: seed-auth
description: "Seed the claude_auth and gh_auth Docker volumes so the production AI service can authenticate with Claude CLI (subscription) and GitHub CLI. Use this skill whenever the user mentions seeding auth, reseeding credentials, fixing Claude or GitHub auth in the container, or after a docker compose down -v that wiped the volumes. Also use when the user reports that Claude Code inside the AI service can't authenticate or that gh commands are failing in the container."
---

# Seed Auth

Configure authentication for the AI service's Claude Code subprocesses and
GitHub CLI.

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

Claude Code authenticates via a long-lived OAuth token set in the environment
variable `CLAUDE_CODE_OAUTH_TOKEN`. The token is valid for 1 year and is
generated on a machine with a browser using `claude setup-token`.

The token is stored in `.env.prod` (production) and `.env.local` (development).
Both files are gitignored.

### Generating a new token

Run on the host machine (not inside the container):

```bash
claude setup-token
```

This opens a browser for OAuth authentication and prints a token like
`sk-ant-oat01-xxxxx...xxxxx`. Copy the token.

### Setting the token

Add or update the token in both env files:

```bash
# .env.prod
CLAUDE_CODE_OAUTH_TOKEN="sk-ant-oat01-your-token-here"

# .env.local
CLAUDE_CODE_OAUTH_TOKEN="sk-ant-oat01-your-token-here"
```

Then restart the AI service:

```bash
$COMPOSE up -d ai-service
```

### Verifying

```bash
$COMPOSE exec ai-service claude auth status 2>&1
```

Expected output must include:
- `"authMethod": "oauth_token"`
- `"loggedIn": true`

If it shows `"authMethod": "api_key"` instead, the `ANTHROPIC_API_KEY`
environment variable is set and taking precedence. Remove it from `.env.prod`
and restart the ai-service.

### Restoring .claude.json

If the container reports a missing `.claude.json`, restore from backup:

```bash
$COMPOSE exec ai-service bash -c '
  BACKUP=$(ls -t /home/agent/.claude/backups/.claude.json.backup.* 2>/dev/null | head -1)
  if [ -n "$BACKUP" ]; then
    cp "$BACKUP" /home/agent/.claude.json
    echo "Restored .claude.json from backup"
  fi
'
```

## GitHub auth

GitHub CLI requires an interactive browser-based login.

### Steps

1. Run the login flow inside the container:

```bash
$COMPOSE exec -it ai-service gh auth login --web --git-protocol https --scopes read:project,project
```

This prints a one-time code and a URL. Open the URL in a browser, enter the
code, and authorise. Wait for the CLI to confirm `Logged in as <username>`.

2. Verify:

```bash
$COMPOSE exec ai-service gh auth status
```

## Volume persistence

The `claude_auth` volume (`/home/agent/.claude`) stores Claude Code's working
data (projects, cache, session state). The `gh_auth` volume stores GitHub CLI
credentials. Both survive container rebuilds, restarts, image updates, and
`docker compose down`. They are only deleted by `docker compose down -v` (the
`-v` flag explicitly removes volumes). After a `-v` teardown, re-run
`/seed-auth` to restore GitHub credentials (Claude auth comes from the env
var and requires no re-seeding).
