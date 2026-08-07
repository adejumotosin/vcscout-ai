from __future__ import annotations

import re
from typing import Any

import pandas as pd
import requests

from .config import settings

_PERCENT_RE = re.compile(r"[-+]?\d+(?:\.\d+)?")


def parse_percent(value: Any) -> float:
    """Parse values such as '+1600%', '-27%', 14, or None into floats."""
    if value is None:
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)
    match = _PERCENT_RE.search(str(value).replace(",", ""))
    return float(match.group(0)) if match else 0.0


def fetch_live_payload(url: str | None = None) -> dict[str, Any]:
    endpoint = url or settings.signals_url
    response = requests.get(
        endpoint,
        timeout=settings.request_timeout_seconds,
        headers={"User-Agent": "VCScoutAI/0.1 (+portfolio-research)"},
    )
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, dict) or "sectors" not in payload:
        raise ValueError("Unexpected VC Deal Flow Signal payload shape")
    return payload


def flatten_startups(payload: dict[str, Any]) -> pd.DataFrame:
    """Flatten the sector-oriented API payload into one row per startup-sector pair."""
    rows: list[dict[str, Any]] = []
    for sector in payload.get("sectors", []):
        sector_name = sector.get("name", "Unknown")
        sector_slug = sector.get("slug", "unknown")
        for startup in sector.get("startups", []):
            rows.append(
                {
                    "name": startup.get("name", "Unknown"),
                    "description": startup.get("description", "") or "",
                    "sector": sector_name,
                    "sector_slug": sector_slug,
                    "stage": startup.get("stage", "Unknown"),
                    "geography": startup.get("geography", "Unknown"),
                    "commit_velocity_14d": float(startup.get("commitVelocity14d") or 0),
                    "commit_velocity_change": parse_percent(startup.get("commitVelocityChange")),
                    "contributors": float(startup.get("contributors") or 0),
                    "contributor_growth": parse_percent(startup.get("contributorGrowth")),
                    "new_repos_30d": float(startup.get("newRepos") or 0),
                    "signal_type": startup.get("signalType", "Unknown"),
                    "github_url": startup.get("githubUrl"),
                    "website_url": startup.get("websiteUrl"),
                    "profile_url": startup.get("profileUrl"),
                }
            )

    df = pd.DataFrame(rows)
    if df.empty:
        return df

    # Some organisations may appear in more than one sector. Preserve all sector labels,
    # but keep one primary observation per org for global rankings.
    df["startup_key"] = df["name"].str.lower().str.strip()
    return df


def dataset_metadata(payload: dict[str, Any]) -> dict[str, Any]:
    meta = payload.get("meta", {})
    period = meta.get("period", {})
    return {
        "name": meta.get("name", "VC Deal Flow Signal"),
        "period": period.get("name", period.get("slug", "Unknown")),
        "last_updated": meta.get("lastUpdated"),
        "total_sectors": meta.get("totalSectors"),
        "total_startups": meta.get("totalStartups"),
        "citation": meta.get("citation"),
        "license": meta.get("license"),
        "methodology": meta.get("methodology"),
    }
