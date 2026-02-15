#!/bin/bash

# Claude Code Custom Status Line — Auto-Compact Awareness
#
# Shows: model, directory, git branch, context usage %, tokens, and cost.
#
# SETUP:
#   1. Copy this script to ~/.claude/statusline-autocompact.sh
#   2. Make it executable: chmod +x ~/.claude/statusline-autocompact.sh
#   3. Add to ~/.claude/settings.json:
#      {
#        "statusLine": {
#          "type": "command",
#          "command": "~/.claude/statusline-autocompact.sh"
#        }
#      }
#   4. Restart Claude Code
#
# REQUIRES: jq (brew install jq / apt install jq)

# Read JSON input from stdin
input=$(cat)

# Extract basic info
model=$(echo "$input" | jq -r '.model.display_name')
model_id=$(echo "$input" | jq -r '.model.id')
dir=$(echo "$input" | jq -r '.workspace.current_dir')
in_tok=$(echo "$input" | jq -r '.context_window.total_input_tokens // 0')
out_tok=$(echo "$input" | jq -r '.context_window.total_output_tokens // 0')

# Calculate auto-compact trigger percentage
# Matches the internal auto-compact calculation:
#   effectiveWindow = total - min(maxOutputTokens, 20000)
#   autoCompactThreshold = effectiveWindow - 13000
#   percentLeft = (autoCompactThreshold - currentUsage) / autoCompactThreshold * 100

total=$(echo "$input" | jq -r '.context_window.context_window_size // 0')
# current_usage.input_tokens only counts non-cached tokens, which is nearly 0 with prompt caching.
# The real context size = input_tokens + cache_creation_input_tokens + cache_read_input_tokens
current_usage=$(echo "$input" | jq -r '
  .context_window.current_usage //empty |
  ((.input_tokens // 0) + (.cache_creation_input_tokens // 0) + (.cache_read_input_tokens // 0))
' 2>/dev/null)
current_usage=${current_usage:-0}

if [ "$total" -gt 0 ] && [ "$current_usage" -gt 0 ]; then
  # effectiveWindow = total - 20000 (output token reserve, capped at 20k)
  # autoCompactThreshold = effectiveWindow - 13000 = total - 33000
  autoCompactThreshold=$((total - 33000))

  if [ "$autoCompactThreshold" -gt 0 ]; then
    percentLeft=$(awk "BEGIN {printf \"%.0f\", (($autoCompactThreshold - $current_usage) / $autoCompactThreshold * 100)}")
    if [ "$percentLeft" -lt 0 ]; then
      percentLeft=0
    elif [ "$percentLeft" -gt 100 ]; then
      percentLeft=100
    fi
  else
    percentLeft=""
  fi
else
  percentLeft=""
fi

# Git branch
branch=$(cd "$dir" 2>/dev/null && git --no-optional-locks branch --show-current 2>/dev/null || echo '')
if [ -n "$branch" ] && ! git -C "$dir" --no-optional-locks diff-index --quiet HEAD -- 2>/dev/null; then
  branch="${branch}*"
fi

# Cost estimate
case "$model_id" in
  *opus-4*) in_price=5; out_price=25;;
  *sonnet-4*) in_price=3; out_price=15;;
  *) in_price=0; out_price=0;;
esac

if [ "$in_price" -gt 0 ]; then
  cost=$(awk "BEGIN {printf \"%.4f\", ($in_tok * $in_price + $out_tok * $out_price) / 1000000}")
else
  cost="0.0000"
fi

# Build status line
status=$(printf '\033[36m%s\033[0m \033[32m%s\033[0m' "$model" "$(basename "$dir")")

[ -n "$branch" ] && status="${status} $(printf '\033[35m(%s)\033[0m' "$branch")"

# Context % to compact with colour coding
if [ -n "$percentLeft" ]; then
  if [ "$percentLeft" -lt 20 ]; then
    status="${status} $(printf '\033[31m%s%% to compact\033[0m' "$percentLeft")"
  elif [ "$percentLeft" -lt 50 ]; then
    status="${status} $(printf '\033[33m%s%% to compact\033[0m' "$percentLeft")"
  else
    status="${status} $(printf '\033[34m%s%% to compact\033[0m' "$percentLeft")"
  fi
fi

status="${status} $(printf '\033[93m%s\xe2\x86\x92%s\033[0m' "$in_tok" "$out_tok")"
status="${status} $(printf '\033[92m$%s\033[0m' "$cost")"

echo "$status"
