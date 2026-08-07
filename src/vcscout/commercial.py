from __future__ import annotations

import re
from functools import lru_cache
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Mapping

import numpy as np
import pandas as pd


class _PageParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.text_parts: list[str] = []
        self.links: list[str] = []
        self._suppressed = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"script", "style", "noscript", "svg"}:
            self._suppressed += 1
        if tag == "a":
            for key, value in attrs:
                if key.lower() == "href" and value:
                    self.links.append(value.strip())

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "noscript", "svg"} and self._suppressed:
            self._suppressed -= 1

    def handle_data(self, data: str) -> None:
        if not self._suppressed:
            value = re.sub(r"\s+", " ", data).strip()
            if value:
                self.text_parts.append(value)


SIGNAL_WEIGHTS: dict[str, float] = {
    "pricing_signal": 18.0,
    "customer_evidence_signal": 20.0,
    "enterprise_signal": 14.0,
    "careers_signal": 10.0,
    "security_signal": 12.0,
    "integrations_signal": 9.0,
    "developer_docs_signal": 5.0,
    "self_serve_signal": 6.0,
    "sales_motion_signal": 6.0,
}

_PATTERNS: dict[str, tuple[str, ...]] = {
    "pricing_signal": ("pricing", "/pricing", "plans and pricing"),
    "customer_evidence_signal": (
        "customers",
        "customer stories",
        "case studies",
        "case study",
        "trusted by",
        "/customers",
        "/case-studies",
        "/case_studies",
    ),
    "enterprise_signal": ("enterprise", "/enterprise", "for enterprise"),
    "careers_signal": ("careers", "jobs", "we're hiring", "we are hiring", "join our team", "/careers", "/jobs"),
    "security_signal": (
        "soc 2",
        "soc2",
        "iso 27001",
        "trust center",
        "security",
        "gdpr",
        "/security",
        "/trust",
    ),
    "integrations_signal": ("integrations", "marketplace", "/integrations", "/marketplace"),
    "developer_docs_signal": ("documentation", "developer docs", "api reference", "/docs", "/developers"),
    "self_serve_signal": ("start free", "free trial", "sign up", "signup", "get started", "try for free"),
    "sales_motion_signal": ("contact sales", "talk to sales", "book a demo", "request a demo", "schedule a demo"),
}

LIVE_SIGNALS_PATH = Path(__file__).resolve().parents[2] / "data" / "commercial" / "live_commercial_signals.csv"


def extract_commercial_signals(html: str | bytes | None) -> dict[str, float]:
    """Extract conservative commercial-maturity indicators from one HTML page.

    Signals are intentionally simple and auditable. They indicate visible go-to-market
    infrastructure, not revenue, valuation, or the probability of fundraising.
    """
    if html is None:
        html = ""
    if isinstance(html, bytes):
        html = html.decode("utf-8", errors="replace")

    parser = _PageParser()
    try:
        parser.feed(str(html))
    except Exception:  # malformed archived HTML should degrade to partial evidence.
        pass

    text = " ".join(parser.text_parts).lower()
    links = " ".join(parser.links).lower()
    evidence = f"{text} {links}"

    result: dict[str, float] = {}
    for signal, patterns in _PATTERNS.items():
        result[signal] = 1.0 if any(pattern in evidence for pattern in patterns) else 0.0

    result["commercial_signal_count"] = float(sum(result[name] for name in SIGNAL_WEIGHTS))
    result["commercial_momentum_score"] = round(
        sum(result[name] * weight for name, weight in SIGNAL_WEIGHTS.items()), 1
    )
    result["page_word_count"] = float(len(text.split()))
    result["page_link_count"] = float(len(parser.links))
    return result


def commercial_feature_dict(row: Mapping[str, Any]) -> dict[str, float]:
    """Return the stable feature set used by historical/live commercial models."""
    features = {name: float(row.get(name) or 0.0) for name in SIGNAL_WEIGHTS}
    features["commercial_signal_count"] = float(row.get("commercial_signal_count") or 0.0)
    return features


@lru_cache(maxsize=1)
def load_live_commercial_signals() -> pd.DataFrame | None:
    if not LIVE_SIGNALS_PATH.exists():
        return None
    try:
        frame = pd.read_csv(LIVE_SIGNALS_PATH)
    except (OSError, pd.errors.ParserError):
        return None
    if "startup_key" not in frame.columns:
        return None
    frame["startup_key"] = frame["startup_key"].astype(str).str.lower().str.strip()
    return frame


def attach_commercial_momentum(frame: pd.DataFrame) -> pd.DataFrame:
    """Attach current website-derived commercial maturity signals to the live universe."""
    result = frame.copy()
    live = load_live_commercial_signals()
    if live is None or live.empty or result.empty:
        result["commercial_momentum_score"] = np.nan
        result["commercial_signal_count"] = np.nan
        result["commercial_signal_status"] = "unavailable"
        return result

    cols = [
        "startup_key",
        "commercial_momentum_score",
        "commercial_signal_count",
        *SIGNAL_WEIGHTS.keys(),
        "commercial_fetched_at",
    ]
    available = [column for column in cols if column in live.columns]
    live = live[available].drop_duplicates("startup_key", keep="last")
    result = result.merge(live, on="startup_key", how="left")
    result["commercial_signal_status"] = np.where(
        result["commercial_momentum_score"].notna(), "observed", "unavailable"
    )
    return result


def commercial_data_status() -> dict[str, Any]:
    live = load_live_commercial_signals()
    if live is None or live.empty:
        return {
            "available": False,
            "status": "unavailable",
            "message": "Live commercial website signals have not been snapshotted yet.",
        }
    fetched = None
    if "commercial_fetched_at" in live.columns:
        values = live["commercial_fetched_at"].dropna().astype(str)
        fetched = values.max() if not values.empty else None
    return {
        "available": True,
        "status": "website_observation",
        "profiles": int(live["startup_key"].nunique()),
        "fetched_at": fetched,
        "output": "transparent commercial maturity score, not funding probability",
        "message": "The score reflects visible go-to-market infrastructure on public company websites.",
    }
