from __future__ import annotations

from dataclasses import dataclass

import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import average_precision_score, roc_auc_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder


FEATURES_NUMERIC = [
    "commit_velocity_14d",
    "commit_velocity_change",
    "contributors",
    "contributor_growth",
    "new_repos_30d",
]
FEATURES_CATEGORICAL = ["stage", "geography", "signal_type", "sector"]
TARGET = "raised_funding_within_90d"


@dataclass
class ModelReport:
    roc_auc: float
    average_precision: float
    rows: int


def build_funding_model() -> Pipeline:
    """Supervised model scaffold for when real funding outcome labels are available."""
    pre = ColumnTransformer(
        transformers=[
            ("cat", OneHotEncoder(handle_unknown="ignore", sparse_output=False), FEATURES_CATEGORICAL),
        ],
        remainder="passthrough",
    )
    return Pipeline(
        steps=[
            ("preprocess", pre),
            (
                "classifier",
                HistGradientBoostingClassifier(
                    learning_rate=0.05,
                    max_iter=250,
                    max_leaf_nodes=15,
                    l2_regularization=1.0,
                    random_state=42,
                ),
            ),
        ]
    )


def train_temporal_holdout(labelled: pd.DataFrame, cutoff_period: str) -> tuple[Pipeline, ModelReport]:
    """Train on periods before cutoff and validate on/after cutoff to reduce leakage.

    Required columns: signal_period, TARGET, numeric features, categorical features.
    """
    required = set(FEATURES_NUMERIC + FEATURES_CATEGORICAL + [TARGET, "signal_period"])
    missing = required - set(labelled.columns)
    if missing:
        raise ValueError(f"Missing labelled columns: {sorted(missing)}")

    train = labelled[labelled["signal_period"] < cutoff_period].copy()
    test = labelled[labelled["signal_period"] >= cutoff_period].copy()
    if train.empty or test.empty:
        raise ValueError("Temporal split produced an empty train or test set")

    features = FEATURES_NUMERIC + FEATURES_CATEGORICAL
    model = build_funding_model()
    model.fit(train[features], train[TARGET])
    prob = model.predict_proba(test[features])[:, 1]

    report = ModelReport(
        roc_auc=float(roc_auc_score(test[TARGET], prob)),
        average_precision=float(average_precision_score(test[TARGET], prob)),
        rows=len(test),
    )
    return model, report
