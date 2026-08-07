from __future__ import annotations

import re
import sys
from collections import defaultdict
from difflib import SequenceMatcher
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from vcscout.outcomes import normalize_company_name  # noqa: E402

HISTORY = ROOT / "data" / "history" / "signals_history.csv"
EVENTS = ROOT / "data" / "funding_events" / "sec_form_d_events.csv"
OUTPUT = ROOT / "data" / "workflow_status" / "entity_match_audit.csv"

HANDLE_SUFFIXES = ("hq", "io", "org", "inc")


def signal_variants(name: str) -> list[str]:
    base = normalize_company_name(name)
    variants = {base}
    compact = re.sub(r"\s+", "", base)
    variants.add(compact)

    tokens = base.split()
    if len(tokens) > 1 and tokens[-1] in HANDLE_SUFFIXES:
        variants.add(" ".join(tokens[:-1]))
    for suffix in HANDLE_SUFFIXES:
        if compact.endswith(suffix) and len(compact) - len(suffix) >= 5:
            variants.add(compact[: -len(suffix)])
    return sorted(v for v in variants if v)


def main() -> None:
    signals = pd.read_csv(HISTORY)
    events = pd.read_csv(EVENTS)
    events["normalized_issuer"] = events["issuer_name"].map(normalize_company_name)
    events["event_date"] = pd.to_datetime(events["event_date"], errors="coerce", utc=True)

    issuer_stats = (
        events[events["normalized_issuer"].astype(bool)]
        .groupby(["normalized_issuer", "issuer_name"], as_index=False)
        .agg(
            filing_count=("event_date", "size"),
            first_event=("event_date", "min"),
            last_event=("event_date", "max"),
        )
    )

    prefix: dict[str, list[tuple[str, str, int, object, object]]] = defaultdict(list)
    for row in issuer_stats.itertuples(index=False):
        key = row.normalized_issuer[:3]
        prefix[key].append(
            (row.normalized_issuer, row.issuer_name, int(row.filing_count), row.first_event, row.last_event)
        )

    output: list[dict] = []
    for signal_name in sorted(signals["name"].dropna().astype(str).unique(), key=str.lower):
        variants = signal_variants(signal_name)
        candidates: dict[tuple[str, str], tuple[float, str, int, object, object]] = {}
        for variant in variants:
            pool = prefix.get(variant[:3], [])
            for normalized, issuer_name, count, first_event, last_event in pool:
                score = SequenceMatcher(None, variant, normalized).ratio()
                exact_variant = variant == normalized
                adjusted = 1.0 if exact_variant else score
                key = (normalized, issuer_name)
                previous = candidates.get(key)
                if previous is None or adjusted > previous[0]:
                    candidates[key] = (adjusted, variant, count, first_event, last_event)

        ranked = sorted(candidates.items(), key=lambda item: item[1][0], reverse=True)[:5]
        if not ranked:
            output.append(
                {
                    "signal_name": signal_name,
                    "signal_variants": " | ".join(variants),
                    "candidate_rank": None,
                    "candidate_issuer": None,
                    "normalized_candidate": None,
                    "similarity": None,
                    "matched_variant": None,
                    "filing_count": None,
                    "first_event": None,
                    "last_event": None,
                }
            )
            continue

        for rank, ((normalized, issuer_name), (score, variant, count, first_event, last_event)) in enumerate(ranked, 1):
            output.append(
                {
                    "signal_name": signal_name,
                    "signal_variants": " | ".join(variants),
                    "candidate_rank": rank,
                    "candidate_issuer": issuer_name,
                    "normalized_candidate": normalized,
                    "similarity": round(score, 4),
                    "matched_variant": variant,
                    "filing_count": count,
                    "first_event": first_event,
                    "last_event": last_event,
                }
            )

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(output).to_csv(OUTPUT, index=False)
    print(f"Wrote {len(output)} candidate rows to {OUTPUT}")


if __name__ == "__main__":
    main()
