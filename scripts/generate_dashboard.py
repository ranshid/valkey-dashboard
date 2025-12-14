import os
import json
import requests
from datetime import datetime, timedelta, timezone
from dateutil.parser import parse as parse_date

# -------- Configuration --------
TOKEN = os.getenv("GITHUB_TOKEN")
TARGET_REPO = os.getenv("TARGET_REPOSITORY") or os.getenv("GITHUB_REPOSITORY")
MONTHS_BACK = 24
OUT_PATH = "docs/data.json"

if not TOKEN or not TARGET_REPO:
    raise SystemExit("GITHUB_TOKEN and TARGET_REPOSITORY must be set")

# -------- GraphQL Setup --------
API_URL = "https://api.github.com/graphql"
HEADERS = {"Authorization": f"Bearer {TOKEN}"}

# -------- Helper functions --------
def run_query(query, variables):
    resp = requests.post(API_URL, json={"query": query, "variables": variables}, headers=HEADERS)
    if resp.status_code != 200:
        raise Exception(f"HTTP error {resp.status_code}: {resp.text}")
    result = resp.json()
    if "data" not in result:
        print("GraphQL response did not contain 'data':")
        print(json.dumps(result, indent=2))
        raise Exception("GraphQL query failed or returned errors")
    return result

def iso(dt):
    if isinstance(dt, str):
        return dt
    return dt.isoformat()

# -------- GraphQL Query (without filterBy) --------
PR_QUERY = """
query($owner: String!, $name: String!, $after: String) {
  repository(owner: $owner, name: $name) {
    pullRequests(
      first: 100
      after: $after
      orderBy: {field: CREATED_AT, direction: DESC}
      states: [OPEN, CLOSED, MERGED]
    ) {
      pageInfo { hasNextPage, endCursor }
      nodes {
        number
        title
        url
        author { login }
        createdAt
        updatedAt
        closedAt
        merged
        reviewRequests(first: 10) { nodes { requestedReviewer { ... on User { login } ... on Team { name } } } }
        comments(first: 50) { nodes { author { login } createdAt } }
        reviews(first: 50) { nodes { author { login } submittedAt state } }
      }
    }
  }
}
"""

# -------- Fetch PRs in last N months --------
owner, name = TARGET_REPO.split("/")
since_dt = datetime.now(timezone.utc) - timedelta(days=MONTHS_BACK*30)

all_prs = []
after_cursor = None

while True:
    variables = {"owner": owner, "name": name, "after": after_cursor}
    result = run_query(PR_QUERY, variables)
    prs = result["data"]["repository"]["pullRequests"]["nodes"]

    if not prs:
        break

    # Keep only PRs within the time window
    for pr in prs:
        if parse_date(pr["createdAt"]) >= since_dt:
            all_prs.append(pr)

    # Check if we need to continue pagination
    page_info = result["data"]["repository"]["pullRequests"]["pageInfo"]
    if not page_info["hasNextPage"] or all(parse_date(pr["createdAt"]) < since_dt for pr in prs):
        break
    after_cursor = page_info["endCursor"]

print(f"Collected {len(all_prs)} PRs from {TARGET_REPO} since {since_dt.isoformat()}")

# -------- Transform data for dashboard --------
output = {
    "repo": TARGET_REPO,
    "generated_at": datetime.now(timezone.utc).isoformat(),
    "pull_requests": []
}

for pr in all_prs:
    events = []

    # Issue comments
    for c in pr.get("comments", {}).get("nodes", []):
        events.append({
            "type": "comment",
            "author": c["author"]["login"] if c["author"] else None,
            "created_at": c["createdAt"]
        })

    # Reviews
    for r in pr.get("reviews", {}).get("nodes", []):
        events.append({
            "type": "review",
            "author": r["author"]["login"] if r["author"] else None,
            "state": r["state"],
            "created_at": r["submittedAt"]
        })

    # Review requests
    reviewers = []
    for rr in pr.get("reviewRequests", {}).get("nodes", []):
        reviewer = rr.get("requestedReviewer")
        if reviewer:
            reviewers.append(reviewer.get("login") or reviewer.get("name"))

    output["pull_requests"].append({
        "number": pr["number"],
        "title": pr["title"],
        "author": pr["author"]["login"] if pr["author"] else None,
        "created_at": pr["createdAt"],
        "updated_at": pr["updatedAt"],
        "closed_at": pr["closedAt"],
        "merged": pr["merged"],
        "html_url": pr["url"],
        "review_requests": reviewers,
        "events": events
    })

# -------- Save JSON --------
os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
with open(OUT_PATH, "w", encoding="utf-8") as f:
    json.dump(output, f, indent=2)

print(f"Wrote {OUT_PATH}")
