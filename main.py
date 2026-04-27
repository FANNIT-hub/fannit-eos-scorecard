"""FANNIT EOS L10 Scorecard - main Cloud Run entry point.

Hosts:
  - Frontend (static / Next.js build) at /
  - Dashboard read API at /api/*
  - Internal snapshot job trigger at /internal/snapshot (called by Cloud Scheduler)
"""

import os
from fastapi import FastAPI
from fastapi.responses import JSONResponse

app = FastAPI(title="FANNIT EOS Scorecard", version="0.0.1")


@app.get("/")
def root():
    return JSONResponse(
        {
            "service": "fannit-eos-scorecard",
            "status": "scaffold",
            "message": "Backend skeleton up. Snapshot job, API endpoints, and frontend not yet wired.",
        }
    )


@app.get("/healthz")
def healthz():
    return {"ok": True}


@app.get("/api/scorecard")
def get_scorecard(agency: str = "FANNIT", period: str = "Weekly", date: str | None = None):
    """Returns the scorecard payload for one agency + one period.

    Not yet implemented. Will return KPIs, weekly strip, YTD, and goals
    once the sheet reader and source clients are wired.
    """
    return JSONResponse(
        status_code=501,
        content={"error": "not_implemented", "agency": agency, "period": period, "date": date},
    )


@app.post("/internal/snapshot")
def run_snapshot():
    """Triggered weekly by Cloud Scheduler. Pulls all sources, writes to the sheet."""
    return JSONResponse(
        status_code=501,
        content={"error": "not_implemented", "next": "wire src/snapshot.py"},
    )
