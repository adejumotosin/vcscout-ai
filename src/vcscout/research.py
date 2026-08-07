from __future__ import annotations

from typing import Any, Mapping


def _n(value: Any, digits: int = 0) -> str:
    try:
        return f"{float(value):,.{digits}f}"
    except (TypeError, ValueError):
        return "n/a"


def _signed(value: Any) -> str:
    try:
        number = float(value)
        return f"{number:+.0f}%"
    except (TypeError, ValueError):
        return "n/a"


def _finite(value: Any) -> bool:
    if value is None:
        return False
    try:
        number = float(value)
        return number == number
    except (TypeError, ValueError):
        return False


def _ordinal(value: Any) -> str:
    try:
        number = int(round(float(value)))
    except (TypeError, ValueError):
        return "n/a"
    suffix = "th" if 10 <= number % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(number % 10, "th")
    return f"{number}{suffix}"


_COMMERCIAL_LABELS = {
    "pricing_signal": "pricing",
    "customer_evidence_signal": "customer/case-study evidence",
    "enterprise_signal": "enterprise positioning",
    "careers_signal": "careers/hiring",
    "security_signal": "security/compliance",
    "integrations_signal": "integrations/marketplace",
    "developer_docs_signal": "developer documentation",
    "self_serve_signal": "self-serve signup/trial",
    "sales_motion_signal": "sales/demo motion",
}


def build_research_report(row: Mapping[str, Any]) -> dict[str, Any]:
    score = float(row.get("vc_scout_score") or 0.0)
    probability = row.get("funding_probability_90d")
    probability_available = _finite(probability)
    pattern_index = row.get("funding_pattern_index")
    pattern_available = _finite(pattern_index)
    commercial_score = row.get("commercial_momentum_score")
    commercial_available = _finite(commercial_score)

    commit_change = float(row.get("commit_velocity_change") or 0.0)
    contributor_growth = float(row.get("contributor_growth") or 0.0)
    new_repos = float(row.get("new_repos_30d") or 0.0)
    contributors = float(row.get("contributors") or 0.0)

    positives: list[str] = []
    if commit_change >= 50:
        positives.append(f"Commit velocity accelerated {_signed(commit_change)} versus the prior 14-day window.")
    if contributor_growth >= 30:
        positives.append(f"Contributor growth is {_signed(contributor_growth)}, consistent with a meaningful expansion in public engineering activity.")
    if new_repos >= 3:
        positives.append(f"The organisation created {_n(new_repos)} public repositories in the last 30 days.")
    if contributors >= 10:
        positives.append(f"The observed public engineering surface includes approximately {_n(contributors)} contributors.")
    if commercial_available:
        visible = [label for key, label in _COMMERCIAL_LABELS.items() if float(row.get(key) or 0.0) > 0]
        evidence_text = ", ".join(visible[:6]) if visible else "limited visible go-to-market infrastructure"
        positives.append(
            f"Its Commercial Momentum Score is {float(commercial_score):.1f}/100 based on public website evidence including {evidence_text}."
        )
    if pattern_available:
        positives.append(
            f"Its Historical Funding Pattern Index is {float(pattern_index):.1f}/100, meaning its current public-engineering pattern ranks near the {_ordinal(pattern_index)} percentile of the live comparison universe under VCScout's historical case-control ranker."
        )
    if not positives:
        positives.append("The company is ranked primarily by its relative position within the current VCScout universe rather than one dominant breakout metric.")

    risks: list[str] = []
    if row.get("risk_flag") and row.get("risk_flag") != "None":
        risks.append(str(row.get("risk_flag")))
    if str(row.get("geography") or "").lower() == "unknown":
        risks.append("Geography is unresolved in the source feed and should be verified before market or regulatory diligence.")
    if not row.get("website_url"):
        risks.append("No company website is attached to the source record; entity verification is required.")
    risks.append("Public GitHub activity can understate teams that build mainly in private repositories and can overstate momentum around open-source launches.")
    if commercial_available:
        risks.append("The Commercial Momentum Score detects visible website go-to-market infrastructure; it does not verify revenue, customer counts, bookings or enterprise contract value.")
    if pattern_available:
        risks.append("The Historical Funding Pattern Index is a relative ranking from a matched historical case-control backtest; it is not a calibrated probability or evidence that a financing event will occur.")
    if not probability_available:
        risks.append("VCScout is withholding a 90-day funding probability until a prospective outcome model has sufficient population-calibrated labels and temporal validation.")

    questions = [
        "What product or release explains the engineering acceleration, and is it tied to customer demand?",
        "Is contributor growth driven by employees, community contributors, contractors, or a one-off open-source event?",
        "What evidence exists for revenue, retention, usage growth, enterprise pilots, or another commercial traction metric?",
        "Do the pricing, customer, security and sales signals visible on the website reflect active adoption or mainly positioning?",
        "Has the company recently hired senior engineering, product, sales, or finance leadership consistent with a financing cycle?",
        "Are there public financing filings, press releases, investor announcements, or corporate registrations that corroborate a raise?",
    ]

    thesis = (
        f"{row.get('name', 'This organisation')} is a {row.get('stage') or 'venture-stage'} "
        f"{row.get('sector') or 'company'} with a VC Scout Score of {score:.1f}/100. "
        f"Its current signal is {row.get('signal_type') or 'unclassified'}, led by {str(row.get('top_driver') or 'relative engineering momentum').lower()}."
    )
    if commercial_available:
        thesis += f" Its Commercial Momentum Score is {float(commercial_score):.1f}/100, measuring visible go-to-market maturity on its public website."
    if pattern_available:
        thesis += f" Its Historical Funding Pattern Index is {float(pattern_index):.1f}/100, a relative historical-pattern percentile rather than a probability."
    if probability_available:
        thesis += f" The prospectively validated model estimates a {float(probability):.1f}% probability of a funding event within 90 days."
    else:
        thesis += " A true 90-day funding-event probability is intentionally not shown because the prospective outcome model is not yet validated."

    return {
        "name": row.get("name"),
        "generated_from": "VCScout public engineering signals, public website commercial signals and historical funding-pattern validation",
        "thesis": thesis,
        "score": score,
        "commercial_momentum_score": float(commercial_score) if commercial_available else None,
        "funding_pattern_index": float(pattern_index) if pattern_available else None,
        "funding_probability_90d": float(probability) if probability_available else None,
        "signal": row.get("signal_type"),
        "momentum": row.get("momentum_flag"),
        "evidence": positives,
        "risks": risks,
        "diligence_questions": questions,
        "links": {
            "github": row.get("github_url"),
            "website": row.get("website_url"),
            "source_profile": row.get("profile_url"),
        },
    }


def research_report_markdown(report: Mapping[str, Any]) -> str:
    probability = report.get("funding_probability_90d")
    probability_text = f"{float(probability):.1f}%" if probability is not None else "Withheld pending prospectively validated outcome model"
    pattern = report.get("funding_pattern_index")
    pattern_text = f"{float(pattern):.1f}/100 percentile index" if pattern is not None else "Unavailable"
    commercial = report.get("commercial_momentum_score")
    commercial_text = f"{float(commercial):.1f}/100" if commercial is not None else "Unavailable"
    evidence = "\n".join(f"- {item}" for item in report.get("evidence", []))
    risks = "\n".join(f"- {item}" for item in report.get("risks", []))
    questions = "\n".join(f"- {item}" for item in report.get("diligence_questions", []))
    links = report.get("links", {}) or {}
    link_lines = "\n".join(f"- {name.replace('_', ' ').title()}: {url}" for name, url in links.items() if url)
    return f"""# VCScout Research Memo: {report.get('name')}

## Investment-sourcing thesis
{report.get('thesis')}

## Signal snapshot
- VC Scout Score: {float(report.get('score') or 0):.1f}/100
- Commercial Momentum Score: {commercial_text}
- Historical Funding Pattern Index: {pattern_text}
- Funding probability (90d): {probability_text}
- Signal: {report.get('signal') or 'n/a'}
- Momentum: {report.get('momentum') or 'n/a'}

## Evidence
{evidence}

## Risks and caveats
{risks}

## Diligence questions
{questions}

## Source links
{link_lines or '- No source links available.'}

---
Generated from public VCScout engineering and website signals. The Commercial Momentum Score is a transparent maturity heuristic, while the Historical Funding Pattern Index is a relative ranking from a matched historical backtest; neither is a funding probability. This memo is for research prioritisation, not investment advice.
"""
