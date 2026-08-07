from __future__ import annotations

import argparse
import os
import time
from dataclasses import dataclass, field
from datetime import timedelta
from pathlib import Path
from typing import Any

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parents[1]
RECEIPTS = ROOT / "data" / "funding_events" / "gitdealflow_validated_funding_receipts.csv"
OUTPUT = ROOT / "data" / "training" / "receipt_backtest_features.csv"
STATUS = ROOT / "data" / "workflow_status" / "receipt_backtest_build.csv"

API = "https://api.github.com"


@dataclass
class GitHubClient:
    token: str | None
    timeout: int = 45
    _release_cache: dict[tuple[str, str], list[dict]] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.session = requests.Session()
        self.session.headers.update(
            {
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
                "User-Agent": "VCScoutAI/0.4 historical-signal-backtest",
            }
        )
        if self.token:
            self.session.headers["Authorization"] = f"Bearer {self.token}"

    def get(self, path: str, params: dict[str, Any] | None = None) -> requests.Response:
        response = self.session.get(f"{API}{path}", params=params, timeout=self.timeout)
        if response.status_code in {403, 429}:
            remaining = response.headers.get("x-ratelimit-remaining")
            reset = response.headers.get("x-ratelimit-reset")
            raise RuntimeError(f"GitHub API rate limited: remaining={remaining} reset={reset}")
        response.raise_for_status()
        return response

    def commits(self, owner: str, repo: str, since: pd.Timestamp, until: pd.Timestamp) -> list[dict]:
        rows: list[dict] = []
        page = 1
        while True:
            response = self.get(
                f"/repos/{owner}/{repo}/commits",
                params={
                    "since": since.isoformat(),
                    "until": until.isoformat(),
                    "per_page": 100,
                    "page": page,
                },
            )
            batch = response.json()
            if not isinstance(batch, list):
                raise RuntimeError(f"Unexpected commit response for {owner}/{repo}")
            rows.extend(batch)
            if len(batch) < 100:
                break
            page += 1
            if page > 30:
                raise RuntimeError(f"Commit pagination exceeded safety limit for {owner}/{repo}")
            time.sleep(0.03)
        return rows

    def releases(self, owner: str, repo: str) -> list[dict]:
        key = (owner.lower(), repo.lower())
        if key in self._release_cache:
            return self._release_cache[key]
        rows: list[dict] = []
        page = 1
        while True:
            response = self.get(
                f"/repos/{owner}/{repo}/releases",
                params={"per_page": 100, "page": page},
            )
            batch = response.json()
            if not isinstance(batch, list):
                raise RuntimeError(f"Unexpected release response for {owner}/{repo}")
            rows.extend(batch)
            if len(batch) < 100 or page >= 10:
                break
            page += 1
            time.sleep(0.03)
        self._release_cache[key] = rows
        return rows

    def search_count(self, query: str) -> int:
        response = self.get("/search/issues", params={"q": query, "per_page": 1})
        payload = response.json()
        time.sleep(2.05)  # Search API has a much tighter authenticated rate limit than core REST.
        return int(payload.get("total_count") or 0)


def _identity(commit: dict) -> str:
    author = commit.get("author") or {}
    login = author.get("login")
    if login:
        return f"gh:{login.lower()}"
    raw = ((commit.get("commit") or {}).get("author") or {})
    email = (raw.get("email") or "").strip().lower()
    if email:
        return f"email:{email}"
    name = (raw.get("name") or "unknown").strip().lower()
    return f"name:{name}"


def _iso_day(value: pd.Timestamp) -> str:
    return value.strftime("%Y-%m-%d")


def _release_metrics(client: GitHubClient, owner: str, repo: str, end: pd.Timestamp) -> dict[str, float]:
    releases = client.releases(owner, repo)
    dates = []
    for release in releases:
        raw = release.get("published_at") or release.get("created_at")
        dt = pd.to_datetime(raw, errors="coerce", utc=True)
        if pd.notna(dt):
            dates.append(pd.Timestamp(dt))
    count_30 = sum(end - timedelta(days=30) <= dt <= end for dt in dates)
    count_90 = sum(end - timedelta(days=90) <= dt <= end for dt in dates)
    return {"releases_30d": float(count_30), "releases_90d": float(count_90)}


def _community_metrics(client: GitHubClient, owner: str, repo: str, end: pd.Timestamp) -> dict[str, float]:
    start = end - timedelta(days=30)
    range_text = f"{_iso_day(start)}..{_iso_day(end)}"
    base = f"repo:{owner}/{repo}"
    issues_opened = client.search_count(f"{base} is:issue created:{range_text}")
    issues_closed = client.search_count(f"{base} is:issue closed:{range_text}")
    prs_merged = client.search_count(f"{base} is:pr is:merged merged:{range_text}")
    return {
        "issues_opened_30d": float(issues_opened),
        "issues_closed_30d": float(issues_closed),
        "prs_merged_30d": float(prs_merged),
        "community_throughput_30d": float(issues_closed + prs_merged),
    }


def _period_metrics(client: GitHubClient, owner: str, repo: str, end: pd.Timestamp) -> dict[str, float]:
    current_start = end - timedelta(days=14)
    prior_start = end - timedelta(days=28)
    current = client.commits(owner, repo, current_start, end)
    prior = client.commits(owner, repo, prior_start, current_start)

    current_contributors = {_identity(c) for c in current}
    prior_contributors = {_identity(c) for c in prior}
    current_count = len(current)
    prior_count = len(prior)
    current_team = len(current_contributors)
    prior_team = len(prior_contributors)

    velocity_change = 999.0 if prior_count == 0 and current_count > 0 else (
        0.0 if prior_count == 0 else 100.0 * (current_count - prior_count) / prior_count
    )
    contributor_growth = 999.0 if prior_team == 0 and current_team > 0 else (
        0.0 if prior_team == 0 else 100.0 * (current_team - prior_team) / prior_team
    )

    if contributor_growth > 50:
        signal_type = "Engineering hiring burst"
    elif velocity_change >= 150:
        signal_type = "Deploy frequency spike"
    else:
        signal_type = "Framework migration"

    return {
        "commit_velocity_14d": float(current_count),
        "commit_velocity_change": round(float(velocity_change), 4),
        "contributors": float(current_team),
        "contributor_growth": round(float(contributor_growth), 4),
        "new_repos_30d": 0.0,
        "signal_type": signal_type,
        **_release_metrics(client, owner, repo, end),
        **_community_metrics(client, owner, repo, end),
    }


def build(limit: int | None, token: str | None) -> tuple[pd.DataFrame, pd.DataFrame]:
    receipts = pd.read_csv(RECEIPTS)
    receipts["event_date"] = pd.to_datetime(receipts["event_date"], errors="coerce", utc=True)
    receipts = receipts[receipts["event_date"].notna()].copy()

    receipts = receipts.sort_values(["event_date", "github_owner", "github_repo"]).drop_duplicates(
        ["github_owner", "event_date"], keep="first"
    )
    if limit:
        receipts = receipts.head(limit)

    client = GitHubClient(token=token)
    rows: list[dict] = []
    status: list[dict] = []

    for i, receipt in enumerate(receipts.itertuples(index=False), 1):
        owner = str(receipt.github_owner)
        repo = str(receipt.github_repo)
        event_date = pd.Timestamp(receipt.event_date)
        windows = [
            (1, event_date - timedelta(days=42), "pre_funding_42d"),
            (0, event_date - timedelta(days=180), "control_180d"),
        ]
        for target, snapshot_date, window_name in windows:
            try:
                metrics = _period_metrics(client, owner, repo, snapshot_date)
                rows.append(
                    {
                        "company": receipt.company,
                        "github_owner": owner,
                        "github_repo": repo,
                        "event_date": event_date,
                        "snapshot_date": snapshot_date,
                        "window_name": window_name,
                        "raised_funding_within_90d": target,
                        **metrics,
                    }
                )
                status.append(
                    {
                        "github_owner": owner,
                        "github_repo": repo,
                        "event_date": event_date,
                        "window_name": window_name,
                        "status": "ok",
                        "detail": "",
                    }
                )
            except Exception as exc:  # noqa: BLE001 - audit every external-data failure.
                status.append(
                    {
                        "github_owner": owner,
                        "github_repo": repo,
                        "event_date": event_date,
                        "window_name": window_name,
                        "status": "error",
                        "detail": str(exc)[:500],
                    }
                )
        print(f"[{i}/{len(receipts)}] {owner}/{repo}")

    return pd.DataFrame(rows), pd.DataFrame(status)


def main() -> None:
    parser = argparse.ArgumentParser(description="Reconstruct historical engineering and product/community windows around validated funding receipts.")
    parser.add_argument("--limit", type=int, default=None, help="Pilot limit on unique funding receipts")
    parser.add_argument("--token", default=os.environ.get("GH_PUBLIC_TOKEN") or os.environ.get("GITHUB_TOKEN"))
    args = parser.parse_args()

    features, status = build(args.limit, args.token)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    STATUS.parent.mkdir(parents=True, exist_ok=True)
    features.to_csv(OUTPUT, index=False)
    status.to_csv(STATUS, index=False)

    ok = int((status["status"] == "ok").sum()) if not status.empty else 0
    errors = int((status["status"] == "error").sum()) if not status.empty else 0
    positives = int((features["raised_funding_within_90d"] == 1).sum()) if not features.empty else 0
    controls = int((features["raised_funding_within_90d"] == 0).sum()) if not features.empty else 0
    print(
        f"Built {len(features)} historical windows ({positives} pre-funding / {controls} controls); "
        f"{ok} API windows succeeded and {errors} failed."
    )


if __name__ == "__main__":
    main()
