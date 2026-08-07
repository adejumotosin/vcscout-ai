from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parents[1]
import sys
sys.path.insert(0, str(ROOT / "src"))

from vcscout.commercial import extract_commercial_signals, is_company_website_url  # noqa: E402
from vcscout.data import fetch_live_payload, flatten_startups  # noqa: E402

OUTPUT = ROOT / "data" / "commercial" / "live_commercial_signals.csv"
HISTORY = ROOT / "data" / "commercial" / "history" / "commercial_signals_history.csv"
STATUS = ROOT / "data" / "workflow_status" / "commercial_live_snapshot.csv"


def _fetch_one(row: dict[str, Any], timeout: int) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    name = str(row.get("name") or "Unknown")
    startup_key = str(row.get("startup_key") or name).lower().strip()
    url = str(row.get("website_url") or "").strip()
    base_status = {"name": name, "startup_key": startup_key, "website_url": url}
    if not url:
        return None, {**base_status, "status": "no_website", "detail": ""}
    if not is_company_website_url(url):
        return None, {**base_status, "status": "excluded_non_company_host", "detail": url[:300]}
    try:
        response = requests.get(
            url,
            timeout=timeout,
            allow_redirects=True,
            headers={"User-Agent": "VCScoutAI/0.5 commercial-snapshot"},
        )
        response.raise_for_status()
        if not is_company_website_url(response.url):
            return None, {**base_status, "status": "excluded_redirect_host", "detail": response.url[:300]}
        content_type = (response.headers.get("content-type") or "").lower()
        if "html" not in content_type and content_type:
            return None, {**base_status, "status": "non_html", "detail": content_type[:180]}
        signals = extract_commercial_signals(response.text)
        fetched_at = datetime.now(timezone.utc).isoformat()
        result = {
            "name": name,
            "startup_key": startup_key,
            "website_url": url,
            "resolved_url": response.url,
            "commercial_fetched_at": fetched_at,
            "http_status": response.status_code,
            **signals,
        }
        return result, {**base_status, "status": "ok", "detail": response.url[:300]}
    except Exception as exc:  # noqa: BLE001 - every external failure is auditable.
        return None, {**base_status, "status": "error", "detail": str(exc)[:400]}


def _attach_change_from_previous(result_df: pd.DataFrame, previous: pd.DataFrame | None) -> pd.DataFrame:
    result_df = result_df.copy()
    result_df["commercial_maturity_score"] = result_df["commercial_momentum_score"]
    result_df["previous_commercial_maturity_score"] = pd.NA
    result_df["commercial_maturity_change"] = pd.NA
    result_df["previous_commercial_fetched_at"] = pd.NA
    if previous is None or previous.empty or "startup_key" not in previous.columns:
        return result_df

    previous = previous.copy()
    previous["startup_key"] = previous["startup_key"].astype(str).str.lower().str.strip()
    previous_score_col = (
        "commercial_maturity_score"
        if "commercial_maturity_score" in previous.columns
        else "commercial_momentum_score"
    )
    if previous_score_col not in previous.columns:
        return result_df
    keep = ["startup_key", previous_score_col]
    if "commercial_fetched_at" in previous.columns:
        keep.append("commercial_fetched_at")
    previous = previous[keep].drop_duplicates("startup_key", keep="last")
    previous = previous.rename(
        columns={
            previous_score_col: "previous_commercial_maturity_score",
            "commercial_fetched_at": "previous_commercial_fetched_at",
        }
    )
    result_df = result_df.drop(
        columns=[
            "previous_commercial_maturity_score",
            "commercial_maturity_change",
            "previous_commercial_fetched_at",
        ]
    ).merge(previous, on="startup_key", how="left")

    current_time = pd.to_datetime(result_df["commercial_fetched_at"], errors="coerce", utc=True)
    prior_time = pd.to_datetime(result_df.get("previous_commercial_fetched_at"), errors="coerce", utc=True)
    different_day = current_time.dt.date != prior_time.dt.date
    current_score = pd.to_numeric(result_df["commercial_maturity_score"], errors="coerce")
    prior_score = pd.to_numeric(result_df["previous_commercial_maturity_score"], errors="coerce")
    result_df["commercial_maturity_change"] = (current_score - prior_score).where(different_day)
    return result_df


def _append_history(result_df: pd.DataFrame) -> None:
    history_cols = [
        "name",
        "startup_key",
        "website_url",
        "resolved_url",
        "commercial_fetched_at",
        "commercial_maturity_score",
        "commercial_momentum_score",
        "commercial_signal_count",
        "pricing_signal",
        "customer_evidence_signal",
        "enterprise_signal",
        "careers_signal",
        "security_signal",
        "integrations_signal",
        "developer_docs_signal",
        "self_serve_signal",
        "sales_motion_signal",
        "page_word_count",
        "page_link_count",
    ]
    current = result_df[[column for column in history_cols if column in result_df.columns]].copy()
    current["snapshot_date"] = pd.to_datetime(
        current["commercial_fetched_at"], errors="coerce", utc=True
    ).dt.strftime("%Y-%m-%d")
    if HISTORY.exists():
        try:
            history = pd.read_csv(HISTORY)
        except (OSError, pd.errors.ParserError):
            history = pd.DataFrame()
        current = pd.concat([history, current], ignore_index=True, sort=False)
    current = current.drop_duplicates(["startup_key", "snapshot_date"], keep="last")
    HISTORY.parent.mkdir(parents=True, exist_ok=True)
    current.to_csv(HISTORY, index=False)


def main() -> None:
    parser = argparse.ArgumentParser(description="Snapshot public website commercial-maturity signals for the live VCScout universe.")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--timeout", type=int, default=15)
    args = parser.parse_args()

    previous = None
    if OUTPUT.exists():
        try:
            previous = pd.read_csv(OUTPUT)
        except (OSError, pd.errors.ParserError):
            previous = None

    payload = fetch_live_payload()
    frame = flatten_startups(payload)
    frame = frame.sort_values("name").drop_duplicates("startup_key", keep="first")
    if args.limit:
        frame = frame.head(args.limit)

    rows = frame.to_dict(orient="records")
    results: list[dict[str, Any]] = []
    statuses: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=max(1, min(args.workers, 16))) as pool:
        futures = {pool.submit(_fetch_one, row, args.timeout): row for row in rows}
        for i, future in enumerate(as_completed(futures), 1):
            result, status = future.result()
            if result:
                results.append(result)
            statuses.append(status)
            print(f"[{i}/{len(rows)}] {status['name']} -> {status['status']}")

    result_df = _attach_change_from_previous(pd.DataFrame(results), previous)
    status_df = pd.DataFrame(statuses)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    STATUS.parent.mkdir(parents=True, exist_ok=True)
    result_df.to_csv(OUTPUT, index=False)
    status_df.to_csv(STATUS, index=False)
    _append_history(result_df)

    ok = int((status_df["status"] == "ok").sum()) if not status_df.empty else 0
    print(f"Snapshotted {ok}/{len(status_df)} public company websites with commercial maturity signals.")


if __name__ == "__main__":
    main()
