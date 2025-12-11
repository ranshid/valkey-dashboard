#!/usr/bin/env python3
# scripts/generate_dashboard.py
from github import Github
import os, json
from datetime import datetime, timezone

# Configuration
STALE_DAYS = int(os.getenv("STALE_DAYS", "7"))  # threshold to call PR 'stale'
OUT_PATH = "docs/data.json"

def iso_now():
    return datetime.now(timezone.utc).isoformat()

def main():
    token = os.getenv("GITHUB_TOKEN")
    repo_full = os.getenv("GITHUB_REPOSITORY")
    if not token or not repo_full:
        raise SystemExit("GITHUB_TOKEN and GITHUB_REPOSITORY must be set in environment.")

    gh = Github(token)
    repo = gh.get_repo(repo_full)

    pulls = list(repo.get_pulls(state="open", sort="created", direction="asc"))
    now = datetime.now(timezone.utc)
    stale = []
    response_hours = []

    for pr in pulls:
        # Use last updated time as proxy for responsiveness (includes comments, commits, reviews)
        last_updated = pr.updated_at.replace(tzinfo=timezone.utc)
        created = pr.created_at.replace(tzinfo=timezone.utc)

        hours_since_update = (now - last_updated).total_seconds() / 3600.0
        days_open = (now - created).days

        pr_info = {
            "number": pr.number,
            "title": pr.title,
            "html_url": pr.html_url,
            "created_at": created.isoformat(),
            "last_updated_at": last_updated.isoformat(),
            "days_open": days_open,
            "last_updated_hours": round(hours_since_update, 1)
        }
        response_hours.append(hours_since_update)
        if days_open >= STALE_DAYS:
            stale.append(pr_info)

    mean_response = round(sum(response_hours)/len(response_hours), 2) if response_hours else None

    output = {
        "repo": repo_full,
        "generated_at": iso_now(),
        "total_open_prs": len(pulls),
        "mean_response_hours": mean_response,
        "stale_threshold_days": STALE_DAYS,
        "stale_prs": sorted(stale, key=lambda p: p["days_open"], reverse=True)
    }

    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2)

    print("Wrote", OUT_PATH)

if __name__ == "__main__":
    main()

