---
name: workload-recovery
description: Investigate and resolve escalated workload errors — merge conflicts, push failures, worktree creation issues, relay crashes, and cancelled workload cleanup. Use this skill whenever you receive a context message about a workload error that needs investigation, or when told to use the /workload-recovery skill. Triggers on any mention of merge conflicts, push failures, worktree problems, relay crashes, or workload investigation in the admin room.
---

# Workload Recovery

You've been brought in because a workload session hit a mechanical error it couldn't handle on its own. Your context message contains the error type, affected paths, and a chat transcript. This skill walks you through diagnosing and resolving each kind of failure.

## First Steps (All Error Types)

1. **Read the chat transcript** if a file path was provided — it shows what the workload agent was doing when the error occurred. This context is essential for making good resolution decisions.
2. **Identify the error type** from your context message — it will be one of: merge conflict, push failure, worktree creation failure, relay crash, or cancelled workload cleanup.
3. **Extract the workload chat ID** from the context message — you'll need it for API calls.

## Merge Conflict

The workload branch couldn't merge cleanly into the target branch. The merge was aborted, and the worktree is preserved for you to work in.

1. `cd` to the **worktree path** from your context message
2. Attempt the merge:
   ```bash
   git merge <target_branch>
   ```
3. Read the conflicting files, understand both sides, and resolve them sensibly — prefer preserving the workload's intent while incorporating upstream changes
4. Stage resolved files and commit:
   ```bash
   git add <resolved_files>
   git commit --no-edit
   ```
5. Switch to the clone path, merge the resolved branch, and push:
   ```bash
   cd <clone_path>
   git merge <branch_name> --no-edit
   git push
   ```
6. Clean up the worktree and remote branch:
   ```bash
   git worktree remove <worktree_path> --force
   git branch -D <branch_name>
   git push origin --delete <branch_name>
   ```
7. Report success:
   ```bash
   curl -s -X POST http://api:8000/chats/<workload_chat_id>/resolve \
     -H 'Content-Type: application/json' \
     -H 'x-internal-key: team-agent-internal' \
     -d '{"outcome": "success", "message": "Resolved merge conflict in <files> and pushed."}'
   ```

If the conflict is too complex or ambiguous to resolve confidently:
```bash
git merge --abort
curl -s -X POST http://api:8000/chats/<workload_chat_id>/resolve \
  -H 'Content-Type: application/json' \
  -H 'x-internal-key: team-agent-internal' \
  -d '{"outcome": "failed", "message": "Merge conflict in <files> requires manual resolution — both sides made structural changes to the same functions."}'
```

## Push Failure

The merge itself succeeded, but `git push` failed afterwards. The worktree has already been cleaned up, so you're working on the **clone path** directly.

1. `cd` to the **clone path**
2. Diagnose:
   ```bash
   git status
   git remote -v
   git log --oneline -5
   ```
3. Common causes and fixes:
   - **Diverged history**: `git pull --rebase origin <branch>` then push again
   - **Auth issues**: check remote URL format, try `git push` and read the error
   - **Branch protection**: the branch may have rules preventing direct push — check the error message
4. Try pushing again:
   ```bash
   git push origin <branch_name>
   ```
5. Report the outcome:
   ```bash
   curl -s -X POST http://api:8000/chats/<workload_chat_id>/resolve \
     -H 'Content-Type: application/json' \
     -H 'x-internal-key: team-agent-internal' \
     -d '{"outcome": "success", "message": "Push succeeded after <what you fixed>."}'
   ```

If the push issue is persistent (e.g., branch protection rules you can't override):
```bash
curl -s -X POST http://api:8000/chats/<workload_chat_id>/resolve \
  -H 'Content-Type: application/json' \
  -H 'x-internal-key: team-agent-internal' \
  -d '{"outcome": "failed", "message": "Cannot push to <branch> — <reason>. Manual intervention needed."}'
```

## Worktree Creation Failure

The system couldn't create a git worktree for the workload, so the session never started.

1. `cd` to the **clone path**
2. Diagnose:
   ```bash
   git worktree list
   ls .git/worktrees/
   df -h .
   ```
3. Common fixes:
   - **Stale worktrees**: `git worktree prune` removes entries for deleted directories
   - **Locked worktree**: `rm .git/worktrees/<name>/locked`
   - **Corrupt refs**: `git gc --prune=now`
   - **Disk full**: free space or clean up old worktrees
   - **Branch already checked out**: remove the stale worktree that has the branch, then prune
4. Once the underlying issue is fixed, retry the workload:
   ```bash
   curl -s -X POST http://api:8000/chats/<workload_chat_id>/retry \
     -H 'x-internal-key: team-agent-internal'
   ```

The retry endpoint re-dispatches the workload from scratch — new worktree, new session.

## Relay Crash

The relay task (which forwards messages between the SDK and the chat) crashed unexpectedly. The traceback in your context message tells you what went wrong.

**If it looks transient** (network timeout, Redis disconnect, connection reset):
```bash
curl -s -X POST http://api:8000/chats/<workload_chat_id>/retry \
  -H 'x-internal-key: team-agent-internal'
```

**If it looks persistent** (code bug, missing dependency, corrupted state), report it so a human can investigate:
```bash
curl -s -X POST http://api:8000/chats/<workload_chat_id>/resolve \
  -H 'Content-Type: application/json' \
  -H 'x-internal-key: team-agent-internal' \
  -d '{"outcome": "failed", "message": "Relay crashed due to <root cause from traceback>. This appears to be a code-level issue, not a transient failure."}'
```

## Cancelled Workload Cleanup

The user cancelled a workload while you were investigating it. Clean up the git resources so they don't accumulate.

1. Remove the worktree (if a path was provided):
   ```bash
   git -C <clone_path> worktree remove <worktree_path> --force
   ```
2. Delete the local and remote branch (if provided):
   ```bash
   git -C <clone_path> branch -D <branch_name>
   git -C <clone_path> push origin --delete <branch_name>
   ```
3. Prune any stale worktree entries:
   ```bash
   git -C <clone_path> worktree prune
   ```

No API call needed — the workload is already cancelled.

## API Reference

| Endpoint | Method | Body | Effect |
|---|---|---|---|
| `/chats/{chat_id}/resolve` | POST | `{"outcome": "success"\|"failed", "message": "..."}` | Transitions workload to `needs_attention`, posts coordinator message to main chat |
| `/chats/{chat_id}/retry` | POST | (none) | Re-dispatches workload from scratch — new worktree, new session |

Both endpoints are on `http://api:8000` inside Docker. All requests require the `x-internal-key: team-agent-internal` header for authentication.
