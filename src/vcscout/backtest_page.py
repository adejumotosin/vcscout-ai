from __future__ import annotations

import html
from typing import Any, Mapping


def _value(value: Any, digits: int = 3) -> str:
    if value is None:
        return "n/a"
    try:
        return f"{float(value):.{digits}f}"
    except (TypeError, ValueError):
        return html.escape(str(value))


def render_backtest_page(status: Mapping[str, Any]) -> str:
    validation = status.get("validation") or {}
    ci = validation.get("roc_auc_95_ci") or {}
    baseline = status.get("baseline_scout_score") or {}
    rows = status.get("training_rows") or 0
    companies = status.get("training_companies") or 0
    auc = _value(validation.get("roc_auc"))
    ap = _value(validation.get("average_precision"))
    ci_low = _value(ci.get("lower_95"))
    ci_high = _value(ci.get("upper_95"))
    baseline_auc = _value(baseline.get("roc_auc"))

    return f'''<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width,initial-scale=1" />
<meta name="description" content="VCScout AI historical funding-pattern validation." />
<title>VCScout AI — Historical Validation</title>
<style>
:root{{--bg:#07100d;--panel:#0d1713;--line:#203329;--text:#eff7f2;--muted:#91a69c;--accent:#72f0a6;--blue:#8bbcff;--warn:#ffc86a}}
*{{box-sizing:border-box}} body{{margin:0;background:radial-gradient(circle at 80% 0%,rgba(114,240,166,.08),transparent 30%),var(--bg);color:var(--text);font-family:Inter,ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}}
a{{color:inherit;text-decoration:none}} .shell{{max-width:1120px;margin:auto;padding:28px 22px 70px}} nav{{display:flex;justify-content:space-between;align-items:center;margin-bottom:58px}} .brand{{font-weight:850;letter-spacing:-.03em}} .navlinks{{display:flex;gap:9px}} .pill{{border:1px solid var(--line);border-radius:999px;padding:8px 12px;color:#b6c9bf;font-size:12px}}
.eyebrow{{color:var(--accent);text-transform:uppercase;letter-spacing:.16em;font-size:11px;font-weight:850}} h1{{font-size:clamp(42px,7vw,76px);line-height:.98;letter-spacing:-.055em;margin:13px 0 20px;max-width:900px}} .lede{{color:#a5b9af;line-height:1.72;max-width:820px;font-size:15px}}
.grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin:34px 0 18px}} .card{{border:1px solid var(--line);background:linear-gradient(180deg,rgba(255,255,255,.027),rgba(255,255,255,.012));border-radius:17px;padding:18px}} .label{{color:#74887e;font-size:9px;text-transform:uppercase;letter-spacing:.08em;font-weight:800}} .metric{{font-size:30px;font-weight:850;letter-spacing:-.04em;margin-top:11px}} .metric.green{{color:var(--accent)}} .metric.blue{{color:var(--blue)}} .sub{{color:#70837a;font-size:10px;margin-top:4px}}
.section{{margin-top:15px}} .section h2{{font-size:17px;margin:0 0 12px}} .section p,.section li{{color:#a5b7ae;font-size:13px;line-height:1.7}} .callout{{border-left:3px solid var(--warn);padding:13px 16px;background:rgba(255,200,106,.05);color:#cfbf9d;border-radius:0 12px 12px 0;margin:18px 0}} .callout strong{{color:#f7e8c9}} .split{{display:grid;grid-template-columns:1fr 1fr;gap:15px}} code{{background:#0a1510;border:1px solid var(--line);padding:2px 5px;border-radius:5px;color:#bee5ce}} .bar{{height:7px;background:#17271f;border-radius:999px;overflow:hidden;margin-top:12px}} .bar span{{display:block;height:100%;background:linear-gradient(90deg,#367959,var(--accent));width:62.52%}} footer{{margin-top:40px;border-top:1px solid var(--line);padding-top:18px;color:#61746b;font-size:10px;line-height:1.6}}
@media(max-width:800px){{.grid{{grid-template-columns:1fr 1fr}}.split{{grid-template-columns:1fr}}nav{{margin-bottom:38px}}}} @media(max-width:480px){{.grid{{grid-template-columns:1fr}}}}
</style>
</head>
<body><div class="shell">
<nav><div class="brand">VCScout AI · Validation Lab</div><div class="navlinks"><a class="pill" href="/">Dashboard</a><a class="pill" href="/pattern-model">JSON</a></div></nav>
<div class="eyebrow">Historical funding-pattern validation</div>
<h1>Useful ranking signal. <span style="color:var(--accent)">Not a probability.</span></h1>
<p class="lede">VCScout reconstructed public GitHub activity before documented financing events and compared it with earlier control windows for the same companies. The result is a modest, out-of-sample ranking signal that now powers the Historical Funding Pattern Index.</p>
<div class="grid">
<div class="card"><div class="label">Companies</div><div class="metric">{companies}</div><div class="sub">matched funded companies</div></div>
<div class="card"><div class="label">Historical windows</div><div class="metric">{rows}</div><div class="sub">funding + matched controls</div></div>
<div class="card"><div class="label">Grouped OOF ROC-AUC</div><div class="metric green">{auc}</div><div class="sub">company-held-out validation</div><div class="bar"><span></span></div></div>
<div class="card"><div class="label">Average precision</div><div class="metric blue">{ap}</div><div class="sub">balanced case-control sample</div></div>
</div>
<div class="callout"><strong>Why VCScout does not show this as “62.5% funding probability”:</strong> the historical experiment is a matched case-control design, which deliberately contains equal funding and control windows. That changes the base rate, so the model can validate ranking ability but cannot calibrate real-world probabilities.</div>
<div class="split">
<section class="card section"><h2>Backtest design</h2><p><strong>Positive window:</strong> {html.escape(str(status.get('positive_window') or 'n/a'))}</p><p><strong>Control window:</strong> {html.escape(str(status.get('control_window') or 'n/a'))}</p><p>Companies are held out by GitHub organisation during cross-validation, preventing the same company from appearing in both train and test folds.</p></section>
<section class="card section"><h2>What the result means</h2><p>The historical ranker achieved ROC-AUC <strong>{auc}</strong>, with a company-cluster bootstrap 95% interval of <strong>{ci_low}–{ci_high}</strong>. The original hand-weighted Scout Score produced ROC-AUC <strong>{baseline_auc}</strong> on this specific funding-window task.</p><p>VCScout therefore keeps the two concepts separate: Scout Score measures engineering momentum; the Historical Funding Pattern Index ranks similarity to patterns observed before known financing events.</p></section>
</div>
<section class="card section"><h2>Interpretation guardrails</h2><ul><li>An index of 90 means the company ranks around the 90th percentile of the <em>current comparison universe</em> under the historical ranker.</li><li>It does not mean a 90% chance of fundraising.</li><li>The backtest uses public repositories; private engineering work is invisible.</li><li>The historical sample is still small, so the signal should be treated as directional rather than production-grade underwriting.</li><li>The separate 90-day probability model remains locked until prospective, population-calibrated outcome labels pass the required validation gates.</li></ul></section>
<footer>VCScout AI · Historical validation report · Research prioritisation only. Metrics are generated from the versioned backtest artifact in this repository.</footer>
</div></body></html>'''
