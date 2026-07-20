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
