# FANNIT EOS L10 Scorecard

Self-updating EOS Level 10 scorecard dashboard for the FANNIT family of agencies (FANNIT, TMSA, HMC, IPA).

Pulls weekly metrics from GA4, HighLevel, Teamwork, QuickBooks Online, and the existing Google Sheet workbook; writes actuals back into the `2026 Scorecard` tab for legacy continuity; serves a read-only dashboard from Cloud Run.

## Status

Pre-build scaffold. See `fannit_eos_scorecard_brief.md` in the discovery folder for the full technical spec.

## Stack

- Python 3.11 / FastAPI on Cloud Run
- Cloud Scheduler weekly trigger
- Google Sheets as data layer (read goals, write actuals)
- Frontend: Next.js (to be added)

## Deployment

GCP project: `fannit-eos-scorecard` (us-central1)
Auto-deploy via Cloud Build on push to `main`.
