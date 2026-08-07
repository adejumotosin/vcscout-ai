from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class ScoreWeights:
    velocity_acceleration: float = 0.30
    contributor_growth: float = 0.22
    absolute_velocity: float = 0.18
    repo_expansion: float = 0.12
    team_depth: float = 0.08
    signal_quality: float = 0.10


WEIGHTS = ScoreWeights()

_SIGNAL_QUALITY = {
    "Engineering hiring burst": 1.00,
    "Infrastructure buildout": 0.88,
    "Deploy frequency spike": 0.78,
    "Framework migration": 0.52,
}


def _winsorized_percentile(series: pd.Series, lower: float = 0.02, upper: float = 0.98) -> pd.Series:
    numeric = pd.to_numeric(series, errors="coerce").fillna(0.0).astype(float)
    if numeric.empty:
        return numeric
    lo = numeric.quantile(lower)
    hi = numeric.quantile(upper)
    clipped = numeric.clip(lo, hi)
    return clipped.rank(method="average", pct=True).fillna(0.0)


def _log_percentile(series: pd.Series) -> pd.Series:
    numeric = pd.to_numeric(series, errors="coerce").fillna(0.0).clip(lower=0.0)
    return np.log1p(numeric).rank(method="average", pct=True).fillna(0.0)


def score_startups(df: pd.DataFrame) -> pd.DataFrame:
    """Create a transparent 0-100 sourcing score from observable engineering signals.

    This is deliberately *not* presented as a probability of funding. It is a ranking
    heuristic until outcome-labelled funding data is joined and validated out-of-sample.
    """
    if df.empty:
        return df.copy()

    work = df.copy()
    work["p_velocity_change"] = _winsorized_percentile(work["commit_velocity_change"])
    work["p_contributor_growth"] = _winsorized_percentile(work["contributor_growth"])
    work["p_velocity_abs"] = _log_percentile(work["commit_velocity_14d"])
    work["p_new_repos"] = _log_percentile(work["new_repos_30d"])
    work["p_team_depth"] = _log_percentile(work["contributors"])
    work["signal_quality"] = work["signal_type"].map(_SIGNAL_QUALITY).fillna(0.45)

    raw = (
        WEIGHTS.velocity_acceleration * work["p_velocity_change"]
        + WEIGHTS.contributor_growth * work["p_contributor_growth"]
        + WEIGHTS.absolute_velocity * work["p_velocity_abs"]
        + WEIGHTS.repo_expansion * work["p_new_repos"]
        + WEIGHTS.team_depth * work["p_team_depth"]
        + WEIGHTS.signal_quality * work["signal_quality"]
    )

    work["vc_scout_score"] = (100 * raw).round(1).clip(0, 100)
    work["momentum_flag"] = np.select(
        [work["vc_scout_score"] >= 80, work["vc_scout_score"] >= 65, work["vc_scout_score"] >= 50],
        ["Breakout", "Strong", "Watch"],
        default="Quiet",
    )

    work["risk_flag"] = np.where(
        (work["commit_velocity_change"] < 0) & (work["contributor_growth"] <= 0),
        "Momentum cooling",
        "None",
    )

    # Explainability: identify the strongest normalized components for every row.
    component_map = {
        "Commit acceleration": work["p_velocity_change"] * WEIGHTS.velocity_acceleration,
        "Contributor growth": work["p_contributor_growth"] * WEIGHTS.contributor_growth,
        "Absolute engineering velocity": work["p_velocity_abs"] * WEIGHTS.absolute_velocity,
        "Repository expansion": work["p_new_repos"] * WEIGHTS.repo_expansion,
        "Team depth": work["p_team_depth"] * WEIGHTS.team_depth,
        "Signal quality": work["signal_quality"] * WEIGHTS.signal_quality,
    }
    component_df = pd.DataFrame(component_map, index=work.index)
    work["top_driver"] = component_df.idxmax(axis=1)

    return work.sort_values(["vc_scout_score", "commit_velocity_14d"], ascending=False)


def deduplicate_for_ranking(scored: pd.DataFrame) -> pd.DataFrame:
    if scored.empty:
        return scored.copy()
    return (
        scored.sort_values(["vc_scout_score", "commit_velocity_14d"], ascending=False)
        .drop_duplicates("startup_key", keep="first")
        .reset_index(drop=True)
    )
