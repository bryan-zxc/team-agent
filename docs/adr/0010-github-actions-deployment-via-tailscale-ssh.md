# ADR-0010: GitHub Actions deployment via Tailscale SSH

## Context

The app runs on a Mac Mini accessible via Tailscale at `bryans-mac-mini.tail22e956.ts.net`. Deployment was manual: SSH in, pull code, run `docker compose up`. A `deploy.sh` script existed to automate the local steps (pull/build images, start services, provision TLS certs, verify health endpoints), but triggering it still required human intervention. The goal was to automate the full pipeline: push code, build images, deploy to the Mac Mini.

## Alternatives Considered

**Self-hosted GitHub Actions runner on the Mac Mini** — install the GitHub Actions runner daemon directly on the Mac Mini so it executes workflow jobs locally. Pros: native ARM64 builds (no cross-compilation), no SSH complexity. Cons: the runner daemon consumes resources on the production host, requires maintenance and updates, mixes CI workload with production workload, and the Mac Mini must be always-on and reachable by GitHub (already satisfied via Tailscale, but adds another daemon to manage).

**GitHub-hosted runners with Tailscale SSH** — build Docker images on GitHub's Ubuntu runners, push to GHCR, then SSH into the Mac Mini via Tailscale to pull and deploy. The `tailscale/github-action` joins the tailnet ephemerally using an OAuth client. Pros: no daemon on the Mac Mini, build workload is offloaded to GitHub, the Mac Mini stays a simple Docker host, the existing `deploy.sh` script is reused as-is. Cons: ARM64 images require QEMU cross-compilation (slower builds), depends on Tailscale availability for the SSH step.

## Decision

Use GitHub-hosted runners with Tailscale SSH. The workflow has two jobs:

1. **Build and push** — runs on `ubuntu-latest`, builds multi-platform Docker images (`linux/amd64,linux/arm64`) using QEMU emulation, pushes to GHCR tagged with the git SHA, `latest`, and any version tag
2. **Deploy** — runs on `ubuntu-latest`, joins the tailnet via `tailscale/github-action@v4` with an OAuth client, SSHes into the Mac Mini, runs `git pull && TAG=sha-xxx ./deploy.sh --skip-certs`

This was chosen because:
- The Mac Mini is a single production host — keeping it free of CI daemons reduces operational complexity
- The existing `deploy.sh` already handles image pulling, service startup, health checks, and TLS cert provisioning. Reusing it avoids duplicating logic in the workflow
- QEMU cross-compilation is slower but acceptable since deployments only happen on release (not on every push)
- Tailscale's ephemeral OAuth nodes are automatically cleaned up after the workflow ends, leaving no persistent access

## Consequences

- ARM64 builds via QEMU are significantly slower than native builds. If build times become a problem, the workflow could be changed to use a self-hosted ARM64 runner or GitHub's `ubuntu-24.04-arm` runners (if available)
- The deployment depends on Tailscale being operational. If Tailscale is down, the deploy job fails but the images are already pushed to GHCR — a manual SSH deploy can recover
- The Mac Mini must have the repo checked out at `~/team-agent` with a valid `.env.prod` file. The workflow runs `git pull` to update the repo (for `docker-compose.yml`, `Caddyfile`, etc.) before running `deploy.sh`
- A `tag:ci` ACL tag in Tailscale restricts what the ephemeral GitHub Actions node can access — it should only be allowed SSH (port 22) to the Mac Mini
