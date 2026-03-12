"""Generate forecast.json with daily granularity.

Usage:
    uv run python .claude/skills/create-forecast/scripts/generate_forecast.py --input '<json>'

The input JSON has:
    start_date: ISO date string (Monday)
    weeks: number of weeks
    humans: [{ name, state, days_per_week, leave: [[start, end], ...] }]
    agents: [name, ...]
    output_path: path to write forecast.json (default: docs/governance/forecast.json)

days_per_week determines which days a person works. 5 = Mon-Fri, 3 = Mon-Wed,
2.5 = Mon-Tue full + Wed half. Days are assigned from Monday forward.
"""

import argparse
import json
from datetime import date, timedelta

import holidays


def parse_date(s: str) -> date:
    return date.fromisoformat(s)


def build_weekdays(start: date, weeks: int) -> list[date]:
    """Return all weekdays (Mon-Fri) across the forecast period."""
    days = []
    for i in range(weeks * 7):
        d = start + timedelta(days=i)
        if d.weekday() < 5:
            days.append(d)
    return days


def day_hours(weekday: int, days_per_week: float) -> float:
    """Hours for a given weekday (0=Mon) based on days_per_week.

    3 days/week = Mon(7.5), Tue(7.5), Wed(7.5), Thu(0), Fri(0).
    2.5 days/week = Mon(7.5), Tue(7.5), Wed(3.75), Thu(0), Fri(0).
    """
    full_days = int(days_per_week)
    remainder = days_per_week - full_days

    if weekday < full_days:
        return 7.5
    elif weekday == full_days and remainder > 0:
        return round(7.5 * remainder, 2)
    else:
        return 0.0


def is_on_leave(d: date, leave_ranges: list[list[str]]) -> bool:
    for start_str, end_str in leave_ranges:
        if parse_date(start_str) <= d <= parse_date(end_str):
            return True
    return False


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, help="JSON input string")
    args = parser.parse_args()

    config = json.loads(args.input)
    start = parse_date(config["start_date"])
    weeks = config["weeks"]
    humans = config["humans"]
    agents = config["agents"]
    output_path = config.get("output_path", "docs/governance/forecast.json")

    weekdays = build_weekdays(start, weeks)

    # Build holiday calendars per state
    years = sorted({d.year for d in weekdays})
    state_holidays: dict[str, holidays.HolidayBase] = {}
    for h in humans:
        state = h["state"]
        if state not in state_holidays:
            state_holidays[state] = holidays.AU(subdiv=state, years=years)

    # Calculate daily forecast for each human
    human_dailies: dict[str, dict[str, float]] = {}
    for h in humans:
        name = h["name"]
        state = h["state"]
        dpw = h["days_per_week"]
        leave = h.get("leave", [])
        hols = state_holidays[state]

        daily = {}
        for d in weekdays:
            base = day_hours(d.weekday(), dpw)
            if base == 0:
                daily[d.isoformat()] = 0.0
            elif d in hols:
                daily[d.isoformat()] = 0.0
            elif is_on_leave(d, leave):
                daily[d.isoformat()] = 0.0
            else:
                daily[d.isoformat()] = base
        human_dailies[name] = daily

    # For agents: active on days where at least one human is working
    agent_dailies: dict[str, dict[str, float]] = {}
    for agent_name in agents:
        daily = {}
        for d in weekdays:
            iso = d.isoformat()
            any_human_working = any(
                human_dailies[h["name"]].get(iso, 0) > 0 for h in humans
            )
            daily[iso] = 100.0 if any_human_working else 0.0
        agent_dailies[agent_name] = daily

    # Combine into forecast.json
    members = {}
    for name, daily in human_dailies.items():
        members[name] = {"daily": daily}
    for name, daily in agent_dailies.items():
        members[name] = {"daily": daily}

    forecast = {
        "start_date": start.isoformat(),
        "weeks": weeks,
        "members": members,
    }

    with open(output_path, "w") as f:
        json.dump(forecast, f, indent=2)

    # Print summary
    print(f"\nForecast written to {output_path}")
    print(f"Period: {start.isoformat()} — {weeks} weeks")
    print()

    # Weekly summary table
    print(f"{'Member':<20} ", end="")
    for w in range(weeks):
        print(f"{'W' + str(w + 1):>8}", end="")
    print(f"{'Total':>10}")
    print("-" * (20 + 8 * weeks + 10))

    all_members = [(h["name"], "human") for h in humans] + [
        (a, "agent") for a in agents
    ]
    for name, mtype in all_members:
        daily = members[name]["daily"]
        print(f"{name:<20} ", end="")
        total = 0.0
        for w in range(weeks):
            week_start = start + timedelta(weeks=w)
            week_total = 0.0
            for di in range(5):
                d = week_start + timedelta(days=di)
                if d.weekday() < 5:
                    week_total += daily.get(d.isoformat(), 0)
            total += week_total
            if mtype == "human":
                print(f"{week_total:>7.1f}h", end="")
            else:
                print(f"  ${week_total:>5.0f}", end="")
        if mtype == "human":
            print(f"{total:>9.1f}h")
        else:
            print(f"  ${total:>6.0f}")

    # Public holiday summary
    print("\nPublic holidays in period:")
    shown = set()
    for h in humans:
        hols = state_holidays[h["state"]]
        for d in weekdays:
            if d in hols:
                key = (d, h["state"])
                if key not in shown:
                    shown.add(key)
                    print(f"  {d.isoformat()} ({h['state']}): {hols.get(d)}")

    # Leave summary
    any_leave = False
    for h in humans:
        for leave_start, leave_end in h.get("leave", []):
            if not any_leave:
                print("\nPlanned leave:")
                any_leave = True
            print(f"  {h['name']}: {leave_start} to {leave_end}")
    if not any_leave:
        print("\nNo planned leave.")


if __name__ == "__main__":
    main()
