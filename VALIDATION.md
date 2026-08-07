# VCScout AI — Historical Funding Validation

VCScout deliberately separates three different outputs:

1. **VC Scout Score** — an explainable engineering-momentum heuristic.
2. **Historical Funding Pattern Index** — a relative percentile rank from a historical matched case-control model.
3. **90-day Funding Probability** — a future prospectively calibrated probability model. This remains withheld until the data requirements are satisfied.

The distinction matters. A ranking model can have predictive information without being a calibrated probability model.

## 1. Outcome sources

### Prospective SEC Form D pipeline

VCScout ingests public SEC Form D quarterly datasets and stores timestamped exempt-offering events. Historical coverage currently includes:

| Period | Form D rows ingested |
| --- | ---: |
| 2025 Q3 | 13,979 |
| 2025 Q4 | 14,637 |
| 2026 Q1 | 15,734 |
| 2026 Q2 | 16,640 |

The deduplicated outcome store contains approximately 60,990 filings.

The prospective labelling pipeline uses:

- a 90-day prediction horizon;
- a reporting-lag buffer before declaring an observation negative;
- conservative company-name/entity matching;
- right-censor handling;
- chronological validation requirements before any probability can be published.

At the current stage, the public 2025–2026 engineering panel does not contain enough safely matched positive financing events. VCScout therefore does **not** fit or publish a 90-day probability from those labels.

### Validated public funding receipts

For historical signal validation, VCScout also imports the public VC Deal Flow Signal Underwriting Receipts ledger. The ledger ties documented financing events to specific public GitHub repositories and provides a historical set of known fundraising outcomes.

This source is used for a **historical ranking backtest only**. It is not used to pretend that the case-control class frequency is the real-world probability of fundraising.

## 2. Historical reconstruction

For each validated funded company, VCScout reconstructs public GitHub commit activity at two pre-specified points:

- **Positive window:** 42 days before the documented funding event.
- **Matched control window:** 180 days before the same funding event.

The 42-day point follows the project's pre-specified three-to-six-week lead-time hypothesis rather than being optimized after seeing the outcomes.

Features reconstructed from the GitHub API include:

- 14-day commit count;
- change in commit count versus the prior 14-day window;
- unique contributor count;
- contributor-count growth;
- positive-acceleration flags;
- dual commit/contributor acceleration.

The final historical dataset contains:

- **48 unique funded companies**;
- **48 pre-funding windows**;
- **48 matched control windows**;
- **96 total observations**.

## 3. Validation design

The historical ranker is a regularized logistic model evaluated using **Stratified Group K-Fold cross-validation**.

The grouping variable is GitHub organisation. This prevents the same company from appearing in both the training and test side of a fold.

Validation metrics are computed from out-of-fold predictions only.

A company-cluster bootstrap is used to quantify uncertainty in ROC-AUC.

## 4. Results

### Learned historical ranker

| Metric | Result |
| --- | ---: |
| Out-of-fold ROC-AUC | **0.6252** |
| Average Precision | **0.6583** |
| ROC-AUC 95% company-cluster bootstrap interval | **0.5269–0.7268** |

Fold ROC-AUC values were approximately:

- 0.690
- 0.600
- 0.710
- 0.593
- 0.624

This is **modest directional ranking signal**, not production-grade underwriting performance.

### Original VC Scout Score on the same funding task

| Metric | Result |
| --- | ---: |
| ROC-AUC | **0.4946** |
| Average Precision | **0.5393** |

This result is important: the original hand-weighted VC Scout Score should remain an **engineering-momentum score**, not be relabelled as a funding predictor.

The learned funding-pattern ranker is therefore kept as a separate model and output.

## 5. Historical Funding Pattern Index

The production site loads the versioned historical ranker artifact and scores the current live startup universe.

Rather than exposing the logistic output as a probability, VCScout converts the current scores into a **cross-sectional percentile**:

```text
Historical Funding Pattern Index = percentile rank within the current live universe
```

Interpretation:

- `90` means the company's current observable engineering pattern ranks around the 90th percentile of the current comparison universe under the historical ranker.
- `90` does **not** mean a 90% probability of raising funding.

This preserves the useful ranking information without making an invalid probability claim.

## 6. Why the 90-day probability remains locked

A real probability requires population-calibrated prospective outcomes. A matched case-control backtest deliberately changes the positive base rate, so its logistic outputs cannot be interpreted as real-world probabilities.

VCScout will only activate the probability field after the prospective dataset has:

- enough uncensored observations;
- enough positive financing events;
- timestamp-safe features;
- chronological out-of-sample validation;
- probability calibration;
- acceptable discrimination and calibration metrics.

Until then, the API returns a null probability and a model status explaining why it is withheld.

## 7. Known limitations

- Public repositories are incomplete proxies for total engineering activity.
- Some startups do most development in private repositories.
- Some open-source organisations are not directly investable corporate entities.
- Control windows may contain unobserved material events not present in the validated funding ledger.
- The historical sample remains small.
- Funding events are heterogeneous across stages, sectors and market regimes.
- The current historical reconstruction does not fully recreate organisation-wide new-repository activity at each old snapshot.

## 8. Reproducibility

Core scripts:

```text
scripts/import_validated_receipts.py
scripts/build_receipt_backtest.py
scripts/evaluate_receipt_backtest.py
scripts/ingest_sec_form_d.py
scripts/build_funding_labels.py
scripts/train_funding_model.py
```

Versioned artifacts:

```text
data/model/funding_pattern_ranker.json
data/model/receipt_backtest_report.json
data/training/receipt_backtest_features.csv
data/training/receipt_backtest_predictions.csv
```

Production endpoints:

```text
GET /pattern-model
GET /model
GET /startups
GET /research/{startup_name}
GET /backtest
```

The public backtest page is available at `/backtest` on the deployed VCScout application.
