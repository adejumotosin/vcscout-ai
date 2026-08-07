from __future__ import annotations

import json
import math
from functools import lru_cache
from pathlib import Path
from typing import Any, Mapping

import numpy as np
import pandas as pd

MODEL_PATH = Path(__file__).resolve().parents[2] / "data" / "model" / "funding_model.json"

STAGES = ["Pre-Seed", "Seed", "Series A/B", "Series A-B", "Growth"]
SIGNAL_TYPES = [
    "Engineering hiring burst",
    "Infrastructure buildout",
    "Deploy frequency spike",
    "Framework migration",
]

FEATURE_NAMES = [
    "log_commit_velocity_14d",
    "commit_velocity_change_scaled",
    "log_contributors",
    "contributor_growth_scaled",
    "log_new_repos_30d",
    *[f"stage::{value}" for value in STAGES],
    *[f"signal::{value}" for value in SIGNAL_TYPES],
]


def _num(value: Any, default: float = 0.0) -> float:
    try:
        value = float(value)
        if math.isfinite(value):
            return value
    except (TypeError, ValueError):
        pass
    return default


def funding_feature_dict(row: Mapping[str, Any]) -> dict[str, float]:
    """Create the stable feature vector shared by offline training and Vercel inference."""
    commit_velocity = max(_num(row.get("commit_velocity_14d")), 0.0)
    commit_change = float(np.clip(_num(row.get("commit_velocity_change")), -100.0, 1000.0)) / 100.0
    contributors = max(_num(row.get("contributors")), 0.0)
    contributor_growth = float(np.clip(_num(row.get("contributor_growth")), -100.0, 1000.0)) / 100.0
    new_repos = max(_num(row.get("new_repos_30d")), 0.0)

    result: dict[str, float] = {
        "log_commit_velocity_14d": math.log1p(commit_velocity),
        "commit_velocity_change_scaled": commit_change,
        "log_contributors": math.log1p(contributors),
        "contributor_growth_scaled": contributor_growth,
        "log_new_repos_30d": math.log1p(new_repos),
    }

    stage = str(row.get("stage") or "")
    signal = str(row.get("signal_type") or "")
    for value in STAGES:
        result[f"stage::{value}"] = 1.0 if stage == value else 0.0
    for value in SIGNAL_TYPES:
        result[f"signal::{value}"] = 1.0 if signal == value else 0.0
    return result


def feature_vector(row: Mapping[str, Any], feature_names: list[str] | None = None) -> np.ndarray:
    features = funding_feature_dict(row)
    names = feature_names or FEATURE_NAMES
    return np.asarray([features.get(name, 0.0) for name in names], dtype=float)


def _sigmoid(value: float) -> float:
    value = float(np.clip(value, -35.0, 35.0))
    return 1.0 / (1.0 + math.exp(-value))


def predict_from_artifact(row: Mapping[str, Any], artifact: Mapping[str, Any]) -> float:
    names = list(artifact["feature_names"])
    x = feature_vector(row, names)
    means = np.asarray(artifact["means"], dtype=float)
    scales = np.asarray(artifact["scales"], dtype=float)
    coefs = np.asarray(artifact["coefficients"], dtype=float)
    scales = np.where(scales == 0, 1.0, scales)
    z = float(np.dot((x - means) / scales, coefs) + float(artifact["intercept"]))

    calibration = artifact.get("calibration") or {}
    if calibration:
        z = float(calibration.get("coefficient", 1.0)) * z + float(calibration.get("intercept", 0.0))
    return float(np.clip(_sigmoid(z), 0.001, 0.999))


@lru_cache(maxsize=1)
def load_model_artifact() -> dict[str, Any] | None:
    if not MODEL_PATH.exists():
        return None
    try:
        artifact = json.loads(MODEL_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if artifact.get("status") != "validated":
        return None
    return artifact


def model_status() -> dict[str, Any]:
    artifact = load_model_artifact()
    if artifact is None:
        return {
            "available": False,
            "status": "awaiting_validated_labels",
            "message": "Funding probability is withheld until a temporally validated model artifact exists.",
            "minimum_training_rows": 50,
            "minimum_positive_events": 10,
            "target_horizon_days": 90,
        }
    validation = artifact.get("validation", {})
    return {
        "available": True,
        "status": "validated",
        "trained_at": artifact.get("trained_at"),
        "target_horizon_days": artifact.get("target_horizon_days", 90),
        "training_rows": artifact.get("training_rows"),
        "positive_events": artifact.get("positive_events"),
        "validation": validation,
        "data_through": artifact.get("data_through"),
    }


def attach_funding_probabilities(frame: pd.DataFrame) -> pd.DataFrame:
    result = frame.copy()
    artifact = load_model_artifact()
    if artifact is None:
        result["funding_probability_90d"] = np.nan
        result["funding_model_status"] = "awaiting_validated_labels"
        return result

    result["funding_probability_90d"] = [
        round(100.0 * predict_from_artifact(row, artifact), 1)
        for row in result.to_dict(orient="records")
    ]
    result["funding_model_status"] = "validated"
    return result
