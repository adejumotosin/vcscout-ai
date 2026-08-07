from __future__ import annotations

import sys
from pathlib import Path

from fastapi.responses import HTMLResponse, Response

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

from vcscout.api import app  # noqa: E402
from vcscout.web import DASHBOARD_HTML  # noqa: E402


@app.get("/", response_class=HTMLResponse, include_in_schema=False)
def dashboard() -> HTMLResponse:
    """Serve the Vercel-native VCScout dashboard."""
    return HTMLResponse(
        content=DASHBOARD_HTML,
        headers={
            "Cache-Control": "public, max-age=0, s-maxage=300, stale-while-revalidate=600"
        },
    )


@app.get("/favicon.ico", include_in_schema=False)
def favicon() -> Response:
    return Response(status_code=204)
