from __future__ import annotations

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

from generate_dashboard import load_all_projects, make_dashboard_payload, render_html


app = FastAPI(title="QA UAT Dashboard")


def build_latest_payload() -> dict:
    """Baca ulang Excel setiap ada request agar dashboard selalu memakai data terbaru."""
    df = load_all_projects()
    return make_dashboard_payload(df)


@app.get("/", include_in_schema=False)
def home() -> RedirectResponse:
    return RedirectResponse(url="/output/uat_dashboard.html")


@app.get("/output/uat_dashboard.html", response_class=HTMLResponse)
def dashboard() -> HTMLResponse:
    try:
        payload = build_latest_payload()
        html = render_html(payload)
        return HTMLResponse(
            content=html,
            headers={
                "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
                "Pragma": "no-cache",
            },
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/api/dashboard-data")
def dashboard_data() -> JSONResponse:
    try:
        payload = build_latest_payload()
        return JSONResponse(
            content=payload,
            headers={"Cache-Control": "no-store, no-cache, must-revalidate, max-age=0"},
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
