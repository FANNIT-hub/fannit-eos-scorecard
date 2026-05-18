"""Live-metrics aggregator with a short TTL cache.

Maps a week label ("M/D") + agency to live source values, keyed by KPI
label so the scorecard reader can override sheet values.

Only the *current / last-completed* week is served live. For older weeks
we return {} so the reader falls back to the sheet (which is what the
snapshot job stamped at the time). This is correct because:
  - HL events/opps ARE historical-accurate (date-filtered), but
  - Teamwork onboarding is a live snapshot with no historical query, so
    a live call for an old week would be wrong.
Limiting live calls to the current week also keeps us well under HL rate
limits and keeps dashboard loads fast.
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from ..config import AGENCIES
from . import highlevel, teamwork

log = logging.getLogger("eos-scorecard.aggregate")

PT = ZoneInfo("America/Los_Angeles")
SCORECARD_YEAR = 2026
CACHE_TTL_SECONDS = 600  # 10 min

# KPI labels in the scorecard that this module can supply live.
LIVE_KPI_LABELS = (
    "Discovery Calls",
    "New Sales (15% of Discovery)",
    "Clients in Onboarding",
)
# Strategy/Planning is computed too (for the snapshot job) but is not yet a
# displayed KPI card.
STRATEGY_KPI_LABEL = "Strategy / Planning Calls"

_cache: dict[tuple[str, str], tuple[float, dict]] = {}


def _week_window(week_label: str) -> tuple[datetime, datetime]:
    """week_label 'M/D' (a Monday) -> [Mon 00:00 PT, next Mon 00:00 PT)."""
    m, d = (int(x) for x in week_label.split("/"))
    start = datetime(SCORECARD_YEAR, m, d, 0, 0, tzinfo=PT)
    return start, start + timedelta(days=7)


def is_live_week(week_label: str, today_label: str) -> bool:
    """Live data is served only for the last-completed week (the dashboard
    default) and the in-progress week. Everything older = sheet fallback.
    """
    try:
        wm, wd = (int(x) for x in week_label.split("/"))
        tm, td = (int(x) for x in today_label.split("/"))
    except (ValueError, AttributeError):
        return False
    wk = datetime(SCORECARD_YEAR, wm, wd, tzinfo=PT)
    tk = datetime(SCORECARD_YEAR, tm, td, tzinfo=PT)
    # within 8 days (current week + last-completed week)
    return abs((wk - tk).days) <= 8


def live_metrics(agency: str, week_label: str) -> dict:
    """Returns {kpi_label: value} for the agency/week, or {} if not a live
    week or on total failure. Individual metric failures yield None for that
    metric (sheet fallback handled by the caller).
    """
    key = (agency, week_label)
    now = time.time()
    hit = _cache.get(key)
    if hit and now - hit[0] < CACHE_TTL_SECONDS:
        return hit[1]

    start, end = _week_window(week_label)
    result: dict = {}
    try:
        hl = highlevel.weekly_metrics(agency, start, end)
        if hl.get("discovery_calls") is not None:
            result["Discovery Calls"] = hl["discovery_calls"]
        if hl.get("new_sales") is not None:
            result["New Sales (15% of Discovery)"] = hl["new_sales"]
        if hl.get("strategy_calls") is not None:
            result[STRATEGY_KPI_LABEL] = hl["strategy_calls"]
    except Exception as exc:  # noqa: BLE001
        log.warning("live HL fail %s %s: %s", agency, week_label, exc)

    try:
        ob = teamwork.onboarding_count(agency)
        if ob is not None:
            result["Clients in Onboarding"] = ob
    except Exception as exc:  # noqa: BLE001
        log.warning("live Teamwork fail %s %s: %s", agency, week_label, exc)

    _cache[key] = (now, result)
    return result


def all_agencies_live(week_label: str) -> dict[str, dict]:
    """Snapshot helper: live metrics for every agency for a week."""
    return {ag: live_metrics(ag, week_label) for ag in AGENCIES}
