from __future__ import annotations

import argparse
import os
import time
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path
from typing import Any
from urllib.parse import urlparse, urlunparse

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parents[1]
import sys
sys.path.insert(0, str(ROOT / "src"))

from vcscout.commercial import extract_commercial_signals  # noqa: E402

BASE = ROOT / "data" / "training" / "receipt_backtest_features.csv"
OUTPUT = ROOT / "data" / "training" / "commercial_backtest_features.csv"
STATUS = ROOT / "data" / "workflow_status" / "commercial_backtest_build.csv"

GITHUB_API = "https://api.github.com"
CDX_API = "https://web.archive.org/cdx/search/cdx"
WAYBACK = "https://web.archive.org/web"

_BLOCKED_HOSTS = {
    "github.com",
    "www.github.com",
    "twitter.com",
    "www.twitter.com",
    "x.com",
    "www.x.com",
    "linkedin.com",
    "www.linkedin.com",
    "discord.com",
    "discord.gg",
    "youtube.com",
    "www.youtube.com",
}


def _safe_url(value: Any) -> str | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    if not raw.startswith(("http://", "https://")):
        raw = "https://" + raw.lstrip("/")
    try:
        parsed = urlparse(raw)
    except ValueError:
        return None
    host = (parsed.hostname or "").lower().strip(".")
    if not host or host in _BLOCKED_HOSTS:
        return None
    path = parsed.path or "/"
    return urlunparse((parsed.scheme or "https", parsed.netloc, path, "", "", ""))


def _root_variants(url: str) -> list[str]:
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    if not host:
        return [url]
    hosts = [host]
    if host.startswith("www."):
        hosts.append(host[4:])
    else:
        hosts.append("www." + host)
    variants: list[str] = []
    for candidate_host in hosts:
        variants.extend([f"https://{candidate_host}/", f"http://{candidate_host}/"])
    if parsed.path and parsed.path != "/":
        variants.insert(0, url)
    return list(dict.fromkeys(variants))


@dataclass
class PublicClient:
    github_token: str | None
    timeout: int = 35

    def __post_init__(self) -> None:
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "VCScoutAI/0.4 commercial-backtest"})
        self.github_headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "VCScoutAI/0.4 commercial-backtest",
        }
        if self.github_token:
            self.github_headers["Authorization"] = f"Bearer {self.github_token}"

    def github_json(self, path: str) -> dict[str, Any]:
        response = self.session.get(
            f"{GITHUB_API}{path}", headers=self.github_headers, timeout=self.timeout
        )
        if response.status_code in {403, 429}:
            raise RuntimeError(
                f"GitHub API rate limited: remaining={response.headers.get('x-ratelimit-remaining')}"
            )
        response.raise_for_status()
        payload = response.json()
        return payload if isinstance(payload, dict) else {}

    def resolve_site(self, owner: str, repo: str) -> str | None:
        candidates: list[Any] = []
        try:
            repo_data = self.github_json(f"/repos/{owner}/{repo}")
            candidates.extend([repo_data.get("homepage")])
        except requests.HTTPError:
            pass
        try:
            owner_data = self.github_json(f"/users/{owner}")
            candidates.extend([owner_data.get("blog")])
        except requests.HTTPError:
            pass
        for candidate in candidates:
            resolved = _safe_url(candidate)
            if resolved:
                return resolved
        return None

    def latest_capture(self, url: str, target: pd.Timestamp) -> dict[str, Any] | None:
        target = pd.Timestamp(target).tz_convert("UTC") if pd.Timestamp(target).tzinfo else pd.Timestamp(target, tz="UTC")
        to_value = target.strftime("%Y%m%d%H%M%S")
        captures: list[dict[str, Any]] = []
        for variant in _root_variants(url):
            try:
                response = self.session.get(
                    CDX_API,
                    params={
                        "url": variant,
                        "output": "json",
                        "fl": "timestamp,original,statuscode,mimetype,digest",
                        "filter": ["statuscode:200", "mimetype:text/html"],
                        "to": to_value,
                        "limit": -5,
                        "collapse": "digest",
                    },
                    timeout=self.timeout,
                )
                if response.status_code in {403, 429, 503}:
                    time.sleep(0.5)
                    continue
                response.raise_for_status()
                payload = response.json()
                if not isinstance(payload, list) or len(payload) < 2:
                    continue
                header = payload[0]
                for row in payload[1:]:
                    if not isinstance(row, list) or len(row) != len(header):
                        continue
                    item = dict(zip(header, row))
                    ts = pd.to_datetime(item.get("timestamp"), format="%Y%m%d%H%M%S", errors="coerce", utc=True)
                    if pd.notna(ts) and ts <= target:
                        item["capture_time"] = ts
                        captures.append(item)
            except (requests.RequestException, ValueError):
                continue
            time.sleep(0.08)
        if not captures:
            return None
        return max(captures, key=lambda item: item["capture_time"])

    def archived_html(self, capture: dict[str, Any]) -> str:
        timestamp = str(capture["timestamp"])
        original = str(capture["original"])
        response = self.session.get(
            f"{WAYBACK}/{timestamp}id_/{original}", timeout=self.timeout
        )
        response.raise_for_status()
        return response.text


def build(limit: int | None, token: str | None, max_capture_age_days: int) -> tuple[pd.DataFrame, pd.DataFrame]:
    base = pd.read_csv(BASE)
    base["snapshot_date"] = pd.to_datetime(base["snapshot_date"], errors="coerce", utc=True)
    base["event_date"] = pd.to_datetime(base["event_date"], errors="coerce", utc=True)
    base = base[base["snapshot_date"].notna()].copy()

    if limit:
        owners = list(dict.fromkeys(base["github_owner"].astype(str)))[:limit]
        base = base[base["github_owner"].astype(str).isin(owners)].copy()

    client = PublicClient(github_token=token)
    site_cache: dict[tuple[str, str], str | None] = {}
    rows: list[dict[str, Any]] = []
    statuses: list[dict[str, Any]] = []

    for i, row in enumerate(base.itertuples(index=False), 1):
        owner = str(row.github_owner)
        repo = str(row.github_repo)
        cache_key = (owner.lower(), repo.lower())
        site = site_cache.get(cache_key)
        if cache_key not in site_cache:
            try:
                site = client.resolve_site(owner, repo)
            except Exception as exc:  # noqa: BLE001
                site = None
                statuses.append({
                    "github_owner": owner,
                    "github_repo": repo,
                    "window_name": row.window_name,
                    "snapshot_date": row.snapshot_date,
                    "status": "site_resolution_error",
                    "detail": str(exc)[:400],
                })
            site_cache[cache_key] = site

        if not site:
            statuses.append({
                "github_owner": owner,
                "github_repo": repo,
                "window_name": row.window_name,
                "snapshot_date": row.snapshot_date,
                "status": "no_company_website",
                "detail": "",
            })
            continue

        try:
            capture = client.latest_capture(site, pd.Timestamp(row.snapshot_date))
            if not capture:
                statuses.append({
                    "github_owner": owner,
                    "github_repo": repo,
                    "window_name": row.window_name,
                    "snapshot_date": row.snapshot_date,
                    "status": "no_prior_capture",
                    "detail": site,
                })
                continue
            age_days = (pd.Timestamp(row.snapshot_date) - pd.Timestamp(capture["capture_time"])).days
            if age_days > max_capture_age_days:
                statuses.append({
                    "github_owner": owner,
                    "github_repo": repo,
                    "window_name": row.window_name,
                    "snapshot_date": row.snapshot_date,
                    "status": "stale_capture",
                    "detail": f"{site} | age_days={age_days}",
                })
                continue

            html = client.archived_html(capture)
            signals = extract_commercial_signals(html)
            rows.append({
                "company": row.company,
                "github_owner": owner,
                "github_repo": repo,
                "event_date": row.event_date,
                "snapshot_date": row.snapshot_date,
                "window_name": row.window_name,
                "raised_funding_within_90d": int(row.raised_funding_within_90d),
                "website_url": site,
                "archive_timestamp": capture["timestamp"],
                "archive_original": capture["original"],
                "archive_age_days": age_days,
                **signals,
            })
            statuses.append({
                "github_owner": owner,
                "github_repo": repo,
                "window_name": row.window_name,
                "snapshot_date": row.snapshot_date,
                "status": "ok",
                "detail": f"{site} | {capture['timestamp']} | age_days={age_days}",
            })
        except Exception as exc:  # noqa: BLE001
            statuses.append({
                "github_owner": owner,
                "github_repo": repo,
                "window_name": row.window_name,
                "snapshot_date": row.snapshot_date,
                "status": "archive_error",
                "detail": str(exc)[:400],
            })
        print(f"[{i}/{len(base)}] {owner}/{repo} {row.window_name}")
        time.sleep(0.1)

    return pd.DataFrame(rows), pd.DataFrame(statuses)


def main() -> None:
    parser = argparse.ArgumentParser(description="Build leakage-resistant archived commercial signals for the funding backtest.")
    parser.add_argument("--limit", type=int, default=None, help="Limit unique GitHub owners for a pilot run")
    parser.add_argument("--max-capture-age-days", type=int, default=120)
    parser.add_argument("--token", default=os.environ.get("GH_PUBLIC_TOKEN") or os.environ.get("GITHUB_TOKEN"))
    args = parser.parse_args()

    features, status = build(args.limit, args.token, args.max_capture_age_days)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    STATUS.parent.mkdir(parents=True, exist_ok=True)
    features.to_csv(OUTPUT, index=False)
    status.to_csv(STATUS, index=False)

    ok = int((status["status"] == "ok").sum()) if not status.empty else 0
    unique_companies = features["github_owner"].nunique() if not features.empty else 0
    paired = 0
    if not features.empty:
        paired = int((features.groupby("github_owner")["raised_funding_within_90d"].nunique() == 2).sum())
    print(
        f"Archived commercial signals: {len(features)} windows, {unique_companies} companies, "
        f"{paired} complete pairs, {ok} successful captures."
    )


if __name__ == "__main__":
    main()
