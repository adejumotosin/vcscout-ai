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

    return {
        "log_commit_velocity": math.log1p(velocity),
        "commit_velocity_change": velocity_change,
        "log_contributors": math.log1p(contributors),
        "contributor_growth": contributor_growth,
        "velocity_positive": 1.0 if velocity_change > 0 else 0.0,
        "growth_positive": 1.0 if contributor_growth > 0 else 0.0,
        "dual_acceleration": 1.0 if velocity_change > 0 and contributor_growth > 0 else 0.0,
    }


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
    """Attach a cross-sectional percentile from the historical case-control ranker.

    This index is deliberately not a funding probability. A score of 90 means the
    organisation currently looks more similar to the historical pre-funding pattern
    than roughly 90% of the companies in this live comparison universe.
    """
    result = frame.copy()
    artifact = load_pattern_artifact()
    if artifact is None or result.empty:
        result["funding_pattern_index"] = np.nan
        result["funding_pattern_model_status"] = "unavailable"
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

    validation = report.get("out_of_fold_model") or {}
    existing = report.get("existing_vc_scout_score") or {}
    return {
        "available": True,
        "status": "historical_ranker",
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
            "The index ranks similarity to historical pre-funding engineering patterns. "
            "It must not be interpreted as the probability that a company will raise capital."
        ),
    }
