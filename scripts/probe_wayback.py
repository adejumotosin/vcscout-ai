from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "data" / "workflow_status" / "wayback_probe.json"
CDX = "https://web.archive.org/cdx/search/cdx"

CASES = [
    {"company": "Strapi", "url": "https://strapi.io/", "to": "20210812000000"},
    {"company": "PostHog", "url": "https://posthog.com/", "to": "20210831000000"},
    {"company": "n8n", "url": "https://n8n.io/", "to": "20211027000000"},
]


def query(case: dict) -> dict:
    session = requests.Session()
    session.headers.update({"User-Agent": "VCScoutAI/0.5 historical-archive-probe"})
    attempts = []
    for url in [case["url"], case["url"].replace("https://", "http://")]:
        try:
            response = session.get(
                CDX,
                params={
                    "url": url,
                    "output": "json",
                    "fl": "timestamp,original,statuscode,mimetype",
                    "filter": ["statuscode:200", "mimetype:text/html"],
                    "to": case["to"],
                    "limit": -3,
                },
                timeout=8,
            )
            attempts.append({"url": url, "status_code": response.status_code, "body_prefix": response.text[:180]})
            if response.ok:
                payload = response.json()
                if isinstance(payload, list) and len(payload) > 1:
                    header = payload[0]
                    rows = [dict(zip(header, row)) for row in payload[1:] if isinstance(row, list)]
                    return {**case, "status": "ok", "captures": rows[-3:], "attempts": attempts}
        except Exception as exc:  # noqa: BLE001
            attempts.append({"url": url, "error": str(exc)[:300]})
    return {**case, "status": "unavailable", "captures": [], "attempts": attempts}


def main() -> None:
    results = [query(case) for case in CASES]
    payload = {
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "successful_cases": sum(item["status"] == "ok" for item in results),
        "cases": results,
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(payload, indent=2))
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
