import json
from datetime import datetime, timedelta
import matplotlib.pyplot as plt
import pandas as pd
import os

# -------- Configuration --------
METRICS_PATH = "docs/metrics.json"
OUTPUT_DIR = "docs/plots"
YEARS_BACK = 3
TOP_N_STALE = 10  # number of top stale PRs to plot

# -------- Load metrics --------
with open(METRICS_PATH) as f:
    metrics = json.load(f)

# -------- Helper: convert week dict to pandas Series --------
def series_from_week_dict(week_dict):
    data = {}
    for week_str, value in week_dict.items():
        year, w = map(int, week_str.split("-W"))
        dt = datetime.fromisocalendar(year, w, 1)  # Monday of the week
        data[dt] = value
    s = pd.Series(data).sort_index()
    return s

os.makedirs(OUTPUT_DIR, exist_ok=True)
cutoff = datetime.now() - timedelta(days=YEARS_BACK*365)

# -------- 1: PR Creation per week --------
pr_creation_series = series_from_week_dict(metrics["pr_creation_weekly"])
pr_creation_series = pr_creation_series[pr_creation_series.index >= cutoff]

plt.figure(figsize=(14,5))
plt.plot(pr_creation_series.index, pr_creation_series.values, label="PRs Created")
plt.title("PR Creation per Week")
plt.xlabel("Week")
plt.ylabel("Number of PRs")
plt.grid(True)
plt.tight_layout()
plt.savefig(os.path.join(OUTPUT_DIR, "pr_creation_per_week.png"))
plt.close()

# -------- 2: PR Closed per week --------
pr_close_series = series_from_week_dict(metrics["pr_close_weekly"])
pr_close_series = pr_close_series[pr_close_series.index >= cutoff]

plt.figure(figsize=(14,5))
plt.plot(pr_close_series.index, pr_close_series.values, label="PRs Closed", color="orange")
plt.title("PR Closed per Week")
plt.xlabel("Week")
plt.ylabel("Number of PRs")
plt.grid(True)
plt.tight_layout()
plt.savefig(os.path.join(OUTPUT_DIR, "pr_closed_per_week.png"))
plt.close()

# -------- 3: Staleness P50, p95, P100 per week --------
stale_df = pd.DataFrame(metrics["stale_weekly_metrics"]).T
stale_df.index = [datetime.fromisocalendar(int(w.split("-W")[0]), int(w.split("-W")[1]), 1)
                  for w in stale_df.index]
stale_df = stale_df[stale_df.index >= cutoff]

plt.figure(figsize=(14,5))
plt.plot(stale_df.index, stale_df["p50"], label="P50")
plt.plot(stale_df.index, stale_df["p95"], label="P95")
plt.plot(stale_df.index, stale_df["p100"], label="P100")
plt.title("PR Staleness (hours) per Week")
plt.xlabel("Week")
plt.ylabel("Staleness Hours")
plt.legend()
plt.grid(True)
plt.tight_layout()
plt.savefig(os.path.join(OUTPUT_DIR, "staleness_per_week.png"))
plt.close()

# -------- 4: Response Time P50, p95, P100 per week --------
resp_df = pd.DataFrame(metrics["response_weekly_metrics"]).T
resp_df.index = [datetime.fromisocalendar(int(w.split("-W")[0]), int(w.split("-W")[1]), 1)
                 for w in resp_df.index]
resp_df = resp_df[resp_df.index >= cutoff]

plt.figure(figsize=(14,5))
plt.plot(resp_df.index, resp_df["p50"], label="P50")
plt.plot(resp_df.index, resp_df["p95"], label="P95")
plt.plot(resp_df.index, resp_df["p100"], label="P100")
plt.title("PR Response Time (hours) per Week")
plt.xlabel("Week")
plt.ylabel("Response Time Hours")
plt.legend()
plt.grid(True)
plt.tight_layout()
plt.savefig(os.path.join(OUTPUT_DIR, "response_time_per_week.png"))
plt.close()

# -------- 5: Top N Most Stale PRs --------
top_stale_prs = metrics.get("top_stale_prs", [])[:TOP_N_STALE]
if top_stale_prs:
    labels = [f"#{pr['number']} {pr['title']}" for pr in top_stale_prs]
    stale_hours = [pr['stale_hours'] for pr in top_stale_prs]

    plt.figure(figsize=(12,6))
    plt.barh(labels[::-1], stale_hours[::-1], color="salmon")  # largest on top
    plt.xlabel("Stale Hours")
    plt.title(f"Top {len(top_stale_prs)} Most Stale PRs")
    plt.tight_layout()
    plt.savefig(os.path.join(OUTPUT_DIR, "top_stale_prs.png"))
    plt.close()

print(f"All plots saved in {OUTPUT_DIR}")
