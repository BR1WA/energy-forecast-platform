# EnergyAI Full Product Audit

**Audit date:** 2026-07-19  
**Audited revision:** `7f131a5` (`main`)  
**Scope:** Landing and authentication, onboarding, frontend workflows, FastAPI
backend, database ownership, ingestion, calculations, forecasting, alerts,
recommendations, administration, security, testing, CI, Docker, and operations.

## 1. Executive Verdict

EnergyAI is a worthwhile and technically substantial PFE. It is not a waste of
time, and it is not merely a collection of static pages. The repository contains
real account isolation, persisted sites and meters, validated ingestion, interval
energy and tariff calculations, model serving, alerts, recommendations, exports,
migrations, CI, and Docker deployment work.

It is currently a **functional PFE beta**, not a product that should be given to
unsupervised clients or publicly launched. Several launch blockers violate the
project's own product-truth rules:

1. The deployable model packages are local and ignored by Git, so a clean clone
   cannot become forecast-ready.
2. Opening the dashboard starts a WebSocket that generates and persists simulated
   smart-meter data without the user deliberately starting the simulator.
3. The forecast result page contains fixed peak, cost, temperature, and AI insight
   claims unrelated to the prediction that was just produced.
4. A forecast that creates an alert can crash because the referenced email
   function does not exist.
5. Forecast validation can compare a prediction with an unrelated later reading
   and label the result as yesterday's accuracy.

### Product ratings today

| Dimension | Rating | Assessment |
|---|---:|---|
| Master's PFE engineering value | **7.5/10** | Strong breadth and several defensible engineering decisions, reduced by truthfulness and validation gaps |
| Demonstrable prototype | **7.0/10** | The main local flows work, but the jury can encounter misleading or dead controls |
| Real client usefulness | **5.0/10** | CSV, costs, budgets, forecasts, reports, and alerts are useful; push setup and data trust are not ready |
| Production readiness | **3.5/10** | Clean deployment, sessions, notifications, end-to-end tests, legal pages, and real validation are incomplete |
| Overall product today | **5.8/10** | A credible beta foundation, not a finished commercial product |
| Realistic potential after the priority roadmap | **9+/10 PFE** | Achievable if integrity and validation are prioritized over adding more decorative screens |

The most important conclusion is that adding Gemini, Google login, email, and
stronger models should happen **after the P0 product-integrity defects are fixed**.
New AI features on top of contaminated or fabricated data would make the product
less trustworthy, not more impressive.

## 2. Audit Method and Evidence

The audit used source inspection, route-contract tracing, clean in-memory API
journeys, model inference checks, existing automated tests, frontend quality gates,
dependency checks, migration review, and deployment-artifact inspection.

### Checks run

| Check | Result |
|---|---|
| Backend suite | **35 passed**, one expected local insecure-admin-password warning |
| Frontend lint | Passed |
| Frontend TypeScript check | Passed |
| Frontend production build | Passed, 22 static routes generated |
| Core API journey | Registration, setup, budget, short CSV preview/import, dashboard, statistics, PDF, and recommendations all returned success |
| Three local 24h model inferences | Passed; each returned a `(24, 1)` forecast |
| Root research/training tests | Failed during collection |
| Frontend production dependency audit | 2 moderate PostCSS findings through the installed Next.js dependency tree |
| Interactive browser UX pass | Not completed because the desktop browser runtime could not initialize |

The browser limitation means responsive layout and visual behavior are based on
source evidence rather than screenshots. It does not affect the API, model,
deployment, or static product-truth findings.

## 3. What Is Implemented Correctly

### 3.1 Account and ownership foundation

- Roles are intentionally limited to `admin` and `user`.
- Registration and login issue short-lived access tokens and persisted refresh
  tokens.
- Refresh tokens are hashed in the database and rotated server-side.
- Disabled users are rejected on authenticated requests.
- User-owned resources are filtered by the authenticated user across consumption,
  forecasts, alerts, recommendations, ingestion, settings, simulation, and sites.
- Cross-user REST and WebSocket ownership tests exist.
- Password changes revoke active refresh sessions.
- Admin account management is separated from customer energy ownership.

This is a good PFE authorization model. It is small enough to explain and strong
enough to demonstrate real isolation.

### 3.2 Data ingestion

- CSV input has byte limits, UTF-8 validation, canonical and legacy aliases,
  timezone-aware timestamps, finite numeric ranges, preview feedback, and rejected
  row details.
- Push ingestion uses per-meter random keys stored only as hashes.
- Push batches are bounded to 1,000 samples and support idempotency keys.
- Duplicate meter timestamps have both application checks and a database unique
  constraint.
- Push samples older than the meter's latest reading are rejected.
- Simulator readings pass through the same canonical ingestion service and are
  persisted with `source="simulation"`.
- Historical CSV imports do not generate a backlog of live incidents.

The ingestion service is one of the strongest parts of the product.

### 3.3 Energy, tariff, and budget calculations

- Power is integrated using the actual elapsed time between samples.
- Direct cumulative energy is used when available.
- Long gaps are excluded instead of being integrated as continuous consumption.
- Intervals are split at tariff-hour boundaries.
- Site timezone is applied to month and tariff boundaries.
- Peak/off-peak rates and monthly budgets are persisted per owned site/user.
- Dashboard, budget, statistics, and CSV exports share the same calculation
  service.
- Golden tests cover interval integration, long gaps, tariffs, and budget values.

This is useful client functionality, not presentation-only code.

### 3.4 Forecasting foundation

- Registry entries include model version, horizon, lookback, dataset, fingerprint,
  metrics, preprocessing metadata, and artifact locations.
- Artifact files and SHA-256 fingerprints are checked before serving.
- Unsupported 168h and 720h horizons are disabled in the UI when no active package
  exists.
- Forecasts persist model identity, input source, input interval, exact input
  snapshot, predictions, horizon, and confidence method.
- Backend and PDF text correctly disclose that the current outputs are point
  forecasts without calibrated uncertainty.
- All three local 24-hour packages successfully performed inference during this
  audit:

| Local artifact | MAE | RMSE | R2 | Audit inference |
|---|---:|---:|---:|---|
| CNN-BiLSTM | 0.534 | 0.707 | 0.182 | Passed |
| PatchTST | 0.522 | 0.683 | 0.238 | Passed |
| SOTA model | 0.549 | 0.704 | 0.191 | Passed |

The current model quality is modest. PatchTST has the best recorded local metrics,
while startup currently selects the newest valid package and has SOTA active.
Model promotion should be based on an explicit validation decision, not artifact
modification time or architecture naming.

### 3.5 Alerts, recommendations, and reports

- High-load and missing-push-data rules persist evidence and use per-rule cooldowns.
- Recommendations are deterministic, user-owned, evidence-backed, and can be
  completed, dismissed, or reopened.
- Excess-load cost is clearly calculated as cost per hour, not invented savings.
- Alert acknowledgement and configuration are persisted.
- Consumption CSV and forecast PDF exports are generated from owned records.
- The forecast PDF includes site, timezone, input source, input period, model,
  version, tariff context, and uncertainty disclosure.

The deterministic recommendation service should remain after Gemini is added. It
is a valuable trusted calculation layer beneath generative explanations.

### 3.6 Engineering and operations

- Alembic migrations are the startup authority and migration failure stops startup.
- Liveness and readiness are separated.
- Readiness checks the database, active model contract, artifact files, and model
  warm-up.
- Production-mode secret validation rejects placeholder JWT/admin secrets.
- Production CORS is restricted to the configured frontend origin.
- Authentication endpoints are rate-limited.
- Request IDs are added to responses and logs.
- Docker Compose includes PostgreSQL, backend, frontend, and an alert worker.
- CI runs backend tests/migrations, frontend lint/typecheck/build, and a Docker
  smoke job.
- Database backup and restore commands are documented, although their Windows
  binary-stream implementation still requires correction and rehearsal.

## 4. Current Functional Surface

| Area | Current status | Product assessment |
|---|---|---|
| Landing page | Functional and mostly honest | Good starting screen with real auth/dashboard CTAs |
| Email/password registration | Functional | Auto-activates accounts; verification is not implemented |
| Login | Functional | Copy incorrectly describes normal login as smart-meter/grid connection |
| Google login/signup | Not implemented | Planned roadmap item |
| Password reset | Not implemented | Requires transactional email and reset-token flow |
| Email verification | Not implemented | Requires transactional email and verification state |
| First-time setup | Site, tariff, budget, CSV, and simulator work | Push choice leads to a dead redirect |
| CSV ingestion | Functional for files the preview accepts | UI journey is effectively limited to 1,000 rows despite a documented 10,000-row import limit |
| Push ingestion backend | Functional and authenticated | No client-facing key/instructions/test screen |
| Explicit simulator | Functional and persisted | Undermined by the separate automatic dashboard simulation path |
| Consumption charts | Live/day/week/month/all endpoints work | `all` means only the last 365 days; errors are often console-only |
| Tariff and budget | Functional | Missing server validation allows invalid negative rates/budgets and invalid hours |
| 24h forecast | Works locally with current packages | Clean deployments lack deployable packages; result page contains fabricated fixed insights |
| Model comparison | UI and endpoint exist | Only one model can be active per dataset/horizon, so comparison normally compares one model |
| 168h/720h forecast | Correctly disabled | Raw weights are not deployable packages yet |
| Alerts | Persisted high load and missing data work | Live WebSocket never broadcasts; forecast-alert path can crash |
| Recommendations | Functional deterministic actions | UI calls them AI recommendations before Gemini exists |
| Reports | PDF and CSV exports work | Dashboard export button discards the downloaded blob |
| Multi-site | Read-only aggregation works for existing records | No client API/UI to create, edit, select, or configure additional sites/meters |
| Admin users | List, role update, activation/deactivation work | Health fallback can show fake healthy values; last admin can demote/disable itself |
| Admin models | Model metadata is visible | Retrain control always reaches a 501 endpoint; activation is backend-only |
| Settings/profile | Main fields, budget, password, and avatar work | Preferences are mostly not exposed; avatars are lost on container replacement |
| Email notifications | Not implemented | Configuration remnants currently create a forecast failure path |
| Gemini chatbot/recommendations | Not implemented | Planned roadmap item |

## 5. Launch-Blocking Findings (P0)

### P0-1: Clean deployments do not contain deployable forecast artifacts

**Evidence:** `backend/experiments/` is ignored by `.gitignore` and has no tracked
files. The serving service reads only `EXPERIMENTS_DIR`, while the tracked raw
files under `models/active/` are not consumed by the API. Docker Compose mounts
the ignored directory over `/app/experiments`.

**Impact:** Forecasting works on the current machine but a clean GitHub checkout
cannot seed an active registry entry. `/api/v1/system/ready` returns 503 and the
Docker smoke job cannot pass model readiness.

**Required fix:** Establish one canonical deployable-artifact pipeline. For the
PFE, package the current 24h artifacts with config, pipeline, metrics, model card,
and fingerprint under a tracked/LFS or release-artifact location. Make Docker
download or copy that exact package and verify its hash before startup. Add a CI
test that starts from a clean checkout with no local ignored files.

### P0-2: Opening the dashboard silently creates simulated customer data

**Evidence:** `frontend/src/app/dashboard/page.tsx:202` connects every authenticated
dashboard to `/forecast/smart-meter/live-ws`. The backend generates random smart
meter values in `backend/app/services/smart_meter_service.py:146` and persists them
as simulation readings inside the WebSocket loop at
`backend/app/routers/forecast.py:782`.

**Impact:** A user who selected CSV or push ingestion has their history, costs,
alerts, and current consumption contaminated by synthetic readings simply by
viewing the dashboard. This directly violates the product rule that live failure
must not become simulated success.

**Required fix:** Remove the synthetic smart-meter WebSocket from the normal
dashboard. Dashboard live data must read the latest owned persisted meter data.
Only an explicitly running `SimulationSession` may generate simulated readings,
and every screen must show the active source and last-seen age.

### P0-3: Forecast results display fabricated fixed decision support

**Evidence:** `frontend/src/app/forecast/page.tsx:991` hardcodes an 18:30 peak,
14.85 MAD daily cost, temperature correlation, 14% demand increase, 5 C weather
rise, and occupancy explanation.

**Impact:** These claims are unrelated to the selected model, uploaded file,
weather, tariff, or returned predictions. They can mislead users and are easy for
a jury to identify as fake.

**Required fix:** Remove the cards until values are calculated. Compute peak step
from predictions, cost from hourly predictions and the site tariff, and only show
an explanation when an implemented explanation service returns evidence. Until
Gemini is integrated, label deterministic text as rule-based, not explainable AI.

### P0-4: Forecast alerts can crash on a missing email function

**Evidence:** Three forecast paths import `send_alert_email` from
`app.services.alert_service` at `backend/app/routers/forecast.py:184`, `:401`, and
`:607`. No such function exists.

**Impact:** When a forecast exceeds the configured threshold and email is enabled
(the default), the request can fail after inference instead of saving the forecast
and alert.

**Required fix:** Until transactional email exists, remove/disable this call and
persist the in-app alert successfully. Later route email through a tested outbox
worker with retries, delivery status, and a dead-letter state.

### P0-5: Forecast outcome validation can pair unrelated timestamps

**Evidence:** `backend/app/services/dashboard_service.py:72` searches for the first
user reading at any time after forecast H+1. It does not require the expected
timestamp, meter, sampling tolerance, or source. The UI labels the comparison as
yesterday's forecast.

**Impact:** A sample forecast whose input ends in 2007 can be compared with a
client reading from 2026 and reported as accuracy. This creates false model
validation evidence.

**Required fix:** Create explicit `ForecastOutcome` matching by forecast, site,
meter, target timestamp, horizon step, and tolerance. Exclude sample/demo forecasts
from client outcome scoring. Report MAE/RMSE only after sufficient matched points.

## 6. High-Priority Findings (P1)

### P1-1: Client refresh-token rotation is broken

The backend returns a new refresh token, but `frontend/src/lib/api.ts:75` stores
the old revoked token. The next refresh fails. Concurrent 401 responses can also
race multiple refresh attempts, allowing one request to rotate the token while
another clears the session.

**Fix:** Store `data.refresh_token`, add a single-flight refresh lock, retry queued
requests once, and add frontend/integration tests for two sequential refreshes and
concurrent 401 responses.

### P1-2: Logout does not revoke the server session

`frontend/src/lib/auth.tsx:65` only clears local storage. It never calls
`POST /auth/logout`, so a stolen refresh token remains valid until expiry.

**Fix:** Call logout with the refresh token, clear local state in `finally`, and
record a logout audit event.

### P1-3: Push onboarding is a dead user journey

Setup sends push users to `/smart-meter`, and that route immediately redirects to
the dashboard. The frontend has no API-key rotation method, sample payload,
connection test, copy-once key state, or last-seen status.

**Fix:** Build a meter connection page around the existing backend endpoint. Show
the key once, provide a cURL/JSON example, send a test sample, show accepted/error
results, and wait for `last_seen_at` before marking connection complete.

### P1-4: In-app real-time notifications are not real-time

The authenticated alert WebSocket exists, but `broadcast_to_client` and
`broadcast_global` are never called. New alerts appear only on page reload or REST
polling.

**Fix:** Publish alert-created events after transaction commit. For one-instance
PFE deployment, a local event bridge is acceptable. For multiple API/worker
processes, use Redis pub/sub or a durable outbox.

### P1-5: Dashboard labels monthly totals as today's values

`backend/app/services/dashboard_service.py:214` maps monthly total kWh and monthly
peak to `today_energy` and `today_peak`.

**Fix:** Calculate local-day aggregates for the selected site. Keep month-to-date
values explicitly labeled and separate.

### P1-6: Dashboard still contains zero-value product theatre

Energy score is always zero. Solar generation is always zero. Scenario projections
with and without recommendations are identical, while the UI still presents them
as scenario analysis. The assistant and AI-decision labels describe deterministic
status strings.

**Fix:** Remove unsupported score, solar, scenario, and AI surfaces. Restore them
only with defined formulas, data requirements, and evidence. Rename the current
assistant to `Energy status` and `AI Recommendations` to `Recommendations` until
Gemini is live.

### P1-7: Model comparison is not a comparison

The registry enforces one active model per `(dataset, horizon)`, and comparison
runs only active models. The result normally contains one model.

**Fix:** Separate `production_active` from `comparison_eligible`. Keep one served
default but allow all validated compatible candidates in explicit comparison.
Return per-model failures instead of silently skipping them.

### P1-8: Model promotion chooses newest valid artifact, not best validated model

Registry synchronization activates the newest valid package when no model is
active. The current active SOTA artifact has worse recorded MAE/RMSE/R2 than the
PatchTST package.

**Fix:** Require explicit admin/CLI promotion with a validation report and reason.
Do not auto-promote based on filesystem modification time.

### P1-9: The CSV limit is internally inconsistent

Import accepts 10,000 rows, but preview rejects files above 1,000 rows. The UI
requires preview, so the real client limit is 1,000. The audit reproduced a 400
response for 1,001 rows.

**Fix:** Preview all rows up to the documented 10,000 limit while returning only a
bounded error sample, or explicitly document and enforce a 1,000-row product limit
everywhere.

### P1-10: Settings accept invalid financial and time values

The backend accepts negative tariffs, negative budgets, invalid peak hours,
arbitrary sensor modes, and invalid timezone strings.

**Fix:** Add Pydantic bounds and enums: non-negative rates/budgets, hours 0-23,
validated IANA timezone, supported currency, and supported source type. Test
overnight tariff windows and invalid inputs.

### P1-11: Admin controls contain deliberate dead behavior

- Health failures are replaced with hardcoded healthy CPU/memory/uptime values.
- Retrain is visible even though the backend always returns 501.
- The success copy still says simulated retraining.
- Admin can demote or deactivate the last/current admin.

**Fix:** Show an unavailable health state, remove retraining until a candidate
training pipeline exists, expose validated activation/rollback instead, and guard
the last active administrator.

### P1-12: The user model-registry page reports incorrect state

The page displays the version as the horizon and falls back to `Active` because it
looks for a `status` field that the endpoint does not return. Inactive models can
therefore appear active. The page also says `manage` without management controls.

**Fix:** Use the endpoint's `horizon` and `active` fields, align TypeScript types,
and describe the page as read-only for users.

### P1-13: Dashboard PDF export is a dead button

The dashboard calls the PDF API but discards the returned Blob and suppresses all
errors. The dedicated Reports page implements the download correctly.

**Fix:** Reuse the Reports download helper or link directly to Reports.

### P1-14: Multi-site is not a complete product capability

Only `GET /multi-site` exists. There is no client API/UI for creating, editing,
selecting, or deleting sites/meters. Settings, budget, forecasts, imports, and the
simulator default to the first site.

**Fix:** Either scope the PFE honestly to one site per user or implement site CRUD,
site selection in every workflow, per-site budget/settings, and explicit meter
creation. Do not market current read-only aggregation as full multi-site support.

### P1-15: Alert reliability and lifecycle are incomplete

- The worker exits on its first transient database/rule failure and Compose has no
  restart policy.
- `resolved_at` is never set.
- Forecast alerts do not use evidence, cooldowns, or recommendation creation and
  may duplicate on repeated forecasts.
- Budget-risk, anomaly, and power-factor rules listed in the plan are absent.

**Fix:** Catch failures per cycle, retry with backoff, add service restart policy,
unify forecast and meter alerts through one rule engine, and implement only the
rules that can be verified with current data.

### P1-16: Automated product validation is not complete

There are no frontend unit/component tests and no browser end-to-end suite. Backend
tests do not cover forecast endpoints, dashboard truth, settings validation, admin
behavior, analytics exports, alert delivery, or full register-to-report flow. Root
tests currently fail collection because settings reject unrelated root `.env`
keys and `tests/training/test_inference.py` imports a removed `prepare_tensors`
function.

**Fix:** Add Playwright flows for registration/setup/CSV/dashboard/forecast/report,
push setup, admin activation, session refresh, and mobile navigation. Repair or
remove stale root tests and make one documented root quality command authoritative.

## 7. Medium-Priority Findings (P2)

### Security and authentication

- Access and refresh tokens are stored in `localStorage`, increasing XSS impact.
  Prefer an HttpOnly, Secure, SameSite refresh cookie and keep the short-lived
  access token in memory.
- WebSocket access tokens are placed in URLs, where proxies and logs may capture
  them. Use a short-lived WebSocket ticket or an authenticated same-origin
  handshake.
- Password minimum length is only six characters. Use at least 10-12 characters
  and compromised-password checks when public registration opens.
- Emails are not normalized before uniqueness/login checks, allowing case variants
  depending on database collation. Store normalized lowercase email and preserve a
  separate display value only if needed.
- Swagger declares an OAuth2 password token URL, but the login endpoint accepts
  JSON rather than OAuth2 form data. The interactive Authorize flow is therefore
  misleading.
- Public API documentation should be disabled or access-controlled in production
  if it exposes operational endpoints not intended for clients.
- Some 500 responses include raw exception text, potentially exposing paths and
  internal model details.

### Data and performance

- Dashboard polling runs every five seconds and recalculates monthly totals by
  loading all user readings. This will degrade quickly with real meter volume.
- Current consumption loads the user's full history twice before selecting the
  latest row.
- History endpoints load all readings before slicing/bucketing in Python.
- `all` history is actually capped at 365 days.
- No pagination exists for alerts, recommendations, forecasts, or raw readings.
- Simulator configuration accepts unvalidated JSON and can persist invalid values
  that break the background generation loop.
- The unused `/dashboard/overview` endpoint shares one SQLAlchemy session across
  worker threads even though sessions are not thread-safe.
- The simulation loop lives in the API process. Scaling the API to multiple
  workers can run duplicate simulator loops. Move it to a dedicated worker.

### Frontend quality

- The authenticated layout always reserves 260px/72px for a fixed sidebar and has
  no mobile drawer behavior. Small screens are likely clipped or severely narrow.
- Dashboard and forecast pages exceed 1,000 lines and use extensive `any` casts,
  making contract regressions easy to hide.
- `dashboardApi.getSummary()` returns `Promise<any>` instead of an explicit
  contract.
- Many API failures are console-only or silently ignored instead of showing
  retryable page states.
- Login copy says `Connect Smart Meter`, `live utility grid feed`, `Secure SSL`,
  and grid automation even though it is normal account login and TLS is not part
  of the local app.
- Metadata describes a premium AI platform while current recommendations are
  deterministic and no chatbot exists.
- Several icon buttons lack accessible labels; no automated accessibility audit
  is configured.

### Operations and maintainability

- Avatar files are stored inside the backend container without a persistent volume
  or object store, so redeployment loses them.
- Avatar validation trusts extension and MIME type without decoding/validating the
  image content.
- The PowerShell backup/restore scripts stream PostgreSQL custom-format binary data
  through PowerShell pipelines/redirection. This is unsafe on common Windows
  PowerShell versions and has not been demonstrated with a restore rehearsal.
- Docker services have no restart policies, CPU/memory limits, or production proxy
  and TLS configuration.
- PostgreSQL is exposed on host port 5432 in the default Compose file.
- Python's heavy scientific dependencies use broad lower bounds, reducing build
  reproducibility.
- CI has no Python dependency audit, container scan, secret scan, or frontend E2E
  job. The current frontend audit reports two moderate dependency findings.
- Audit events are useful but incomplete: logout, report export, profile/avatar,
  forecast creation, and simulator actions are not consistently recorded. There
  is also no audit viewer/export.
- Old documents under `docs/` still claim billing, subscriptions, production-ready
  status, SMTP fallback, and other features that no longer exist. They contradict
  the current README and can damage a PFE defense.
- There are no current Terms, Privacy, account deletion, support contact, or
  incident contact pages.

## 8. Planned Features and Correct Integration Design

The following items are planned by the project owner and should be presented as
roadmap work until they pass their acceptance criteria.

### 8.1 Transactional email, verification, and password reset

Implement this before email alerts because it creates the shared delivery and
token foundation.

Required design:

1. Use a project-owned domain and transactional provider rather than a personal
   mailbox SMTP password.
2. Configure SPF, DKIM, and DMARC for the sending domain.
3. Add `email_verified_at` to users.
4. Store only hashed, single-use verification/reset tokens with purpose, expiry,
   used timestamp, and attempt counters.
5. Rate-limit request and resend endpoints without revealing whether an email is
   registered.
6. Revoke all refresh sessions after successful password reset.
7. Add an email outbox with pending/sent/failed/dead-letter state, retry count,
   next attempt, provider message ID, and sanitized error.
8. Run delivery in a worker, not FastAPI `BackgroundTasks`.
9. Add templates for verify email, reset password, security notice, and alert.
10. Test expiration, reuse, replay, throttling, provider failure, retry, and account
    deactivation.

### 8.2 Google login and signup

Required design:

1. Add an `oauth_accounts` table keyed by `(provider, provider_subject)`.
2. Use Google Authorization Code with PKCE or Google Identity Services and verify
   issuer, audience, signature, expiry, nonce, and `email_verified` server-side.
3. Never identify a Google account by email alone after initial verified linking.
4. Define safe account-linking behavior for an existing password account.
5. Issue the same EnergyAI access/refresh session model after successful Google
   authentication.
6. Support disconnecting Google only when another login method remains.
7. Add login, signup, linking, conflict, disabled-user, and replay tests.

### 8.3 Project email alert notifications

Build on the transactional outbox:

- Add user and per-site notification preferences.
- Send only after the alert transaction commits.
- Include site, meter, observed time, rule, evidence, severity, and a deep link.
- Deduplicate email using alert ID and channel.
- Record delivery state and make failures visible to administrators.
- Add quiet hours and digest mode later; do not block the first PFE release on
  them.

### 8.4 Gemini recommendations

Do not replace deterministic calculations with Gemini. Use a layered design:

1. Deterministic services calculate energy, cost, budget, forecast facts, alerts,
   and safe candidate actions.
2. A backend Gemini service receives a small structured, user-owned evidence
   bundle. The API key stays server-side.
3. Gemini returns a strict JSON schema: title, explanation, suggested actions,
   evidence references, limitations, and safety flags.
4. Store provider model name, prompt version, evidence snapshot, generated time,
   and user feedback for every generated recommendation.
5. Display citations back to EnergyAI facts such as reading timestamps, tariff,
   alert threshold, or forecast version.
6. Never let Gemini query the database directly, execute commands, change settings,
   or control devices.
7. Redact unnecessary personal information and define retention/opt-out behavior.
8. Add quotas, timeouts, retries, circuit breaking, cost tracking, and a deterministic
   fallback when Gemini is unavailable.
9. Test prompt injection through CSV/meter names, malformed output, hallucinated
   savings, cross-user context, and provider outage.

Until this exists, rename AI recommendation labels to rule-based recommendations.

### 8.5 Gemini chatbot

The chatbot should be an evidence navigator, not a general chatbot pasted onto the
dashboard.

Suggested allowlisted tools:

- Get current meter status and freshness.
- Summarize a selected period's energy/cost.
- Explain the current tariff and budget projection.
- Explain a persisted forecast and its limitations.
- List alerts/recommendations and their evidence.
- Link the user to the correct page/action.

Each tool must resolve the authenticated user and selected site server-side. The
chatbot should refuse unsupported device-control, billing, and guaranteed-savings
requests. Conversations need retention controls and a clear `AI-generated` label.

### 8.6 Stronger forecasting models

New models should not be integrated by copying only weight files. Promotion
requires:

1. A complete portable package: model, preprocessing pipeline, config, feature and
   target schemas, lookback, horizon, sampling interval, metrics, fingerprint, and
   model card.
2. Time-based held-out evaluation against persistence and seasonal-naive baselines.
3. Per-horizon MAE/RMSE and a meaningful percentage metric; current `MAPE=0` should
   be treated as unavailable, not perfect performance.
4. Evaluation on the single-site contract used by the app. Multi-house ECL models
   must not be promoted directly.
5. Residual or conformal interval calibration before confidence bands are shown.
6. Candidate warm-up and shape tests in CI.
7. Shadow comparison on representative data before activation.
8. Explicit promotion and rollback records.
9. Continuous matched actual-versus-forecast scoring after deployment.

The current 24h models can remain as the product baseline while this process is
built.

## 9. Recommended Implementation Order

### Phase A: Restore product truth and deployability (P0, 2-4 focused days)

1. Package deployable 24h artifacts for a clean clone and make Docker readiness
   pass without local ignored files.
2. Remove the automatic synthetic dashboard WebSocket and hardcoded `sota` live
   forecast.
3. Remove fixed forecast peak/cost/weather/AI claims.
4. Disable the broken email call while preserving in-app forecast alerts.
5. Replace outcome matching with timestamp/site/meter-safe logic or hide validation
   until implemented.
6. Correct today's versus month-to-date labels.

**Exit gate:** A clean checkout can register, onboard with CSV, view only its real
or explicitly simulated data, run a 24h forecast, and produce a truthful report.

### Phase B: Finish existing client workflows (P1, 3-5 days)

1. Fix refresh rotation, concurrent refresh, and server logout.
2. Build the push-meter connection screen.
3. Align CSV preview/import limits.
4. Validate settings, tariffs, budgets, simulator config, and data mode.
5. Fix admin health/models, remove retrain, and add activation/rollback controls.
6. Fix model comparison eligibility and model-registry display.
7. Decide honestly between single-site PFE scope and full site CRUD.
8. Make alerts publish in-app events and harden worker retries.

### Phase C: Authentication and email foundation (3-5 days)

1. Add transactional provider/domain configuration and email outbox worker.
2. Add verification and reset-token flows.
3. Add project email templates and security notices.
4. Add Google login/signup and safe account linking.
5. Move refresh sessions toward secure cookie storage.

### Phase D: Gemini intelligence (4-7 days)

1. Add structured evidence bundles and Gemini recommendation enrichment.
2. Add feedback and generation provenance.
3. Add the allowlisted chatbot tool layer.
4. Add injection, ownership, outage, quota, and hallucination tests.

### Phase E: Model evaluation and promotion (parallel with C/D)

1. Repair the research test suite and define one reproducible evaluation command.
2. Evaluate current/new models against naive baselines on held-out single-site data.
3. Package candidates using the production artifact contract.
4. Add calibrated intervals and matched outcome scoring.
5. Promote the best justified model and preserve rollback.

### Phase F: Launch hardening and validation (4-7 days plus observation time)

1. Add frontend component tests and Playwright desktop/mobile journeys.
2. Optimize reading queries and add pagination/aggregates.
3. Fix persistent avatar storage and rehearse backup restore.
4. Add dependency/container/secret scanning.
5. Add privacy, terms, data deletion, support, and incident contacts.
6. Run volunteer or representative-data validation and record findings.
7. Record at least one real decision improved by EnergyAI with evidence.

## 10. Minimum Release Acceptance Tests

The product should not be called client-ready until all of these pass from a clean
checkout:

1. Register -> verify email -> setup -> CSV import -> dashboard -> forecast -> PDF.
2. Register with Google -> safe account link -> logout -> revoked refresh session.
3. Create push key -> send valid sample -> dashboard updates -> stale meter alert ->
   in-app and email notification.
4. Start and stop the simulator explicitly; no simulation data appears before
   start or after stop.
5. User A cannot access User B's sites, readings, exports, forecasts, alerts,
   recommendations, WebSockets, or chat context.
6. Invalid/negative tariff, budget, timezone, and simulator values are rejected.
7. 1,000 and documented maximum-row CSV files preview/import consistently.
8. Forecast output matches its registered horizon/schema and contains no fixed
   explanation or confidence claim.
9. Outcome scoring uses matching timestamps and ignores sample/demo forecasts.
10. Gemini outage falls back to deterministic recommendations without losing the
    core application.
11. Database/model/email failures are visible, retryable, and do not become fake
    success states.
12. Desktop and mobile critical journeys pass automated browser tests.
13. Backup is restored into an empty rehearsal database and data counts/checksums
    are verified.

## 11. PFE Positioning

The strongest defense is not to call EnergyAI an enterprise production platform.
Present it as:

> A trustworthy single-site energy intelligence platform that validates owned
> meter data, calculates interval-based cost, produces versioned 24-hour forecasts,
> detects evidence-backed operational issues, and supports user decisions with
> transparent recommendations.

That claim is technically interesting and defensible once the P0 findings are
closed. Gemini, Google authentication, transactional email, email alerts, and
stronger calibrated models then become clear extensions rather than features that
must hide weaknesses in the current core.

## 12. Final Assessment

EnergyAI already contains the foundation of a strong career project. The backend
ownership and ingestion design, calculation engine, artifact-aware forecasting,
evidence-backed actions, exports, and deployment discipline are meaningful work.

The current gap is trust. Some old simulation and dashboard code still bypasses
the newer product-truth architecture, several UI labels promise AI/live behavior
that does not exist, and the deployable model artifacts are not reproducible from
a clean repository. Fixing those issues will improve the PFE more than adding
another dashboard page.

**Current recommendation:** do not recruit real clients yet. Close Phase A and B,
then run a supervised volunteer/representative-data beta. Add the planned email,
Google, Gemini, and stronger-model work on top of that verified baseline.
