# FANNIT EOS L10 Scorecard - Master Brief

> **Audience:** Chris Fink (owner) and any future operator (technical or non-technical) who needs to run, deploy, debug, or extend this system.
>
> **Status:** Living document. Update on every architectural change, new integration, or new operational procedure. Last meaningful update: 2026-04-27.

---

## 1. What this is

A self-updating EOS Level 10 Scorecard dashboard for the FANNIT family of agencies (FANNIT, TMSA, HMC, IPA). Replaces the manual weekly update of the `2026 Scorecard` tab in the existing `All Accounts & KPIs - FANNIT` Google Sheet.

The system:
1. Reads goals + existing weekly actuals directly from the Google Sheet on every dashboard request (no caching layer).
2. Once the snapshot job is wired (Cloud Scheduler weekly), it will pull from GA4, HighLevel, Teamwork, QBO, and the internal Upsells & Churn tab and write actuals back into the same `2026 Scorecard` tab cells, preserving the existing manual workflow as legacy continuity.
3. Serves a read-only dashboard from Cloud Run mirroring the Perplexity-built prototype layout.

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

Latest deployed Cloud Run revision: `eos-scorecard-00005-229` (commit `92dae7b`, "pass2b").

---

## 3. Repo structure

`G:\fannit-eos-scorecard\` (local working copy) → `https://github.com/FANNIT-hub/fannit-eos-scorecard.git`

```
fannit-eos-scorecard/
├── .gitignore                      # Python + Node + secrets exclusions
├── .dockerignore                   # excludes .env, .git, tests from container
├── .env.example                    # local-dev secrets template (real .env gitignored)
├── BRIEF.md                        # this file - master operational brief
├── README.md                       # short overview, status, stack
├── Dockerfile                      # python:3.11-slim, gunicorn + uvicorn worker, port 8080
├── cloudbuild.yaml                 # Build -> Push -> Deploy to Cloud Run us-central1
├── requirements.txt                # fastapi, uvicorn, gunicorn, google-* libs
├── main.py                         # FastAPI app entry point
│                                   #   GET  /healthz            liveness probe
│                                   #   GET  /api/agencies       list of mapped agencies
│                                   #   GET  /api/scorecard      per-agency KPI payload
│                                   #   POST /internal/snapshot  weekly job (501 stub)
│                                   #   GET  /                   serves static/index.html
├── src/
│   ├── __init__.py
│   ├── config.py                   # per-agency non-secret IDs:
│   │                               #   HIGHLEVEL[agency] -> {location, secret, pipeline, won_stage}
│   │                               #   GA4_PROPERTY_IDS[agency]
│   │                               #   TEAMWORK_AGENCY_CATEGORY[agency]
│   │                               #   QBO_AGENCIES_WITH_ACCESS
│   │                               #   SCORECARD_SHEET_ID, SCORECARD_TAB_NAME
│   └── sheets/
│       ├── __init__.py
│       ├── client.py               # google-auth ADC -> Sheets API v4 client
│       └── scorecard.py            # 2026 Scorecard tab reader:
│                                   #   AGENCY_BLOCKS row offsets per agency
│                                   #   read_agency_kpis()  returns 8 KPIs with goal,
│                                   #     YTD, hit%, current_week_value, current_week_date,
│                                   #     weekly_goal, weekly_hit_pct, last 8 weeks trend
└── static/
    ├── index.html                  # dashboard page (sidebar + period tabs + grid + table)
    ├── styles.css                  # dark theme matching Perplexity prototype
    └── app.js                      # vanilla JS: fetches /api/* and renders dashboard
```

---

## 4. Stack and infrastructure

| Layer | Tech / Detail |
|---|---|
| Backend | Python 3.11, FastAPI, gunicorn (uvicorn worker) |
| Frontend | Vanilla HTML / CSS / JavaScript, no framework. May upgrade to Next.js later if complexity warrants. |
| Compute | Cloud Run (managed), us-central1, single service `eos-scorecard` |
| Container registry | Artifact Registry: `us-central1-docker.pkg.dev/fannit-eos-scorecard/eos-scorecard/` |
| Build | Cloud Build, manual via `gcloud builds submit` (GitHub auto-trigger pending Chris's UI auth) |
| Secrets | Secret Manager, per-secret IAM grants to runtime service account |
| Auth (runtime) | Application Default Credentials → Cloud Run runtime service account |
| Auth (viewer) | Currently public. Cloudflare Access planned. |
| Schedule | Cloud Scheduler (planned, weekly Mon 06:00 PT). Not yet wired; no snapshot job to call. |
| Region | us-central1 (matches existing FANNIT systems convention) |
| GCP project | `fannit-eos-scorecard` under `fannit.com` org (org id 664017568272) |
| Billing | Linked to billing account `01C259-EB0584-76CB57` ("My Billing Account") |

---

## 5. Service accounts

| Account | Purpose | Roles granted |
|---|---|---|
| `eos-scorecard-runtime@fannit-eos-scorecard.iam.gserviceaccount.com` | Cloud Run runtime identity | Per-secret `roles/secretmanager.secretAccessor` on each project secret. Editor on the source Google Sheet (granted out-of-band by Chris via the Sheets share dialog). |
| `909120368032-compute@developer.gserviceaccount.com` | Cloud Build default SA | `roles/run.admin`, `roles/iam.serviceAccountUser`, `roles/artifactregistry.writer`, `roles/logging.logWriter` (project-level). |

To grant the runtime SA access to a new resource (e.g. a new GA4 property): add the SA email as a Viewer/Editor on that resource. No code changes needed since the SA picks up its identity automatically.

---

## 6. Data sources

### 6.1 Source map per KPI

| KPI | Source | Reader status | Per-agency setup |
|---|---|---|---|
| Website / LP Traffic | GA4 (sessions) | ⏳ not yet built | One property per agency. SA needs Viewer on each. |
| Discovery Calls (showed) | HighLevel calendar events | ⏳ not yet built | Calendar pipelineId == `HIGHLEVEL[agency].pipeline_id` AND name CONTAINS "discovery" AND name DOES NOT CONTAIN "internal" AND isActive AND appointmentStatus = "showed". |
| Strategy / Planning Calls (showed) | HighLevel calendar events | ⏳ not yet built | Same filter, calendar name CONTAINS "strategy" or "planning". |
| New Sales (won) | HighLevel pipeline | ⏳ not yet built | Opportunities entering `HIGHLEVEL[agency].won_stage_id` during the week. |
| Clients in Onboarding | Teamwork projects | ⏳ not yet built | Filter projects: Category = `TEAMWORK_AGENCY_CATEGORY[agency]` AND Tag = "Onboarding". Single shared instance (`fannit.teamwork.com`). |
| Churn (trailing 12 mo) | Internal sheet `Upsells & Churn` (gid 130117843) | ⏳ not yet built | Currently aggregate. Per-agency split if data structure permits. |
| Total $ AR Past 30 Days | QuickBooks Online (AR aging report, 30+ day bucket) | ⏳ not yet built | FANNIT / TMSA / HMC only. IPA: no QBO at time of build. |
| Cash Collected | QBO P&L | ⏳ not yet built | Same. |
| Cash on Hand | QBO Balance Sheet | ⏳ not yet built | Same. |

**Today the dashboard reads only what's in the `2026 Scorecard` sheet.** All values shown in the live dashboard are whatever was last manually entered or calculated by sheet formulas. Once the snapshot job is wired, those cells get updated weekly automatically.

### 6.2 Auth status per source

| Source | Auth method | Storage | Status |
|---|---|---|---|
| GA4 | Service account (Viewer per property) | n/a (SA email alone) | ❌ SA not yet added to the 4 properties |
| HighLevel | Private Integration Token (PIT, location-scoped) | Secret Manager | ✅ All 4 PITs stored: `highlevel-pit-fannit`, `highlevel-pit-hmc`, `highlevel-pit-tmsa`, `highlevel-pit-ipa` |
| Teamwork | API token (per-user, one shared) | Secret Manager `teamwork-api-token` | ✅ Stored |
| QBO | OAuth 2.0 + refresh token | Secret Manager (planned) | ❌ Intuit Developer app not yet registered; no tokens minted |
| Google Sheets | Service account → Editor on workbook | Workbook share dialog | ✅ Done |

---

## 7. Per-agency configuration (`src/config.py`)

### 7.1 HighLevel

| Agency | Location ID | Pipeline | Pipeline ID | Won Stage |
|---|---|---|---|---|
| FANNIT | `q2x8tokGpDhlOu8bgVLN` | 2: Active Sales | `OeYgK000wVzh0pxH3edY` | `ff032485-ffef-4a8f-91b7-1f5db6596678` (Closed - Won) |
| HMC | `LAkDi1yul6kxjPcqkLxb` | 💸 SALES PIPELINE | `UwK3pSQmvBJGzeNPfmoJ` | `45fa598d-26a8-4b82-81aa-55242518a2cd` (💸 Closed and Won) |
| TMSA | `Fj5y9oD9dIJWGHRCeNCW` | 💸 SALES PIPELINE | `5wfjI8JTTuesnVlFSWg5` | `a2a57886-4de4-4701-9c21-8f6843facc28` (💸 Closed and Won) |
| IPA | `TTv1Bn2QeGBIKwcP72zA` | 💸 SALES PIPELINE | `T4bqE5CGEaw8P2vU1H0z` | `a8b13c1f-149c-49ff-a48e-876082b8a646` (🖐️ CLOSED AND WON) |

IPA caveat: two pipelines named `💸 SALES PIPELINE` exist. Per Chris (2026-04-27), the canonical one is the variant with 63 opportunities (`T4bqE...`).

PIT scopes required (when minting in HL UI): View Calendars, View Calendar Events, View Opportunities, View Pipelines (read-only).

### 7.2 GA4

| Agency | Property ID |
|---|---|
| FANNIT | `319269316` |
| HMC | `464894002` |
| TMSA | `473651067` |
| IPA | `496676704` |

Metric: `sessions`.

### 7.3 Teamwork

Single shared instance: `fannit.teamwork.com`. Filter: project Category equals the agency name + Tag equals `Onboarding`.

| Agency | Teamwork Category (best guess, verify when wiring) |
|---|---|
| FANNIT | FANNIT |
| HMC | Hardscape Marketing Crew |
| TMSA | The Med Spa Agency |
| IPA | Inspired Painting Marketing Agency |

### 7.4 QBO

Active agencies: FANNIT, TMSA, HMC. **IPA has no QBO** and will render "—" for AR / Cash Collected / Cash on Hand until set up.

---

## 8. Sheet layout reference

### 8.1 Workbook
- Name: `All Accounts & KPIs - FANNIT`
- Sheet ID: `1QyyYNoNR05V8hxjGSBYfvPqWANx37kJiGw3ePx-hz8c`

### 8.2 Tabs used by this system

| Tab | gid | Used for |
|---|---|---|
| `2026 Scorecard` | (not captured; main tab) | Goals + weekly actuals for all 4 agencies. Both the dashboard's read source AND (eventually) the snapshot job's write target. |
| `Upsells & Churn` | 130117843 | Source for trailing-12-month churn. Currently aggregate; per-agency split TBD. |

### 8.3 `2026 Scorecard` tab structure

Each agency block is shaped identically and stacked vertically:

| Offset from header row | Content |
|---|---|
| 0 | Agency name in col E. Year (2026) spans F-G. Month band headers across J onward (JANUARY, FEBRUARY, ...). |
| 1 | Column headers: Own \| KPI \| Goal (F=annual) \| Actual (G=YTD, formula) \| Hit (H, formula) \| then per-month: Goal \| weekly cells \| Calendar Month Actual. |
| 2-9 | 8 KPI rows in fixed order. |

**Block start rows (the agency-name header row), confirmed during build:**

| Agency | Header row | KPI data rows |
|---|---|---|
| FANNIT | 36 | 38-45 |
| HMC | 73 | 75-82 |
| TMSA | 94 | 96-103 |
| IPA | 115 | 117-124 |

These offsets are hard-coded in `AGENCY_BLOCKS` (`src/sheets/scorecard.py`). If a new agency is added to the sheet, append a new entry there.

**KPI row order (always the same 8, top to bottom):**

1. Website / LP Traffic
2. Discovery Calls
3. New Sales (15% of Discovery)
4. Clients in Onboarding
5. Churn Over Last 12 Months
6. Total $ AR Past 30 Days
7. Cash Collected
8. Cash on Hand

### 8.4 Column meaning per block

| Column | Meaning |
|---|---|
| E | KPI label |
| **F** | **Annual goal** (manually maintained; dashboard reads here; snapshot job NEVER writes) |
| G | YTD Actual (sheet formula; snapshot job NEVER writes) |
| H | Hit % (sheet formula; snapshot job NEVER writes) |
| I | blank / separator |
| J | January monthly goal (sheet formula or manual; not written by job) |
| K, L, M, N (and possibly O for 5-week months) | Weekly actuals for January, week-ending Mondays |
| (next col after weeklies) | January Calendar Month Actual (sheet formula sum; not written) |
| ... | Pattern repeats per month through December |

The snapshot job writes ONLY to weekly-actual cells. Goal cells, YTD cells, Hit cells, and Calendar Month Actual cells are formula-driven or manually maintained.

### 8.5 Weekly column discovery (how the reader works)

Hard-coding monthly column offsets is fragile because some months have 4 week-ending Mondays and some have 5. The reader instead **discovers weekly columns dynamically** by reading the agency's KPI-header row (e.g. row 37 for FANNIT) and:

1. Skipping cells whose normalized lowercase label is in `NON_WEEK_HEADER_LABELS` (`goal`, `actual`, `hit`, `kpi`, `own`, `calendar month actual`, `""`).
2. Whitespace-normalizing the header (collapses `\n` from multi-line cells like "Calendar\nMonth\nActual").
3. Requiring the label to contain a `/` (matches `M/D` date patterns).
4. Returning [(absolute_col_index_1based, date_label), ...].

This logic lives in `_get_week_columns()`. Bug history: an early version did exact-match comparison without whitespace normalization, causing the multi-line "Calendar\nMonth\nActual" cells to leak through and be treated as weekly columns. Fixed in commit `92dae7b`.

---

## 9. Dashboard behavior

### 9.1 API endpoints

| Endpoint | Method | Purpose |
|---|---|---|
| `/healthz` | GET | Liveness probe. Returns `{"ok": true}`. |
| `/api/agencies` | GET | Lists agencies the dashboard knows how to render (`AGENCY_BLOCKS` keys). |
| `/api/scorecard?agency=FANNIT` | GET | Returns the agency's KPI payload. See §9.2. |
| `/internal/snapshot` | POST | Weekly Cloud Scheduler trigger. Currently 501 stub. |
| `/` | GET | Serves `static/index.html`. CSS/JS at `/styles.css`, `/app.js`. |

### 9.2 `/api/scorecard` payload shape

```json
{
  "agency": "FANNIT",
  "kpis": [
    {
      "label": "Website / LP Traffic",
      "source": "GA4",
      "fmt": "number",
      "metric_type": "incremental",
      "annual_goal": 36000.0,
      "ytd_actual": 11026.0,
      "hit_pct": 0.306,
      "current_week_value": 436.0,
      "current_week_date": "4/27",
      "weekly_goal": 692.3,
      "weekly_hit_pct": 0.63,
      "weeks": [
        {"date": "3/9", "value": 325},
        {"date": "3/16", "value": 299},
        ...
      ]
    },
    ...
  ]
}
```

`fmt` is one of `"number"`, `"currency"`, `"percent"`. `metric_type` is one of `"incremental"`, `"snapshot"`, `"rate"`. The frontend uses both for formatting and color logic.

### 9.3 Frontend layout (mirrors Perplexity prototype)

- **Left sidebar:** logo + 4 active agency tabs (FANNIT, HMC, IPA, TMSA) + a disabled "Total Rollup" placeholder.
- **Top-right period tabs:** Weekly active. Q1, Q2, Q3, Q4, Last Month, YTD all disabled until period roll-up logic is implemented.
- **Main pane:**
  - 4×2 KPI card grid. Each card: title, source label, current-week value (big number), week-of date tag, weekly goal, weekly hit %, status dot.
  - "Weekly Scorecard Detail" table below: KPI \| Source \| Annual Goal \| YTD \| Hit % + last 8 trailing weekly columns.
  - Two chart placeholders ("Traffic & Discovery Trend", "Financial Metrics") — render once trend data accumulates.

### 9.4 Color thresholds

| Status | Range | Apply when |
|---|---|---|
| Green | hit % ≥ 100 | Standard metrics: at or above weekly goal. Inverted metrics: at or below the rate cap. |
| Yellow | 50 ≤ hit % < 100 | Standard metrics: half to full goal. |
| Red | hit % < 50 | Standard metrics: less than half goal. |
| Inverted (Churn, AR Past 30) | Reverse mapping: low value = green, high value = red |

Final thresholds may be tuned by Chris; current values are starter defaults.

### 9.5 Metric-type behavior

| Type | KPIs | Aggregation in period | Goal direction | Weekly goal calc |
|---|---|---|---|---|
| Incremental | Traffic, Discovery, Strategy, New Sales, Cash Collected | Sum the weeks in the period | Higher = better | `annual / 52` |
| Snapshot | Onboarding, AR Past 30, Cash on Hand | Latest week's value in the period | Mixed (Cash on Hand higher = better; AR lower = better) | `annual` (target balance) |
| Rate | Churn (trailing 12 mo) | Latest week's value in the period | Lower = better (inverted) | `annual` (target rate) |

---

## 10. Secrets

All secrets in Secret Manager, project `fannit-eos-scorecard`. Each grants `roles/secretmanager.secretAccessor` to the runtime SA.

| Secret name | Contents | Status |
|---|---|---|
| `highlevel-pit-fannit` | HL PIT for FANNIT sub-account | ✅ stored |
| `highlevel-pit-hmc` | HL PIT for HMC sub-account | ✅ stored |
| `highlevel-pit-tmsa` | HL PIT for TMSA sub-account | ✅ stored |
| `highlevel-pit-ipa` | HL PIT for IPA sub-account | ✅ stored |
| `teamwork-api-token` | Teamwork API token (`fannit.teamwork.com`) | ✅ stored |
| `qbo-client-id` | Shared Intuit dev app client_id | ⏳ pending app registration |
| `qbo-client-secret` | Shared Intuit dev app client_secret | ⏳ pending |
| `qbo-refresh-token-fannit` | OAuth refresh token for FANNIT realm | ⏳ pending |
| `qbo-refresh-token-tmsa` | Same for TMSA | ⏳ pending |
| `qbo-refresh-token-hmc` | Same for HMC | ⏳ pending |

To rotate or update a secret:

```bash
echo -n 'new-value' | gcloud secrets versions add SECRET_NAME --project=fannit-eos-scorecard --data-file=-
```

The runtime SA always reads `latest`; next request picks up the new value.

---

## 11. Deployment flow

### 11.1 Manual deploy (current)

From `G:\fannit-eos-scorecard\`:

```bash
gcloud builds submit \
  --config=cloudbuild.yaml \
  --project=fannit-eos-scorecard \
  --substitutions=COMMIT_SHA=$(git rev-parse --short HEAD)
```

Pipeline steps:
1. Docker build (`FROM python:3.11-slim`, COPY repo, `pip install -r requirements.txt`).
2. Push image to Artifact Registry (`us-central1-docker.pkg.dev/fannit-eos-scorecard/eos-scorecard/eos-scorecard:<COMMIT_SHA>` and `:latest`).
3. Deploy revision to Cloud Run service `eos-scorecard` in `us-central1`. `--allow-unauthenticated`, 512Mi memory, 1 CPU, min=0 max=3, 300s timeout, runtime SA attached.

Typical build duration: 2-3 minutes.

### 11.2 Auto-deploy on push (planned)

Once Chris connects GitHub at https://console.cloud.google.com/cloud-build/triggers/connect?project=fannit-eos-scorecard, a 2nd-gen trigger will run the same `cloudbuild.yaml` on every push to `main`.

Critical: the trigger MUST be created with `serviceAccount` specified explicitly via REST API, not via `gcloud builds triggers create` (the latter throws opaque INVALID_ARGUMENT). See `feedback_cloudbuild_trigger_service_account.md` in Chris's memory.

### 11.3 Rollback

```bash
# list recent revisions
gcloud run revisions list --service=eos-scorecard --region=us-central1 --project=fannit-eos-scorecard

# route 100% traffic to a prior revision
gcloud run services update-traffic eos-scorecard \
  --to-revisions=<REVISION_NAME>=100 \
  --region=us-central1 --project=fannit-eos-scorecard
```

---

## 12. Operational procedures

### 12.1 Update the dashboard's data

Dashboard reads directly from the `2026 Scorecard` tab on every request. Edits to that tab show on next page load (no caching). Verify with:

```
https://eos-scorecard-btpczli7ra-uc.a.run.app/api/scorecard?agency=FANNIT
```

### 12.2 Change a goal

Edit cell **F** of the relevant KPI row in the agency's block in the `2026 Scorecard` tab. Picked up on next request.

### 12.3 Add a new agency

1. Add a new block in the `2026 Scorecard` tab matching the existing shape.
2. Add the row offsets to `AGENCY_BLOCKS` in `src/sheets/scorecard.py`.
3. Add HL location_id, pipeline_id, won_stage_id to `HIGHLEVEL` dict in `src/config.py`.
4. Add GA4 property ID, Teamwork Category, etc. as applicable.
5. Mint and store credentials in Secret Manager (`highlevel-pit-<agency>`, QBO refresh token if applicable).
6. Commit, deploy.

### 12.4 Debug an integration

```bash
# read recent service logs
gcloud run services logs read eos-scorecard \
  --region=us-central1 --project=fannit-eos-scorecard --limit=100

# stream logs live
gcloud beta run services logs tail eos-scorecard \
  --region=us-central1 --project=fannit-eos-scorecard

# probe an endpoint
curl -s https://eos-scorecard-btpczli7ra-uc.a.run.app/api/scorecard?agency=FANNIT | python -m json.tool
```

### 12.5 Run snapshot job manually (after wired)

```bash
TOKEN=$(gcloud auth print-identity-token)
curl -X POST -H "Authorization: Bearer $TOKEN" \
  https://eos-scorecard-btpczli7ra-uc.a.run.app/internal/snapshot
```

---

## 13. Known issues and gotchas

| # | Issue | Resolution / workaround |
|---|---|---|
| 1 | Multi-line cell headers (`Calendar\nMonth\nActual`) leak through naive lowercase exact-match filters | `_get_week_columns()` collapses whitespace via `" ".join(s.split())` and additionally requires `/` in the header before treating a column as weekly. Fixed in commit `92dae7b`. |
| 2 | Service account cannot use `/oauth/installedLocations` with PITs (returns 401 "not authorized for this scope") | Don't rely on that endpoint to discover locations; collect location IDs manually from HL UI per sub-account. |
| 3 | Cloud Run URL serves `/healthz` via the `StaticFiles` mount fallthrough sometimes (404 from Google front-door) | Treat as a known oddity; `/api/*` and `/` work reliably. May resolve by reordering routes if it matters. |
| 4 | IPA has no QBO data; cells render "—" | By design. Each integration runs independently; missing creds for one source don't block others. |
| 5 | Sheet has duplicate "💸 SALES PIPELINE" pipelines in IPA's HL location | Use `T4bqE5CGEaw8P2vU1H0z` (the 63-opportunity variant). The other one is stale. |

---

## 14. Open items / pending work

| # | Item | Owner | Notes |
|---|---|---|---|
| 1 | Wire GA4 client (sessions per agency, weekly window) | claude | Service account needs Viewer on each of 4 properties first |
| 2 | Wire HighLevel client (calendars + opportunities + won-stage transitions) | claude | All 4 PITs and IDs ready; calendar inclusion rule defined |
| 3 | Wire Teamwork client (project filter by Category + Tag) | claude | Token ready; verify exact category names match the Teamwork UI |
| 4 | Register Intuit Developer app for QBO | Chris | Provides client_id / client_secret + per-realm refresh tokens |
| 5 | Wire QBO client (AR aging, P&L, Balance Sheet) | claude | After app registration |
| 6 | Wire `Upsells & Churn` tab reader | claude | Verify aggregate vs per-agency structure first |
| 7 | Implement snapshot orchestrator (`src/snapshot.py`) | claude | Coordinates all sources, writes to `2026 Scorecard` weekly cells |
| 8 | Implement period roll-ups (Q1-Q4, Last Month, YTD) | claude | Dashboard tabs disabled until this lands |
| 9 | Build out chart components (Traffic & Discovery line, Financial bars) | claude | Need ≥4 weeks of trend data |
| 10 | Set up Cloud Scheduler weekly trigger | claude | Mon 06:00 PT, after snapshot job exists |
| 11 | Connect GitHub → Cloud Build for auto-deploy | Chris | One-time UI auth |
| 12 | Stand up Cloudflare Access | Chris + claude | Define viewer allowlist |
| 13 | Strategy/Planning Calls UI placement | Chris | Currently absent from grid; add as 9th card or merge with Discovery |
| 14 | Hit % thresholds final values | Chris | Currently 100/50 boundaries, inverted for Churn+AR |
| 15 | Total Rollup view (sidebar item disabled today) | claude | Aggregate KPIs across all 4 agencies |

---

## 15. Out of scope

- **Custom date ranges** (arbitrary start/end). Only Weekly + Q1-Q4 + Last Month + YTD presets.
- **Editing goals from the dashboard.** Goals are edited in the sheet directly.
- **Manual data entry from the dashboard.** Read-only.
- **Daily snapshot cadence.** Weekly only.
- **Per-client drill-down.** Aggregates only, at the agency level.
- **Historical backfill of years prior to 2026.** Backfill flag (when implemented) covers recent weeks only.

---

## 16. Change log

| Date | Commits | Summary |
|---|---|---|
| 2026-04-27 | `1eb3cdc` | Initial Cloud Run scaffold (Dockerfile, cloudbuild.yaml, FastAPI hello-world). Manual `gcloud builds submit` deploy succeeds. Service live at https://eos-scorecard-btpczli7ra-uc.a.run.app. |
| 2026-04-27 | `908f9bc` | `src/config.py` with all per-agency non-secret IDs (HL location/pipeline/won_stage, GA4 property IDs, Teamwork categories, QBO access list). |
| 2026-04-27 | `4a2c8bc` | Pass 1: Sheets reader (`src/sheets/scorecard.py`) + minimal frontend (`static/`). FANNIT and HMC blocks mapped. `/api/scorecard?agency=FANNIT` returns real values from the sheet. |
| 2026-04-27 | `4060b55` | TMSA (row 94) and IPA (row 115) agency blocks added. All 4 agencies now mapped. |
| 2026-04-27 | `7ecfead` | Pass 2: KPI cards now show last week's value as the big number (instead of YTD). Weekly goal pro-rated for incremental metrics. New "Weekly Scorecard Detail" table below the cards with last 8 trailing weekly columns. Metric-type behavior (incremental/snapshot/rate) drives goal calc and color logic. |
| 2026-04-27 | `92dae7b` | Pass 2b: Fixed Calendar Month Actual cells leaking into weekly-column list (multi-line header `Calendar\nMonth\nActual` wasn't being normalized). After fix, FANNIT current-week values match Chris's expected: Discovery=4, New Sales=0, Onboarding=1, Churn=4.8%, AR=$23,932, Cash Collected=$13,247. |
| 2026-04-27 | this commit | Comprehensive brief regeneration; first sync to `fannit-system-docs`. |

