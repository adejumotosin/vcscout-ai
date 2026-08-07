from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from vcscout.scoring import score_startups  # noqa: E402

DATA = ROOT / "data" / "training" / "receipt_backtest_features.csv"
REPORT = ROOT / "data" / "model" / "receipt_backtest_report.json"
RANKER = ROOT / "data" / "model" / "funding_pattern_ranker.json"
PREDICTIONS = ROOT / "data" / "training" / "receipt_backtest_predictions.csv"

BASE_FEATURES = [
    "commit_velocity_14d",
    "commit_velocity_change",
    "contributors",
    "contributor_growth",
]
EXPANDED_FEATURES = BASE_FEATURES + [
    "releases_30d",
    "releases_90d",
    "issues_opened_30d",
    "issues_closed_30d",
    "prs_merged_30d",
    "community_throughput_30d",
]


def _prepare_features(frame: pd.DataFrame, expanded: bool) -> pd.DataFrame:
    x = pd.DataFrame(index=frame.index)
    x["log_commit_velocity"] = np.log1p(pd.to_numeric(frame["commit_velocity_14d"], errors="coerce").fillna(0).clip(lower=0))
    x["commit_velocity_change"] = pd.to_numeric(frame["commit_velocity_change"], errors="coerce").fillna(0).clip(-100, 500)
    x["log_contributors"] = np.log1p(pd.to_numeric(frame["contributors"], errors="coerce").fillna(0).clip(lower=0))
    x["contributor_growth"] = pd.to_numeric(frame["contributor_growth"], errors="coerce").fillna(0).clip(-100, 500)
    x["velocity_positive"] = (x["commit_velocity_change"] > 0).astype(int)
    x["growth_positive"] = (x["contributor_growth"] > 0).astype(int)
    x["dual_acceleration"] = ((x["commit_velocity_change"] > 0) & (x["contributor_growth"] > 0)).astype(int)
    if expanded:
        for source, target in [
            ("releases_30d", "log_releases_30d"),
            ("releases_90d", "log_releases_90d"),
            ("issues_opened_30d", "log_issues_opened_30d"),
            ("issues_closed_30d", "log_issues_closed_30d"),
            ("prs_merged_30d", "log_prs_merged_30d"),
            ("community_throughput_30d", "log_community_throughput_30d"),
        ]:
            x[target] = np.log1p(pd.to_numeric(frame[source], errors="coerce").fillna(0).clip(lower=0))
        x["release_active"] = (pd.to_numeric(frame["releases_30d"], errors="coerce").fillna(0) > 0).astype(int)
        x["community_active"] = (pd.to_numeric(frame["community_throughput_30d"], errors="coerce").fillna(0) > 0).astype(int)
    return x


def _paired_summary(frame: pd.DataFrame) -> dict:
    pivot_cols = [
        "commit_velocity_14d", "commit_velocity_change", "contributors", "contributor_growth",
        "releases_30d", "issues_opened_30d", "issues_closed_30d", "prs_merged_30d",
        "community_throughput_30d", "vc_scout_score",
    ]
    summaries = {}
    for col in pivot_cols:
        if col not in frame.columns:
            continue
        pivot = frame.pivot_table(index="github_owner", columns="raised_funding_within_90d", values=col, aggfunc="mean")
        if 0 not in pivot.columns or 1 not in pivot.columns:
            continue
        pair = pivot.dropna(subset=[0, 1])
        diff = pair[1] - pair[0]
        summaries[col] = {
            "pairs": int(len(pair)),
            "funding_window_mean": round(float(pair[1].mean()), 4) if len(pair) else None,
            "control_window_mean": round(float(pair[0].mean()), 4) if len(pair) else None,
            "mean_difference": round(float(diff.mean()), 4) if len(pair) else None,
            "funding_window_win_rate": round(float((diff > 0).mean()), 4) if len(pair) else None,
            "ties": int((diff == 0).sum()) if len(pair) else 0,
        }
    return summaries


def _group_bootstrap_auc(y: np.ndarray, pred: np.ndarray, groups: np.ndarray, iterations: int = 2000) -> dict:
    from sklearn.metrics import roc_auc_score

    rng = np.random.default_rng(42)
    unique = np.unique(groups)
    by_group = {group: np.flatnonzero(groups == group) for group in unique}
    values: list[float] = []
    for _ in range(iterations):
        sampled = rng.choice(unique, size=len(unique), replace=True)
        idx = np.concatenate([by_group[group] for group in sampled])
        values.append(float(roc_auc_score(y[idx], pred[idx])))
    lo, mid, hi = np.quantile(values, [0.025, 0.5, 0.975])
    return {
        "method": "company-cluster bootstrap",
        "iterations": iterations,
        "lower_95": round(float(lo), 4),
        "median": round(float(mid), 4),
        "upper_95": round(float(hi), 4),
    }


def _evaluate(x: pd.DataFrame, y: np.ndarray, groups: np.ndarray) -> tuple[np.ndarray, dict]:
    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import average_precision_score, roc_auc_score
    from sklearn.model_selection import StratifiedGroupKFold
    from sklearn.pipeline import Pipeline
    from sklearn.preprocessing import StandardScaler

    unique_groups = pd.Series(groups).nunique()
    cv = StratifiedGroupKFold(n_splits=min(5, unique_groups), shuffle=True, random_state=42)
    oof = np.full(len(y), np.nan)
    folds = []
    for fold, (train_idx, test_idx) in enumerate(cv.split(x, y, groups), 1):
        model = Pipeline([
            ("scale", StandardScaler()),
            ("model", LogisticRegression(C=0.35, max_iter=2000, class_weight="balanced", random_state=42)),
        ])
        model.fit(x.iloc[train_idx], y[train_idx])
        oof[test_idx] = model.predict_proba(x.iloc[test_idx])[:, 1]
        fold_y = y[test_idx]
        fold_p = oof[test_idx]
        folds.append({
            "fold": fold,
            "rows": int(len(test_idx)),
            "companies": int(pd.Series(groups[test_idx]).nunique()),
            "roc_auc": round(float(roc_auc_score(fold_y, fold_p)), 4),
            "average_precision": round(float(average_precision_score(fold_y, fold_p)), 4),
        })
    valid = ~np.isnan(oof)
    metrics = {
        "roc_auc": round(float(roc_auc_score(y[valid], oof[valid])), 4),
        "average_precision": round(float(average_precision_score(y[valid], oof[valid])), 4),
        "roc_auc_95_ci": _group_bootstrap_auc(y[valid], oof[valid], groups[valid]),
        "folds": folds,
    }
    return oof, metrics


def main() -> None:
    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import average_precision_score, roc_auc_score
    from sklearn.pipeline import Pipeline
    from sklearn.preprocessing import StandardScaler

    frame = pd.read_csv(DATA)
    required = set(EXPANDED_FEATURES + ["raised_funding_within_90d", "github_owner", "signal_type"])
    missing = required - set(frame.columns)
    if missing:
        raise SystemExit(f"Backtest data missing columns: {sorted(missing)}")

    frame = frame.dropna(subset=["raised_funding_within_90d", "github_owner"]).copy()
    frame["raised_funding_within_90d"] = frame["raised_funding_within_90d"].astype(int)
    frame["startup_key"] = frame["github_owner"].astype(str).str.lower()
    frame["stage"] = "Unknown"
    frame["geography"] = "Unknown"
    scored = score_startups(frame)
    frame = frame.join(scored[["vc_scout_score"]], how="left", rsuffix="_scored")
    if "vc_scout_score_scored" in frame.columns:
        frame["vc_scout_score"] = frame["vc_scout_score_scored"]
        frame = frame.drop(columns=["vc_scout_score_scored"])

    y = frame["raised_funding_within_90d"].to_numpy()
    groups = frame["github_owner"].astype(str).to_numpy()
    x_base = _prepare_features(frame, expanded=False)
    x_expanded = _prepare_features(frame, expanded=True)

    base_oof, base_metrics = _evaluate(x_base, y, groups)
    expanded_oof, expanded_metrics = _evaluate(x_expanded, y, groups)
    scout_auc = float(roc_auc_score(y, frame["vc_scout_score"].astype(float)))
    scout_ap = float(average_precision_score(y, frame["vc_scout_score"].astype(float)))

    output_cols = [
        "company", "github_owner", "github_repo", "event_date", "snapshot_date", "window_name",
        "raised_funding_within_90d", "vc_scout_score", *[c for c in EXPANDED_FEATURES if c in frame.columns],
    ]
    output = frame[output_cols].copy()
    output["engineering_only_oof_rank_score"] = base_oof
    output["expanded_oof_rank_score"] = expanded_oof
    PREDICTIONS.parent.mkdir(parents=True, exist_ok=True)
    output.to_csv(PREDICTIONS, index=False)

    final_model = Pipeline([
        ("scale", StandardScaler()),
        ("model", LogisticRegression(C=0.35, max_iter=2000, class_weight="balanced", random_state=42)),
    ])
    final_model.fit(x_expanded, y)
    scaler = final_model.named_steps["scale"]
    logistic = final_model.named_steps["model"]
    ranker_artifact = {
        "artifact_type": "historical_case_control_ranker",
        "version": 2,
        "feature_names": list(x_expanded.columns),
        "feature_mean": [float(v) for v in scaler.mean_],
        "feature_scale": [float(v) for v in scaler.scale_],
        "coefficients": [float(v) for v in logistic.coef_[0]],
        "intercept": float(logistic.intercept_[0]),
        "training_rows": int(len(frame)),
        "training_companies": int(pd.Series(groups).nunique()),
        "validation_roc_auc": expanded_metrics["roc_auc"],
        "validation_average_precision": expanded_metrics["average_precision"],
        "validation_auc_95_ci": expanded_metrics["roc_auc_95_ci"],
        "engineering_only_validation": base_metrics,
        "probability_calibrated": False,
        "output_semantics": "Use for ranking only; convert to a percentile within the current candidate universe. Do not present it as funding probability.",
    }
    RANKER.parent.mkdir(parents=True, exist_ok=True)
    RANKER.write_text(json.dumps(ranker_artifact, indent=2))

    report = {
        "status": "completed",
        "design": "historical matched case-control backtest",
        "positive_window": "42 days before a validated public funding event",
        "control_window": "180 days before the same event",
        "rows": int(len(frame)),
        "unique_companies": int(pd.Series(groups).nunique()),
        "positive_rows": int(y.sum()),
        "control_rows": int((y == 0).sum()),
        "engineering_only_model": base_metrics,
        "expanded_engineering_product_community_model": expanded_metrics,
        "auc_improvement_vs_engineering_only": round(expanded_metrics["roc_auc"] - base_metrics["roc_auc"], 4),
        "ap_improvement_vs_engineering_only": round(expanded_metrics["average_precision"] - base_metrics["average_precision"], 4),
        "existing_vc_scout_score": {
            "roc_auc": round(scout_auc, 4),
            "average_precision": round(scout_ap, 4),
        },
        "paired_signal_summary": _paired_summary(frame),
        "historical_pattern_ranker_exported": True,
        "ranker_version": 2,
        "probability_calibrated": False,
        "production_probability_eligible": False,
        "caveats": [
            "This is a matched case-control study, so the positive base rate is artificial and predicted values are ranking scores, not real-world funding probabilities.",
            "All added product/community features are reconstructed from timestamps available before each historical snapshot to avoid hindsight leakage.",
            "Current web traffic, employee counts and present-day company metadata are intentionally excluded from this historical test because they would leak future information unless archival snapshots are available.",
            "The listed GitHub repository is a public engineering proxy; some companies build primarily in private repositories.",
            "Control windows can contain unobserved financing or other material events not present in the validated-receipts ledger.",
        ],
    }
    REPORT.write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
