# Audit Fix Implementation Tasks

This task list tracks the resolution of open issues identified in the v2 Technical Audit.

## Priority 1: Security (High Impact)
- [x] **H1-WS: Authenticate WebSocket Connections**
  - [x] Update `/ws/{client_id}` in `alerts.py` to require token
  - [x] Update `/smart-meter/live-ws` in `forecast.py` to require token
  - [x] Update frontend WebSocket instantiations to pass `token` parameter
- [x] **H2-NEW: Secure `GET /settings`**
  - [x] Add `get_current_user` dependency to `GET /api/v1/settings` in `settings.py`
- [x] **H3-NEW: Secure Global Setup**
  - [x] Restrict `POST /api/v1/settings/setup` to admin role

## Priority 2: Correctness & Architecture (Medium Impact)
- [x] **M1-NEW: Remove Hardcoded Localhost URLs**
  - [x] Add `settingsApi.getSettings()` to `api.ts`
  - [x] Add `settingsApi.getSetupStatus()` to `api.ts`
  - [x] Add `settingsApi.postSetup()` to `api.ts`
  - [x] Replace `fetch('http://localhost:8000/...')` in `multi-site/page.tsx`
  - [x] Replace `fetch` in `analytics/page.tsx`
  - [x] Replace `fetch` in `dashboard/page.tsx`
  - [x] Replace `fetch` in `alerts/page.tsx`
  - [x] Replace `fetch` in `setup/page.tsx`
  - [x] Replace `fetch` in `SetupGuard.tsx`
- [ ] **M3-NEW: Fix Alert User Attribution**
  - [ ] Update `auto_forecast_loop` in `main.py` to attribute alerts correctly (or broadcast globally without saving to the first DB user)
- [ ] **M7-NEW: Fix UI Tier Checks**
  - [ ] Update PDF export lock icon in `analytics/page.tsx` to check `Feature.PDF_EXPORT` instead of Enterprise tier
- [ ] **M4-NEW: Consistent Smart-Meter Gating**
  - [ ] Align role gating on smart-meter endpoints (`smart-meter/sync`, `smart-meter/compare`) with standard forecast endpoints (require `admin` or `analyst`)

## Priority 3: Robustness & Hygiene (Lower Impact)
- [ ] **M5-NEW: Prevent SSRF**
  - [ ] Validate `sensor_api_url` in `smart_meter_service.py` before making requests (block internal IPs)
- [ ] **L1-NEW: Cleanup Unused Features**
  - [ ] Resolve unused `Feature.HEATMAP` feature gate (either apply to an endpoint or remove)
- [ ] **L6-NEW: Docker Configuration**
  - [ ] Add `NEXT_PUBLIC_API_URL` ARG/ENV to frontend `Dockerfile`
- [ ] **L2-NEW: Type Safety**
  - [ ] Update `User.subscription_tier` to union type `'free' | 'pro' | 'enterprise'` in frontend types
