from __future__ import annotations

from vcscout.probability import FEATURE_NAMES, predict_from_artifact


def test_portable_probability_is_bounded_and_monotonic_for_stronger_signal():
    artifact = {
        "feature_names": FEATURE_NAMES,
        "means": [0.0] * len(FEATURE_NAMES),
        "scales": [1.0] * len(FEATURE_NAMES),
        "coefficients": [0.3, 0.8, 0.2, 0.7, 0.4] + [0.0] * (len(FEATURE_NAMES) - 5),
        "intercept": -2.0,
        "calibration": {"coefficient": 1.0, "intercept": 0.0},
    }
    weak = {
        "commit_velocity_14d": 5,
        "commit_velocity_change": 5,
        "contributors": 2,
        "contributor_growth": 0,
        "new_repos_30d": 0,
        "stage": "Seed",
        "signal_type": "Framework migration",
    }
    strong = {
        "commit_velocity_14d": 100,
        "commit_velocity_change": 250,
        "contributors": 20,
        "contributor_growth": 150,
        "new_repos_30d": 5,
        "stage": "Seed",
        "signal_type": "Engineering hiring burst",
    }

    p_weak = predict_from_artifact(weak, artifact)
    p_strong = predict_from_artifact(strong, artifact)
    assert 0 < p_weak < 1
    assert 0 < p_strong < 1
    assert p_strong > p_weak
