"""Agency configuration: per-agency identifiers for each upstream source.

Secrets (HL PITs, QBO refresh tokens, Teamwork API token, service account JSON)
live in Secret Manager and are fetched at runtime, not stored here.

Non-secret IDs (HL location IDs, pipeline IDs, stage IDs, GA4 property IDs)
live in this file because they are config, not credentials, and tracking them
in source control gives us auditable change history.
"""

from typing import TypedDict


# ---------------------------------------------------------------------------
# Agency keys used everywhere in the codebase.
# ---------------------------------------------------------------------------
AGENCIES = ("FANNIT", "TMSA", "HMC", "IPA")


# ---------------------------------------------------------------------------
# HighLevel V2 API config
#
# - location_id:    sub-account ID; required in path/query of every HL V2 call
# - secret_name:    name of the Secret Manager secret holding the PIT for this
#                   location (PITs are location-scoped; one per sub-account)
# - pipeline_id:    the pipeline that drives discovery/strategy/won counts
#                   for this agency. Per Chris (2026-04-27): FANNIT uses
#                   "2: Active Sales", others use "💸 SALES PIPELINE"
# - won_stage_id:   the stage in pipeline_id that signals a closed-won deal
# ---------------------------------------------------------------------------
class HighLevelAgencyConfig(TypedDict):
    location_id: str
    secret_name: str
    pipeline_id: str
    pipeline_name: str
    won_stage_id: str


HIGHLEVEL: dict[str, HighLevelAgencyConfig] = {
    "FANNIT": {
        "location_id": "q2x8tokGpDhlOu8bgVLN",
        "secret_name": "highlevel-pit-fannit",
        "pipeline_id": "OeYgK000wVzh0pxH3edY",
        "pipeline_name": "2: Active Sales",
        "won_stage_id": "ff032485-ffef-4a8f-91b7-1f5db6596678",  # Closed - Won
    },
    "HMC": {
        "location_id": "LAkDi1yul6kxjPcqkLxb",
        "secret_name": "highlevel-pit-hmc",
        "pipeline_id": "UwK3pSQmvBJGzeNPfmoJ",
        "pipeline_name": "💸 SALES PIPELINE",
        "won_stage_id": "45fa598d-26a8-4b82-81aa-55242518a2cd",  # 💸 Closed and Won
    },
    "TMSA": {
        "location_id": "Fj5y9oD9dIJWGHRCeNCW",
        "secret_name": "highlevel-pit-tmsa",
        "pipeline_id": "5wfjI8JTTuesnVlFSWg5",
        "pipeline_name": "💸 SALES PIPELINE",
        "won_stage_id": "a2a57886-4de4-4701-9c21-8f6843facc28",  # 💸 Closed and Won
    },
    "IPA": {
        "location_id": "TTv1Bn2QeGBIKwcP72zA",
        "secret_name": "highlevel-pit-ipa",
        # Two "💸 SALES PIPELINE" pipelines exist in IPA. Chris confirmed
        # 2026-04-27: use the one with 63 opportunities (clean linear flow).
        "pipeline_id": "T4bqE5CGEaw8P2vU1H0z",
        "pipeline_name": "💸 SALES PIPELINE",
        "won_stage_id": "a8b13c1f-149c-49ff-a48e-876082b8a646",  # 🖐️ CLOSED AND WON
    },
}


# ---------------------------------------------------------------------------
# Calendar inclusion rules for discovery / strategy / planning call counts.
#
# Per Chris (2026-04-27):
#   - Calendar must be wired to the agency's named pipeline (calendar's
#     pipelineId == HIGHLEVEL[agency].pipeline_id).
#   - Calendar must be active (isActive=True).
#   - Calendar name must NOT contain "internal" (case-insensitive).
#   - Bucketing: name contains "discovery" -> discovery; name contains
#     "strategy" or "planning" -> strategy/planning.
#   - Appointment status must be "showed".
# ---------------------------------------------------------------------------
DISCOVERY_NAME_TOKENS = ("discovery",)
STRATEGY_NAME_TOKENS = ("strategy", "planning")
EXCLUDED_NAME_TOKENS = ("internal",)
APPOINTMENT_SHOWED_STATUS = "showed"


# ---------------------------------------------------------------------------
# GA4 config
#
# One property per agency. Service account auth (single shared SA) granted
# Viewer on each property out-of-band by Chris.
# ---------------------------------------------------------------------------
GA4_PROPERTY_IDS: dict[str, str] = {
    "FANNIT": "319269316",
    "HMC": "464894002",
    "TMSA": "473651067",
    "IPA": "496676704",
}
GA4_METRIC = "sessions"


# ---------------------------------------------------------------------------
# Teamwork config
#
# Single shared instance at fannit.teamwork.com. Per Chris: filter projects
# by Category = agency name AND Tag = "Onboarding".
# ---------------------------------------------------------------------------
TEAMWORK_DOMAIN = "fannit.teamwork.com"
TEAMWORK_ONBOARDING_TAG = "Onboarding"

# Map agency key -> Teamwork project Category name. To be confirmed when
# wiring Teamwork (the category strings need to match exactly what's in the
# Teamwork UI).
TEAMWORK_AGENCY_CATEGORY: dict[str, str] = {
    "FANNIT": "FANNIT",
    "HMC": "Hardscape Marketing Crew",
    "TMSA": "The Med Spa Agency",
    "IPA": "Inspired Painting Marketing Agency",
}


# ---------------------------------------------------------------------------
# QuickBooks Online config
#
# IPA does not have QBO at time of build. AR / Cash Collected / Cash on Hand
# render as "—" for IPA until that's set up.
#
# Realm IDs and refresh tokens come from Secret Manager at runtime. Shared
# Intuit developer app's client_id / client_secret also from Secret Manager.
# ---------------------------------------------------------------------------
QBO_AGENCIES_WITH_ACCESS = ("FANNIT", "TMSA", "HMC")


# ---------------------------------------------------------------------------
# Google Sheet (workbook hosting goals + weekly actuals)
# ---------------------------------------------------------------------------
SCORECARD_SHEET_ID = "1QyyYNoNR05V8hxjGSBYfvPqWANx37kJiGw3ePx-hz8c"
SCORECARD_TAB_NAME = "2026 Scorecard"
UPSELLS_CHURN_TAB_GID = 130117843
