"""Reader for the `2026 Scorecard` tab in the All Accounts & KPIs workbook.

Each agency block in the tab is laid out the same way:

  Row N          | <AGENCY NAME>     | (year header band)
  Row N+1        | Own | KPI         | Goal (col F, annual) | Actual (G, YTD) | Hit (H) | per-month bands
  Rows N+2..N+9  | 8 KPI rows in fixed order

The per-month bands repeat: [Goal | week1 | week2 | week3 | (week4|week5) | Calendar Month Actual]
where the weekN cells are the actual weekly values written by the snapshot job
or entered manually.

This reader pulls per KPI:
  - annual_goal (col F)
  - ytd_actual (col G)
  - hit_pct (col H)
  - current_week_value: rightmost populated weekly cell (skips Goal / CMA cells)
  - current_week_date: the header label for that column (e.g. "4/27")
  - weekly_goal: annual_goal / 52 for incremental metrics; annual_goal for
    snapshot / rate metrics
  - weekly_hit_pct: current_week_value vs weekly_goal
"""

from dataclasses import asdict, dataclass, field
from typing import Optional

from .client import get_sheets_service
from ..config import SCORECARD_SHEET_ID, SCORECARD_TAB_NAME


# Agency block layout in the 2026 Scorecard tab.
# Confirmed during scoping (2026-04-27); TMSA / IPA offsets to be verified
# the first time the reader runs against them.
AGENCY_BLOCKS: dict[str, dict[str, int]] = {
    "FANNIT": {"header_row": 36, "kpi_rows_start": 38},
    "HMC": {"header_row": 73, "kpi_rows_start": 75},
    "TMSA": {"header_row": 94, "kpi_rows_start": 96},
    "IPA": {"header_row": 115, "kpi_rows_start": 117},
}


KPI_LABELS: list[str] = [
    "Website / LP Traffic",
    "Discovery Calls",
    "New Sales (15% of Discovery)",
    "Clients in Onboarding",
    "Churn Over Last 12 Months",
    "Total $ AR Past 30 Days",
    "Cash Collected",
    "Cash on Hand",
]

KPI_DATA_SOURCE: dict[str, str] = {
    "Website / LP Traffic": "GA4",
    "Discovery Calls": "HighLevel Calendar",
    "New Sales (15% of Discovery)": "HighLevel Pipeline",
    "Clients in Onboarding": "Teamwork",
    "Churn Over Last 12 Months": "Upsells & Churn Sheet",
    "Total $ AR Past 30 Days": "QuickBooks Online",
    "Cash Collected": "QuickBooks P&L",
    "Cash on Hand": "QuickBooks Balance Sheet",
}

# Some KPIs use percent values (Churn, Hit), some are dollars, some are counts.
# Drives display formatting on the frontend.
KPI_FORMAT: dict[str, str] = {
    "Website / LP Traffic": "number",
    "Discovery Calls": "number",
    "New Sales (15% of Discovery)": "number",
    "Clients in Onboarding": "number",
    "Churn Over Last 12 Months": "percent",
    "Total $ AR Past 30 Days": "currency",
    "Cash Collected": "currency",
    "Cash on Hand": "currency",
}

# Metric behavior, drives how weekly_goal and hit % are computed per KPI:
#   incremental: sum across weeks; weekly_goal = annual_goal / 52
#   snapshot:    point-in-time; weekly_goal = annual_goal (the target balance)
#   rate:        trailing-12mo rate; weekly_goal = annual_goal (the target rate)
KPI_TYPE: dict[str, str] = {
    "Website / LP Traffic": "incremental",
    "Discovery Calls": "incremental",
    "New Sales (15% of Discovery)": "incremental",
    "Clients in Onboarding": "snapshot",
    "Churn Over Last 12 Months": "rate",
    "Total $ AR Past 30 Days": "snapshot",
    "Cash Collected": "incremental",
    "Cash on Hand": "snapshot",
}

# Cells in row 37 (header row) that are NOT weekly date columns. Used to
# distinguish weekly cells from Goal / Calendar Month Actual cells.
NON_WEEK_HEADER_LABELS = {
    "goal",
    "actual",
    "hit",
    "kpi",
    "own",
    "calendar month actual",
    "",
}


@dataclass
class WeekValue:
    date: str
    value: float | None


@dataclass
class Kpi:
    label: str
    source: str
    fmt: str  # "number" / "currency" / "percent"
    metric_type: str  # "incremental" / "snapshot" / "rate"
    annual_goal: float | None
    ytd_actual: float | None
    hit_pct: float | None  # YTD against annual goal (formula in sheet)
    current_week_value: float | None
    current_week_date: str | None
    weekly_goal: float | None  # pro-rated for incremental, target for snapshot/rate
    weekly_hit_pct: float | None  # current week against weekly goal
    weeks: list[WeekValue] = field(default_factory=list)  # last 8 populated weeks


def _to_float(v) -> float | None:
    if v is None or v == "":
        return None
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).strip()
    if not s:
        return None
    # Tolerate stray "$", ",", "%" if a cell happened to be string-formatted.
    s = s.replace("$", "").replace(",", "").replace("%", "").strip()
    try:
        return float(s)
    except ValueError:
        return None


def _col_index_to_letter(idx_1based: int) -> str:
    s = ""
    n = idx_1based
    while n > 0:
        n, r = divmod(n - 1, 26)
        s = chr(65 + r) + s
    return s


def _get_week_columns(header_row: int, max_col: str = "DZ") -> list[tuple[int, str]]:
    """Reads the agency's KPI-header row (e.g. row 37 for FANNIT) and returns
    [(absolute_col_index_1based, date_label), ...] for cells that are weekly
    date columns. Skips Goal, Hit, Calendar Month Actual, and blanks.
    """
    rng = f"'{SCORECARD_TAB_NAME}'!I{header_row}:{max_col}{header_row}"
    svc = get_sheets_service()
    resp = (
        svc.spreadsheets()
        .values()
        .get(
            spreadsheetId=SCORECARD_SHEET_ID,
            range=rng,
            valueRenderOption="FORMATTED_VALUE",
        )
        .execute()
    )
    rows = resp.get("values", [])
    if not rows:
        return []
    headers = rows[0]
    out: list[tuple[int, str]] = []
    for i, h in enumerate(headers):
        col_idx = 9 + i  # I = column 9 (1-based)
        label = "" if h is None else str(h).strip()
        if not label:
            continue
        if label.lower() in NON_WEEK_HEADER_LABELS:
            continue
        out.append((col_idx, label))
    return out


def _compute_weekly_goal(annual_goal: float | None, metric_type: str) -> float | None:
    if annual_goal is None:
        return None
    if metric_type == "incremental":
        return annual_goal / 52.0
    return annual_goal  # snapshot or rate


def _compute_weekly_hit_pct(
    current: float | None, weekly_goal: float | None
) -> float | None:
    if current is None or weekly_goal is None or weekly_goal == 0:
        return None
    return current / weekly_goal


def read_agency_kpis(agency: str, weeks_history: int = 8) -> list[Kpi]:
    """Returns 8 KPI rows including the rightmost-populated weekly value plus
    the last `weeks_history` populated weekly values for trend display.
    """
    if agency not in AGENCY_BLOCKS:
        raise ValueError(
            f"Agency block for '{agency}' not yet mapped in AGENCY_BLOCKS. "
            f"Available: {list(AGENCY_BLOCKS)}"
        )
    block = AGENCY_BLOCKS[agency]
    header_row = block["header_row"] + 1  # KPI column-header row (e.g. 37)
    start = block["kpi_rows_start"]
    end = start + len(KPI_LABELS) - 1

    week_cols = _get_week_columns(header_row)
    if not week_cols:
        last_col_letter = "H"
    else:
        last_col_letter = _col_index_to_letter(week_cols[-1][0])

    rng = f"'{SCORECARD_TAB_NAME}'!E{start}:{last_col_letter}{end}"
    svc = get_sheets_service()
    resp = (
        svc.spreadsheets()
        .values()
        .get(
            spreadsheetId=SCORECARD_SHEET_ID,
            range=rng,
            valueRenderOption="UNFORMATTED_VALUE",
        )
        .execute()
    )
    rows = resp.get("values", [])

    out: list[Kpi] = []
    for i, label in enumerate(KPI_LABELS):
        row = rows[i] if i < len(rows) else []
        annual_goal = _to_float(row[1]) if len(row) > 1 else None
        ytd_actual = _to_float(row[2]) if len(row) > 2 else None
        hit_pct = _to_float(row[3]) if len(row) > 3 else None

        # Walk weekly columns, collect all populated weekly values
        all_weeks: list[WeekValue] = []
        for col_idx, date_str in week_cols:
            offset = col_idx - 5  # E is col 5 (1-based) -> offset 0
            v = _to_float(row[offset]) if 0 <= offset < len(row) else None
            if v is not None:
                all_weeks.append(WeekValue(date=date_str, value=v))

        # Most recent populated week = rightmost; last N = trailing for the table
        current = all_weeks[-1] if all_weeks else None
        recent = all_weeks[-weeks_history:] if all_weeks else []

        metric_type = KPI_TYPE.get(label, "incremental")
        weekly_goal = _compute_weekly_goal(annual_goal, metric_type)
        current_value = current.value if current else None
        current_date = current.date if current else None
        weekly_hit = _compute_weekly_hit_pct(current_value, weekly_goal)

        out.append(
            Kpi(
                label=label,
                source=KPI_DATA_SOURCE.get(label, "—"),
                fmt=KPI_FORMAT.get(label, "number"),
                metric_type=metric_type,
                annual_goal=annual_goal,
                ytd_actual=ytd_actual,
                hit_pct=hit_pct,
                current_week_value=current_value,
                current_week_date=current_date,
                weekly_goal=weekly_goal,
                weekly_hit_pct=weekly_hit,
                weeks=recent,
            )
        )
    return out


def kpis_to_payload(agency: str) -> dict:
    """Public wrapper that returns a JSON-friendly payload for the API."""
    kpis = read_agency_kpis(agency)
    return {
        "agency": agency,
        "kpis": [asdict(k) for k in kpis],
    }
