import json
import os
from datetime import datetime, timezone, timedelta
from dateutil.parser import parse as parse_date
from collections import defaultdict
import numpy as np

# -------- Configuration --------
DATA_JSON_PATH = "docs/data.json"
OUTPUT_PATH = "docs/metrics.json"
TOP_STALE = 10  # number of top stale PRs to include

# -------- Load data --------
with open(DATA_JSON_PATH, encoding="utf-8") as f:
    data = json.load(f)

pr_list = data.get("pull_requests", [])
now = datetime.now(timezone.utc)

# -------- Helper: week bucket --------
def week_bucket(dt_str):
    d = parse_date(dt_str)
    year, week, _ = d.isocalendar()
    return f"{year}-W{week:02d}"  # YYYY-Www (zero-padded)

def week_to_date(week_str):
    year, week = week_str.split("-W")
    return datetime.fromisocalendar(int(year), int(week), 1).replace(tzinfo=timezone.utc)

def date_to_week(d):
    year, week, _ = d.isocalendar()
    return f"{year}-W{week:02d}"

# -------- Metric 1: Open PRs --------
open_prs = [pr for pr in pr_list if pr.get("closed_at") is None]
open_pr_count = len(open_prs)

# -------- Metric 2: Unassigned PRs --------
unassigned_prs = [pr for pr in open_prs if not pr.get("review_requests")]
unassigned_pr_count = len(unassigned_prs)

# -------- Metric 3: PR throughput (weekly) --------
created_weeks = defaultdict(int)
closed_weeks = defaultdict(int)
all_week_dates = []

for pr in pr_list:
    if pr.get("created_at"):
        w = week_bucket(pr["created_at"])
        created_weeks[w] += 1
        all_week_dates.append(week_to_date(w))
    if pr.get("closed_at"):
        w = week_bucket(pr["closed_at"])
        closed_weeks[w] += 1
        all_week_dates.append(week_to_date(w))

# -------- Metric 4: PR staleness (hours), distributed across weeks --------
stale_weekly = defaultdict(list)
stale_times_hours = []

for pr in pr_list:
    # Include creation as first event
    events = []
    if pr.get("created_at"):
        events.append({"created_at": pr["created_at"]})
    events += [e for e in pr.get("events", []) if e.get("created_at")]
    events = sorted(events, key=lambda e: parse_date(e["created_at"]))

    for i in range(1, len(events)):
        start_dt = parse_date(events[i-1]["created_at"])
        end_dt = parse_date(events[i]["created_at"])
        delta_hours = (end_dt - start_dt).total_seconds() / 3600
        stale_times_hours.append(delta_hours)

        # Split delta across all weeks spanned
        current_dt = start_dt
        while current_dt < end_dt:
            week_label = date_to_week(current_dt)
            # End of this ISO week
            week_end = current_dt + timedelta(days=7 - current_dt.weekday())
            segment_end = min(week_end, end_dt)
            segment_hours = (segment_end - start_dt).total_seconds() / 3600
            stale_weekly[week_label].append(segment_hours)
            all_week_dates.append(current_dt)
            current_dt = segment_end

stale_weekly_metrics = {}
for week, values in stale_weekly.items():
    stale_weekly_metrics[week] = {
        "p50": float(np.percentile(values, 50)),
        "p90": float(np.percentile(values, 90)),
        "p100": float(np.max(values))
    }

# -------- Metric 5: PR response time (hours) --------
response_weekly = defaultdict(list)

for pr in pr_list:
    valid_events = [e for e in pr.get("events", []) if e.get("created_at")]
    if valid_events and pr.get("created_at"):
        first_event_time = min(parse_date(e["created_at"]) for e in valid_events)
        delta_hours = (first_event_time - parse_date(pr["created_at"])).total_seconds() / 3600
        w = week_bucket(pr["created_at"])
        response_weekly[w].append(delta_hours)
        all_week_dates.append(week_to_date(w))

response_weekly_metrics = {}
for week, values in response_weekly.items():
    response_weekly_metrics[week] = {
        "p50": float(np.percentile(values, 50)),
        "p90": float(np.percentile(values, 90)),
        "p100": float(np.max(values))
    }

# -------- Metric 6: Weekly Open PRs (P100) --------
weekly_open_counts = defaultdict(int)
all_weeks_set = set()

for pr in pr_list:
    if not pr.get("created_at"):
        continue
    created_dt = parse_date(pr["created_at"])
    closed_dt = parse_date(pr["closed_at"]) if pr.get("closed_at") else now

    current_dt = created_dt
    while current_dt <= closed_dt:
        week = date_to_week(current_dt)
        weekly_open_counts[week] += 1
        all_weeks_set.add(week)
        current_dt += timedelta(days=7)

all_weeks = sorted(all_weeks_set)
weekly_open_counts_full = {week: weekly_open_counts.get(week, 0) for week in all_weeks}

# -------- Metric 7: First Interaction Staleness (weekly snapshot) --------
first_interaction_staleness_weekly = defaultdict(list)

for pr in pr_list:
    if not pr.get("created_at"):
        continue

    created_dt = parse_date(pr["created_at"])

    # Find first review event (if any)
    review_events = [
        e for e in pr.get("events", [])
        if e.get("created_at") and e.get("type") == "review"
    ]

    first_review_dt = (
        min(parse_date(e["created_at"]) for e in review_events)
        if review_events else None
    )

    # PR contributes until first review or now
    end_dt = first_review_dt if first_review_dt else now

    # Walk week by week
    current_week_start = week_to_date(date_to_week(created_dt))
    while current_week_start <= end_dt:
        week_end = min(
            current_week_start + timedelta(days=7),
            end_dt
        )

        # staleness = how long PR has existed by end of this week
        staleness_hours = (week_end - created_dt).total_seconds() / 3600

        week_label = date_to_week(current_week_start)
        first_interaction_staleness_weekly[week_label].append(staleness_hours)
        all_week_dates.append(current_week_start)

        current_week_start += timedelta(weeks=1)

first_interaction_staleness_weekly_metrics = {}
for week, values in first_interaction_staleness_weekly.items():
    first_interaction_staleness_weekly_metrics[week] = {
        "p50": float(np.percentile(values, 50)),
        "p90": float(np.percentile(values, 90)),
        "p100": float(np.max(values))
    }

# -------- Fill missing weeks with zeros --------
if all_week_dates:
    start = min(all_week_dates)
    end = max(all_week_dates)

    current = start
    while current <= end:
        w = date_to_week(current)

        created_weeks.setdefault(w, 0)
        closed_weeks.setdefault(w, 0)
        weekly_open_counts_full.setdefault(w, 0)

        stale_weekly_metrics.setdefault(w, {"p50": 0, "p90": 0, "p100": 0})
        response_weekly_metrics.setdefault(w, {"p50": 0, "p90": 0, "p100": 0})
        first_interaction_staleness_weekly_metrics.setdefault(w, {"p50": 0, "p90": 0, "p100": 0})

        current += timedelta(weeks=1)

# -------- Top N most stale PRs --------
top_stale_prs = []

for pr in open_prs:
    events = [e for e in pr.get("events", []) if e.get("created_at")]
    last_event_time = max(parse_date(e["created_at"]) for e in events) if events else parse_date(pr["created_at"])
    delta_hours = (now - last_event_time).total_seconds() / 3600

    author_field = pr.get("author")
    author = author_field.get("login") if isinstance(author_field, dict) else author_field

    reviewers = []
    if pr.get("review_requests"):
        reviewers = [r if isinstance(r, str) else r.get("login") for r in pr["review_requests"]]

    top_stale_prs.append({
        "number": pr["number"],
        "title": pr.get("title"),
        "author": author,
        "reviewers": reviewers,
        "created_at": pr.get("created_at"),
        "last_event_at": last_event_time.isoformat(),
        "stale_hours": delta_hours,
        "url": f"https://github.com/{data['repo']}/pull/{pr['number']}"
    })

top_stale_prs = sorted(top_stale_prs, key=lambda x: x["stale_hours"], reverse=True)[:TOP_STALE]

# -------- Build metrics dictionary --------
metrics = {
    "generated_at": now.isoformat(),
    "repo": data.get("repo"),
    "open_prs_count": open_pr_count,
    "unassigned_prs_count": unassigned_pr_count,
    "pr_creation_weekly": dict(sorted(created_weeks.items())),
    "pr_close_weekly": dict(sorted(closed_weeks.items())),
    "weekly_open_prs": weekly_open_counts_full,
    "stale_times_hours": stale_times_hours,
    "stale_weekly_metrics": dict(sorted(stale_weekly_metrics.items())),
    "response_weekly_metrics": dict(sorted(response_weekly_metrics.items())),
    "first_interaction_weekly_metrics": dict(sorted(first_interaction_staleness_weekly_metrics.items())),
    "top_stale_prs": top_stale_prs
}

# -------- Save metrics --------
os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
    json.dump(metrics, f, indent=2)

print(f"Metrics written to {OUTPUT_PATH}")
print(f"Open PRs: {open_pr_count}, Unassigned PRs: {unassigned_pr_count}")
print(f"Top {TOP_STALE} most stale PRs included in metrics.json")
