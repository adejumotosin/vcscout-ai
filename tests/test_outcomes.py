from __future__ import annotations

import pandas as pd

from vcscout.outcomes import build_90d_labels, normalize_company_name


def test_normalize_company_name_removes_common_suffixes():
    assert normalize_company_name("Acme, Inc.") == "acme"
    assert normalize_company_name("Example Labs LLC") == "example labs"


def test_90d_label_builder_handles_positive_negative_and_censoring():
    signals = pd.DataFrame(
        [
            {"name": "Acme", "snapshot_date": "2026-01-01", "commit_velocity_14d": 10},
            {"name": "Beta Labs", "snapshot_date": "2026-01-01", "commit_velocity_14d": 8},
            {"name": "Gamma", "snapshot_date": "2026-07-15", "commit_velocity_14d": 5},
        ]
    )
    events = pd.DataFrame(
        [
            {
                "issuer_name": "Acme Inc.",
                "event_date": "2026-02-10",
                "amount_sold": 5_000_000,
                "source": "SEC Form D",
            }
        ]
    )

    labelled = build_90d_labels(signals, events, as_of="2026-08-07")
    labels = dict(zip(labelled["name"], labelled["raised_funding_within_90d"]))

    assert labels["Acme"] == 1
    assert labels["Beta Labs"] == 0
    assert "Gamma" not in labels  # right-censored: full 90-day horizon has not elapsed
