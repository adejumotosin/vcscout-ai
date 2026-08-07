from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import timedelta
from difflib import SequenceMatcher

import pandas as pd

CORPORATE_SUFFIXES = {
    "inc", "incorporated", "llc", "ltd", "limited", "corp", "corporation",
    "co", "company", "plc", "lp", "llp", "gmbh", "sa", "sas", "bv",
}


def normalize_company_name(value: str | None) -> str:
    text = (value or "").lower().replace("&", " and ")
    text = re.sub(r"[^a-z0-9]+", " ", text)
    tokens = [t for t in text.split() if t and t not in CORPORATE_SUFFIXES]
    return " ".join(tokens)


def conservative_name_match(left: str, right: str, threshold: float = 0.94) -> bool:
    a, b = normalize_company_name(left), normalize_company_name(right)
    if not a or not b:
        return False
    if a == b:
        return True
    if min(len(a), len(b)) < 5:
        return False
    return SequenceMatcher(None, a, b).ratio() >= threshold


@dataclass(frozen=True)
class LabelConfig:
    horizon_days: int = 90
    fuzzy_threshold: float = 0.94
    reporting_lag_days: int = 20


def _alias_lookup(aliases: pd.DataFrame | None) -> dict[str, str]:
    if aliases is None or aliases.empty:
        return {}
    required = {"signal_name", "funding_issuer_name"}
    if not required.issubset(aliases.columns):
        raise ValueError("Alias file must contain signal_name and funding_issuer_name")
    return {
        normalize_company_name(row.signal_name): normalize_company_name(row.funding_issuer_name)
        for row in aliases.itertuples(index=False)
        if normalize_company_name(row.signal_name) and normalize_company_name(row.funding_issuer_name)
    }


def _build_prefix_index(names: list[str], width: int = 3) -> dict[str, list[str]]:
    index: dict[str, list[str]] = {}
    for name in names:
        if not name:
            continue
        key = name[:width]
        index.setdefault(key, []).append(name)
    return index


def build_90d_labels(
    signals: pd.DataFrame,
    events: pd.DataFrame,
    *,
    as_of: str | pd.Timestamp,
    aliases: pd.DataFrame | None = None,
    config: LabelConfig = LabelConfig(),
) -> pd.DataFrame:
    """Create leakage-resistant labels from timestamped funding events.

    A signal is positive when a matched funding event occurs strictly after the signal
    and on/before the prediction horizon. A negative is emitted only after both the
    prediction horizon and a reporting-lag buffer have elapsed. The lag is important
    for sources such as SEC Form D where a filing can arrive after the first sale.
    """
    required_signals = {"name", "snapshot_date"}
    required_events = {"issuer_name", "event_date"}
    if not required_signals.issubset(signals.columns):
        raise ValueError(f"Signals missing columns: {sorted(required_signals - set(signals.columns))}")
    if not required_events.issubset(events.columns):
        raise ValueError(f"Events missing columns: {sorted(required_events - set(events.columns))}")

    sig = signals.copy()
    evt = events.copy()
    sig["snapshot_date"] = pd.to_datetime(sig["snapshot_date"], errors="coerce", utc=True)
    evt["event_date"] = pd.to_datetime(evt["event_date"], errors="coerce", utc=True)
    sig = sig[sig["snapshot_date"].notna()].copy()
    evt = evt[evt["event_date"].notna()].copy()
    sig["normalized_name"] = sig["name"].map(normalize_company_name)
    evt["normalized_issuer"] = evt["issuer_name"].map(normalize_company_name)
    alias_map = _alias_lookup(aliases)
    as_of_ts = pd.to_datetime(as_of, utc=True)

    events_by_name: dict[str, list[pd.Series]] = {}
    for _, row in evt.sort_values("event_date").iterrows():
        events_by_name.setdefault(row["normalized_issuer"], []).append(row)

    all_event_names = [name for name in events_by_name if name]
    prefix_index = _build_prefix_index(all_event_names)
    match_cache: dict[str, tuple[str | None, str | None]] = {}

    def resolve_candidate(mapped: str) -> tuple[str | None, str | None]:
        if not mapped:
            return None, None
        if mapped in match_cache:
            return match_cache[mapped]
        if mapped in events_by_name:
            result = (mapped, "exact")
            match_cache[mapped] = result
            return result

        candidates = prefix_index.get(mapped[:3], []) if len(mapped) >= 3 else all_event_names
        best_name, best_score = None, 0.0
        for event_name in candidates:
            if min(len(mapped), len(event_name)) < 5:
                continue
            score = SequenceMatcher(None, mapped, event_name).ratio()
            if score > best_score:
                best_name, best_score = event_name, score
        if best_name and best_score >= config.fuzzy_threshold:
            result = (best_name, f"fuzzy:{best_score:.3f}")
        else:
            result = (None, None)
        match_cache[mapped] = result
        return result

    output: list[dict] = []
    horizon = timedelta(days=config.horizon_days)
    reporting_lag = timedelta(days=config.reporting_lag_days)

    for _, row in sig.iterrows():
        signal_name = row["normalized_name"]
        mapped = alias_map.get(signal_name, signal_name)
        candidate_name, match_method = resolve_candidate(mapped)

        start = row["snapshot_date"]
        end = start + horizon
        matched_event = None
        if candidate_name:
            for event in events_by_name.get(candidate_name, []):
                if start < event["event_date"] <= end:
                    matched_event = event
                    break

        labelled = row.to_dict()
        labelled["raised_funding_within_90d"] = None
        labelled["funding_event_date"] = None
        labelled["funding_amount"] = None
        labelled["funding_source"] = None
        labelled["match_method"] = match_method

        if matched_event is not None:
            labelled["raised_funding_within_90d"] = 1
            labelled["funding_event_date"] = matched_event["event_date"]
            labelled["funding_amount"] = matched_event.get("amount_sold")
            labelled["funding_source"] = matched_event.get("source", "unknown")
        elif end + reporting_lag <= as_of_ts:
            labelled["raised_funding_within_90d"] = 0

        output.append(labelled)

    result = pd.DataFrame(output)
    return result[result["raised_funding_within_90d"].notna()].copy()


def dedupe_funding_events(events: pd.DataFrame) -> pd.DataFrame:
    frame = events.copy()
    frame["event_date"] = pd.to_datetime(frame["event_date"], errors="coerce", utc=True)
    frame["normalized_issuer"] = frame["issuer_name"].map(normalize_company_name)
    subset = ["normalized_issuer", "event_date"]
    if "accession_number" in frame.columns:
        subset.append("accession_number")
    return frame.drop_duplicates(subset=subset).sort_values("event_date").reset_index(drop=True)
