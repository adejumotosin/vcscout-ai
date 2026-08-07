from __future__ import annotations

import re
from html.parser import HTMLParser
from typing import Any, Mapping


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
