from __future__ import annotations

import json
import math
from functools import lru_cache
from pathlib import Path
from typing import Any, Mapping

import numpy as np
import pandas as pd

ARTIFACT_PATH = Path(__file__).resolve().parents[2] / "data" / "model" / "funding_pattern_ranker.json"
REPORT_PATH = Path(__file__).resolve().parents[2] / "data" / "model" / "receipt_backtest_report.json"

BASE_LIVE_FEATURES = {
    "log_commit_velocity",
    "commit_velocity_change",
    "log_contributors",
    "contributor_growth",
    "velocity_positive",
    "growth_positive",
    "dual_acceleration",
}
EXPANDED_LIVE_FEATURES = BASE_LIVE_FEATURES | {
    "log_releases_30d",
    "log_releases_90d",
    "log_issues_opened_30d",
    "log_issues_closed_30d",
    "log_prs_merged_30d",
    "log_community_throughput_30d",
    "release_active",
    "community_active",
}


def _num(value: Any, default: float = 0.0) -> float:
    try:
        number = float(value)
        return number if math.isfinite(number) else default
    except (TypeError, ValueError):
        return default


def pattern_feature_dict(row: Mapping[str, Any]) -> dict[str, float]:
    velocity = max(_num(row.get("commit_velocity_14d")), 0.0)
    velocity_change = float(np.clip(_num(row.get("commit_velocity_change")), -100.0, 500.0))
    contributors = max(_num(row.get("contributors")), 0.0)
    contributor_growth = float(np.clip(_num(row.get("contributor_growth")), -100.0, 500.0))
    releases_30d = max(_num(row.get("releases_30d")), 0.0)
    releases_90d = max(_num(row.get("releases_90d")), 0.0)
    issues_opened = max(_num(row.get("issues_opened_30d")), 0.0)
    issues_closed = max(_num(row.get("issues_closed_30d")), 0.0)
    prs_merged = max(_num(row.get("prs_merged_30d")), 0.0)
    throughput = max(_num(row.get("community_throughput_30d")), 0.0)

    return {
        "log_commit_velocity": math.log1p(velocity),
        "commit_velocity_change": velocity_change,
        "log_contributors": math.log1p(contributors),
        "contributor_growth": contributor_growth,
        "velocity_positive": 1.0 if velocity_change > 0 else 0.0,
        "growth_positive": 1.0 if contributor_growth > 0 else 0.0,
        "dual_acceleration": 1.0 if velocity_change > 0 and contributor_growth > 0 else 0.0,
        "log_releases_30d": math.log1p(releases_30d),
        "log_releases_90d": math.log1p(releases_90d),
        "log_issues_opened_30d": math.log1p(issues_opened),
        "log_issues_closed_30d": math.log1p(issues_closed),
        "log_prs_merged_30d": math.log1p(prs_merged),
        "log_community_throughput_30d": math.log1p(throughput),
        "release_active": 1.0 if releases_30d > 0 else 0.0,
        "community_active": 1.0 if throughput > 0 else 0.0,
    }


def _artifact_live_compatible(artifact: Mapping[str, Any], frame: pd.DataFrame | None = None) -> bool:
    names = set(artifact.get("feature_names") or [])
    if not names.issubset(EXPANDED_LIVE_FEATURES):
        return False
    expanded_required = names - BASE_LIVE_FEATURES
    if expanded_required and frame is not None:
        source_columns = {
            "releases_30d", "releases_90d", "issues_opened_30d", "issues_closed_30d",
            "prs_merged_30d", "community_throughput_30d",
        }
        if not source_columns.issubset(frame.columns):
            return False
    return True


@lru_cache(maxsize=1)
def load_pattern_artifact() -> dict[str, Any] | None:
    if not ARTIFACT_PATH.exists():
        return None
    try:
        artifact = json.loads(ARTIFACT_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if artifact.get("artifact_type") != "historical_case_control_ranker":
        return None
    return artifact


@lru_cache(maxsize=1)
def load_backtest_report() -> dict[str, Any] | None:
    if not REPORT_PATH.exists():
        return None
    try:
        return json.loads(REPORT_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def raw_pattern_score(row: Mapping[str, Any], artifact: Mapping[str, Any] | None = None) -> float:
    model = artifact or load_pattern_artifact()
    if model is None:
        return float("nan")

    names = list(model["feature_names"])
    features = pattern_feature_dict(row)
    x = np.asarray([features.get(name, 0.0) for name in names], dtype=float)
    means = np.asarray(model["feature_mean"], dtype=float)
    scales = np.asarray(model["feature_scale"], dtype=float)
    coefficients = np.asarray(model["coefficients"], dtype=float)
    scales = np.where(scales == 0, 1.0, scales)
    return float(np.dot((x - means) / scales, coefficients) + float(model["intercept"]))


def attach_funding_pattern_index(frame: pd.DataFrame) -> pd.DataFrame:
    result = frame.copy()
    artifact = load_pattern_artifact()
    if artifact is None or result.empty:
        result["funding_pattern_index"] = np.nan
        result["funding_pattern_model_status"] = "unavailable"
        return result
    if not _artifact_live_compatible(artifact, result):
        result["funding_pattern_index"] = np.nan
        result["funding_pattern_model_status"] = "awaiting_live_feature_enrichment"
        return result

    raw = pd.Series(
        [raw_pattern_score(row, artifact) for row in result.to_dict(orient="records")],
        index=result.index,
        dtype=float,
    )
    result["funding_pattern_index"] = (100.0 * raw.rank(method="average", pct=True)).round(1)
    result["funding_pattern_model_status"] = "historical_ranker"
    return result


def historical_pattern_status() -> dict[str, Any]:
    artifact = load_pattern_artifact()
    report = load_backtest_report() or {}
    if artifact is None:
        return {
            "available": False,
            "status": "unavailable",
            "message": "Historical funding-pattern ranker artifact is unavailable.",
        }

    compatible = _artifact_live_compatible(artifact)
    expanded = bool(set(artifact.get("feature_names") or []) - BASE_LIVE_FEATURES)
    validation = (
        report.get("expanded_engineering_product_community_model")
        or report.get("out_of_fold_model")
        or {}
    )
    existing = report.get("existing_vc_scout_score") or {}
    return {
        "available": compatible,
        "status": "historical_ranker" if compatible else "awaiting_live_feature_enrichment",
        "ranker_version": artifact.get("version", 1),
        "expanded_signal_layer": expanded,
        "output": "cross-sectional percentile index, not probability",
        "training_rows": artifact.get("training_rows"),
        "training_companies": artifact.get("training_companies"),
        "validation": {
            "roc_auc": artifact.get("validation_roc_auc"),
            "average_precision": artifact.get("validation_average_precision"),
            "roc_auc_95_ci": artifact.get("validation_auc_95_ci"),
        },
        "baseline_scout_score": existing,
        "design": report.get("design"),
        "positive_window": report.get("positive_window"),
        "control_window": report.get("control_window"),
        "probability_calibrated": False,
        "production_probability_eligible": False,
        "message": (
            "The index ranks similarity to historical pre-funding patterns and is not a funding probability."
            if compatible
            else "The expanded historical ranker is validated offline but remains disabled in live inference until the same product/community features are enriched for current candidates."
        ),
    }
