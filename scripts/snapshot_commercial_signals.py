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

from vcscout.commercial import extract_commercial_signals  # noqa: E402
from vcscout.data import fetch_live_payload, flatten_startups  # noqa: E402

OUTPUT = ROOT / "data" / "commercial" / "live_commercial_signals.csv"
STATUS = ROOT / "data" / "workflow_status" / "commercial_live_snapshot.csv"


def _fetch_one(row: dict[str, Any], timeout: int) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    name = str(row.get("name") or "Unknown")
    startup_key = str(row.get("startup_key") or name).lower().strip()
    url = str(row.get("website_url") or "").strip()
    base_status = {"name": name, "startup_key": startup_key, "website_url": url}
    if not url:
        return None, {**base_status, "status": "no_website", "detail": ""}
    try:
        response = requests.get(
            url,
            timeout=timeout,
            allow_redirects=True,
            headers={"User-Agent": "VCScoutAI/0.4 commercial-snapshot"},
        )
        response.raise_for_status()
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


def main() -> None:
    parser = argparse.ArgumentParser(description="Snapshot public website commercial-maturity signals for the live VCScout universe.")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--timeout", type=int, default=15)
    args = parser.parse_args()

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

    result_df = pd.DataFrame(results)
    status_df = pd.DataFrame(statuses)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    STATUS.parent.mkdir(parents=True, exist_ok=True)
    result_df.to_csv(OUTPUT, index=False)
    status_df.to_csv(STATUS, index=False)

    ok = int((status_df["status"] == "ok").sum()) if not status_df.empty else 0
    print(f"Snapshotted {ok}/{len(status_df)} public company websites with commercial maturity signals.")


if __name__ == "__main__":
    main()
