# PFE Release Implementation Log

**Branch:** `release/pfe`  
**Baseline:** `7f131a5`  
**Plan:** `docs/PRODUCT_IMPLEMENTATION_PLAN_2026-07-20.md`

## 2026-07-20 - Release Initialization

### Completed

- Created `release/pfe` sequentially from stable `main` at `7f131a5`.
- Replaced the open-ended roadmap with PFE, Product V1, and Product V2 milestones.
- Locked Google, email, 168h, monthly forecasting, Gemini, multi-site, billing,
  retraining, model comparison, and advanced monitoring out of the PFE scope.
- Preserved truthful live monitoring, all historical timeframes, 24h Global TFT
  readiness gates, explicit seasonal fallback, and monthly aggregate research.

### Baseline status

- Backend: `python -m pytest -q` -> 35 passed, one expected DEBUG-only insecure
  admin-password warning.
- Frontend: `npm run lint` -> passed.
- Frontend: `npm run typecheck` -> passed.
- Frontend: `npm run build` -> passed; 22 static routes generated.
- The build confirms duplicate/out-of-scope routes for Models, Multi-site,
  Smart-meter, Analytics, Profile, Budget, and Simulation that must be removed or
  consolidated during truth cleanup.
- Existing research notebooks and model experiment outputs remain untracked and
  untouched.

### Active workstream

- Establish baseline gates, then remove misleading and out-of-scope surfaces.

### Release blockers

- To be updated after each workstream and final audit.

## 2026-07-20 - Truth Cleanup Slice 1

### Completed

- Removed the forecast smart-meter WebSocket that generated random readings and
  forecasts merely because Dashboard was open.
- Removed the frontend connection to that synthetic endpoint.
- Removed forecast calls to the nonexistent email sender. Email remains deferred
  to Product V1 and cannot crash PFE forecasts.
- Disabled forecast outcome validation that matched the first arbitrary later
  reading instead of an exact target timestamp.
- Unregistered and deleted the multi-site API.
- Removed the backend retraining endpoint that always returned 501.
- Updated obsolete ownership/WebSocket tests to enforce the reduced product scope.

### Verification

- Backend: 33 tests passed after removal of two obsolete synthetic-WebSocket tests.
- Frontend lint: passed.
- Frontend typecheck: passed.

### Remaining in truth cleanup

- Remove fabricated dashboard/forecast sections, client model comparison, fake
  admin health/retraining UI, multi-site/client model pages, duplicate routes, and
  misleading copy.

## 2026-07-20 - One-Site and Session Integrity

### Completed

- Added a migration that creates missing site/meter/settings records, refuses
  ambiguous duplicate-site ownership, enforces one site per user, and marks one
  primary meter per site with a partial unique index.
- Added strict single-site/primary-meter resolution while retaining temporary
  caller aliases during the release refactor.
- Made registration create user ownership records in one transaction.
- Normalized registration/login emails and raised password minimum to 8 characters.
- Protected the final active administrator from demotion or deactivation.
- Fixed the client to retain rotated refresh tokens and share one in-flight refresh
  across concurrent 401 responses.
- Made logout revoke all backend refresh sessions before clearing local state.
- Removed Admin's fake health fallback and Retrain UI/API.
- Removed Multi-site and client Models pages plus their navigation/API clients.
- Added root `pytest.ini` so the default suite is the backend product suite;
  research tests remain explicitly runnable in their own environment.

### Verification

- Backend product suite: 36 tests passed before the final uniqueness regression.
- Frontend lint and typecheck: passed.
- Fresh SQLite Alembic upgrade to head: passed.
- Downgrade of the one-site migration: passed.

### Remaining in this area

- Remove meter/site choices from normal-user contracts where they are not needed.
- Complete frontend truth cleanup and consolidate duplicate routes.

## 2026-07-20 - Truthful Live Monitoring

### Completed

- Added an authenticated read-only WebSocket that streams only committed push and
  explicitly simulated readings from the authenticated user's primary meter.
- Added typed snapshot/reading events and optional reading cursor support without
  putting access tokens in URLs.
- Excluded imported CSV history from live events.
- Added regressions proving invalid clients are rejected, CSV is excluded, owned
  simulation data is visible, and opening Live creates no database rows.

### Verification

- Backend product suite: 40 tests passed.

### Remaining in this area

- Continue into reconnect coverage, historical periods, and the focused Dashboard.

## 2026-07-20 - Period Tracking and Focused Dashboard

### Completed

- Replaced the former 365-day "All" approximation with real Live, Today, 7 days,
  This month, This year, All, and Custom periods.
- Added site-timezone boundaries, streaming bounded queries, adaptive chart
  granularity, interval-derived energy, tariff-consistent cost, source counts,
  coverage, and freshness metadata.
- Restricted all consumption calculations to the user's primary meter.
- Rebuilt Dashboard around measured power, energy, cost, peak, freshness, source,
  coverage, and data controls; removed geolocation, weather, solar, energy score,
  and unsupported AI command-center claims.
- Connected Live mode to the authenticated read-only monitoring stream with cursor
  resume, client deduplication, reconnect state, and REST resynchronization.
- Added a responsive mobile navigation drawer and stable chart/KPI layouts.

### Verification

- Backend product suite: 42 tests passed before the final cursor regression.
- Frontend lint: passed.
- Frontend typecheck: passed.
- Browser login against the isolated current-source pair was blocked by the local
  browser URL policy after the port correction; final browser screenshots remain
  pending rather than being claimed as complete.

### Remaining in this area

- Add raw-reading pagination for detailed drill-down.
- Add tariff/budget, forecast, alert, and recommendation summaries once their
  focused backend contracts are complete.
- Add automated desktop/mobile browser journeys.

## 2026-07-20 - Client-Usable Data Sources

### Completed

- Made CSV preview and import share the same 5 MB/10,000-row limits and exposed
  mapped columns plus row-level validation errors in Consumption.
- Added primary-meter metadata, expected-cadence configuration, one-time push-key
  generation/rotation, last-seen status, a request example, and an intentional
  test-reading action to Settings.
- Made push-key rotation explicitly invalidate the previous key and stop an active
  simulator session.
- Prevented push and simulator writers from committing concurrently to one meter.
- Replaced arbitrary simulator JSON with a strict bounded schema.
- Rebuilt the simulator as a clearly labelled demo source without claims of real
  appliances, anomaly generation, or recommendation intelligence.
- Rebuilt Consumption as the seven-period historical drill-down and CSV workspace.
- Added strict site/tariff/timezone/budget input constraints and aligned the
  password UI with the backend's eight-character minimum.

### Verification

- Backend product suite: 46 tests passed.
- Frontend lint: passed.
- Frontend typecheck: passed.

### Remaining in this area

- Add raw-reading pagination for large detailed drill-downs.
- Cover CSV/push/simulator onboarding in browser journey tests.

## 2026-07-20 - Route and Notification Truth Cleanup

### Completed

- Removed duplicate Analytics, Budget, Profile, and Smart-meter routes after
  preserving their required functions in Consumption, Reports, and Settings.
- Redirected account-security actions to the Security settings tab and push setup
  to the Data sources tab.
- Removed the unvalidated user data-mode API/context and its misleading global
  mode badge; source and freshness now come from actual meter readings.
- Removed the unused alert WebSocket, URL-token authentication, client hook, and
  obsolete tests. The navbar now refreshes owned alerts over the authenticated
  REST API every 30 seconds.
- Replaced dead Analytics search results with Consumption, Recommendations, and
  Reports destinations.

### Verification

- Backend product suite: 42 tests passed; four deleted tests belonged exclusively
  to the removed no-op alert WebSocket.
- Frontend lint and typecheck: passed.

## 2026-07-20 - Product 24-Hour Global TFT

### Completed

- Packaged the selected 5.6 MB Global TFT checkpoint with its inference
  architecture, SHA-256 fingerprint, feature contract, research metrics,
  provenance, and limitations; no training arrays or prediction samples ship.
- Added primary-meter interval integration into 336 site-local hourly-kWh inputs,
  95% coverage and three-hour gap gates, finite checks, bounded interpolation,
  site calendar features, and rolling-window z-score adaptation.
- Persisted the scaler, imputed timestamps, source, coverage, model fingerprint,
  target timestamps, quantiles, method, runtime, and fallback reason.
- Added readiness, run, latest, and owned-history APIs for one fixed 24-hour
  contract. PyTorch and artifact failures use a visibly labelled weekly seasonal
  baseline with no fabricated uncertainty interval.
- Rebuilt Forecast around meter readiness, one Generate action, hourly kWh,
  10th/50th/90th model quantiles, fallback disclosure, provenance, and history.
  Removed sample uploads, client model choice, model comparison, and static claims.

### Verification

- Packaged checkpoint inference test: ordered finite 24-hour quantiles passed.
- Forecast API ownership and explicit fallback test: passed.
- Backend product suite before the final API regression: 44 tests passed.
- Focused forecast tests after provenance completion: 6 passed.
- Frontend lint, typecheck, and production build: passed; 16 static pages generated.

### Remaining in this area

- Exercise deterministic repeatability and measured latency in release validation.
- Validate packaged model readiness from the clean Docker runtime.
- Complete browser-level insufficient-data, TFT, and fallback journeys.

## 2026-07-20 - Client Actions, Reports, and Release-Facing Truth

### Completed

- Added open, acknowledged, resolved, and reopened alert lifecycle actions with
  ownership checks, state filters, audit events, and automatic resolution when a
  high-load condition clears or push telemetry resumes.
- Prevented repeated alerts while the same incident remains unresolved and made
  the periodic missing-data worker survive and retry after an iteration failure.
- Removed the dormant email-delivery toggle from the PFE alert contract and UI;
  alerts are explicitly in-app only until Product V1.
- Kept recommendations deterministic and evidence-backed with complete, dismiss,
  and reopen actions, measured threshold details, and no projected-saving claim.
- Rebuilt the forecast PDF around hourly kWh, target timestamps, method/version,
  quantiles, source, coverage, tariff context, fallback reason, and limitations.
- Expanded monthly consumption CSV metadata with site, timezone, tariff, source,
  coverage, calculation, currency, and daily energy/cost rows.
- Added site identity and peak timestamp to period summaries and added compact
  monthly budget, latest forecast, open alert, and top action summaries to the
  focused Dashboard.
- Deleted the obsolete composite dashboard/weather backend and client, which was
  the last source of solar/grid/energy-score and remote-weather product claims.
- Reworked landing, sign-in, and registration copy around the actual one-site
  product, fixed the frontend password minimum and setup redirect, corrected the
  forecast contract, and added a product hero asset.

### Verification

- Backend product suite: 47 passed.
- Alert lifecycle, auto-resolution, cooldown, ownership, recommendation, PDF,
  CSV, and report-summary regressions passed.
- Frontend lint, typecheck, and production build passed; 16 pages generated.

### Remaining in this area

- Browser-check alert/recommendation actions and downloads.
- Finish the read-only Admin model/runtime readiness replacement.

## 2026-07-20 - Fixed Artifact Runtime and Focused Admin

### Completed

- Removed the legacy model registry API, activation controls, experiment scanner,
  multi-architecture loader, and stale client/server schemas.
- Rebuilt Admin around user role/activation management plus read-only database,
  process, and fixed-artifact readiness with fingerprint and warm-up status.
- Replaced system readiness with database validation and packaged Global TFT
  integrity/load checks; no registry row or research directory is required.
- Removed research `models/` and `training/` copies and host experiment mounts
  from Docker. The runtime receives only the packaged backend artifact.
- Split ML runtime dependencies so ordinary tests do not install Torch and the
  runtime image installs the CPU-only PyTorch wheel rather than CUDA packages.
- Removed dormant SMTP configuration, synthetic demo database seeding, and stale
  model-registry operations documentation. Added the fixed artifact contract and
  local inference dependency instructions.

### Verification

- Backend product suite: 47 passed.
- Frontend lint, typecheck, and production build: passed; 16 pages generated.
- `docker compose config --quiet`: passed.
- The first local Docker test-image build exceeded the 120-second command window;
  the pre-existing image timestamp confirmed that run did not complete. A longer
  release build remains required and is not recorded as passed.
