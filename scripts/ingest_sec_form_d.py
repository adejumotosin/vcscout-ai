from __future__ import annotations

import argparse
import io
import sys
import zipfile
from pathlib import Path

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from vcscout.outcomes import dedupe_funding_events  # noqa: E402

OUTPUT = ROOT / "data" / "funding_events" / "sec_form_d_events.csv"
SEC_URLS = [
    "https://www.sec.gov/files/datastandardsinnovation/data/form-d-data-sets/{year}q{quarter}_d.zip",
    "https://www.sec.gov/files/structureddata/data/form-d-data-sets/{year}q{quarter}_d.zip",
]


def _read_table(zf: zipfile.ZipFile, stem: str) -> pd.DataFrame:
    matches = [name for name in zf.namelist() if stem.upper() in Path(name).name.upper()]
    if not matches:
        raise FileNotFoundError(f"Could not find {stem} table in SEC ZIP")
    with zf.open(matches[0]) as handle:
        return pd.read_csv(handle, sep="\t", dtype=str, low_memory=False, encoding="utf-8")


def _money(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series.replace({"Indefinite": None, "": None}), errors="coerce")


def _download_zip(year: int, quarter: int, user_agent: str) -> bytes:
    headers = {
        "User-Agent": user_agent,
        "Accept-Encoding": "gzip, deflate",
        "Accept": "application/zip, application/octet-stream, */*",
    }
    attempts: list[str] = []
    for template in SEC_URLS:
        url = template.format(year=year, quarter=quarter)
        response = requests.get(url, timeout=90, headers=headers)
        if response.ok:
            print(f"Downloaded SEC Form D {year}Q{quarter} from {url}")
            return response.content
        attempts.append(f"{response.status_code} {url}")
        if response.status_code not in {404, 410}:
            response.raise_for_status()
    raise FileNotFoundError(
        f"SEC Form D ZIP not found for {year}Q{quarter}; attempts: {'; '.join(attempts)}"
    )


def download_quarter(year: int, quarter: int, user_agent: str) -> pd.DataFrame:
    content = _download_zip(year, quarter, user_agent)

    with zipfile.ZipFile(io.BytesIO(content)) as zf:
        submissions = _read_table(zf, "FORMDSUBMISSION")
        issuers = _read_table(zf, "ISSUERS")
        offerings = _read_table(zf, "OFFERING")

    primary = issuers.copy()
    if "IS_PRIMARYISSUER_FLAG" in primary.columns:
        mask = primary["IS_PRIMARYISSUER_FLAG"].astype(str).str.upper().isin({"Y", "YES", "TRUE", "1"})
        if mask.any():
            primary = primary[mask]
    primary = primary.drop_duplicates("ACCESSIONNUMBER", keep="first")

    merged = submissions.merge(primary, on="ACCESSIONNUMBER", how="inner", suffixes=("", "_issuer"))
    merged = merged.merge(offerings, on="ACCESSIONNUMBER", how="left", suffixes=("", "_offering"))

    filing_date = pd.to_datetime(merged.get("FILING_DATE"), errors="coerce", utc=True)
    sale_date = pd.to_datetime(merged.get("SALE_DATE"), errors="coerce", utc=True)
    event_date = sale_date.where(sale_date.notna(), filing_date)

    output = pd.DataFrame(
        {
            "issuer_name": merged.get("ENTITYNAME"),
            "event_date": event_date,
            "filing_date": filing_date,
            "sale_date": sale_date,
            "cik": merged.get("CIK"),
            "accession_number": merged.get("ACCESSIONNUMBER"),
            "industry_group": merged.get("INDUSTRYGROUPTYPE"),
            "is_equity": merged.get("ISEQUITYTYPE"),
            "is_debt": merged.get("ISDEBTTYPE"),
            "offering_amount": _money(merged.get("TOTALOFFERINGAMOUNT", pd.Series(index=merged.index, dtype=object))),
            "amount_sold": _money(merged.get("TOTALAMOUNTSOLD", pd.Series(index=merged.index, dtype=object))),
            "investors": pd.to_numeric(merged.get("TOTALNUMBERALREADYINVESTED"), errors="coerce"),
            "source": "SEC Form D",
            "source_quarter": f"{year}Q{quarter}",
        }
    )
    return output[output["issuer_name"].notna() & output["event_date"].notna()].copy()


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest public SEC Form D quarterly data into VCScout funding events.")
    parser.add_argument("--year", type=int, required=True)
    parser.add_argument("--quarter", type=int, choices=[1, 2, 3, 4], required=True)
    parser.add_argument(
        "--user-agent",
        required=True,
        help="SEC-compliant identity string, e.g. 'VCScoutAI research your-email@example.com'",
    )
    args = parser.parse_args()

    new_events = download_quarter(args.year, args.quarter, args.user_agent)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    if OUTPUT.exists():
        existing = pd.read_csv(OUTPUT)
        combined = pd.concat([existing, new_events], ignore_index=True)
    else:
        combined = new_events
    combined = dedupe_funding_events(combined)
    combined.to_csv(OUTPUT, index=False)
    print(f"Added {len(new_events)} Form D filings; funding-event store now has {len(combined)} rows.")


if __name__ == "__main__":
    main()
