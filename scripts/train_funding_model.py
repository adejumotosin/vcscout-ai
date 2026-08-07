from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, brier_score_loss, roc_auc_score
from sklearn.preprocessing import StandardScaler

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from vcscout.probability import FEATURE_NAMES, feature_vector  # noqa: E402

LABELS = ROOT / "data" / "training" / "funding_labels.csv"
OUTPUT = ROOT / "data" / "model" / "funding_model.json"


def lift_at_fraction(y_true: np.ndarray, prob: np.ndarray, fraction: float = 0.10) -> float | None:
    if len(y_true) == 0 or y_true.mean() == 0:
        return None
    n = max(1, int(np.ceil(len(y_true) * fraction)))
    order = np.argsort(-prob)[:n]
    return float(y_true[order].mean() / y_true.mean())


def temporal_partitions(frame: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    data = frame.sort_values("snapshot_date").copy()
    unique_dates = np.array(sorted(data["snapshot_date"].dropna().unique()))
    if len(unique_dates) < 3:
        raise ValueError("Need observations from at least 3 distinct dates for train/calibration/test partitions")

    train_idx = max(1, int(len(unique_dates) * 0.70))
    calibration_idx = max(train_idx + 1, int(len(unique_dates) * 0.85))
    calibration_idx = min(calibration_idx, len(unique_dates) - 1)
    train_cut = unique_dates[train_idx]
    test_cut = unique_dates[calibration_idx]

    train = data[data["snapshot_date"] < train_cut]
    calibration = data[(data["snapshot_date"] >= train_cut) & (data["snapshot_date"] < test_cut)]
    test = data[data["snapshot_date"] >= test_cut]
    if train.empty or calibration.empty or test.empty:
        raise ValueError("Temporal partition produced an empty split")
    return train, calibration, test


def matrix(frame: pd.DataFrame) -> np.ndarray:
    return np.vstack([feature_vector(row, FEATURE_NAMES) for row in frame.to_dict(orient="records")])


def metric_or_none(fn, y_true: np.ndarray, prob: np.ndarray) -> float | None:
    if len(np.unique(y_true)) < 2:
        return None
    return float(fn(y_true, prob))


def main() -> None:
    parser = argparse.ArgumentParser(description="Train and export a Vercel-portable 90-day funding probability model.")
    parser.add_argument("--labels", type=Path, default=LABELS)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--allow-small-sample", action="store_true", help="Export an experimental artifact even below safety gates.")
    args = parser.parse_args()

    labelled = pd.read_csv(args.labels)
    labelled["snapshot_date"] = pd.to_datetime(labelled["snapshot_date"], errors="coerce", utc=True)
    labelled["raised_funding_within_90d"] = pd.to_numeric(labelled["raised_funding_within_90d"], errors="coerce")
    labelled = labelled.dropna(subset=["snapshot_date", "raised_funding_within_90d"]).copy()
    labelled["raised_funding_within_90d"] = labelled["raised_funding_within_90d"].astype(int)

    rows = len(labelled)
    positives = int(labelled["raised_funding_within_90d"].sum())
    if rows < 50 or positives < 10:
        message = f"Safety gate failed: need >=50 labelled rows and >=10 positive events; found {rows} rows/{positives} positives."
        if not args.allow_small_sample:
            raise SystemExit(message)
        print("WARNING:", message)

    train, calibration, test = temporal_partitions(labelled)
    for name, part in [("train", train), ("calibration", calibration), ("test", test)]:
        if part["raised_funding_within_90d"].nunique() < 2:
            raise SystemExit(f"{name} split contains only one class; collect more outcome history before training.")

    x_train, y_train = matrix(train), train["raised_funding_within_90d"].to_numpy()
    x_cal, y_cal = matrix(calibration), calibration["raised_funding_within_90d"].to_numpy()
    x_test, y_test = matrix(test), test["raised_funding_within_90d"].to_numpy()

    scaler = StandardScaler().fit(x_train)
    model = LogisticRegression(C=0.5, class_weight="balanced", max_iter=2000, random_state=42)
    model.fit(scaler.transform(x_train), y_train)

    cal_decision = model.decision_function(scaler.transform(x_cal)).reshape(-1, 1)
    calibrator = LogisticRegression(C=10.0, max_iter=1000, random_state=42)
    calibrator.fit(cal_decision, y_cal)

    test_decision = model.decision_function(scaler.transform(x_test)).reshape(-1, 1)
    probability = calibrator.predict_proba(test_decision)[:, 1]
    validation = {
        "roc_auc": metric_or_none(roc_auc_score, y_test, probability),
        "average_precision": metric_or_none(average_precision_score, y_test, probability),
        "brier_score": float(brier_score_loss(y_test, probability)),
        "base_rate": float(y_test.mean()),
        "lift_at_10pct": lift_at_fraction(y_test, probability, 0.10),
        "test_rows": int(len(test)),
        "test_positives": int(y_test.sum()),
        "train_through": str(train["snapshot_date"].max()),
        "calibration_through": str(calibration["snapshot_date"].max()),
        "test_from": str(test["snapshot_date"].min()),
    }

    status = "validated" if rows >= 50 and positives >= 10 else "experimental"
    artifact = {
        "version": "1.0",
        "status": status,
        "trained_at": datetime.now(timezone.utc).isoformat(),
        "target_horizon_days": 90,
        "feature_names": FEATURE_NAMES,
        "means": scaler.mean_.tolist(),
        "scales": scaler.scale_.tolist(),
        "coefficients": model.coef_[0].tolist(),
        "intercept": float(model.intercept_[0]),
        "calibration": {
            "coefficient": float(calibrator.coef_[0][0]),
            "intercept": float(calibrator.intercept_[0]),
            "method": "Platt scaling on chronological calibration split",
        },
        "training_rows": rows,
        "positive_events": positives,
        "data_through": str(labelled["snapshot_date"].max()),
        "validation": validation,
        "notes": "Predictions are enabled in production only when status is validated.",
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(artifact, indent=2), encoding="utf-8")
    print(json.dumps(validation, indent=2))
    print(f"Wrote {status} artifact to {args.output}")


if __name__ == "__main__":
    main()
