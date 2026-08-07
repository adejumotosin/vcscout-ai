from __future__ import annotations

import sys
from pathlib import Path

from fastapi.responses import HTMLResponse, Response

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

from vcscout.api import app  # noqa: E402
from vcscout.backtest_page import render_backtest_page  # noqa: E402
from vcscout.pattern import historical_pattern_status  # noqa: E402
from vcscout.web_v2 import DASHBOARD_HTML  # noqa: E402


def _dashboard_html() -> str:
    """Apply small Phase 2.1 UI additions without duplicating the main dashboard bundle."""
    html = DASHBOARD_HTML
    html = html.replace(
        '<a class="ghost" href="/docs" target="_blank">API Docs ↗</a>',
        '<a class="ghost" href="/backtest">Backtest ↗</a><a class="ghost" href="/docs" target="_blank">API Docs ↗</a>',
    )
    html = html.replace(
        '<th>#</th><th>Company</th><th>Scout</th><th>Funding 90d</th>',
        '<th>#</th><th>Company</th><th>Scout</th><th>Pattern</th><th>Funding 90d</th>',
    )
    html = html.replace(
        'function probabilityCell(x){',
        'function patternCell(x){return Number.isFinite(Number(x.funding_pattern_index))?`<span class="prob">${Number(x.funding_pattern_index).toFixed(1)}</span>`:`<span class="pending">n/a</span>`}\nfunction probabilityCell(x){',
    )
    html = html.replace(
        '<td class="score">${Number(x.vc_scout_score).toFixed(1)}</td><td>${probabilityCell(x)}</td>',
        '<td class="score">${Number(x.vc_scout_score).toFixed(1)}</td><td>${patternCell(x)}</td><td>${probabilityCell(x)}</td>',
    )
    html = html.replace('colspan="9"', 'colspan="10"')
    return html


@app.get("/", response_class=HTMLResponse, include_in_schema=False)
def dashboard() -> HTMLResponse:
    """Serve the Vercel-native VCScout dashboard."""
    return HTMLResponse(
        content=_dashboard_html(),
        headers={
            "Cache-Control": "public, max-age=0, s-maxage=300, stale-while-revalidate=600"
        },
    )


@app.get("/backtest", response_class=HTMLResponse, include_in_schema=False)
def backtest() -> HTMLResponse:
    return HTMLResponse(
        content=render_backtest_page(historical_pattern_status()),
        headers={
            "Cache-Control": "public, max-age=0, s-maxage=300, stale-while-revalidate=600"
        },
    )


@app.get("/favicon.ico", include_in_schema=False)
def favicon() -> Response:
    return Response(status_code=204)
