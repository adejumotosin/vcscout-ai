import pandas as pd

from vcscout.scoring import deduplicate_for_ranking, score_startups


def fixture_df():
    return pd.DataFrame(
        [
            {
                "name": "FastCo", "startup_key": "fastco", "commit_velocity_14d": 100,
                "commit_velocity_change": 300, "contributors": 30, "contributor_growth": 120,
                "new_repos_30d": 4, "signal_type": "Engineering hiring burst",
            },
            {
                "name": "SlowCo", "startup_key": "slowco", "commit_velocity_14d": 5,
                "commit_velocity_change": -30, "contributors": 4, "contributor_growth": 0,
                "new_repos_30d": 0, "signal_type": "Framework migration",
            },
        ]
    )


def test_score_is_bounded_and_orders_momentum():
    scored = score_startups(fixture_df())
    assert scored["vc_scout_score"].between(0, 100).all()
    scores = dict(zip(scored["name"], scored["vc_scout_score"]))
    assert scores["FastCo"] > scores["SlowCo"]


def test_deduplicate():
    df = fixture_df()
    duplicate = pd.concat([df, df.iloc[[0]]], ignore_index=True)
    ranked = deduplicate_for_ranking(score_startups(duplicate))
    assert ranked["startup_key"].nunique() == len(ranked)
