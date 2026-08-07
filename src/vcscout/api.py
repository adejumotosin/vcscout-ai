from __future__ import annotations

from fastapi import FastAPI, HTTPException, Query

from .service import get_ranked_startups

app = FastAPI(
    title="VCScout AI API",
    version="0.1.0",
    description="Alternative-data sourcing API for ranking engineering momentum in venture-stage organisations.",
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/meta")
def meta() -> dict:
    _, metadata = get_ranked_startups()
    return metadata


@app.get("/startups")
def startups(
    limit: int = Query(25, ge=1, le=200),
    sector: str | None = None,
    geography: str | None = None,
    stage: str | None = None,
    min_score: float = Query(0, ge=0, le=100),
) -> list[dict]:
    df, _ = get_ranked_startups()
    filtered = df[df["vc_scout_score"] >= min_score]
    if sector:
        filtered = filtered[filtered["sector"].str.lower() == sector.lower()]
    if geography:
        filtered = filtered[filtered["geography"].str.lower() == geography.lower()]
    if stage:
        filtered = filtered[filtered["stage"].str.lower() == stage.lower()]

    cols = [
        "name", "description", "sector", "stage", "geography", "vc_scout_score",
        "momentum_flag", "top_driver", "risk_flag", "commit_velocity_14d",
        "commit_velocity_change", "contributors", "contributor_growth",
        "new_repos_30d", "signal_type", "github_url", "website_url", "profile_url",
    ]
    return filtered.head(limit)[cols].where(filtered[cols].notna(), None).to_dict(orient="records")


@app.get("/startups/{startup_name}")
def startup_detail(startup_name: str) -> dict:
    df, _ = get_ranked_startups()
    match = df[df["name"].str.lower() == startup_name.lower()]
    if match.empty:
        raise HTTPException(status_code=404, detail="Startup not found")
    row = match.iloc[0].where(match.iloc[0].notna(), None)
    return row.to_dict()
