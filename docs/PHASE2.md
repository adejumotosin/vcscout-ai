# VCScout AI Phase 2

Phase 2 turns VCScout from a live engineering-momentum screener into an outcome-aware venture research workflow.

## Product features

- Browser-persistent watchlist (up to 30 companies)
- Structured research memo per company
- Watchlist brief endpoint
- Dedicated 90-day funding-probability field
- Probability is automatically withheld until the model passes data and temporal-validation gates
- Model metadata endpoint at `/model`

## Data pipeline

### 1. Historical engineering signals

`python scripts/import_gitdealflow_history.py`

Imports the public `startup_signals` panel from the Hugging Face mirror of VC Deal Flow Signal. Weekly production snapshots are appended by:

`python scripts/snapshot_signals.py`

History is stored at `data/history/signals_history.csv` and deduplicated by observation date + organisation.

### 2. Funding outcomes

The first outcome source is the SEC's official quarterly Form D datasets. They contain structured exempt-offering filings and are available from 2008 onward.

Example:

```bash
python scripts/ingest_sec_form_d.py \
  --year 2026 \
  --quarter 2 \
  --user-agent "VCScoutAI research you@example.com"
```

Events are stored at `data/funding_events/sec_form_d_events.csv`.

SEC Form D is incomplete as a global VC outcome source. It primarily improves coverage for US exempt offerings and must be supplemented later by company press releases, investor announcements, corporate registries, and licensed funding databases where available.

### 3. Entity resolution

VCScout defaults to conservative normalized-name matching. Add verified aliases to:

`data/funding_events/company_aliases.csv`

Do not add ambiguous mappings just to increase match count. False positive funding labels are worse than missing labels.

### 4. Label construction

`python scripts/build_funding_labels.py`

The target is `raised_funding_within_90d`.

Rules:

- Positive: a matched funding event occurs after a signal observation and within 90 days.
- Negative: no event occurs and the full 90-day horizon has elapsed.
- Right-censored: observations less than 90 days old are excluded from training.
- Future information is never allowed into a signal row.

### 5. Model training

Install ML dependencies:

```bash
pip install -e '.[ml]'
python scripts/train_funding_model.py
```

The training pipeline uses chronological train, calibration, and test partitions. It exports a lightweight JSON logistic model so Vercel inference does not need scikit-learn.

Production safety gates:

- at least 50 uncensored labelled observations
- at least 10 positive funding events
- every temporal split must contain both classes

The model is Platt-calibrated on a chronological calibration split. The held-out report includes ROC-AUC, average precision, Brier score, base rate, and lift in the top decile.

A model below the minimum sample gate may be exported only with `--allow-small-sample`; such artifacts have `status: experimental` and are ignored by the production app.

## API additions

- `GET /model`
- `GET /research/{startup_name}`
- `GET /research/{startup_name}/markdown`
- `GET /watchlist/brief?names=CompanyA,CompanyB`

## Automation

`.github/workflows/snapshot-signals.yml` runs weekly and backfills/imports public engineering history before appending the latest snapshot.

`.github/workflows/ingest-sec-form-d.yml` is manual because SEC requests should use an identifying User-Agent. Add a repository secret named `SEC_USER_AGENT` before running it.

## Interpretation

The VC Scout Score remains a sourcing heuristic. The 90-day funding probability is a separate supervised outcome model. VCScout never substitutes the score itself for a probability.
