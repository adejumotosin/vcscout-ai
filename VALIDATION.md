# VCScout AI - Validation and Model Governance

VCScout deliberately separates four outputs:

1. **VC Scout Score** - an explainable engineering-momentum heuristic.
2. **Commercial Maturity Score** - a transparent public-website maturity heuristic based on visible go-to-market infrastructure.
3. **Historical Funding Pattern Index** - a relative percentile rank from a historical matched case-control model.
4. **90-day Funding Probability** - a future prospectively calibrated probability model. This remains withheld until the data requirements are satisfied.

A useful sourcing score or historical rank does not automatically justify a probability claim. The system keeps these outputs separate in both the API and user interface.

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

The current 2025-2026 public engineering panel still does not contain enough safely matched positive financing events. VCScout therefore does **not** publish a 90-day funding probability from these labels.

### Validated public funding receipts

For historical signal validation, VCScout also imports the public VC Deal Flow Signal Underwriting Receipts ledger. The ledger ties documented financing events to public GitHub repositories and provides a historical set of known fundraising outcomes.

This source is used for a **historical ranking backtest only**. It is not used to infer a real-world fundraising base rate.

## 2. Historical engineering reconstruction

For each validated funded company, VCScout reconstructs public GitHub activity at two pre-specified points:

- **Positive window:** 42 days before the documented funding event.
- **Matched control window:** 180 days before the same funding event.

The 42-day point follows the project's pre-specified three-to-six-week lead-time hypothesis rather than being optimized after seeing the outcomes.

Core engineering features include:

- 14-day commit count;
- commit-count change versus the prior 14-day window;
- unique contributor count;
- contributor-count growth;
- positive-acceleration flags;
- dual commit/contributor acceleration.

The final matched dataset contains:

- **48 unique funded companies**;
- **48 pre-funding windows**;
- **48 matched control windows**;
- **96 total observations**.

## 3. Validation design

The historical rankers use regularized logistic regression evaluated with **Stratified Group K-Fold cross-validation**.

The grouping variable is GitHub organisation, which prevents the same company from appearing in both train and test partitions of a fold. Reported validation metrics are calculated from out-of-fold predictions only.

A company-cluster bootstrap with 2,000 iterations is used to quantify uncertainty in ROC-AUC.

## 4. Historical model results

### Production engineering-only ranker

The current production Historical Funding Pattern Index retains the original engineering-only ranker:

| Metric | Production artifact |
| --- | ---: |
| Out-of-fold ROC-AUC | **0.6252** |
| Average Precision | **0.6583** |
| ROC-AUC 95% bootstrap interval | **0.5269-0.7268** |

A subsequent rerun of the engineering-only specification produced ROC-AUC **0.6261** and Average Precision **0.6585**, which was not materially better than the incumbent.

### Original VC Scout Score on the same funding task

| Metric | Result |
| --- | ---: |
| ROC-AUC | **0.4946** |
| Average Precision | **0.5393** |

This is why the VC Scout Score remains an **engineering-momentum score**, not a funding predictor.

### Product/community challenger

VCScout reconstructed additional timestamp-safe GitHub signals before each historical snapshot:

- releases in the prior 30 and 90 days;
- issues opened in the prior 30 days;
- issues closed in the prior 30 days;
- pull requests merged in the prior 30 days;
- combined community throughput.

The expanded model produced:

| Model | ROC-AUC | Average Precision |
| --- | ---: | ---: |
| Engineering-only rerun | **0.6261** | **0.6585** |
| Engineering + product/community | 0.6274 | 0.6321 |

The challenger gained only **0.0013 ROC-AUC** versus the engineering-only rerun while losing **0.0264 Average Precision**. It was therefore rejected.

The experiment remains versioned in the repository because negative results are useful evidence. The added signals may still help research and diligence even though they did not improve this funding-ranking task.

## 5. Production model promotion policy

VCScout now enforces model promotion in code rather than relying on manual judgement.

A challenger may replace the production Historical Funding Pattern Index only if all of the following are true:

- ROC-AUC improves by at least **0.02** versus the incumbent;
- Average Precision improves by at least **0.01** versus the incumbent;
- both improvements occur in grouped out-of-sample validation;
- every feature required by the challenger is available in the live inference path.

The current governance decision is:

```text
Production action: retain incumbent
Incumbent ROC-AUC: 0.6252
Incumbent Average Precision: 0.6583
Engineering-only challenger AUC lift: +0.0009
Engineering-only challenger AP lift: +0.0002
Expanded challenger AUC lift: +0.0022
Expanded challenger AP lift: -0.0262
```

Neither challenger clears the material-lift thresholds. The expanded challenger is also not live-feature compatible because the production Pattern Index does not yet calculate historical community/release features for the live universe.

The promotion rule is implemented in `src/vcscout/governance.py` and covered by automated tests.

## 6. Historical Funding Pattern Index

The production site loads the versioned historical ranker artifact and scores the current live startup universe.

Rather than exposing the logistic output as a probability, VCScout converts current scores into a cross-sectional percentile:

```text
Historical Funding Pattern Index = percentile rank within the current live universe
```

Interpretation:

- `90` means the company's observable engineering pattern ranks around the 90th percentile of the current comparison universe under the historical ranker.
- `90` does **not** mean a 90% probability of raising funding.

## 7. Commercial Maturity Score

VCScout snapshots the public websites attached to the live source universe and records visible go-to-market infrastructure. The current stored production snapshot observed **273 of 369 tracked organisations**, approximately **74%** of the live universe.

The transparent score uses visible evidence for:

- pricing;
- customer or case-study evidence;
- enterprise positioning;
- careers or hiring pages;
- security or compliance infrastructure;
- integrations or marketplaces;
- developer documentation;
- self-serve signup or trial flows;
- sales or demo motions.

The weighted components form a 0-100 **Commercial Maturity Score**. It is not revenue, ARR, bookings, valuation, customer count, funding probability, or verified commercial traction.

Code-hosting and social-media URLs are excluded from website scoring. The snapshot is refreshed weekly and appended to dated history so future models can use genuine changes rather than one-time observations.

## 8. Leakage-resistant commercial research

Present-day company fundamentals cannot safely be inserted into a 2021-2025 historical prediction test because that would leak future information.

For archived commercial research, VCScout therefore:

1. resolves a company website from public repository or organisation metadata;
2. queries archived captures only on or before the historical feature date;
3. rejects captures that are too old for the configured freshness limit;
4. extracts the same transparent commercial features from archived HTML;
5. keeps historical and current observations separate.

Archived web coverage is incomplete and non-random, so no archived commercial challenger is promoted without sufficient matched coverage and measurable out-of-sample lift.

## 9. Why the 90-day probability remains locked

A real probability requires population-calibrated prospective outcomes. A matched case-control backtest deliberately changes the positive base rate, so its logistic outputs cannot be interpreted as real-world probabilities.

VCScout will activate the probability field only after the prospective dataset has:

- enough uncensored observations;
- enough positive financing events;
- timestamp-safe features;
- chronological out-of-sample validation;
- probability calibration;
- acceptable discrimination and calibration metrics.

Until then, the API returns a null probability and a model-status explanation.

## 10. Known limitations

- Public repositories are incomplete proxies for total engineering activity.
- Some startups do most development in private repositories.
- Some open-source organisations are not directly investable corporate entities.
- Public website maturity does not establish revenue or verified commercial traction.
- Company websites may be missing, unavailable, or block automated retrieval.
- Archived website availability is incomplete and non-random.
- Control windows may contain unobserved material events not present in the validated funding ledger.
- The historical sample remains small.
- Funding events are heterogeneous across stages, sectors, and market regimes.
- Historical reconstruction does not fully recreate every organisation-wide signal at each old snapshot.

## 11. Reproducibility

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

Governance and runtime modules:

```text
src/vcscout/governance.py
src/vcscout/pattern.py
src/vcscout/probability.py
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

The public validation page is available at `/backtest` on the deployed VCScout application.
