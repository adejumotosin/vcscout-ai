from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from vcscout.outcomes import LabelConfig, build_90d_labels  # noqa: E402

HISTORY = ROOT / "data" / "history" / "signals_history.csv"
EVENTS = ROOT / "data" / "funding_events" / "sec_form_d_events.csv"
ALIASES = ROOT / "data" / "funding_events" / "company_aliases.csv"
OUTPUT = ROOT / "data" / "training" / "funding_labels.csv"


def _coverage_date(events: pd.DataFrame) -> pd.Timestamp:
    for column in ("filing_date", "event_date"):
        if column in events.columns:
            parsed = pd.to_datetime(events[column], errors="coerce", utc=True).dropna()
            if not parsed.empty:
                return parsed.max()
    raise SystemExit("Could not infer funding-event coverage date from filing_date or event_date.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Join VCScout signal history to timestamped funding events.")
    parser.add_argument(
        "--as-of",
        default=None,
        help="Outcome-data coverage date. Defaults to the latest filing/event date in the funding store.",
    )
    parser.add_argument("--horizon-days", type=int, default=90)
    parser.add_argument("--reporting-lag-days", type=int, default=20)
    parser.add_argument("--fuzzy-threshold", type=float, default=0.94)
    args = parser.parse_args()

    if not HISTORY.exists():
        raise SystemExit(f"Missing signal history: {HISTORY}. Run scripts/snapshot_signals.py first.")
    if not EVENTS.exists():
        raise SystemExit(f"Missing funding events: {EVENTS}. Run scripts/ingest_sec_form_d.py first.")

    signals = pd.read_csv(HISTORY)
    events = pd.read_csv(EVENTS)
    aliases = pd.read_csv(ALIASES) if ALIASES.exists() else None
    as_of = pd.to_datetime(args.as_of, utc=True) if args.as_of else _coverage_date(events)

    labelled = build_90d_labels(
        signals,
        events,
        as_of=as_of,
        aliases=aliases,
        config=LabelConfig(
            horizon_days=args.horizon_days,
            fuzzy_threshold=args.fuzzy_threshold,
            reporting_lag_days=args.reporting_lag_days,
        ),
    )
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    labelled.to_csv(OUTPUT, index=False)

    positives = int(pd.to_numeric(labelled["raised_funding_within_90d"], errors="coerce").fillna(0).sum()) if not labelled.empty else 0
    print(
        f"Wrote {len(labelled)} uncensored labels with {positives} positive funding events "
        f"to {OUTPUT}. Outcome coverage through {as_of.date()} with "
        f"{args.reporting_lag_days}-day reporting lag."
    )


if __name__ == "__main__":
    main()
