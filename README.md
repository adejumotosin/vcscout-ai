# VCScout AI

**Alternative-data venture sourcing from public engineering momentum.**

VCScout AI ranks venture-stage organisations using observable GitHub engineering signals: commit acceleration, contributor growth, absolute engineering velocity, repository expansion, team depth and signal type.

> The current **VC Scout Score is a sourcing heuristic, not a funding probability**. A true financing-probability model requires timestamped funding outcomes and out-of-sample validation.

## Why this exists

Traditional startup databases often become most informative after a company has already attracted attention. VCScout AI is designed for a different workflow: identify unusual engineering acceleration first, then prioritize human diligence.

The initial signal source is **VC Deal Flow Signal (GitDealFlow)**, whose live API exposes startup engineering activity derived from public GitHub data. The source reports 14-day commit velocity, change in commit velocity, contributor counts/growth, new repositories, stage, geography and signal type.

Source: https://signals.gitdealflow.com/api/signals.json  
Methodology: https://signals.gitdealflow.com/methodology

Attribution: **VC Deal Flow Signal (signals.gitdealflow.com)**.

## MVP features

- Live ingestion from the GitDealFlow signal API
- One-row-per-organisation global ranking
- Transparent 0–100 VC Scout Score
- Outlier-resistant percentile transforms
- Filters for sector, stage and geography
- Momentum scatterplot and sector heat view
- Startup deep-dive panel
- FastAPI endpoints for programmatic access
- Supervised-model scaffold for future real funding labels
- Tests, Dockerfile and GitHub Actions CI

## Score design

Current weights:

| Component | Weight |
|---|---:|
| Commit velocity acceleration | 30% |
| Contributor growth | 22% |
| Absolute 14-day commit velocity | 18% |
| New repositories | 12% |
| Team depth | 8% |
| Signal type quality | 10% |

Percentile ranks and log transforms reduce distortion from extreme values such as very large percentage changes off tiny baselines.

## Run locally

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\\Scripts\\activate
pip install -e '.[dev]'
streamlit run app.py
```

Run the API:

```bash
uvicorn vcscout.api:app --app-dir src --reload
```

Then open:

- Dashboard: http://localhost:8501
- API docs: http://localhost:8000/docs

## API examples

```text
GET /health
GET /meta
GET /startups?limit=25&min_score=65
GET /startups?sector=Healthcare&stage=Seed
GET /startups/fleetbase
```

## Funding model roadmap

The repository already includes `src/vcscout/modeling.py` and `data/funding_labels_template.csv` for the next phase.

A credible supervised model should:

1. Join every signal observation to a timestamped financing outcome.
2. Define a target such as `raised_funding_within_90d`.
3. Use only information that existed on the signal date.
4. Split training and validation chronologically, not randomly.
5. Report ROC-AUC **and** average precision because funding events are likely imbalanced.
6. Calibrate predicted probabilities before showing them in the product.
7. Backtest whether top-decile scores produce materially higher subsequent financing rates than the full universe.

## Architecture

```text
GitDealFlow live JSON
        |
        v
 data ingestion / normalization
        |
        v
 transparent scoring engine
        |
   +----+----+
   |         |
Streamlit   FastAPI
Dashboard    API
   |
   v
VC sourcing + diligence queue

Future:
Funding/news/company outcomes -> labelled panel -> temporal ML model -> calibrated probability
```

## Important limitations

- GitHub activity is not equivalent to commercial traction.
- Some tracked organisations may not be investable startups in the conventional VC sense.
- Extreme growth percentages can result from tiny prior-period baselines.
- Public repositories understate engineering activity for companies building primarily in private repositories.
- The score is intended to surface candidates for diligence, not automate investment decisions.

## Next upgrades

- Crunchbase/PitchBook-compatible outcome import (user-provided licensed export)
- Public funding-event labels from press releases and SEC Form D where applicable
- Product Hunt / Hacker News / Google Trends attention signals
- Founder-network and investor graph features
- Hiring velocity from public jobs pages
- Release-frequency and dependency-adoption signals
- SHAP explanations for the supervised model
- Weekly email/watchlist alerts
- PostgreSQL historical signal store
- Next.js institutional-style frontend

## License

Code in this repository can be released under MIT. Third-party datasets retain their own licenses/terms. Check the live data source terms before commercial redistribution.
