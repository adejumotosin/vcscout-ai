# VCScout AI — Historical Funding and Alternative-Data Validation

VCScout deliberately separates four different outputs:

1. **VC Scout Score** — an explainable engineering-momentum heuristic.
2. **Commercial Maturity Score** — a transparent public-website maturity heuristic based on visible go-to-market infrastructure.
3. **Historical Funding Pattern Index** — a relative percentile rank from a historical matched case-control model.
4. **90-day Funding Probability** — a future prospectively calibrated probability model. This remains withheld until the data requirements are satisfied.

The distinction matters. A maturity score or ranking model can contain useful sourcing information without being a calibrated probability model.

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

## 2. Historical engineering reconstruction

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

The final historical engineering dataset contains:

- **48 unique funded companies**;
- **48 pre-funding windows**;
- **48 matched control windows**;
- **96 total observations**.

## 3. Validation design

The historical ranker is a regularized logistic model evaluated using **Stratified Group K-Fold cross-validation**.

The grouping variable is GitHub organisation. This prevents the same company from appearing in both the training and test side of a fold.

Validation metrics are computed from out-of-fold predictions only.

A company-cluster bootstrap is used to quantify uncertainty in ROC-AUC.

## 4. Engineering-model results

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

## 6. Commercial Maturity Score

VCScout now snapshots the public websites attached to the live source universe and records visible go-to-market infrastructure. The current production snapshot successfully observed **273 of 369 tracked organisations**, or approximately **74%** of the live universe.

The score is intentionally transparent. It is built from binary evidence for:

- pricing;
- customer or case-study evidence;
- enterprise positioning;
- careers or hiring pages;
- security or compliance infrastructure;
- integrations or marketplaces;
- developer documentation;
- self-serve signup or trial flows;
- sales or demo motions.

The weighted components sum to a 0–100 **Commercial Maturity Score**. The score is not revenue, ARR, bookings, customer count, valuation, or fundraising probability.

Code-hosting and social-media URLs are excluded from website scoring so, for example, a GitHub profile cannot be mistaken for a commercial company website.

The production snapshot is refreshed weekly and appended to a dated history. Once multiple distinct-date snapshots exist, VCScout can measure genuine changes in visible commercial maturity rather than inferring “momentum” from a single observation.

## 7. Leakage-resistant commercial backtest design

To test whether commercial website evidence improves the historical funding ranker, VCScout uses archived web pages rather than current websites.

For each historical positive/control snapshot, the commercial backtest:

1. resolves a company website from public repository or organisation metadata;
2. queries Internet Archive captures only **on or before** the historical feature date;
3. rejects captures that are older than the configured freshness limit;
4. extracts the same transparent commercial features from the archived HTML;
5. retains matched companies only when both historical windows are observed;
6. compares engineering-only, commercial-only, and engineering-plus-commercial models using company-grouped out-of-sample validation.

This design avoids using a company's present-day website to predict a past financing event.

The Internet Archive coverage probe successfully found pre-snapshot captures for Strapi, PostHog and n8n. The full multimodal result is not promoted into the production funding ranker unless it produces sufficient matched coverage and measurable out-of-sample lift.

## 8. Why the 90-day probability remains locked

A real probability requires population-calibrated prospective outcomes. A matched case-control backtest deliberately changes the positive base rate, so its logistic outputs cannot be interpreted as real-world probabilities.

VCScout will only activate the probability field after the prospective dataset has:

- enough uncensored observations;
- enough positive financing events;
- timestamp-safe features;
- chronological out-of-sample validation;
- probability calibration;
- acceptable discrimination and calibration metrics.

Until then, the API returns a null probability and a model status explaining why it is withheld.

## 9. Known limitations

- Public repositories are incomplete proxies for total engineering activity.
- Some startups do most development in private repositories.
- Some open-source organisations are not directly investable corporate entities.
- Public website maturity does not establish commercial traction or revenue.
- Some company websites are missing, unavailable or block automated retrieval.
- Archived website availability is incomplete and non-random.
- Control windows may contain unobserved material events not present in the validated funding ledger.
- The historical sample remains small.
- Funding events are heterogeneous across stages, sectors and market regimes.
- The current historical reconstruction does not fully recreate organisation-wide new-repository activity at each old snapshot.

## 10. Reproducibility

Core scripts:

```text
scripts/import_validated_receipts.py
scripts/build_receipt_backtest.py
scripts/evaluate_receipt_backtest.py
scripts/snapshot_commercial_signals.py
scripts/build_commercial_backtest.py
scripts/evaluate_multimodal_backtest.py
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
data/commercial/live_commercial_signals.csv
```

Production endpoints:

```text
GET /commercial-signals
GET /pattern-model
GET /model
GET /startups
GET /research/{startup_name}
GET /backtest
```

The public backtest page is available at `/backtest` on the deployed VCScout application.
