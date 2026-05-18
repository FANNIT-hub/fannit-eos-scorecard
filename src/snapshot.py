"""Weekly snapshot job.

Pulls live source metrics for every agency for a target week and writes the
values into the matching weekly cells of the `2026 Scorecard` tab. This is
the "push INTO the sheet" half of the architecture: sources are the source
of truth, the sheet is the durable write target / legacy view.

Only KPIs we can currently source live are written:
  - Discovery Calls          (HighLevel)
  - New Sales (15% of ...)   (HighLevel)
  - Clients in Onboarding    (Teamwork)

Strategy/Planning is computed but has no row in the 8-KPI block, so it is
not written. Traffic (GA4) and the QBO trio are not written until those
integrations are unblocked.

Triggered weekly by Cloud Scheduler (planned) or manually via
POST /internal/snapshot.
"""

from __future__ import annotations

import logging

from .config import AGENCIES
from .sheets.client import get_sheets_service
from .sheets.scorecard import (
    AGENCY_BLOCKS,
    KPI_LABELS,
    SCORECARD_TAB_NAME,
    _col_index_to_letter,
    _get_week_columns,
    last_completed_week_label,
)
from .config import SCORECARD_SHEET_ID
from .sources import aggregate

log = logging.getLogger("eos-scorecard.snapshot")

# Live KPI label -> its index within the 8-row KPI block.
_LIVE_LABEL_ROW_OFFSET = {
    "Website / LP Traffic": KPI_LABELS.index("Website / LP Traffic"),
    "Discovery Calls": KPI_LABELS.index("Discovery Calls"),
    "New Sales (15% of Discovery)": KPI_LABELS.index("New Sales (15% of Discovery)"),
    "Clients in Onboarding": KPI_LABELS.index("Clients in Onboarding"),
}


def run_snapshot(week_label: str | None = None) -> dict:
    """Pull live metrics for all agencies for `week_label` (default: last
    completed week) and write them into the sheet. Returns a summary.
    """
    week = week_label or last_completed_week_label()
    svc = get_sheets_service()
    summary: dict = {"week": week, "agencies": {}, "cells_written": 0}

    for agency in AGENCIES:
        block = AGENCY_BLOCKS.get(agency)
        if not block:
            summary["agencies"][agency] = "no block mapped"
            continue

        header_row = block["header_row"] + 1
        kpi_start = block["kpi_rows_start"]

        # Find the sheet column for this week label.
        week_cols = _get_week_columns(header_row)
        col_idx = next((ci for ci, lbl in week_cols if lbl == week), None)
        if col_idx is None:
            summary["agencies"][agency] = f"week column '{week}' not found"
            continue
        col_letter = _col_index_to_letter(col_idx)

        live = aggregate.live_metrics(agency, week)
        if not live:
            summary["agencies"][agency] = "no live data"
            continue

        data = []
        written = []
        for label, offset in _LIVE_LABEL_ROW_OFFSET.items():
            if label not in live or live[label] is None:
                continue
            row = kpi_start + offset
            cell = f"'{SCORECARD_TAB_NAME}'!{col_letter}{row}"
            data.append({"range": cell, "values": [[live[label]]]})
            written.append(f"{label}={live[label]}@{col_letter}{row}")

        if not data:
            summary["agencies"][agency] = "live data present but nothing mappable"
            continue

        try:
            svc.spreadsheets().values().batchUpdate(
                spreadsheetId=SCORECARD_SHEET_ID,
                body={"valueInputOption": "USER_ENTERED", "data": data},
            ).execute()
            summary["agencies"][agency] = written
            summary["cells_written"] += len(data)
        except Exception as exc:  # noqa: BLE001
            log.exception("snapshot write failed for %s", agency)
            summary["agencies"][agency] = f"write error: {exc}"

    log.info("snapshot complete: %s", summary)
    return summary
