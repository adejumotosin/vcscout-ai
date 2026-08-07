from __future__ import annotations

import argparse
import re
from pathlib import Path
from urllib.parse import urlparse

import pandas as pd
import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
OUTPUT_ALL = ROOT / "data" / "funding_events" / "gitdealflow_validated_receipts.csv"
OUTPUT_FUNDING = ROOT / "data" / "funding_events" / "gitdealflow_validated_funding_receipts.csv"
WINS_URL = "https://signals.gitdealflow.com/wins"

DATE_RE = re.compile(
    r"\b(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{1,2},\s+\d{4}\b"
)
FUNDING_RE = re.compile(
    r"(?:\bseed\b|\bseries\s+[a-e]\b|\brais(?:e|ed|ing)\b|\bfund(?:ing|raise)\b)",
    re.IGNORECASE,
)
EXCLUDE_RE = re.compile(
    r"(?:acquisition|acquired|mass adoption|breakout adoption|commercial release|tender offer)",
    re.IGNORECASE,
)


def _repo_parts(href: str) -> tuple[str, str] | None:
    parsed = urlparse(href)
    if parsed.netloc.lower() not in {"github.com", "www.github.com"}:
        return None
    parts = [p for p in parsed.path.split("/") if p]
    if len(parts) < 2:
        return None
    return parts[0], parts[1]


def _small_receipt_container(anchor) -> object | None:
    node = anchor
    for _ in range(8):
        node = getattr(node, "parent", None)
        if node is None:
            return None
        text = " ".join(node.stripped_strings)
        github_links = [
            a for a in node.find_all("a", href=True)
            if _repo_parts(a.get("href", "")) is not None
        ]
        if len(github_links) == 1 and DATE_RE.search(text) and len(text) <= 700:
            return node
    return None


def _extract_company(anchor, container, owner: str) -> str:
    text_nodes = list(container.stripped_strings)
    anchor_text = " ".join(anchor.stripped_strings).strip()
    # The receipt card usually renders the company label immediately before the repo link.
    for i, text in enumerate(text_nodes):
        if anchor_text and anchor_text in text:
            if i > 0 and text_nodes[i - 1].strip():
                return text_nodes[i - 1].strip()
    return owner


def import_receipts(url: str = WINS_URL) -> tuple[pd.DataFrame, pd.DataFrame]:
    response = requests.get(
        url,
        timeout=60,
        headers={"User-Agent": "VCScoutAI/0.3 public-research"},
    )
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")

    rows: list[dict] = []
    for anchor in soup.find_all("a", href=True):
        parts = _repo_parts(anchor.get("href", ""))
        if parts is None:
            continue
        container = _small_receipt_container(anchor)
        if container is None:
            continue

        owner, repo = parts
        text = " ".join(container.stripped_strings)
        date_match = DATE_RE.search(text)
        if not date_match:
            continue
        event_date = pd.to_datetime(date_match.group(0), errors="coerce", utc=True)
        if pd.isna(event_date):
            continue

        company = _extract_company(anchor, container, owner)
        # Remove the company/repo/date tokens from the card text to retain a compact event description.
        event_text = text
        for token in [company, " ".join(anchor.stripped_strings), date_match.group(0)]:
            if token:
                event_text = event_text.replace(token, " ")
        event_text = re.sub(r"\s+", " ", event_text).strip(" ·-|:")

        is_funding = bool(FUNDING_RE.search(event_text)) and not bool(EXCLUDE_RE.search(event_text))
        rows.append(
            {
                "company": company,
                "github_owner": owner,
                "github_repo": repo,
                "github_url": f"https://github.com/{owner}/{repo}",
                "event_date": event_date,
                "event_text": event_text,
                "is_funding_event": is_funding,
                "source": "VC Deal Flow Signal Underwriting Receipts",
                "source_url": url,
            }
        )

    frame = pd.DataFrame(rows)
    if frame.empty:
        raise RuntimeError("No validated receipts could be parsed from the public ledger")

    frame = (
        frame.sort_values(["event_date", "company", "github_url"])
        .drop_duplicates(["github_url", "event_date", "event_text"], keep="first")
        .reset_index(drop=True)
    )
    funding = frame[frame["is_funding_event"]].copy().reset_index(drop=True)
    return frame, funding


def main() -> None:
    parser = argparse.ArgumentParser(description="Import the public GitDealFlow validated-receipts ledger.")
    parser.add_argument("--url", default=WINS_URL)
    args = parser.parse_args()

    all_receipts, funding = import_receipts(args.url)
    OUTPUT_ALL.parent.mkdir(parents=True, exist_ok=True)
    all_receipts.to_csv(OUTPUT_ALL, index=False)
    funding.to_csv(OUTPUT_FUNDING, index=False)
    print(
        f"Imported {len(all_receipts)} unique validated receipt rows, including "
        f"{len(funding)} funding-labelled rows. Funding dates span "
        f"{funding['event_date'].min()} to {funding['event_date'].max()}."
    )


if __name__ == "__main__":
    main()
