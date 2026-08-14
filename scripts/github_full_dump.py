"""
GitHub repo dump, adapted to run as a single bounded chunk inside a GitHub
Actions job (triggered hourly by the accompanying workflow).

Each run:
  - reads checkpoint.txt for the last repo ID processed
  - fetches pages from /repositories?since=ID until the token's rate limit
    is nearly used up, or a wall-clock time budget is hit (whichever first)
  - writes the new records to a fresh file under data/ (keeps individual
    files well under GitHub's 100MB per-file push limit)
  - updates checkpoint.txt

The workflow commits data/ and checkpoint.txt back to the repo after each
run, so progress persists between hourly invocations with no server to keep on.
"""

import json
import os
import time
import sys
import urllib.request
import urllib.error

API_URL = "https://api.github.com/repositories"
CHECKPOINT_FILE = "checkpoint.txt"
DATA_DIR = "data"
PER_PAGE = 100
TIME_BUDGET_SECONDS = 50 * 60  # stop after 50 min so the job finishes within the hour

TOKEN = os.environ.get("DUMP_PAT")
if not TOKEN:
    print("ERROR: DUMP_PAT env var not set (add it as a repo secret).")
    sys.exit(1)

HEADERS = {
    "Authorization": f"Bearer {TOKEN}",
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
    "User-Agent": "repo-dump-actions",
}


def load_checkpoint():
    if os.path.exists(CHECKPOINT_FILE):
        with open(CHECKPOINT_FILE, "r") as f:
            return int(f.read().strip() or 0)
    return 0


def save_checkpoint(since_id):
    with open(CHECKPOINT_FILE, "w") as f:
        f.write(str(since_id))


def fetch_page(since_id):
    url = f"{API_URL}?since={since_id}&per_page={PER_PAGE}"
    req = urllib.request.Request(url, headers=HEADERS)
    try:
        with urllib.request.urlopen(req) as resp:
            remaining = int(resp.headers.get("X-RateLimit-Remaining", "1"))
            data = json.loads(resp.read().decode())
            return data, remaining
    except urllib.error.HTTPError as e:
        if e.code == 403:
            return None, 0
        raise


def main():
    os.makedirs(DATA_DIR, exist_ok=True)
    since_id = load_checkpoint()
    start_id = since_id
    started_at = time.time()

    out_path = os.path.join(DATA_DIR, f"repos_from_{start_id}.jsonl")
    total_written = 0

    print(f"Starting from repo ID {since_id}. Writing to {out_path}.")

    with open(out_path, "w", encoding="utf-8") as out:
        while True:
            if time.time() - started_at > TIME_BUDGET_SECONDS:
                print("Time budget reached for this run, stopping.")
                break

            data, remaining = fetch_page(since_id)

            if data is None:
                print("Rate limited by GitHub. Stopping this run early; next scheduled run will continue.")
                break

            if not data:
                print("Reached the end of the repo ID sequence — full dump complete.")
                break

            for repo in data:
                record = {
                    "id": repo["id"],
                    "full_name": repo["full_name"],
                    "private": repo["private"],
                    "owner": repo["owner"]["login"],
                    "owner_type": repo["owner"]["type"],
                    "html_url": repo["html_url"],
                    "fork": repo["fork"],
                }
                out.write(json.dumps(record) + "\n")
                total_written += 1

            since_id = data[-1]["id"]

            if total_written % 5000 == 0:
                print(f"{total_written} repos written this run. Last ID: {since_id}. Rate remaining: {remaining}")

            if remaining <= 1:
                print("Rate limit nearly exhausted, stopping this run.")
                break

    save_checkpoint(since_id)
    print(f"Run complete. {total_written} repos written. Checkpoint now at {since_id}.")


if __name__ == "__main__":
    main()
