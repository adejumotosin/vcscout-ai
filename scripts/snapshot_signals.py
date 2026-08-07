from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from vcscout.data import dataset_metadata, fetch_live_payload, flatten_startups  # noqa: E402
from vcscout.scoring import deduplicate_for_ranking, score_startups  # noqa: E402

OUTPUT = ROOT / "data" / "history" / "signals_history.csv"


def main() -> None:
    payload = fetch_live_payload()
    meta = dataset_metadata(payload)
    frame = deduplicate_for_ranking(score_startups(flatten_startups(payload)))

    observed_at = pd.to_datetime(meta.get("last_updated"), errors="coerce", utc=True)
    if pd.isna(observed_at):
        observed_at = pd.Timestamp.now(tz="UTC")
    snapshot_date = observed_at.strftime("%Y-%m-%d")

    frame.insert(0, "snapshot_date", snapshot_date)
    frame.insert(1, "source_period", meta.get("period"))
    frame.insert(2, "source_updated_at", observed_at.isoformat())

    keep = [
        "snapshot_date", "source_period", "source_updated_at", "name", "description",
        "sector", "sector_slug", "stage", "geography", "commit_velocity_14d",
        "commit_velocity_change", "contributors", "contributor_growth", "new_repos_30d",
        "signal_type", "vc_scout_score", "momentum_flag", "top_driver", "risk_flag",
        "github_url", "website_url", "profile_url",
    ]
    snapshot = frame[[col for col in keep if col in frame.columns]].copy()

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    if OUTPUT.exists():
        old = pd.read_csv(OUTPUT)
        combined = pd.concat([old, snapshot], ignore_index=True)
    else:
        combined = snapshot

    combined = combined.drop_duplicates(subset=["snapshot_date", "name"], keep="last")
    combined = combined.sort_values(["snapshot_date", "name"]).reset_index(drop=True)
    combined.to_csv(OUTPUT, index=False)
    print(f"Saved {len(snapshot)} rows for {snapshot_date}; history now has {len(combined)} rows.")


if __name__ == "__main__":
    main()
