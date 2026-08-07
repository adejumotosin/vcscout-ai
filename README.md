# VCScout AI

**Alternative-data venture sourcing from public engineering momentum.**

VCScout AI ranks venture-stage organisations using observable GitHub engineering signals: commit acceleration, contributor growth, absolute engineering velocity, repository expansion, team depth and signal type.

> The current **VC Scout Score is a sourcing heuristic, not a funding probability**. A true financing-probability model requires timestamped funding outcomes and out-of-sample validation.

## What it does

Traditional startup databases often become most informative after a company has already attracted attention. VCScout AI is designed for a different workflow: identify unusual engineering acceleration first, then prioritise human diligence.

The initial source is **VC Deal Flow Signal (GitDealFlow)**. Its live feed exposes startup engineering activity derived from public GitHub data, including 14-day commit velocity, velocity change, contributor growth, new repositories, stage, geography and signal type.

Source: https://signals.gitdealflow.com/api/signals.json  
Methodology: https://signals.gitdealflow.com/methodology

Attribution: **VC Deal Flow Signal (signals.gitdealflow.com)**.

## MVP features

- Live ingestion from the GitDealFlow signal API
- One-row-per-organisation global ranking
- Transparent 0–100 VC Scout Score
- Outlier-resistant percentile transforms
- Search and filters for sector, stage, geography and minimum score
- Deal-flow leaderboard
- Momentum map and sector heat view
- Startup diligence snapshot
- FastAPI endpoints and OpenAPI docs
- Vercel-native responsive web interface
- Supervised-model scaffold for future funding labels
- Tests and GitHub Actions CI

## Score design

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
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -e '.[local]'
uvicorn app:app --reload
```

Open:

- Dashboard: http://localhost:8000
- API docs: http://localhost:8000/docs

## Deploy to Vercel

This repository is configured for Vercel's native Python/FastAPI runtime.

1. Import `adejumotosin/vcscout-ai` into Vercel.
2. Keep the project root as `./`.
3. Leave Framework Preset on automatic detection / Other.
4. No environment variables are required for the current public-data MVP.
5. Deploy.

`vercel.json` sets the FastAPI function duration. `requirements.txt` intentionally contains only the packages required in production so the serverless bundle remains lightweight.

Once the GitHub repository is connected, every push to `main` can trigger a production deployment and pull-request branches can receive preview deployments.

## API

```text
GET /health
GET /meta
GET /startups?limit=25&min_score=65
GET /startups?sector=Healthcare&stage=Seed
GET /startups/{startup_name}
```

## Architecture

```text
VC Deal Flow live feed
        |
        v
normalisation + validation
        |
        v
transparent scoring engine
        |
        v
      FastAPI
       /   \
      /     \
 web UI    JSON API
      \     /
       \   /
 venture sourcing + diligence queue
```

## Funding model roadmap

The repository includes `src/vcscout/modeling.py` and `data/funding_labels_template.csv` for the next phase.

A credible supervised model should:

1. Join every signal observation to a timestamped financing outcome.
2. Define a target such as `raised_funding_within_90d`.
3. Use only information that existed on the signal date.
4. Split training and validation chronologically, not randomly.
5. Report ROC-AUC and average precision because financing events will be imbalanced.
6. Calibrate predicted probabilities before displaying them.
7. Backtest whether top-decile scores produce materially higher subsequent financing rates than the full universe.

## Important limitations

- GitHub activity is not equivalent to commercial traction.
- Some tracked organisations may not be investable startups in the conventional VC sense.
- Extreme growth percentages can result from tiny prior-period baselines.
- Public repositories understate engineering activity for companies building primarily in private repositories.
- The score is intended to surface candidates for diligence, not automate investment decisions.

## Next upgrades

- Timestamped public funding-event labels
- SEC Form D / press-release outcome ingestion where applicable
- Product Hunt, Hacker News and Google Trends attention signals
- Founder-network and investor graph features
- Hiring velocity from public careers pages
- Release-frequency and dependency-adoption signals
- SHAP explanations for the supervised model
- Weekly watchlist alerts
- PostgreSQL historical signal store
- Calibrated funding probability after temporal backtesting

## License

Code in this repository is MIT licensed. Third-party datasets retain their own licences and terms; verify source terms before commercial redistribution.
