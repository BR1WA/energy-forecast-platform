# EnergyAI Milestone Delivery Plan

**Date:** 2026-07-20  
**Baseline:** `7f131a5`  
**Source audit:** `docs/PRODUCT_AUDIT_2026-07-19.md`  
**Active milestone:** PFE Release Candidate  
**Active branch:** `release/pfe`

This plan replaces every older roadmap where scopes conflict. Work proceeds
sequentially. Product V1 starts only after the PFE branch is reviewed and merged;
Product V2 starts only after Product V1 is merged.

## 1. Product Contract

EnergyAI is a truthful single-site electricity monitoring and forecasting product
for a household or small business. A normal user owns exactly one site and one
primary electricity meter.

The product must help a client:

1. provide readings through CSV, authenticated push ingestion, or a manually
   started simulator;
2. monitor newly persisted readings live without generating data by viewing them;
3. track consumption across Live, Today, 7 days, This month, This year, All
   history, and Custom periods;
4. understand energy, tariff cost, peak demand, freshness, and monthly budget;
5. obtain a versioned 24-hour forecast when input is compatible;
6. receive evidence-backed alerts and deterministic recommendations; and
7. export useful CSV and PDF reports.

## 2. Permanent Truth Rules

1. Every measurement has an owner, site, meter, timestamp, unit, source, and
   freshness state.
2. Opening or watching Dashboard never creates readings or starts simulation.
3. Live mode emits only newly persisted push or explicitly simulated readings.
4. Historical CSV rows are never animated or labelled live.
5. Simulation starts only through an explicit user action and remains visibly
   labelled everywhere it affects data.
6. Failed or stale real ingestion never silently becomes simulation.
7. Current power is current only while the latest reading is inside the configured
   freshness threshold; otherwise it is a last reading with an age.
8. Period boundaries use the user's site timezone.
9. Forecasts run only against an approved model/input contract.
10. Seasonal fallback is explicit, labelled, persisted with its reason, and never
    silently presented as TFT output.
11. Recommendations include measured evidence and do not invent appliance state,
    solar flow, grid exchange, savings, or control capability.
12. Loading, empty, stale, partial, unavailable, and failed states are visible.
13. A visible control cannot call fake, missing, or intentionally unimplemented
    behavior.

## 3. Sequential Branch Strategy

| Milestone | Branch creation point | Rule |
|---|---|---|
| PFE Release Candidate | `release/pfe` from stable `main` | Active now |
| Product V1 | `release/product-v1` from merged PFE | Do not create during PFE |
| Product V2 | `release/product-v2` from merged Product V1 | Do not create during PFE/V1 |

Each branch must finish as a coherent ready-to-run application. Deferred work is
not left half-connected or hidden behind visible dead controls.

## 4. Milestone 1 - PFE Release Candidate

**Branch:** `release/pfe`  
**Timebox:** one week  
**Implementation target:** main code work in the first focused run; remaining days
for review, debugging, integration tests, UI refinement, deployment checks, and
PFE report writing.

### 4.1 Included features

#### Product and ownership

- Roles remain only `admin` and `user`.
- Exactly one Site and one primary Meter per normal user.
- Site remains an internal ownership/timezone boundary; users do not select or
  create additional sites.
- Admin manages users and sees truthful read-only system/model readiness.

#### Data sources

- CSV preview/import with consistent row and byte limits, clear accepted/rejected
  feedback, source metadata, and historical-only semantics.
- Authenticated push ingestion with key creation/rotation, one-time reveal, sample
  request, test status, expected interval, and last-seen status.
- Simulator with explicit Start, Stop, Configure, and Reset actions. Simulator
  configuration is typed and bounded.
- All sources use the canonical ingestion service and ownership checks.

#### Monitoring and calculations

- Live mode streams only committed push or explicitly simulated readings.
- Live stream reconnects from a cursor and does not duplicate or create readings.
- Historical modes: Today, 7 days, This month, This year, All history, Custom.
- Clear source, latest timestamp, Fresh/Stale/No data, loading, empty, partial, and
  error states.
- Consistent interval energy, timezone, tariff, cost, peak, and budget calculations
  across Dashboard, Consumption, Budget, reports, and exports.
- Bounded history queries and readable aggregation per period.

#### Dashboard

- Compact header: site name, timezone, source, freshness, and period selector.
- KPI row: current/last power, selected-period energy, selected-period cost, peak
  and timestamp, monthly budget progress/projected cost.
- One primary consumption chart with units, timezone, gaps, source, and optional
  forecast overlay.
- Compact tariff split, latest forecast summary, open alerts, and top
  recommendations.
- Responsive desktop/mobile layout with no nested decorative cards or fabricated
  product concepts.

#### Forecasting

- Portable 24-hour Global TFT package with architecture, checkpoint, preprocessing
  specification, metrics, checksums, provenance, and artifact version.
- Input is one site's hourly energy in kWh.
- Required window: 336 hours.
- Minimum observed coverage: 95%.
- Maximum consecutive missing gap: 3 hours.
- No unresolved non-finite values.
- Accepted short-gap imputations and scaler parameters are persisted in forecast
  provenance.
- Forecast readiness endpoint reports observed/required hours, coverage, missing
  and imputed hours, maximum gap, unit, resolution, active artifact, and reason.
- Global TFT median is the point forecast. Quantile bands are labelled model
  quantile range unless empirical calibration is measured.
- Explicit seasonal-naive fallback is available and persisted with method/reason.
- Forecast stores target timestamps, method, model version, input snapshot, source,
  output unit, and uncertainty metadata.

#### Actions and reports

- Basic high-consumption and missing-data alerts with evidence and cooldown.
- Alert open, acknowledged, and resolved lifecycle.
- Deterministic recommendations with evidence and complete/dismiss/reopen actions.
- Working consumption CSV and forecast PDF downloads.
- Reports disclose period, timezone, data source, tariff, forecast method/model,
  and uncertainty limitations.

#### Authentication, deployment, and tests

- Correct client refresh-token rotation and single-flight 401 recovery.
- Logout revokes the backend refresh session.
- Email normalization, stronger password validation, and final-admin protection.
- Reproducible migrations, Docker startup, liveness/readiness, and pinned forecast
  artifact availability from a clean checkout.
- Critical backend, frontend, and browser journeys.
- Backup/restore command review sufficient for the PFE deployment demonstration.

### 4.2 Explicit exclusions

The following cannot enter `release/pfe` unless already complete and requiring
negligible integration work:

- 168-hour production forecasting.
- Detailed 30-day forecasting or aggregate monthly projection.
- Google login/signup.
- Transactional email, verification, reset, or email alerts.
- Gemini chatbot or generative recommendations.
- Multi-site UI/API or site selectors.
- Subscriptions, plans, billing, organizations, or invitations.
- Application model retraining, client model selection, or comparison.
- Appliance control/detection, solar, battery, grid exchange, invented savings,
  energy scores, AI decisions, or AI assistant surfaces.
- Pull connectors and utility-provider integrations.
- Prometheus, Grafana, SIEM, or advanced infrastructure monitoring.

### 4.3 Dependencies

- Current working ownership, ingestion, calculation, report, and admin foundations.
- `models/lcl_global_forecasting/full_selected_v1/runs/global_tft/day_24h/best.pt`.
- LCL training architecture and preprocessing definitions.
- PostgreSQL for migration and deployment validation.
- Existing frontend component system and chart library.

No email, Google, or Gemini credential is required for the PFE milestone.

### 4.4 Finite implementation checklist

Status values: `[ ]` pending, `[~]` in progress, `[x]` complete, `[!]` blocked.

#### A. Baseline and scope

- [x] Create `release/pfe` from stable `main` at `7f131a5`.
- [x] Replace the roadmap with three sequential milestones.
- [x] Record baseline backend tests, frontend gates, and repository status.
- [x] Create/update the running PFE implementation log.

#### B. Truth cleanup

- [x] Remove the synthetic dashboard smart-meter WebSocket and automatic data
  generation on view.
- [x] Remove fabricated forecast peak/cost/weather/AI insight content.
- [x] Remove missing email dispatch calls from forecast execution.
- [x] Disable unsafe forecast outcome matching until exact timestamps are used.
- [x] Remove client model comparison/training performance and client Models page.
- [x] Remove Admin retraining and fake healthy fallback behavior.
- [x] Remove multi-site frontend/API/navigation.
- [x] Merge or redirect duplicate Profile, Analytics, Budget, Smart Meter, and
  Simulator pages into the focused navigation without losing required functions.
- [x] Remove unsupported AI/solar/grid/appliance/energy-score language and widgets.
- [x] Fix duplicate/dead report download controls and misleading auth/landing copy.

#### C. One-site and sessions

- [x] Add reversible one-site data migration and unique `sites.user_id` constraint.
- [x] Add exactly-one primary meter constraint/repair strategy.
- [x] Replace default-site ambiguity with a strict authenticated user-site resolver.
- [x] Remove normal-user site/meter selection from request contracts.
- [x] Store rotated refresh token returned by backend.
- [x] Add single-flight refresh handling.
- [x] Revoke refresh session on logout.
- [x] Normalize email and enforce password policy.
- [x] Protect the final active admin.
- [x] Add migration, ownership, refresh, concurrency, and logout tests.

#### D. Data-source workflows

- [x] Make CSV preview/import limits and UI messaging consistent.
- [x] Complete push key generate/rotate/test/last-seen UI.
- [x] Add bounded simulator configuration schemas.
- [x] Ensure explicit simulator execution has one durable owner.
- [x] Add source/quality visibility and relevant ingestion regression tests.

#### E. Live and historical monitoring

- [x] Add authenticated read-only live endpoint for committed push/simulator data.
- [x] Add typed initial snapshot and reading event contracts.
- [x] Add cursor reconnect/resynchronization and deduplication.
- [x] Ensure CSV history is excluded from live events.
- [x] Implement exact Live/Today/7d/Month/Year/All/Custom semantics.
- [x] Add bounded period aggregation.
- [x] Add raw-history pagination.
- [x] Add freshness/stale rules from expected meter interval.
- [x] Test that dashboard/live viewing creates no readings.

#### F. Focused dashboard

- [x] Replace broad dashboard response with a typed period summary.
- [x] Correct today versus monthly calculations.
- [x] Implement source/freshness header and period selector.
- [x] Implement KPI row and primary consumption chart.
- [x] Add tariff/budget, forecast, alert, and recommendation summaries.
- [x] Implement loading/empty/stale/partial/error/live reconnect states.
- [x] Implement mobile drawer and responsive chart/KPI behavior.
- [x] Complete the desktop/mobile dashboard journey in Chrome at desktop and
  360px widths.

#### G. 24-hour Global TFT

- [x] Extract Global TFT architecture into reusable backend code.
- [x] Build hourly-kWh aggregation and site-local preprocessing adapter.
- [x] Implement 336h/95%/3h/non-finite readiness validation.
- [x] Persist imputation and scaler provenance.
- [x] Package the 24h artifact without training arrays.
- [x] Add an inference loader and clean-deployment artifact delivery.
- [x] Persist target timestamps, quantile output, unit, method, and fallback reason.
- [x] Add readiness endpoint and client insufficient-data UI.
- [x] Add explicit seasonal-naive fallback.
- [x] Remove static forecast claims and client model selection.
- [x] Add shape, finite, deterministic, warm-up, latency, baseline, and API tests.

#### H. Alerts, recommendations, and reports

- [x] Unify high-load/missing-data alert paths with evidence/cooldown.
- [x] Add resolved lifecycle and worker exception resilience.
- [x] Remove unused notification WebSocket; use truthful refresh behavior.
- [x] Verify deterministic recommendation actions and evidence.
- [x] Repair all CSV/PDF downloads and product-truth metadata.
- [x] Add alert, recommendation, export, and ownership tests.

#### I. Release validation

- [x] Backend product suite passes.
- [x] Frontend lint, typecheck, build, and focused tests pass.
- [x] Fresh PostgreSQL migration reaches head.
- [x] Critical browser journeys pass on desktop and mobile.
- [x] Clean Docker deployment reaches liveness and model readiness.
- [x] Restore procedure is demonstrated.
- [x] Complete final code review and P0/P1 audit.
- [x] Record final walkthrough, known limitations, and PFE report notes.

### 4.5 Acceptance criteria

The PFE milestone is complete only when:

1. Every user has exactly one site and primary meter enforced by the database.
2. CSV, push, and explicit simulator workflows complete without developer help.
3. Watching Dashboard or Live creates no readings or simulation sessions.
4. New push/simulator readings appear once in Live mode and reconnect correctly.
5. CSV rows appear only in historical periods.
6. Live, Today, 7 days, This month, This year, All, and Custom have tested timezone
   boundaries and consistent totals.
7. Dashboard, Consumption, Budget, CSV, and reports agree on energy and cost.
8. Source, freshness, stale, empty, partial, loading, and errors are visible.
9. The focused dashboard works at 360px, tablet, and desktop widths.
10. A clean deployment contains and warms the 24h Global TFT artifact.
11. TFT runs only after the 336h/95%/3h/non-finite gates pass.
12. Seasonal fallback is explicit and never presented as TFT.
13. No fixed or fabricated forecast insight remains.
14. Alerts and recommendations contain evidence and working lifecycle actions.
15. CSV and PDF downloads contain owned data and required context.
16. Refresh rotation, concurrent 401 recovery, logout revocation, ownership, and
    final-admin protection pass.
17. Backend tests, frontend gates, critical browser journeys, migrations, and
    Docker smoke/readiness pass.
18. No visible PFE control reaches fake, missing, or intentionally unimplemented
    behavior.

### 4.6 Expected result

A jury or supervised volunteer can register, configure one site, import CSV or
connect push data or explicitly simulate data, monitor it live and historically,
understand cost/budget/peaks, request a truthful 24h forecast or labelled baseline,
act on evidence-backed alerts/recommendations, and export reports from a clean
Docker deployment.

## 5. Milestone 2 - Product V1

**Branch:** `release/product-v1`  
**Creation dependency:** PFE reviewed and merged  
**Timebox:** approximately one week  
**Status:** Active on `release/product-v1`.

**Detailed execution plan:** `docs/PRODUCT_V1_IMPLEMENTATION_PLAN_2026-07-22.md`

### 5.1 Included features

- Package, validate, and feature-flag the 168-hour Global TFT independently.
- Transactional email outbox with retries and deduplication.
- Email verification and password reset with hashed, expiring, single-use tokens.
- Critical alert email using the verified project sender and user preferences.
- Google authentication with server validation and safe account linking.
- Secure refresh-cookie migration if not completed in PFE.
- Expanded browser/mobile coverage, dependency scanning, avatar storage, restore
  rehearsal, privacy/terms/deletion/export/support information.
- Performance profiling and aggregation/index improvements based on measured load.

### 5.2 Exclusions

- Detailed or aggregate 30-day forecasting.
- Gemini features.
- Multi-site, organizations, billing, provider pull connectors, or device control.
- Application retraining and client model selection/comparison.
- Prometheus/Grafana unless an actual operational need appears.

### 5.3 Dependencies

- Merged and stable PFE release.
- Product sender email, SMTP/provider credentials, and public frontend URL.
- Google OAuth client configuration and approved origins/redirect URIs.
- Independently packaged 168h checkpoint and evaluation report.

### 5.4 Acceptance criteria

1. PFE functionality and truth rules remain green.
2. 168h is hidden unless its artifact/readiness gates pass.
3. Email verification/reset are secure, rate-limited, single-use, and non-enumerating.
4. Provider outage cannot roll back alerts or crash forecasts.
5. Google account creation/linking/revocation preserves one-site ownership.
6. Security, legal, restore, and wider browser checks pass.

### 5.5 Expected result

A client-ready Product V1 with convenient authentication, recoverable accounts,
reliable email delivery, independently validated day/week forecasting, and stronger
release operations without changing the focused single-site product.

## 6. Milestone 3 - Product V2 / Future Research

**Branch:** `release/product-v2`  
**Creation dependency:** Product V1 reviewed and merged  
**Timebox:** approximately one week for a selected coherent V2 theme; research may
continue outside the release branch.  
**Status:** Deferred; do not implement during PFE or Product V1.

### 6.1 Candidate features

- Evaluate monthly candidates for aggregate next-30-day energy and budget value:
  total MAE/sMAPE, bias, budget-exceedance precision/recall, empirical range
  coverage/width, and seasonal monthly-total baseline improvement.
- Ship only an aggregate monthly projection if separate gates and representative
  target-client validation pass. Do not expose unreliable 30-point daily detail.
- Gemini evidence navigator/recommendations only after deterministic product data
  remains the trusted source and strict schemas, quotas, privacy, and fallback are
  designed.
- Optional provider connectors, organizations, or advanced operations only as a
  separately selected V2 theme, not all at once.

### 6.2 Exclusions unless V2 is explicitly rescoped

- Fabricated AI insight or savings.
- Silent model/simulation fallback.
- Remote appliance/grid control without real hardware and safety contracts.
- Model retraining through the client application.

### 6.3 Dependencies

- Merged Product V1 and stable production feedback.
- Representative target-client datasets.
- Documented monthly aggregate acceptance thresholds.
- Gemini credentials only if Gemini is selected for that V2 theme.

### 6.4 Acceptance criteria

1. Product V1 remains complete and ready to run.
2. V2 selects one coherent product theme and completes it end to end.
3. Monthly projection is absent unless aggregate and calibration gates pass.
4. Generative output, if selected, is evidence-bound, labelled, auditable, and
   unable to access another user's data or execute control actions.

### 6.5 Expected result

A validated extension of Product V1, not a broad collection of partially finished
startup features.

## 7. PFE Work Order and Scope Lock

The only active sequence is:

`baseline -> truth cleanup -> one-site/session repair -> data sources -> live/history -> dashboard -> 24h TFT -> actions/reports -> tests/Docker -> review`

No PFE implementation task may add Product V1/V2 scope. New ideas are written under
the deferred milestone and do not interrupt the active checklist.

## 8. Implementation Log

Detailed work, commands, test results, commits, blockers, and next actions are kept
in `docs/PFE_IMPLEMENTATION_LOG.md`. The checklist above is updated as each
workstream completes.
