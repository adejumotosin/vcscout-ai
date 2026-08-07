from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Any

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

OUTPUT = ROOT / "data" / "history" / "signals_history.csv"
DATASET = "the-data-nerd/vc-deal-flow-signal"
ROWS_API = "https://datasets-server.huggingface.co/rows"


def _pick(row: dict[str, Any], *names: str, default: Any = None) -> Any:
    lower = {str(k).lower(): v for k, v in row.items()}
    for name in names:
        if name in row:
            return row[name]
        if name.lower() in lower:
            return lower[name.lower()]
    return default


def _period_date(value: str | None) -> str | None:
    text = str(value or "").lower().strip()
    match = re.search(r"q([1-4])[-_ ]?(20\d{2})", text)
    if not match:
        match = re.search(r"(20\d{2})[-_ ]?q([1-4])", text)
        if not match:
            return None
        year, quarter = int(match.group(1)), int(match.group(2))
    else:
        quarter, year = int(match.group(1)), int(match.group(2))
    month = 1 + (quarter - 1) * 3
    return f"{year:04d}-{month:02d}-01"


def fetch_rows(page_size: int = 100) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    offset = 0
    while True:
        response = requests.get(
            ROWS_API,
            params={
                "dataset": DATASET,
                "config": "startup_signals",
                "split": "train",
                "offset": offset,
                "length": page_size,
            },
            timeout=60,
            headers={"User-Agent": "VCScoutAI/0.3 (+public-research)"},
        )
        response.raise_for_status()
        payload = response.json()
        page = [item.get("row", item) for item in payload.get("rows", [])]
        rows.extend(page)
        if len(page) < page_size:
            break
        offset += len(page)
    return rows


def normalize(rows: list[dict[str, Any]]) -> pd.DataFrame:
    output: list[dict[str, Any]] = []
    for row in rows:
        period = _pick(row, "period", "quarter", "signal_period")
        snapshot_date = _period_date(period)
        name = _pick(row, "startup_name", "name", "organization", "org_name", "github_org")
        if not snapshot_date or not name:
            continue
        output.append(
            {
                "snapshot_date": snapshot_date,
                "source_period": period,
                "source_updated_at": None,
                "name": name,
                "description": _pick(row, "description", default="") or "",
                "sector": _pick(row, "sector_name", "sector", default="Unknown"),
                "sector_slug": _pick(row, "sector_slug", default="unknown"),
                "stage": _pick(row, "stage_estimate", "stage", default="Unknown"),
                "geography": _pick(row, "geography", "region", default="Unknown"),
                "commit_velocity_14d": _pick(row, "commit_velocity_14d", "commitVelocity14d", default=0),
                "commit_velocity_change": _pick(row, "commit_velocity_change", "commit_velocity_change_pct", "commitVelocityChange", default=0),
                "contributors": _pick(row, "contributors", "contributor_count", default=0),
                "contributor_growth": _pick(row, "contributor_growth", "contributor_growth_pct", default=0),
                "new_repos_30d": _pick(row, "new_repos_30d", "new_repositories_30d", "new_repos", default=0),
                "signal_type": _pick(row, "signal_type", "signalType", default="Unknown"),
                "vc_scout_score": None,
                "momentum_flag": None,
                "top_driver": None,
                "risk_flag": None,
                "github_url": _pick(row, "github_url", "githubUrl"),
                "website_url": _pick(row, "website_url", "websiteUrl"),
                "profile_url": _pick(row, "profile_url", "profileUrl"),
            }
        )
    return pd.DataFrame(output)


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill VCScout history from the public GitDealFlow Hugging Face panel.")
    parser.add_argument("--page-size", type=int, default=100)
    args = parser.parse_args()

    historical = normalize(fetch_rows(args.page_size))
    if historical.empty:
        raise SystemExit("No historical rows returned from Hugging Face dataset server.")

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    if OUTPUT.exists():
        existing = pd.read_csv(OUTPUT)
        combined = pd.concat([existing, historical], ignore_index=True)
    else:
        combined = historical
    combined = combined.drop_duplicates(subset=["snapshot_date", "name"], keep="last")
    combined = combined.sort_values(["snapshot_date", "name"]).reset_index(drop=True)
    combined.to_csv(OUTPUT, index=False)
    print(f"Imported {len(historical)} historical startup-period rows; store now contains {len(combined)} rows.")


if __name__ == "__main__":
    main()
