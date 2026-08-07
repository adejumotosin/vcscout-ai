from vcscout.data import flatten_startups, parse_percent


def test_parse_percent():
    assert parse_percent("+1600%") == 1600.0
    assert parse_percent("-27%") == -27.0
    assert parse_percent(None) == 0.0


def test_flatten_startups():
    payload = {
        "sectors": [
            {
                "name": "AI",
                "slug": "ai",
                "startups": [
                    {
                        "name": "Example",
                        "commitVelocity14d": 10,
                        "commitVelocityChange": "+50%",
                        "contributors": 5,
                        "contributorGrowth": "+25%",
                        "newRepos": 1,
                        "signalType": "Engineering hiring burst",
                    }
                ],
            }
        ]
    }
    df = flatten_startups(payload)
    assert len(df) == 1
    assert df.iloc[0]["commit_velocity_change"] == 50.0
    assert df.iloc[0]["sector"] == "AI"
