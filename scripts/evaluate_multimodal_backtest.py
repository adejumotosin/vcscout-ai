from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
ENGINEERING = ROOT / "data" / "training" / "receipt_backtest_features.csv"
COMMERCIAL = ROOT / "data" / "training" / "commercial_backtest_features.csv"
REPORT = ROOT / "data" / "model" / "multimodal_backtest_report.json"
PREDICTIONS = ROOT / "data" / "training" / "multimodal_backtest_predictions.csv"

COMMERCIAL_FEATURES = [
    "pricing_signal",
    "customer_evidence_signal",
    "enterprise_signal",
    "careers_signal",
    "security_signal",
    "integrations_signal",
    "developer_docs_signal",
    "self_serve_signal",
    "sales_motion_signal",
    "commercial_signal_count",
]


def _engineering_features(frame: pd.DataFrame) -> pd.DataFrame:
    x = pd.DataFrame(index=frame.index)
    velocity = pd.to_numeric(frame["commit_velocity_14d"], errors="coerce").fillna(0).clip(lower=0)
    velocity_change = pd.to_numeric(frame["commit_velocity_change"], errors="coerce").fillna(0).clip(-100, 500)
    contributors = pd.to_numeric(frame["contributors"], errors="coerce").fillna(0).clip(lower=0)
    growth = pd.to_numeric(frame["contributor_growth"], errors="coerce").fillna(0).clip(-100, 500)
    x["log_commit_velocity"] = np.log1p(velocity)
    x["commit_velocity_change"] = velocity_change
    x["log_contributors"] = np.log1p(contributors)
    x["contributor_growth"] = growth
    x["velocity_positive"] = (velocity_change > 0).astype(int)
    x["growth_positive"] = (growth > 0).astype(int)
    x["dual_acceleration"] = ((velocity_change > 0) & (growth > 0)).astype(int)
    return x


def _commercial_features(frame: pd.DataFrame) -> pd.DataFrame:
    x = pd.DataFrame(index=frame.index)
    for name in COMMERCIAL_FEATURES:
        x[name] = pd.to_numeric(frame[name], errors="coerce").fillna(0.0)
    return x


def _evaluate(x: pd.DataFrame, y: np.ndarray, groups: np.ndarray, seed: int = 42) -> tuple[np.ndarray, dict]:
    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import average_precision_score, roc_auc_score
    from sklearn.model_selection import StratifiedGroupKFold
    from sklearn.pipeline import Pipeline
    from sklearn.preprocessing import StandardScaler

    unique_groups = pd.Series(groups).nunique()
    n_splits = min(5, unique_groups)
    if n_splits < 3:
        raise ValueError("Need at least three companies for grouped validation")

    cv = StratifiedGroupKFold(n_splits=n_splits, shuffle=True, random_state=seed)
    oof = np.full(len(x), np.nan)
    folds: list[dict] = []
    for fold, (train_idx, test_idx) in enumerate(cv.split(x, y, groups), 1):
        model = Pipeline([
            ("scale", StandardScaler()),
            ("model", LogisticRegression(C=0.5, max_iter=2000, class_weight="balanced", random_state=seed)),
        ])
        model.fit(x.iloc[train_idx], y[train_idx])
        oof[test_idx] = model.predict_proba(x.iloc[test_idx])[:, 1]
        fold_y = y[test_idx]
        folds.append({
            "fold": fold,
            "rows": int(len(test_idx)),
            "companies": int(pd.Series(groups[test_idx]).nunique()),
            "roc_auc": round(float(roc_auc_score(fold_y, oof[test_idx])), 4) if len(np.unique(fold_y)) > 1 else None,
            "average_precision": round(float(average_precision_score(fold_y, oof[test_idx])), 4),
        })

    valid = ~np.isnan(oof)
    return oof, {
        "roc_auc": round(float(roc_auc_score(y[valid], oof[valid])), 4),
        "average_precision": round(float(average_precision_score(y[valid], oof[valid])), 4),
        "folds": folds,
    }


def _cluster_bootstrap_auc(y: np.ndarray, scores: np.ndarray, groups: np.ndarray, iterations: int = 2000) -> dict:
    from sklearn.metrics import roc_auc_score

    rng = np.random.default_rng(42)
    group_values = np.asarray(pd.Series(groups).unique())
    aucs: list[float] = []
    for _ in range(iterations):
        sampled = rng.choice(group_values, size=len(group_values), replace=True)
        indices: list[int] = []
        for group in sampled:
            indices.extend(np.where(groups == group)[0].tolist())
        yy = y[indices]
        if len(np.unique(yy)) < 2:
            continue
        aucs.append(float(roc_auc_score(yy, scores[indices])))
    if not aucs:
        return {"method": "company-cluster bootstrap", "iterations": 0}
    return {
        "method": "company-cluster bootstrap",
        "iterations": len(aucs),
        "lower_95": round(float(np.quantile(aucs, 0.025)), 4),
        "median": round(float(np.quantile(aucs, 0.5)), 4),
        "upper_95": round(float(np.quantile(aucs, 0.975)), 4),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare engineering-only, commercial-only and combined historical funding rankers.")
    parser.add_argument("--minimum-companies", type=int, default=10)
    args = parser.parse_args()

    eng = pd.read_csv(ENGINEERING)
    com = pd.read_csv(COMMERCIAL)
    keys = ["github_owner", "github_repo", "window_name"]
    keep = keys + ["archive_age_days", "commercial_momentum_score", *COMMERCIAL_FEATURES]
    merged = eng.merge(com[keep], on=keys, how="inner", validate="one_to_one")

    # Preserve the matched case-control design by keeping only companies with both windows.
    paired_owners = (
        merged.groupby("github_owner")["raised_funding_within_90d"].nunique()
        .loc[lambda series: series == 2]
        .index
    )
    merged = merged[merged["github_owner"].isin(paired_owners)].copy()
    companies = merged["github_owner"].nunique()
    if companies < args.minimum_companies:
        raise SystemExit(f"Need at least {args.minimum_companies} complete commercial pairs; found {companies}")

    merged = merged.sort_values(["github_owner", "raised_funding_within_90d"]).reset_index(drop=True)
    y = merged["raised_funding_within_90d"].astype(int).to_numpy()
    groups = merged["github_owner"].astype(str).to_numpy()

    x_eng = _engineering_features(merged)
    x_com = _commercial_features(merged)
    x_combined = pd.concat([x_eng, x_com], axis=1)

    p_eng, report_eng = _evaluate(x_eng, y, groups)
    p_com, report_com = _evaluate(x_com, y, groups)
    p_combined, report_combined = _evaluate(x_combined, y, groups)
    report_eng["roc_auc_95_ci"] = _cluster_bootstrap_auc(y, p_eng, groups)
    report_com["roc_auc_95_ci"] = _cluster_bootstrap_auc(y, p_com, groups)
    report_combined["roc_auc_95_ci"] = _cluster_bootstrap_auc(y, p_combined, groups)

    improvement = round(report_combined["roc_auc"] - report_eng["roc_auc"], 4)
    output = merged[[
        "company", "github_owner", "github_repo", "event_date", "snapshot_date", "window_name",
        "raised_funding_within_90d", "commercial_momentum_score", "archive_age_days",
    ]].copy()
    output["engineering_oof_score"] = p_eng
    output["commercial_oof_score"] = p_com
    output["combined_oof_score"] = p_combined
    PREDICTIONS.parent.mkdir(parents=True, exist_ok=True)
    output.to_csv(PREDICTIONS, index=False)

    report = {
        "status": "completed",
        "design": "historical matched case-control backtest with leakage-resistant archived website captures",
        "rows": int(len(merged)),
        "unique_companies": int(companies),
        "positive_rows": int(y.sum()),
        "control_rows": int((y == 0).sum()),
        "archive_age_days": {
            "median": round(float(pd.to_numeric(merged["archive_age_days"]).median()), 1),
            "max": int(pd.to_numeric(merged["archive_age_days"]).max()),
        },
        "engineering_only": report_eng,
        "commercial_only": report_com,
        "engineering_plus_commercial": report_combined,
        "combined_auc_improvement_vs_engineering": improvement,
        "combined_ranker_candidate": bool(improvement >= 0.02 and report_combined["roc_auc"] >= 0.63),
        "probability_calibrated": False,
        "caveats": [
            "Archived homepage captures are used only when captured on or before the historical snapshot date.",
            "Companies without sufficiently recent archived websites are excluded from this matched comparison, so coverage is not random.",
            "Commercial indicators are visible go-to-market infrastructure signals, not verified revenue, bookings or customer counts.",
            "This case-control design validates relative ranking only and cannot calibrate real-world funding probabilities.",
        ],
    }
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
