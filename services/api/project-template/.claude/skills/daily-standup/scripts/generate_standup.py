#!/usr/bin/env python3
"""Generate hourly standup summaries for a single chat.

Called once per chat by the daily-standup skill. Fetches messages and tool
approvals, converts to dialogue-form markdown, groups into hourly windows,
summarises each window via the AI service, and appends results to the output
markdown file.

Usage:
    python generate_standup.py \
        --chat-id <uuid> \
        --date 2026-03-13 \
        --output docs/standup/2026-03-13.md \
        --chat-name "General" \
        --chat-type primary

Reads from environment:
    API_BASE_URL, AI_SERVICE_URL, INTERNAL_API_KEY, AGENT_MEMBER_ID, PROJECT_ID
"""

import argparse
import json
import os
import sys
import urllib.request
from collections import defaultdict
from datetime import datetime
from zoneinfo import ZoneInfo

DISPLAY_TZ = ZoneInfo("Australia/Sydney")


def env(name: str) -> str:
    val = os.environ.get(name)
    if not val:
        print(f"ERROR: {name} environment variable not set", file=sys.stderr)
        sys.exit(1)
    return val


def api_get(url: str, api_key: str) -> dict | list:
    req = urllib.request.Request(url, headers={"X-Internal-Key": api_key})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode())


def api_post(url: str, data: dict) -> dict:
    body = json.dumps(data).encode()
    req = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read().decode())


def extract_text_from_content(content_str: str) -> str:
    """Convert structured message content to readable dialogue text.

    Follows the same pattern as escalation.py — extracts text blocks,
    labels tool uses and tool results.
    """
    try:
        data = json.loads(content_str)
        if isinstance(data, dict) and "blocks" in data:
            parts = []
            for block in data["blocks"]:
                block_type = block.get("type", "")
                if block_type == "text":
                    parts.append(block.get("value", ""))
                elif block_type == "tool_use":
                    parts.append(f"[Tool: {block.get('name', '?')}]")
                elif block_type == "tool_result":
                    parts.append("[Tool result]")
                elif block_type == "thinking":
                    pass  # skip internal thinking
                elif block_type == "mention":
                    parts.append(f"@{block.get('display_name', '?')}")
                elif block_type == "skill":
                    parts.append(f"/{block.get('name', '?')}")
            return "\n".join(parts) if parts else content_str
    except (json.JSONDecodeError, TypeError):
        pass
    return content_str


def parse_timestamp(ts: str) -> datetime:
    """Parse an ISO timestamp and convert to AEST (Australia/Sydney)."""
    ts = ts.replace("Z", "+00:00")
    return datetime.fromisoformat(ts).astimezone(DISPLAY_TZ)


def hour_key(ts: str) -> str:
    """Return the hour bucket in AEST, e.g. '09:00'."""
    dt = parse_timestamp(ts)
    return f"{dt.hour:02d}:00"


def hour_end(hk: str) -> str:
    """Return the end of the hour, e.g. '09:00' → '10:00'."""
    h = int(hk.split(":")[0])
    return f"{(h + 1) % 24:02d}:00"


def build_dialogue(messages: list, approvals: list, target_date: str) -> dict[str, list[str]]:
    """Build hourly dialogue buckets from messages and approvals.

    Returns a dict mapping hour keys to lists of dialogue lines.
    """
    buckets: dict[str, list[str]] = defaultdict(list)

    # Combine messages and approvals into a single timeline
    timeline = []

    for msg in messages:
        created = msg.get("created_at", "")
        if not created:
            continue
        ts = parse_timestamp(created)
        if ts.strftime("%Y-%m-%d") != target_date:
            continue
        name = msg.get("display_name", "Unknown")
        msg_type = msg.get("type", "")
        content = extract_text_from_content(msg.get("content", ""))
        time_str = f"{ts.hour:02d}:{ts.minute:02d}"
        line = f"**{name}** ({msg_type}) — {time_str}\n{content}"
        timeline.append((created, line))

    for appr in approvals:
        created = appr.get("created_at", "")
        user_name = appr.get("user_name", "Unknown")
        tool_name = appr.get("tool_name", "?")
        decision = appr.get("decision", "?")
        reason = appr.get("reason")
        ts = parse_timestamp(created)
        time_str = f"{ts.hour:02d}:{ts.minute:02d}"

        if "deny" in decision.lower() and reason:
            line = f"**{user_name}** denied {tool_name} — {time_str}: \"{reason}\""
        elif "deny" in decision.lower():
            line = f"**{user_name}** denied {tool_name} — {time_str}"
        else:
            line = f"**{user_name}** approved {tool_name} — {time_str}"
        timeline.append((created, line))

    # Sort by timestamp and bucket into hours
    timeline.sort(key=lambda x: x[0])
    for created, line in timeline:
        hk = hour_key(created)
        buckets[hk].append(line)

    return dict(buckets)


def main():
    parser = argparse.ArgumentParser(description="Generate standup summaries for one chat")
    parser.add_argument("--chat-id", required=True)
    parser.add_argument("--date", required=True, help="ISO date, e.g. 2026-03-13")
    parser.add_argument("--output", required=True, help="Path to output markdown file")
    parser.add_argument("--chat-name", required=True)
    parser.add_argument("--chat-type", required=True)
    args = parser.parse_args()

    api_base = env("API_BASE_URL")
    ai_service = env("AI_SERVICE_URL")
    api_key = env("INTERNAL_API_KEY")
    member_id = env("AGENT_MEMBER_ID")
    project_id = env("PROJECT_ID")

    # 1. Fetch messages (existing endpoint)
    messages = api_get(
        f"{api_base}/chats/{args.chat_id}/messages",
        api_key,
    )

    # 2. Fetch tool approvals
    approvals = api_get(
        f"{api_base}/chats/{args.chat_id}/tool-approvals?date={args.date}",
        api_key,
    )

    # 3. Build hourly dialogue buckets
    buckets = build_dialogue(messages, approvals, args.date)

    if not buckets:
        print(f"No activity on {args.date} for {args.chat_name}")
        return

    # 4. Summarise each hour via AI service
    sorted_hours = sorted(buckets.keys())
    summaries = []

    for hk in sorted_hours:
        lines = buckets[hk]
        dialogue_text = "\n\n".join(lines)
        context = f"Chat: {args.chat_name} ({args.chat_type}), Hour: {hk}–{hour_end(hk)}"

        result = api_post(
            f"{ai_service}/summarise",
            {
                "text": dialogue_text,
                "context": context,
                "member_id": member_id,
                "project_id": project_id,
            },
        )
        summaries.append((hk, result.get("summary", "")))

    # 5. Append to output markdown file
    os.makedirs(os.path.dirname(args.output), exist_ok=True)

    with open(args.output, "a") as f:
        f.write(f"\n## {args.chat_name}\n\n")
        for hk, summary in summaries:
            f.write(f"### {hk}–{hour_end(hk)}\n\n")
            f.write(f"{summary}\n\n")

    print(f"Wrote {len(summaries)} hourly summaries for {args.chat_name}")


if __name__ == "__main__":
    main()
