"""FANNIT EOS L10 Scorecard - main Cloud Run entry point.

Hosts:
  - Frontend (static index.html + assets) at /
  - Dashboard read API at /api/*
  - Internal snapshot job trigger at /internal/snapshot (called by Cloud Scheduler)
"""

import os
import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from src.sheets.scorecard import AGENCY_BLOCKS, kpis_to_payload

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("eos-scorecard")

STATIC_DIR = Path(__file__).parent / "static"

app = FastAPI(title="FANNIT EOS Scorecard", version="0.1.0")


@app.get("/healthz")
def healthz():
    return {"ok": True}


@app.get("/api/agencies")
def list_agencies():
    """Which agencies the dashboard knows how to render right now."""
    return {"agencies": sorted(AGENCY_BLOCKS.keys())}


@app.get("/api/scorecard")
def get_scorecard(agency: str = "FANNIT"):
    if agency not in AGENCY_BLOCKS:
        return JSONResponse(
            status_code=404,
            content={
                "error": "agency_not_mapped",
                "agency": agency,
                "available": sorted(AGENCY_BLOCKS.keys()),
                "note": "TMSA and IPA block offsets in the 2026 Scorecard tab "
                "still need to be wired. FANNIT and HMC are live.",
            },
        )
    try:
        return kpis_to_payload(agency)
    except Exception as exc:  # noqa: BLE001
        log.exception("Failed to read scorecard for %s", agency)
        return JSONResponse(
            status_code=500,
            content={"error": "sheet_read_failed", "agency": agency, "detail": str(exc)},
        )


@app.post("/internal/snapshot")
def run_snapshot():
    return JSONResponse(
        status_code=501,
        content={"error": "not_implemented", "next": "wire src/snapshot.py"},
    )


# Serve the static frontend last so /api/* and /healthz win when paths overlap.
if STATIC_DIR.exists():
    app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True), name="static")
else:
    log.warning("Static directory %s does not exist; frontend not mounted", STATIC_DIR)

    @app.get("/")
    def fallback_root():
        return JSONResponse(
            {
                "service": "fannit-eos-scorecard",
                "status": "scaffold",
                "message": "Static dir missing; backend up.",
            }
        )
