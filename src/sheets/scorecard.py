"""Reader for the `2026 Scorecard` tab in the All Accounts & KPIs workbook.

Each agency block in the tab is laid out the same way:

  Row N          | <AGENCY NAME>     | (year header band)
  Row N+1        | Own | KPI         | Goal (col F, annual) | Actual (G, YTD) | Hit (H) | per-month bands
  Rows N+2..N+9  | 8 KPI rows in fixed order

This reader takes a known agency-block start row and pulls the 8 KPI labels +
annual goal + YTD actual + hit % for each. Per-week values come later.
"""

from dataclasses import asdict, dataclass

from .client import get_sheets_service
from ..config import SCORECARD_SHEET_ID, SCORECARD_TAB_NAME


# Agency block layout in the 2026 Scorecard tab.
# Confirmed during scoping (2026-04-27); TMSA / IPA offsets to be verified
# the first time the reader runs against them.
AGENCY_BLOCKS: dict[str, dict[str, int]] = {
    "FANNIT": {"header_row": 36, "kpi_rows_start": 38},
    "HMC": {"header_row": 73, "kpi_rows_start": 75},
    # TMSA: TBD
    # IPA: TBD
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


@dataclass
class Kpi:
    label: str
    source: str
    fmt: str  # "number" / "currency" / "percent"
    annual_goal: float | None
    ytd_actual: float | None
    hit_pct: float | None


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


def read_agency_kpis(agency: str) -> list[Kpi]:
    """Returns 8 KPI rows for an agency from the 2026 Scorecard tab.

    Reads E:H of the 8 KPI rows (label / annual goal / YTD actual / hit %).
    """
    if agency not in AGENCY_BLOCKS:
        raise ValueError(
            f"Agency block for '{agency}' not yet mapped in AGENCY_BLOCKS. "
            f"Available: {list(AGENCY_BLOCKS)}"
        )
    block = AGENCY_BLOCKS[agency]
    start = block["kpi_rows_start"]
    end = start + len(KPI_LABELS) - 1
    rng = f"'{SCORECARD_TAB_NAME}'!E{start}:H{end}"

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
        # Row layout: [E=label, F=goal, G=actual, H=hit]
        out.append(
            Kpi(
                label=label,
                source=KPI_DATA_SOURCE.get(label, "—"),
                fmt=KPI_FORMAT.get(label, "number"),
                annual_goal=_to_float(row[1]) if len(row) > 1 else None,
                ytd_actual=_to_float(row[2]) if len(row) > 2 else None,
                hit_pct=_to_float(row[3]) if len(row) > 3 else None,
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
