from __future__ import annotations

import argparse
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse, urlunparse

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parents[1]
import sys
sys.path.insert(0, str(ROOT / "src"))

from vcscout.commercial import extract_commercial_signals, is_company_website_url  # noqa: E402

BASE = ROOT / "data" / "training" / "receipt_backtest_features.csv"
OUTPUT = ROOT / "data" / "training" / "commercial_backtest_features.csv"
STATUS = ROOT / "data" / "workflow_status" / "commercial_backtest_build.csv"

GITHUB_API = "https://api.github.com"
CDX_API = "https://web.archive.org/cdx/search/cdx"
WAYBACK = "https://web.archive.org/web"


def _safe_url(value: Any) -> str | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    if not raw.startswith(("http://", "https://")):
        raw = "https://" + raw.lstrip("/")
    if not is_company_website_url(raw):
        return None
    try:
        parsed = urlparse(raw)
    except ValueError:
        return None
    if not parsed.hostname:
        return None
    path = parsed.path or "/"
    return urlunparse((parsed.scheme or "https", parsed.netloc, path, "", "", ""))


def _archive_variants(url: str) -> list[str]:
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    if not host:
        return [url]
    path = parsed.path or "/"
    variants = [urlunparse((parsed.scheme or "https", parsed.netloc, path, "", "", ""))]
    variants.extend([f"https://{host}/", f"http://{host}/"])
    if host.startswith("www."):
        bare = host[4:]
        variants.extend([f"https://{bare}/", f"http://{bare}/"])
    return list(dict.fromkeys(variants))


@dataclass
class GitHubResolver:
    token: str | None
    timeout: int = 8

    def __post_init__(self) -> None:
        self.session = requests.Session()
        self.headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "VCScoutAI/0.5 commercial-backtest",
        }
        if self.token:
            self.headers["Authorization"] = f"Bearer {self.token}"

    def _json(self, path: str) -> dict[str, Any]:
        response = self.session.get(
            f"{GITHUB_API}{path}", headers=self.headers, timeout=self.timeout
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
            candidates.append(self._json(f"/repos/{owner}/{repo}").get("homepage"))
        except requests.RequestException:
            pass
        try:
            candidates.append(self._json(f"/users/{owner}").get("blog"))
        except requests.RequestException:
            pass
        for candidate in candidates:
            site = _safe_url(candidate)
            if site:
                return site
        return None


def _capture_candidates(site: str, target: pd.Timestamp, timeout: int) -> tuple[list[dict[str, Any]], list[str]]:
    target = pd.Timestamp(target)
    target = target.tz_convert("UTC") if target.tzinfo else target.tz_localize("UTC")
    to_value = target.strftime("%Y%m%d%H%M%S")
    errors: list[str] = []
    session = requests.Session()
    session.headers.update({"User-Agent": "VCScoutAI/0.5 historical-commercial-backtest"})

    for variant in _archive_variants(site):
        try:
            response = session.get(
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
                timeout=timeout,
            )
            if response.status_code in {403, 429, 503}:
                errors.append(f"{variant}: HTTP {response.status_code}")
                continue
            response.raise_for_status()
            payload = response.json()
            if not isinstance(payload, list) or len(payload) < 2:
                continue
            header = payload[0]
            captures: list[dict[str, Any]] = []
            for raw in payload[1:]:
                if not isinstance(raw, list) or len(raw) != len(header):
                    continue
                item = dict(zip(header, raw))
                capture_time = pd.to_datetime(
                    item.get("timestamp"), format="%Y%m%d%H%M%S", errors="coerce", utc=True
                )
                if pd.notna(capture_time) and capture_time <= target:
                    item["capture_time"] = capture_time
                    captures.append(item)
            if captures:
                captures.sort(key=lambda item: item["capture_time"], reverse=True)
                return captures, errors
        except (requests.RequestException, ValueError) as exc:
            errors.append(f"{variant}: {str(exc)[:180]}")
    return [], errors


def _fetch_archived_html(capture: dict[str, Any], timeout: int) -> str:
    timestamp = str(capture["timestamp"])
    original = str(capture["original"])
    response = requests.get(
        f"{WAYBACK}/{timestamp}id_/{original}",
        timeout=timeout,
        headers={"User-Agent": "VCScoutAI/0.5 historical-commercial-backtest"},
    )
    response.raise_for_status()
    return response.text


def _process_window(
    row: dict[str, Any],
    site: str | None,
    resolution_error: str | None,
    max_capture_age_days: int,
    timeout: int,
) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    owner = str(row["github_owner"])
    repo = str(row["github_repo"])
    status_base = {
        "github_owner": owner,
        "github_repo": repo,
        "window_name": row["window_name"],
        "snapshot_date": row["snapshot_date"],
    }
    if not site:
        return None, {
            **status_base,
            "status": "site_resolution_error" if resolution_error else "no_company_website",
            "detail": resolution_error or "",
        }

    target = pd.Timestamp(row["snapshot_date"])
    captures, lookup_errors = _capture_candidates(site, target, timeout)
    if not captures:
        return None, {
            **status_base,
            "status": "no_prior_capture",
            "detail": f"{site} | {' | '.join(lookup_errors[-2:])}"[:700],
        }

    stale_age: int | None = None
    fetch_errors: list[str] = []
    for capture in captures:
        age_days = int((target - pd.Timestamp(capture["capture_time"])).days)
        if age_days > max_capture_age_days:
            stale_age = age_days
            continue
        try:
            html = _fetch_archived_html(capture, timeout=max(timeout, 10))
            signals = extract_commercial_signals(html)
            feature = {
                "company": row["company"],
                "github_owner": owner,
                "github_repo": repo,
                "event_date": row["event_date"],
                "snapshot_date": row["snapshot_date"],
                "window_name": row["window_name"],
                "raised_funding_within_90d": int(row["raised_funding_within_90d"]),
                "website_url": site,
                "archive_timestamp": capture["timestamp"],
                "archive_original": capture["original"],
                "archive_age_days": age_days,
                **signals,
            }
            return feature, {
                **status_base,
                "status": "ok",
                "detail": f"{site} | {capture['timestamp']} | age_days={age_days}",
            }
        except requests.RequestException as exc:
            fetch_errors.append(str(exc)[:180])

    if stale_age is not None and not fetch_errors:
        return None, {
            **status_base,
            "status": "stale_capture",
            "detail": f"{site} | newest_eligible_age_days={stale_age}",
        }
    return None, {
        **status_base,
        "status": "archive_fetch_error",
        "detail": f"{site} | {' | '.join(fetch_errors[-2:])}"[:700],
    }


def build(
    limit: int | None,
    token: str | None,
    max_capture_age_days: int,
    timeout: int,
    workers: int,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    base = pd.read_csv(BASE)
    base["snapshot_date"] = pd.to_datetime(base["snapshot_date"], errors="coerce", utc=True)
    base["event_date"] = pd.to_datetime(base["event_date"], errors="coerce", utc=True)
    base = base[base["snapshot_date"].notna()].copy()

    if limit:
        owners = list(dict.fromkeys(base["github_owner"].astype(str)))[:limit]
        base = base[base["github_owner"].astype(str).isin(owners)].copy()

    resolver = GitHubResolver(token=token, timeout=timeout)
    sites: dict[tuple[str, str], str | None] = {}
    resolution_errors: dict[tuple[str, str], str | None] = {}
    unique_repos = base[["github_owner", "github_repo"]].drop_duplicates()
    for repo_row in unique_repos.itertuples(index=False):
        owner, repo = str(repo_row.github_owner), str(repo_row.github_repo)
        key = (owner.lower(), repo.lower())
        try:
            sites[key] = resolver.resolve_site(owner, repo)
            resolution_errors[key] = None
        except Exception as exc:  # noqa: BLE001
            sites[key] = None
            resolution_errors[key] = str(exc)[:400]

    records = base.to_dict(orient="records")
    features: list[dict[str, Any]] = []
    statuses: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=max(1, min(workers, 8))) as pool:
        futures = {}
        for row in records:
            key = (str(row["github_owner"]).lower(), str(row["github_repo"]).lower())
            future = pool.submit(
                _process_window,
                row,
                sites.get(key),
                resolution_errors.get(key),
                max_capture_age_days,
                timeout,
            )
            futures[future] = row
        for i, future in enumerate(as_completed(futures), 1):
            feature, status = future.result()
            if feature:
                features.append(feature)
            statuses.append(status)
            print(
                f"[{i}/{len(records)}] {status['github_owner']}/{status['github_repo']} "
                f"{status['window_name']} -> {status['status']}"
            )

    return pd.DataFrame(features), pd.DataFrame(statuses)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build leakage-resistant archived commercial signals for the funding backtest."
    )
    parser.add_argument("--limit", type=int, default=None, help="Limit unique GitHub owners for a pilot run")
    parser.add_argument("--max-capture-age-days", type=int, default=120)
    parser.add_argument("--timeout", type=int, default=8)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument(
        "--token", default=os.environ.get("GH_PUBLIC_TOKEN") or os.environ.get("GITHUB_TOKEN")
    )
    args = parser.parse_args()

    features, status = build(
        args.limit,
        args.token,
        args.max_capture_age_days,
        args.timeout,
        args.workers,
    )
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    STATUS.parent.mkdir(parents=True, exist_ok=True)
    features.to_csv(OUTPUT, index=False)
    status.to_csv(STATUS, index=False)

    ok = int((status["status"] == "ok").sum()) if not status.empty else 0
    unique_companies = features["github_owner"].nunique() if not features.empty else 0
    paired = 0
    if not features.empty:
        paired = int(
            (features.groupby("github_owner")["raised_funding_within_90d"].nunique() == 2).sum()
        )
    print(
        f"Archived commercial signals: {len(features)} windows, {unique_companies} companies, "
        f"{paired} complete pairs, {ok} successful captures."
    )


if __name__ == "__main__":
    main()
