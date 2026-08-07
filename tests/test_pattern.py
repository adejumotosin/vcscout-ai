from __future__ import annotations

import pandas as pd

from vcscout.pattern import attach_funding_pattern_index, historical_pattern_status, raw_pattern_score


def _row(velocity: float, change: float, contributors: float, growth: float) -> dict:
    return {
        "commit_velocity_14d": velocity,
        "commit_velocity_change": change,
        "contributors": contributors,
        "contributor_growth": growth,
    }


def test_pattern_artifact_is_rank_only_not_probability():
    status = historical_pattern_status()
    assert status["available"] is True
    assert status["probability_calibrated"] is False
    assert status["production_probability_eligible"] is False
    assert "not probability" in status["output"]


def test_pattern_index_is_cross_sectional_percentile():
    frame = pd.DataFrame(
        [
            _row(5, -50, 2, -40),
            _row(50, 20, 12, 25),
            _row(160, 90, 30, 140),
        ]
    )
    ranked = attach_funding_pattern_index(frame)
    assert ranked["funding_pattern_index"].between(0, 100).all()
    assert ranked["funding_pattern_index"].nunique() == 3
    assert set(ranked["funding_pattern_model_status"]) == {"historical_ranker"}


def test_raw_pattern_score_is_finite():
    value = raw_pattern_score(_row(100, 50, 20, 75))
    assert isinstance(value, float)
    assert value == value
