from github import Github
import os, json
from datetime import datetime, timezone

OUT = "docs/data.json"

def iso(dt):
    return dt.isoformat() if dt else None

def main():
    token = os.getenv("GITHUB_TOKEN")
    repo_full = os.getenv("GITHUB_REPOSITORY")
    if not token or not repo_full:
        raise SystemExit("GITHUB_TOKEN and GITHUB_REPOSITORY required")

    gh = Github(token)
    repo = gh.get_repo(repo_full)
    pulls = repo.get_pulls(state="all")

    data = {
        "repo": repo_full,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "pull_requests": []
    }

    for pr in pulls:
        pr_data = {
            "number": pr.number,
            "title": pr.title,
            "author": pr.user.login,
            "created_at": iso(pr.created_at),
            "updated_at": iso(pr.updated_at),
            "closed_at": iso(pr.closed_at),
            "merged": pr.is_merged(),
            "html_url": pr.html_url,
            "review_requests": [r.login for r in pr.get_review_requests()[0]],
            "events": []
        }

        # Issue comments
        for c in pr.get_issue_comments():
            pr_data["events"].append({
                "type": "comment",
                "author": c.user.login,
                "created_at": iso(c.created_at)
            })

        # Reviews
        for r in pr.get_reviews():
            pr_data["events"].append({
                "type": "review",
                "author": r.user.login,
                "state": r.state,
                "created_at": iso(r.submitted_at)
            })

        data["pull_requests"].append(pr_data)

    with open(OUT, "w") as f:
        json.dump(data, f, indent=2)

    print(f"Wrote {OUT}")

if __name__ == "__main__":
    main()
