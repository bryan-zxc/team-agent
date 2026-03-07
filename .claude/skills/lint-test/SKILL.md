---
name: lint-test
description: Run all linting and static analysis tools across the entire codebase — ruff, pyright, vulture for Python services; ESLint, TypeScript compiler, knip for the frontend. Auto-fixes what it can, asks the user about the rest, and reports a summary. Use this skill whenever the user asks to lint, run static analysis, check code quality, find dead code, type-check, or clean up the codebase. Also trigger on "lint", "lint test", "run linters", "code quality", "type check", "dead code", or "static analysis".
---

# Lint Test

Run all linting and static analysis tools across the codebase, fix issues, and report a summary. Tools run one by one in a specific order. Auto-fixable issues are fixed silently. Non-auto-fixable issues are presented to the user for discussion before applying a fix.

## Tool order

Run in this exact sequence — earlier tools may fix issues that later tools would flag:

1. **Ruff** (Python lint + format) — `services/api/` and `services/ai/`
2. **Pyright** (Python type checking, standard mode) — `services/api/` and `services/ai/`
3. **Vulture** (Python dead code) — `services/api/` and `services/ai/`
4. **ESLint** (TypeScript/React lint) — `services/frontend/`
5. **TypeScript compiler** (type checking) — `services/frontend/`
6. **Knip** (unused exports, files, dependencies) — `services/frontend/`

## Running each tool

### 1. Ruff

Ruff has extensive auto-fix capabilities. Run auto-fix first, then check for remaining issues.

```bash
# Auto-fix (safe fixes only)
ruff check --fix services/api/src/ services/ai/src/

# Format
ruff format services/api/src/ services/ai/src/

# Check for remaining issues
ruff check services/api/src/ services/ai/src/
```

**Auto-fixable:** Most import sorting, unused imports, formatting issues, simple lint rules.
**Needs human input:** Complex refactors, ambiguous fixes flagged with `--unsafe-fixes`.

Record the number of files changed by the auto-fix step (compare `git diff --stat` before and after).

### 2. Pyright

Pyright has no auto-fix. All issues require manual resolution.

```bash
cd services/api && pyright src/
cd services/ai && pyright src/
```

Present all errors to the user grouped by file. For each error, explain what it means and propose a fix. Common fixes:
- Add type annotations to function parameters/return types
- Add `# type: ignore[rule]` with justification for false positives
- Fix genuine type mismatches

Wait for user approval before applying fixes. Fix one file (or logical group) at a time.

### 3. Vulture

Vulture has no auto-fix. It reports potentially unused code.

```bash
vulture services/api/src/ --min-confidence 80
vulture services/ai/src/ --min-confidence 80
```

Vulture has false positives — code used via frameworks (FastAPI routes, SQLAlchemy models, Pydantic fields) often looks unused. For each finding:
- If it's genuinely dead code: propose deletion
- If it's a false positive (framework magic): propose adding to a whitelist file

Create whitelist files (`services/api/vulture_whitelist.py`, `services/ai/vulture_whitelist.py`) for false positives. Present findings to the user before making changes.

### 4. ESLint

ESLint has auto-fix for many rules.

```bash
cd services/frontend

# Auto-fix
npx eslint --fix src/

# Check remaining
npx eslint src/
```

**Auto-fixable:** Import ordering, semicolons, quotes, simple formatting, unused imports.
**Needs human input:** Accessibility issues (a11y), React hooks violations, complex patterns.

Record auto-fixed count from the `--fix` output.

### 5. TypeScript compiler

No auto-fix. All issues require manual resolution.

```bash
cd services/frontend && npx tsc --noEmit
```

Present errors to the user grouped by file. Common fixes:
- Add missing type annotations
- Fix type mismatches
- Add null checks
- Update interface definitions

Wait for user approval before applying fixes.

### 6. Knip

No auto-fix. Reports unused exports, files, and dependencies.

```bash
cd services/frontend && npx knip
```

Knip can produce false positives for dynamic imports, Next.js page/layout exports, CSS module imports, and framework-specific patterns (dockview, react-arborist). If knip has excessive false positives, create `services/frontend/knip.json` to tune entry points and ignore patterns.

Present findings to the user before making changes.

## Interaction model

For each tool:

1. **Run the tool** and capture output
2. **Auto-fix** where the tool supports it (ruff, eslint) — apply silently
3. **Re-run** to get remaining issues
4. **If issues remain**, present them to the user in a clear format:
   - File path and line number
   - The error/warning message
   - Your proposed fix
5. **Wait for user approval** before applying non-auto-fixable changes
6. **Re-run** the tool to confirm zero issues before moving to the next tool

Only move to the next tool when the current tool reports zero issues (or the user explicitly decides to skip remaining issues).

## Summary report

After all six tools pass cleanly, present this summary:

```
## Lint Test Summary

### Auto-fixed
- **Ruff**: X issues auto-fixed (Y files)
- **ESLint**: X issues auto-fixed (Y files)
- **Total auto-fixed**: X issues

### Manually resolved

| # | Tool | File | Issue | Resolution |
|---|------|------|-------|------------|
| 1 | Pyright | src/api/routes/data.py:42 | Missing return type | Added `-> dict` return annotation |
| 2 | Vulture | src/api/guards.py:15 | Unused `get_db` | False positive — added to whitelist |
| 3 | ESLint | src/components/Chat.tsx:8 | Missing key prop | Added key={msg.id} to list items |
| ... | ... | ... | ... | ... |

### Final status
- Ruff: PASS
- Pyright (standard): PASS
- Vulture: PASS
- ESLint: PASS
- TypeScript: PASS
- Knip: PASS
```

Track counts throughout the run. The table should include every issue that required human interaction — even if the resolution was "false positive, added to whitelist".
