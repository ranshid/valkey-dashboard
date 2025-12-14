import json
import os
from datetime import datetime, timezone
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
    return f"{d.isocalendar()[0]}-W{d.isocalendar()[1]}"  # "YYYY-Www"

# -------- Metric 1: Open PRs --------
open_prs = [pr for pr in pr_list if pr.get("closed_at") is None]
open_pr_count = len(open_prs)

# -------- Metric 2: Unassigned PRs --------
unassigned_prs = [pr for pr in open_prs if not pr.get("review_requests")]
unassigned_pr_count = len(unassigned_prs)

# -------- Metric 3: PR throughput (weekly) --------
created_weeks = defaultdict(int)
closed_weeks = defaultdict(int)
for pr in pr_list:
    if pr.get("created_at"):
        created_weeks[week_bucket(pr["created_at"])] += 1
    if pr.get("closed_at"):
        closed_weeks[week_bucket(pr["closed_at"])] += 1

# -------- Metric 4: PR staleness (hours) --------
stale_weekly = defaultdict(list)
stale_times_hours = []

for pr in pr_list:
    events = sorted(
        [e for e in pr.get("events", []) if e.get("created_at")],
        key=lambda e: parse_date(e["created_at"])
    )

    for i in range(1, len(events)):
        delta_hours = (parse_date(events[i]["created_at"]) - parse_date(events[i-1]["created_at"])).total_seconds() / 3600
        stale_times_hours.append(delta_hours)
        week = week_bucket(events[i]["created_at"])
        stale_weekly[week].append(delta_hours)

# Compute weekly P50, P99, P100
stale_weekly_metrics = {}
for week, values in stale_weekly.items():
    stale_weekly_metrics[week] = {
        "p50": np.percentile(values, 50),
        "p99": np.percentile(values, 99),
        "p100": np.max(values)
    }

# -------- Metric 5: PR response time (hours) --------
response_weekly = defaultdict(list)
response_times_hours = []

for pr in pr_list:
    valid_events = [e for e in pr.get("events", []) if e.get("created_at")]
    if valid_events and pr.get("created_at"):
        first_event_time = min(parse_date(e["created_at"]) for e in valid_events)
        delta_hours = (first_event_time - parse_date(pr["created_at"])).total_seconds() / 3600
        response_times_hours.append(delta_hours)
        week = week_bucket(pr["created_at"])
        response_weekly[week].append(delta_hours)

# Compute weekly P50, P99, P100 for response time
response_weekly_metrics = {}
for week, values in response_weekly.items():
    response_weekly_metrics[week] = {
        "p50": np.percentile(values, 50),
        "p99": np.percentile(values, 99),
        "p100": np.max(values)
    }

# -------- Top N most stale PRs --------
top_stale_prs = []

for pr in open_prs:
    events = [e for e in pr.get("events", []) if e.get("created_at")]
    last_event_time = max(parse_date(e["created_at"]) for e in events) if events else parse_date(pr["created_at"])
    delta_hours = (now - last_event_time).total_seconds() / 3600

    # Author
    author_field = pr.get("author")
    if isinstance(author_field, dict):
        author = author_field.get("login")
    else:
        author = author_field  # string or None

    # Reviewers
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

# Sort descending by staleness and take top N
top_stale_prs = sorted(top_stale_prs, key=lambda x: x["stale_hours"], reverse=True)[:TOP_STALE]

# -------- Build metrics dictionary --------
metrics = {
    "generated_at": now.isoformat(),
    "repo": data.get("repo"),
    "open_prs_count": open_pr_count,
    "unassigned_prs_count": unassigned_pr_count,
    "pr_creation_weekly": dict(created_weeks),
    "pr_close_weekly": dict(closed_weeks),
    "stale_times_hours": stale_times_hours,
    "stale_weekly_metrics": stale_weekly_metrics,
    "response_times_hours": response_times_hours,
    "response_weekly_metrics": response_weekly_metrics,
    "top_stale_prs": top_stale_prs
}

# -------- Save metrics --------
os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
    json.dump(metrics, f, indent=2)

print(f"Metrics written to {OUTPUT_PATH}")
print(f"Open PRs: {open_pr_count}, Unassigned PRs: {unassigned_pr_count}")
print(f"Top {TOP_STALE} most stale PRs included in metrics.json")
