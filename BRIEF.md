# FANNIT EOS L10 Scorecard — Master Brief

> **Audience:** Chris Fink (owner) and any future operator (technical or non-technical) who needs to run, deploy, debug, or extend this system.
>
> **Status:** This is a living document. Update it whenever architecture, integrations, or operational procedures change. Last meaningful update: 2026-04-27 (initial build).

---

## 1. What this is

A self-updating EOS Level 10 Scorecard dashboard for the FANNIT family of agencies (FANNIT, TMSA, HMC, IPA). Replaces the manual weekly update of the `2026 Scorecard` tab in the existing `All Accounts & KPIs - FANNIT` Google Sheet.

It pulls weekly metrics from GA4, HighLevel, Teamwork, QuickBooks Online, and an internal sheet tab; writes the actuals back into the existing `2026 Scorecard` tab for legacy continuity; and serves a read-only dashboard from Cloud Run that mirrors the Perplexity-built prototype.

---

## 2. Live URLs

| Resource | URL |
|---|---|
| Dashboard (live) | https://eos-scorecard-btpczli7ra-uc.a.run.app |
| GitHub repo | https://github.com/FANNIT-hub/fannit-eos-scorecard |
| Cloud Build (build progress) | https://console.cloud.google.com/cloud-build/builds?project=fannit-eos-scorecard |
| Cloud Run revisions | https://console.cloud.google.com/run/detail/us-central1/eos-scorecard/revisions?project=fannit-eos-scorecard |
| Secret Manager | https://console.cloud.google.com/security/secret-manager?project=fannit-eos-scorecard |
| Source Google Sheet | https://docs.google.com/spreadsheets/d/1QyyYNoNR05V8hxjGSBYfvPqWANx37kJiGw3ePx-hz8c/edit |

---

## 3. Repo structure

`G:\fannit-eos-scorecard\` (local working copy) → `https://github.com/FANNIT-hub/fannit-eos-scorecard.git`

```
fannit-eos-scorecard/
├── .gitignore                      # Python + Node + secrets exclusions
├── .dockerignore                   # excludes .env, .git, tests from container
├── .env.example                    # template for local dev (gitignored as .env)
├── BRIEF.md                        # this file
├── README.md                       # short marketing/intro
├── Dockerfile                      # python:3.11-slim, gunicorn + uvicorn worker, port 8080
├── cloudbuild.yaml                 # Build → Push → Deploy to Cloud Run us-central1
├── requirements.txt                # fastapi, uvicorn, gunicorn, google-* libs
├── main.py                         # FastAPI app: /api/agencies, /api/scorecard,
│                                   #   /internal/snapshot (501 stub), mounts /static
├── src/
│   ├── __init__.py
│   ├── config.py                   # per-agency IDs (HL, GA4, Teamwork, QBO list)
│   └── sheets/
│       ├── __init__.py
│       ├── client.py               # google-auth ADC client for Sheets API v4
│       └── scorecard.py            # reads 2026 Scorecard tab; KPI parsing,
│                                   #   weekly column discovery, metric-type logic
└── static/
    ├── index.html                  # dashboard page (sidebar + top-tabs + KPI grid + detail table)
    ├── styles.css                  # dark theme matching Perplexity prototype
    └── app.js                      # fetches /api/* and renders the dashboard
```

---

## 4. Stack & infrastructure

| Layer | Tech |
|---|---|
| Backend | Python 3.11, FastAPI, gunicorn (uvicorn worker) |
| Frontend | Plain HTML / CSS / vanilla JS (no framework yet, may upgrade later) |
| Compute | Cloud Run (managed), us-central1, single service |
| Container registry | Artifact Registry: `us-central1-docker.pkg.dev/fannit-eos-scorecard/eos-scorecard/` |
| Build | Cloud Build (manual via `gcloud builds submit`; GitHub auto-trigger pending) |
| Secrets | Secret Manager (per-secret IAM grants to runtime SA) |
| Auth (runtime) | Application Default Credentials → runtime SA in Cloud Run |
| Auth (viewer) | Currently public; Cloudflare Access planned |
| Schedule | Cloud Scheduler (planned, weekly Monday 06:00 PT — not yet wired) |

GCP project: `fannit-eos-scorecard` (under `fannit.com` org, billing 01C259-EB0584-76CB57)

---

## 5. Service accounts

| Account | Purpose |
|---|---|
| `eos-scorecard-runtime@fannit-eos-scorecard.iam.gserviceaccount.com` | Cloud Run runtime identity. Has Sheets API access (granted Editor on the source workbook) and Secret Manager Accessor on each project secret. |
| `909120368032-compute@developer.gserviceaccount.com` | Cloud Build default SA. Has Cloud Run admin, Service Account user, Artifact Registry writer, Logging writer (granted at project level). |

---

## 6. Data sources

### 6.1 Source map per KPI

| KPI | Source | Per-agency setup | Status |
|---|---|---|---|
| Website / LP Traffic | GA4 | One property per agency | ⏳ Property IDs in `src/config.py`; GA4 client not yet written. |
| Discovery Calls | HighLevel | One PIT per sub-account, calendars wired to named pipeline | ⏳ PITs in Secret Manager; HL client not yet written. |
| Strategy / Planning Calls | HighLevel | Same | ⏳ Same. |
| New Sales (won) | HighLevel Pipeline | Won-stage IDs locked in `src/config.py` | ⏳ Same. |
| Clients in Onboarding | Teamwork | Filter projects by Category=agency, Tag="Onboarding" | ⏳ API token in Secret Manager; Teamwork client not yet written. |
| Churn (trailing 12mo) | Internal sheet (Upsells & Churn tab, gid 130117843) | Aggregate today; per-agency split if data permits | ⏳ Reader not yet written. |
| Total $ AR Past 30 Days | QuickBooks Online | FANNIT/TMSA/HMC only (IPA: no QBO) | ⏳ No Intuit app yet. |
| Cash Collected | QBO | Same | ⏳ Same. |
| Cash on Hand | QBO | Same | ⏳ Same. |

### 6.2 Auth status per source

| Source | Auth method | Stored where | Set up |
|---|---|---|---|
| GA4 | Service account → Viewer per property | `eos-scorecard-runtime` SA needs to be added to each GA4 property | ❌ Not granted yet |
| HighLevel | Private Integration Token | Secret Manager: `highlevel-pit-{fannit,tmsa,hmc,ipa}` | ✅ All 4 stored |
| Teamwork | API token | Secret Manager: `teamwork-api-token` | ✅ Stored |
| QBO | OAuth 2.0 + refresh token | Secret Manager (planned: `qbo-refresh-token-{fannit,tmsa,hmc}`) | ❌ Intuit app not registered |
| Google Sheets | Service account → Editor on workbook | Workbook shared with `eos-scorecard-runtime` SA | ✅ Done |

---

## 7. Per-agency configuration

Lives in `src/config.py`. Non-secret IDs live here so they get version-controlled audit history.

### 7.1 HighLevel

| Agency | Location ID | Pipeline | Pipeline ID | Won Stage ID |
|---|---|---|---|---|
| FANNIT | `q2x8tokGpDhlOu8bgVLN` | 2: Active Sales | `OeYgK000wVzh0pxH3edY` | `ff032485-ffef-4a8f-91b7-1f5db6596678` (Closed - Won) |
| HMC | `LAkDi1yul6kxjPcqkLxb` | 💸 SALES PIPELINE | `UwK3pSQmvBJGzeNPfmoJ` | `45fa598d-26a8-4b82-81aa-55242518a2cd` (💸 Closed and Won) |
| TMSA | `Fj5y9oD9dIJWGHRCeNCW` | 💸 SALES PIPELINE | `5wfjI8JTTuesnVlFSWg5` | `a2a57886-4de4-4701-9c21-8f6843facc28` (💸 Closed and Won) |
| IPA | `TTv1Bn2QeGBIKwcP72zA` | 💸 SALES PIPELINE | `T4bqE5CGEaw8P2vU1H0z` | `a8b13c1f-149c-49ff-a48e-876082b8a646` (🖐️ CLOSED AND WON) |

Note for IPA: there are two pipelines named `💸 SALES PIPELINE`. Per Chris (2026-04-27), the canonical one is the variant with 63 opportunities (T4bqE...).

### 7.2 GA4 properties

| Agency | Property ID |
|---|---|
| FANNIT | `319269316` |
| HMC | `464894002` |
| TMSA | `473651067` |
| IPA | `496676704` |

Metric: `sessions`. Service account needs Viewer access on each property (not yet granted).

### 7.3 Teamwork

Single shared instance: `fannit.teamwork.com`.

Filter: project Category equals the agency name + project Tag equals `Onboarding`.

| Agency | Teamwork Category |
|---|---|
| FANNIT | FANNIT |
| HMC | Hardscape Marketing Crew |
| TMSA | The Med Spa Agency |
| IPA | Inspired Painting Marketing Agency |

Category strings are best guesses based on the agency-name conventions seen in other tabs of the workbook. Will be confirmed when the Teamwork client is wired and tested against a real project list.

### 7.4 QBO

QBO access at time of build: FANNIT, TMSA, HMC. **IPA has no QBO** and will render "—" for AR / Cash Collected / Cash on Hand until set up.

---

## 8. Sheet layout reference

### 8.1 Workbook
- File name: `All Accounts & KPIs - FANNIT`
- Sheet ID: `1QyyYNoNR05V8hxjGSBYfvPqWANx37kJiGw3ePx-hz8c`

### 8.2 Tabs used by this system

| Tab | gid | Used for |
|---|---|---|
| `2026 Scorecard` | (varies) | Goals + weekly actuals for all 4 agencies. Both the dashboard's data source AND the snapshot job's write target. |
| `Upsells & Churn` | 130117843 | Source for trailing-12-month churn per agency. |

### 8.3 `2026 Scorecard` tab structure

Each agency block follows the same shape, stacked vertically:

| Row offset (from header) | Content |
|---|---|
| 0 | Agency name in col E, year (2026) spanning F-G, month band headers across J onward |
| 1 | Column headers: Own \| KPI \| **Goal (F=annual)** \| Actual (G=YTD, formula) \| Hit (H, formula) \| then per-month: Goal \| weekN cells \| Calendar Month Actual |
| 2-9 | 8 KPI rows in fixed order |

**Block start rows (the agency-name row):**

| Agency | Header row | KPI rows |
|---|---|---|
| FANNIT | 36 | 38–45 |
| HMC | 73 | 75–82 |
| TMSA | 94 | 96–103 |
| IPA | 115 | 117–124 |

**KPI row order (always the same 8, top to bottom):**

1. Website / LP Traffic
2. Discovery Calls
3. New Sales (15% of Discovery)
4. Clients in Onboarding
5. Churn Over Last 12 Months
6. Total $ AR Past 30 Days
7. Cash Collected
8. Cash on Hand

### 8.4 Column meaning per agency block

| Column | Meaning |
|---|---|
| E | KPI label |
| **F** | **Annual goal** (read by dashboard; do not let formulas overwrite) |
| G | YTD Actual (formula; dashboard reads, snapshot job does NOT write) |
| H | Hit % (formula; same) |
| I | blank / separator |
| J | January monthly goal (formula or value) |
| K, L, M, N (or more) | Weekly actuals for January (week-ending Mondays) |
| O | January Calendar Month Actual (formula sum; do not write) |
| P | blank / separator |
| Q onward | February, repeating pattern |
| ... | Through December |

Snapshot job writes ONLY to weekly cells (the K/L/M/N… type columns), never to Goal cells, YTD cells, Hit cells, or Calendar Month Actual cells.

---

## 9. Dashboard behavior

### 9.1 Backend API endpoints

| Endpoint | Method | Purpose |
|---|---|---|
| `/healthz` | GET | Liveness probe. Returns `{"ok": true}`. |
| `/api/agencies` | GET | Lists agencies the dashboard knows how to render (`AGENCY_BLOCKS` keys). |
| `/api/scorecard?agency=FANNIT` | GET | Returns the agency's KPI payload. See §9.2. |
| `/internal/snapshot` | POST | Triggered by Cloud Scheduler weekly. Currently 501 stub. |
| `/` | GET | Serves `static/index.html`. Static assets served at `/styles.css`, `/app.js`. |

### 9.2 `/api/scorecard` payload shape

```json
{
  "agency": "FANNIT",
  "kpis": [
    {
      "label": "Website / LP Traffic",
      "source": "GA4",
      "fmt": "number",                 // "number" | "currency" | "percent"
      "metric_type": "incremental",    // "incremental" | "snapshot" | "rate"
      "annual_goal": 36000.0,
      "ytd_actual": 11026.0,
      "hit_pct": 0.306,
      "current_week_value": 458.0,
      "current_week_date": "4/27",
      "weekly_goal": 692.3,
      "weekly_hit_pct": 0.66,
      "weeks": [
        {"date": "3/2", "value": 338},
        {"date": "3/9", "value": 325},
        ...
      ]
    },
    ...
  ]
}
```

### 9.3 Frontend layout

Mirrors the Perplexity prototype:

- **Left sidebar:** logo + agency switcher (4 mapped agencies + a "Total Rollup" disabled item).
- **Top right:** period tabs (Weekly active; Q1-Q4 / Last Month / YTD disabled until weekly history accumulates).
- **Main pane:**
  - 4×2 grid of KPI cards: title, source, big number = current week value, "Week of" tag, weekly goal, weekly hit %, status dot (green ≥100%, yellow 50-99%, red <50%; inverted for Churn / AR Past 30).
  - "Weekly Scorecard Detail" table: KPI / Source / Annual Goal / YTD / Hit % + last 8 trailing weekly columns.
  - Two chart placeholders (Traffic & Discovery Trend, Financial Metrics) — to be wired once trend data is rich enough.

### 9.4 Metric-type behavior

| Type | KPIs | Aggregation in period | Goal direction | Weekly goal calc |
|---|---|---|---|---|
| Incremental | Traffic, Discovery, Strategy, New Sales, Cash Collected | sum the weeks in the period | higher = better | `annual / 52` |
| Snapshot | Onboarding, AR Past 30, Cash on Hand | latest week's value | mixed (Cash on Hand higher = better; AR lower = better) | `annual` (target balance) |
| Rate | Churn (trailing 12mo) | latest week's value | lower = better (inverted) | `annual` (target rate) |

---

## 10. Secrets

All secrets live in Secret Manager under project `fannit-eos-scorecard`. Each grants `roles/secretmanager.secretAccessor` to `eos-scorecard-runtime@fannit-eos-scorecard.iam.gserviceaccount.com`.

| Secret name | Contents | Owner of token |
|---|---|---|
| `highlevel-pit-fannit` | HL PIT for FANNIT sub-account | minted by Chris |
| `highlevel-pit-hmc` | HL PIT for HMC sub-account | minted by Chris |
| `highlevel-pit-tmsa` | HL PIT for TMSA sub-account | minted by Chris |
| `highlevel-pit-ipa` | HL PIT for IPA sub-account | minted by Chris |
| `teamwork-api-token` | Teamwork API token for `fannit.teamwork.com` | minted by Chris |
| (planned) `qbo-client-id` | shared Intuit dev app client_id | TBD |
| (planned) `qbo-client-secret` | shared Intuit dev app client_secret | TBD |
| (planned) `qbo-refresh-token-fannit` | OAuth refresh token for FANNIT realm | TBD |
| (planned) `qbo-refresh-token-tmsa` | same for TMSA | TBD |
| (planned) `qbo-refresh-token-hmc` | same for HMC | TBD |

To rotate a token:

```bash
echo -n 'new-token-value' | gcloud secrets versions add SECRET_NAME --project=fannit-eos-scorecard --data-file=-
```

The runtime SA always reads `latest`, so the next request picks up the new value.

---

## 11. Deployment flow

### 11.1 Manual deploy (current)

From `G:\fannit-eos-scorecard\`:

```bash
gcloud builds submit --config=cloudbuild.yaml --project=fannit-eos-scorecard --substitutions=COMMIT_SHA=$(git rev-parse --short HEAD)
```

Build pipeline:
1. Docker build (FROM python:3.11-slim, COPY ., pip install requirements)
2. Push image to Artifact Registry
3. Deploy revision to Cloud Run `eos-scorecard` service in `us-central1`

### 11.2 Auto-deploy on push (planned)

Once Chris connects GitHub to Cloud Build at https://console.cloud.google.com/cloud-build/triggers/connect?project=fannit-eos-scorecard, a 2nd-gen trigger will run the same `cloudbuild.yaml` on every push to `main`.

Per `feedback_cloudbuild_trigger_service_account.md`: the trigger MUST be created with `serviceAccount` specified explicitly via REST API, not via `gcloud builds triggers create` (the latter throws opaque INVALID_ARGUMENT errors).

### 11.3 Rollback

```bash
# list recent revisions
gcloud run revisions list --service=eos-scorecard --region=us-central1 --project=fannit-eos-scorecard

# route 100% traffic to a prior revision
gcloud run services update-traffic eos-scorecard --to-revisions=<REVISION_NAME>=100 --region=us-central1 --project=fannit-eos-scorecard
```

---

## 12. Operational procedures

### 12.1 How to update the dashboard's data

The dashboard reads directly from the `2026 Scorecard` tab on every request. Changes to that tab show up immediately on next page load (no caching layer in front yet). To validate, hit:
- https://eos-scorecard-btpczli7ra-uc.a.run.app/api/scorecard?agency=FANNIT

### 12.2 How to add or change a goal

Edit cell **F** of the relevant KPI row in the agency's block in the `2026 Scorecard` tab. The dashboard picks it up on the next request.

### 12.3 How to add a new agency

1. Add a new block to the `2026 Scorecard` tab following the existing shape (agency name in col E of the header row; 8 KPI rows starting 2 rows below).
2. Add the row offsets to `AGENCY_BLOCKS` in `src/sheets/scorecard.py`.
3. Add HL location_id, pipeline_id, won_stage_id to `HIGHLEVEL` in `src/config.py`.
4. Add GA4 property ID, Teamwork Category, etc.
5. Mint and store: HL PIT in Secret Manager (`highlevel-pit-<agency>`), QBO refresh token if applicable.
6. Commit and deploy.

### 12.4 How to debug an integration

```bash
# Read service logs
gcloud run services logs read eos-scorecard --region=us-central1 --project=fannit-eos-scorecard --limit=100

# Stream logs live
gcloud beta run services logs tail eos-scorecard --region=us-central1 --project=fannit-eos-scorecard

# Hit an endpoint and watch the response
curl -s https://eos-scorecard-btpczli7ra-uc.a.run.app/api/scorecard?agency=FANNIT | python -m json.tool
```

### 12.5 How to run the snapshot job manually (when wired)

```bash
# get an identity token for the runtime SA
TOKEN=$(gcloud auth print-identity-token)

# trigger the snapshot endpoint
curl -X POST -H "Authorization: Bearer $TOKEN" https://eos-scorecard-btpczli7ra-uc.a.run.app/internal/snapshot
```

---

## 13. Open items / pending work

| # | Item | Owner | Notes |
|---|---|---|---|
| 1 | Wire GA4 client | claude | Service account needs Viewer on each of 4 properties first |
| 2 | Wire HighLevel client (calendars, opportunities, won-stage transitions) | claude | All 4 PITs + IDs are ready |
| 3 | Wire Teamwork client (project filter by Category + Tag) | claude | Token ready; verify category names match exactly |
| 4 | Register Intuit Developer app for QBO | Chris | Provides client_id/client_secret + per-realm refresh tokens |
| 5 | Wire QBO client (AR, P&L, balance sheet) | claude | After app registration |
| 6 | Wire `Upsells & Churn` tab reader | claude | Verify aggregate vs per-agency structure first |
| 7 | Implement snapshot job orchestrator (`src/snapshot.py`) | claude | Coordinates all sources, writes to `2026 Scorecard` weekly cells |
| 8 | Implement period roll-ups (Q1–Q4, Last Month, YTD) | claude | Dashboard displays disabled tabs until this lands |
| 9 | Build out chart components (Traffic & Discovery line, Financial bars) | claude | Need ≥4 weeks of trend data |
| 10 | Set up Cloud Scheduler weekly trigger | claude | Mon 06:00 PT after snapshot job is implemented |
| 11 | Connect GitHub → Cloud Build for auto-deploy | Chris | One-time UI auth |
| 12 | Stand up Cloudflare Access in front of dashboard | Chris + claude | Define viewer allowlist |
| 13 | Hit % thresholds final values | Chris | Currently 100% green / 50% yellow / <50% red, inverted for Churn+AR |
| 14 | Strategy/Planning Calls UI placement | Chris | Currently absent from grid; add as 9th card or merge with Discovery |

---

## 14. Out of scope

- Custom date ranges (arbitrary start/end). Only Weekly + Q1-Q4 + Last Month + YTD presets.
- Editing goals from the dashboard. Goals are edited in the sheet directly.
- Manual data entry from the dashboard. Read-only.
- Daily snapshot cadence. Weekly only.
- Per-client drill-down. Aggregates only, at the agency level.
- Historical backfill of years prior to 2026.

---

## 15. Change log

| Date | Change | Author |
|---|---|---|
| 2026-04-27 | Initial scaffold + Sheets reader + minimal frontend deployed (commits `1eb3cdc` → `7ecfead`) | claude |

