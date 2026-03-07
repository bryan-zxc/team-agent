---
name: release
description: Create a release by raising a PR from develop to main, running lint tests and parallel agent-based code review, resolving all issues, then merging, tagging, and deploying. Use when the user asks to release, deploy, cut a release, bump a version, or ship to production.
---

# Release

Raise a PR from develop to main, run quality gates (lint + agent review),
resolve all issues, merge the PR, tag a semver version, and push the tag to
trigger the CI/CD deployment pipeline (`.github/workflows/deploy.yml`).

## Usage

```
/release [major|minor|patch|vX.Y.Z]
```

If a bump type or specific version is provided, use it as the starting
recommendation. If no argument is given, analyse the changes to recommend a
version. In all cases, present the recommendation and wait for user approval.

## Workflow

### 1. Ensure working tree is clean and sync local branches

```bash
git status --porcelain
```

If there are uncommitted changes, warn the user and stop.

Then sync local branches with origin so all comparisons are accurate:

```bash
git fetch origin main develop
git checkout develop
git pull origin develop
git checkout main
git pull origin main
git checkout develop
```

### 2. Create the pull request

Create a PR from develop to main with a placeholder title. The title and
description will be updated after version is determined.

```bash
gh pr create --base main --head develop \
  --title "Release (pending version)" \
  --body "Release PR — version and description will be populated after review."
```

If a PR already exists from develop to main, skip creation and use it.

### 3. Determine the current version

Read the latest version tag from git:

```bash
git tag --list 'v*' --sort=-version:refname | head -1
```

If no tags exist, the current version is `v0.0.0`.

### 4. Analyse changes and determine version

Run:

```bash
git log main..develop --oneline
git diff main..develop --stat
```

Read the commit list and file-level diff summary. For key files with
significant changes, read the full diff to understand the scope:

```bash
git diff main..develop -- <file>
```

Based on the analysis, recommend a bump type:

- **major** — breaking changes, API contract changes, incompatible migrations
- **minor** — new features, new endpoints, new UI capabilities
- **patch** — bug fixes, refactors, dependency updates, config changes

Compute the proposed next version by bumping from the current version.

### 5. Confirm version with the user

Present:
- Current version (latest tag, or "no previous release")
- Proposed next version and bump type
- Why this bump type was recommended (brief summary of what changed)
- Commit list
- Files changed summary (`--stat` output)

Wait for the user to approve, change the version, or cancel. Never proceed
without explicit approval.

### 6. Update the PR title and description

Once version is confirmed, update the PR with a proper title and description:

```bash
gh pr edit <PR_NUMBER> \
  --title "Release vX.Y.Z" \
  --body "$(cat <<'EOF'
## Release vX.Y.Z

### Changes
<bullet list of commits grouped by theme>

### Version bump
<major|minor|patch> — <brief rationale>
EOF
)"
```

### 7. Run lint tests

Invoke the `/lint-test` skill. All 6 tools (ruff, pyright, vulture, eslint,
tsc, knip) must pass with zero issues before proceeding. If lint-test
produces fixes, commit and push them to develop before continuing.

### 8. Run agent review

Launch 6 parallel agents on the PR diff. Each agent independently reviews the
changes and returns a list of issues.

#### Agent inventory

| # | Agent | What it checks |
|---|-------|----------------|
| 1 | **Bug scanner** | Logic errors, null handling, race conditions, memory leaks, security vulnerabilities, performance. Diff-focused, avoids nitpicks. |
| 2 | **Comment analyser** | Comment accuracy (cross-references claims against code), completeness, long-term value, misleading elements, comment rot. Also checks that PR changes comply with guidance in existing code comments. |
| 3 | **Error handling auditor** | Silent failures, empty catch blocks, broad exception catching, missing user feedback, unjustified fallbacks, swallowed errors, hidden failures via optional chaining. |
| 4 | **Type design reviewer** | Only runs if types are added/modified. Encapsulation, invariant expression, usefulness, enforcement. Only surfaces concerns rated 8+. |
| 5 | **History analyser** | Git blame + history of modified files for contextual bugs. Previous PRs that touched these files — checks if past review comments apply to current changes. |
| 6 | **ADR compliance** | Reads `docs/adr/adr.md` index, determines which ADRs are relevant to the changed files/functionality, reads each relevant ADR in full, checks for violations of decisions or consequences. |

#### Agent prompts

**Bug scanner:**
```
Review the PR diff for bugs. Focus on:
- Logic errors, off-by-one, incorrect conditions
- Null/undefined handling and missing guards
- Race conditions in async code
- Memory leaks (unclosed resources, dangling listeners)
- Security vulnerabilities (injection, auth bypass, exposed secrets)
- Performance problems (N+1 queries, unbounded loops)

Only flag issues in the changed lines — not pre-existing code. Avoid nitpicks,
formatting issues, and things a linter would catch. Focus on bugs that a senior
engineer would flag. Return each issue with: file, line, description, severity.
```

**Comment analyser:**
```
Analyse code comments in the changed files. Check:
1. Factual accuracy — cross-reference every claim against actual code.
   Function signatures match? Described behaviour matches logic? Referenced
   types/functions exist?
2. Completeness — critical assumptions documented? Non-obvious side effects
   mentioned? Complex algorithms explained?
3. Long-term value — flag comments that merely restate obvious code. Prefer
   'why' over 'what'. Flag comments likely to become outdated.
4. Misleading elements — ambiguous language, outdated references, stale TODOs
5. Compliance — do the PR changes comply with guidance written in existing
   code comments? If a comment says "always call X before Y" and the PR
   doesn't, flag it.

Return each issue with: file, line, description, severity.
```

**Error handling auditor:**
```
Audit error handling in the PR changes. Check every:
- try-catch/try-except block
- Error callbacks and event handlers
- Conditional branches handling error states
- Fallback logic and default values on failure
- Optional chaining that might hide errors

For each handler, verify:
- Is the error logged with sufficient context?
- Does the user receive actionable feedback?
- Is the catch block specific (not catching all exceptions)?
- Is fallback behaviour explicit and justified?
- Should the error propagate instead of being caught here?

Flag: empty catch blocks, catch-and-continue without logging, returning
null/default on error silently, broad exception catching, unjustified
fallbacks. Return each issue with: file, line, description, severity.
```

**Type design reviewer:**
```
Only run if types/interfaces/classes were added or modified in the PR.

For each new or modified type, evaluate:
- Encapsulation (1-10): are internals properly hidden?
- Invariant expression (1-10): are constraints clear from the type structure?
- Invariant usefulness (1-10): do constraints prevent real bugs?
- Invariant enforcement (1-10): are invariants checked at construction time?

Flag: anemic domain models, exposed mutable internals, invariants enforced
only through documentation, types with too many responsibilities, missing
constructor validation. Only return concerns rated 8+.
```

**History analyser:**
```
Review git history for context on the PR changes.

1. For each modified file, run:
   - git log --oneline -10 -- <file>
   - git blame on the modified line ranges
2. Look for patterns: was similar code recently changed/reverted? Are there
   known fragile areas? Was this code recently fixed for a related issue?
3. Check previous merged PRs that touched these files:
   gh pr list --state merged --search "<filename>" --limit 5
   Read comments on those PRs. Flag any past review feedback that also
   applies to the current changes.

Return each issue with: file, line, historical context, description.
```

**ADR compliance:**
```
Check the PR for compliance with Architecture Decision Records.

1. Read docs/adr/adr.md to get the full ADR index.
2. Read the PR diff to understand what changed.
3. For each ADR, assess relevance to the changes:
   - Authentication ADR? Only relevant if auth code changed.
   - Inter-service communication ADR? Only if service boundaries touched.
   - Deployment ADR? Only if infra/CI changed.
   Skip irrelevant ADRs entirely.
4. For each relevant ADR, read the full file at docs/adr/NNNN-*.md.
5. Check if the PR violates the Decision or contradicts the Consequences.

Return each violation with: ADR number, the specific decision text violated,
the file and line in the PR that violates it.
```

#### Confidence scoring

After all 6 agents complete, launch a parallel Haiku scorer for each issue.
Give each scorer the PR diff, the issue description, and this rubric:

| Score | Meaning |
|-------|---------|
| 0 | False positive, doesn't stand up to scrutiny, or pre-existing issue |
| 25 | Might be real but unverified |
| 50 | Real but minor/nitpick, not important relative to the rest of the PR |
| 75 | Very likely real, important, will impact functionality |
| 100 | Confirmed real, will happen frequently in practice |

Filter out all issues scoring below **75**.

#### Code simplifier (runs after main review)

After all 75+ issues are resolved, run a final **code simplifier** pass on
the current state of the changed files. It reviews for:
- Unnecessary complexity and nesting
- Redundant code and abstractions
- Nested ternaries (prefer switch/if-else)
- Clarity over brevity

Its suggestions also go through the same confidence scoring and user
approval flow.

### 9. Resolve issues

Present all 75+ issues in a numbered list grouped by agent. Work through each
issue one by one:

1. Show the issue: agent, file, line, description, confidence score
2. Propose a fix
3. Wait for user approval or alternative direction
4. Apply the fix
5. Move to the next issue

If fixes are made, commit and push to develop. The PR updates automatically.

### 10. Summary report

After all issues are resolved, present:

```
## Agent Review Summary

### Issues found and resolved

| # | Agent | File | Issue | Confidence | Resolution |
|---|-------|------|-------|------------|------------|
| 1 | Bug scanner | src/api/routes/data.py:42 | Null dereference | 85 | Added null check |
| 2 | ADR compliance | src/routes/projects.py:180 | Violates ADR-0003 | 92 | Refactored |
| ... | ... | ... | ... | ... | ... |

### Statistics
- Total issues found (pre-filter): X
- Issues above 75% confidence: Y
- Issues resolved: Y
```

### 11. Merge the PR

```bash
gh pr merge <PR_NUMBER> --merge
```

### 12. Tag the version and push

```bash
git checkout main
git pull origin main
git tag -a vX.Y.Z -m "Release vX.Y.Z"
git push origin vX.Y.Z
```

Pushing the tag triggers the GitHub Actions deploy workflow.

### 13. Switch back to develop

```bash
git checkout develop
```

### 14. Monitor deployment

Poll the workflow run until it completes:

```bash
RUN_ID=$(gh run list --repo bryan-zxc/team-agent --limit 1 --json databaseId --jq '.[0].databaseId')
gh run watch "$RUN_ID" --repo bryan-zxc/team-agent
```

If the run **succeeds**, report the result and finish.

If the run **fails**:

1. Fetch the logs to identify the failure:
   ```bash
   gh run view "$RUN_ID" --repo bryan-zxc/team-agent --log-failed
   ```
2. Diagnose the root cause from the logs
3. Fix the issue on develop, commit and push
4. Create a new PR, merge it, and re-tag (delete old tag first):
   ```bash
   git tag -d vX.Y.Z
   git push origin :refs/tags/vX.Y.Z
   git checkout main && git pull origin main
   git tag -a vX.Y.Z -m "Release vX.Y.Z"
   git push origin vX.Y.Z
   git checkout develop
   ```
5. This triggers a new workflow run — go back to the polling step
6. Repeat until deployment succeeds

### 15. Report result

Print:
- The version released (e.g. `v0.3.0`)
- Link to the successful run
- Confirm deployment is live

## Rules

- Never auto-decide a version — always present a recommendation and wait for user approval
- Never force-push to main
- Always return to the develop branch after the release
- If any step fails, stop immediately and report the error
- Production deploys from **main only** — the CI/CD pipeline triggers on version tag push, builds from main, and the Mac Mini checks out and runs main
- All agent review issues above 75% confidence must be resolved before merging
- Lint tests must pass with zero issues before agent review begins
