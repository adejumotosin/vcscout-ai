from __future__ import annotations

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import PlainTextResponse

from .commercial import commercial_data_status
from .pattern import historical_pattern_status
from .probability import model_status
from .research import build_research_report, research_report_markdown
from .service import get_ranked_startups

app = FastAPI(
    title="VCScout AI API",
    version="0.5.1",
    description="Alternative-data venture intelligence API for engineering momentum, website-derived commercial maturity, historical funding-pattern ranking and diligence research.",
)


def _startup_row(startup_name: str) -> dict:
    df, _ = get_ranked_startups()
    match = df[df["name"].str.lower() == startup_name.lower()]
    if match.empty:
        raise HTTPException(status_code=404, detail="Startup not found")
    row = match.iloc[0].where(match.iloc[0].notna(), None)
    return row.to_dict()


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/meta")
def meta(refresh: bool = False) -> dict:
    _, metadata = get_ranked_startups(force_refresh=refresh)
    return metadata


@app.get("/model")
def funding_model() -> dict:
    """Prospective 90-day probability model status."""
    return model_status()


@app.get("/pattern-model")
def funding_pattern_model() -> dict:
    """Historical matched case-control ranker validation and semantics."""
    return historical_pattern_status()


@app.get("/commercial-signals")
def commercial_signals() -> dict:
    """Current public-website commercial-maturity dataset status."""
    return commercial_data_status()


@app.get("/startups")
def startups(
    limit: int = Query(25, ge=1, le=200),
    sector: str | None = None,
    geography: str | None = None,
    stage: str | None = None,
    min_score: float = Query(0, ge=0, le=100),
    min_commercial_score: float = Query(0, ge=0, le=100),
    min_pattern_index: float = Query(0, ge=0, le=100),
    refresh: bool = False,
) -> list[dict]:
    df, _ = get_ranked_startups(force_refresh=refresh)
    filtered = df[df["vc_scout_score"] >= min_score]
    if "commercial_maturity_score" in filtered.columns and min_commercial_score > 0:
        filtered = filtered[filtered["commercial_maturity_score"] >= min_commercial_score]
    if "funding_pattern_index" in filtered.columns and min_pattern_index > 0:
        filtered = filtered[filtered["funding_pattern_index"] >= min_pattern_index]
    if sector:
        filtered = filtered[filtered["sector"].str.lower() == sector.lower()]
    if geography:
        filtered = filtered[filtered["geography"].str.lower() == geography.lower()]
    if stage:
        filtered = filtered[filtered["stage"].str.lower() == stage.lower()]

    cols = [
        "name", "description", "sector", "stage", "geography", "vc_scout_score",
        "commercial_maturity_score", "commercial_momentum_score", "commercial_signal_count", "commercial_signal_status",
        "pricing_signal", "customer_evidence_signal", "enterprise_signal", "careers_signal",
        "security_signal", "integrations_signal", "developer_docs_signal", "self_serve_signal",
        "sales_motion_signal", "funding_pattern_index", "funding_pattern_model_status",
        "funding_probability_90d", "funding_model_status", "momentum_flag", "top_driver",
        "risk_flag", "commit_velocity_14d", "commit_velocity_change", "contributors",
        "contributor_growth", "new_repos_30d", "signal_type", "github_url",
        "website_url", "profile_url",
    ]
    available = [column for column in cols if column in filtered.columns]
    return filtered.head(limit)[available].where(filtered[available].notna(), None).to_dict(orient="records")


@app.get("/startups/{startup_name}")
def startup_detail(startup_name: str) -> dict:
    return _startup_row(startup_name)


@app.get("/research/{startup_name}")
def research_report(startup_name: str) -> dict:
    return build_research_report(_startup_row(startup_name))


@app.get("/research/{startup_name}/markdown", response_class=PlainTextResponse)
def research_report_md(startup_name: str) -> PlainTextResponse:
    report = build_research_report(_startup_row(startup_name))
    return PlainTextResponse(
        research_report_markdown(report),
        headers={"Content-Disposition": f'attachment; filename="vcscout-{startup_name}-memo.md"'},
    )


@app.get("/watchlist/brief")
def watchlist_brief(names: str = Query(..., description="Comma-separated organisation names")) -> dict:
    requested = [name.strip() for name in names.split(",") if name.strip()]
    if not requested:
        raise HTTPException(status_code=400, detail="At least one organisation name is required")
    if len(requested) > 30:
        raise HTTPException(status_code=400, detail="Watchlist brief is limited to 30 organisations")

    df, metadata = get_ranked_startups()
    lower_map = {str(row["name"]).lower(): row for row in df.to_dict(orient="records")}
    reports, missing = [], []
    for name in requested:
        row = lower_map.get(name.lower())
        if row is None:
            missing.append(name)
        else:
            reports.append(build_research_report(row))
    return {
        "count": len(reports),
        "missing": missing,
        "source_period": metadata.get("period"),
        "commercial_signals": commercial_data_status(),
        "funding_pattern_model": historical_pattern_status(),
        "funding_model": model_status(),
        "reports": reports,
    }
