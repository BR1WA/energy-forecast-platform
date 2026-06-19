# Energy Forecast Platform — Improvement Suggestions

Based on a thorough audit of the codebase (backend, frontend, ML pipeline, billing, and infrastructure).

---

## 🤖 1. ML Model & Forecasting

### 1.1 Fix the Month Encoding Inconsistency (H5 — Correctness Bug)
Three input paths encode the month differently:
- `predict_upload`: `sin(2π·month/12)` with month ∈ {1..12}
- Smart-meter path: uses `month - 1` (0..11)
- `_load_samples`: raw `df.index.month` (1..12)

**Identical data fed through different routes produces different predictions.** Standardize to a single convention (month ∈ {1..12} with sin/cos encoding) in one shared preprocessing function called by all three paths.

### 1.2 Persist Forecast Start Hour (H2 — Data Integrity)
`Forecast.input_start` and `input_end` columns exist in the model but are never populated by `predict`. Every downstream calculation (PDF cost alignment, analytics tariff windows) then has to guess the wall-clock hour, leading to:
- Wrong peak/off-peak classification in the PDF report (H1)
- Synthetic "actual" values with fabricated noise (H3)

**Fix:** Store `input_start = datetime.now(timezone.utc)` at prediction time. Derive all tariff and cost calculations from it.

### 1.3 Moroccan ONEE Pricing — Complete the Wiring
The 6-tier progressive/selective billing structure is implemented in the setup wizard but the **analytics PDF cost calculation still uses the old `h_idx` as a wall-clock proxy**. After fixing 1.2, replace the misaligned cost logic in `analytics.py` with the ONEE bracket calculator already used elsewhere.

### 1.4 Make "Actual" Values Honest (H3)
`analytics.py` generates:
```python
actual_val = pred_val * (1.0 + (i % 5 - 2) * 0.02)
```
This synthetic noise is presented as historical actuals on charts. Since the thesis's whole argument is that the original paper fabricated metrics — **this is the most academically damaging inconsistency in the project.** Options:
- Label it explicitly as **"Demo / Simulated Data"** on every chart where it appears
- Or store real `SmartMeterReading` rows and compute actuals from them

### 1.5 Sandbox the Retrain Flow (H4 — Critical ML Bug)
`POST /admin/models/{name}/retrain` trains on `torch.randn()` calendar dummy data and then **overwrites the production `.pth` files on disk**, permanently degrading the served models while bumping the reported `r2_score` by a hardcoded `+0.0035`.

**Fix options (pick one):**
- Write retrained weights to a `_candidate/` path and require an admin "promote" step
- Gate retrain behind a separate sandboxed model slot; never overwrite canonical weights
- At minimum, remove the `+0.0035` synthetic accuracy bump and gate the endpoint with a confirmation

### 1.6 Add Uncertainty / Confidence Intervals
All three models return point forecasts only. Modern energy dashboards show a shaded confidence band (e.g., ±1σ from a MC-Dropout pass or a simple bootstrap). This is a **high-visibility UX improvement** that also makes the academic thesis stronger — showing that the model knows what it doesn't know.

### 1.7 Multi-Step Horizon Selector
The current forecast is fixed at 24 steps. A simple `horizon` parameter (6h, 12h, 24h, 48h, 72h) in the predict request and a matching UI slider would make the app immediately more useful and demonstrates the model's generalization.

### 1.8 Explainability Layer (SHAP / Attention Visualization)
PatchTST uses self-attention internally. Extracting and visualizing which input timesteps drove the prediction (attention heatmap over the input window) would be a compelling academic addition and a Pro-tier differentiator. Even a simple feature-importance bar chart (gradient-based) for CNN-BiLSTM would add value.

---

## 🔒 2. Security & Architecture

### 2.1 Authenticate WebSocket Connections (H1-WS — High Priority)
Both WS endpoints (`/alerts/ws/{client_id}` and `/forecast/smart-meter/live-ws`) accept connections with zero auth. The fix is straightforward:

```python
@router.websocket("/ws/{client_id}")
async def websocket_endpoint(websocket: WebSocket, client_id: str, token: str = Query(...), db: Session = Depends(get_db)):
    user = verify_token(token, db)  # raises WebSocketException on failure
    await manager.connect(user.id, websocket)
```

Frontend passes the access token as a query param: `new WebSocket(\`ws://...?token=${accessToken}\`)`.

### 2.2 Authenticate `GET /settings` (H2-NEW)
One line fix — add `current_user: User = Depends(get_current_user)` to the settings GET endpoint. Also restrict `POST /settings/setup` to admin role.

### 2.3 Replace All Hardcoded `localhost:8000` Fetches (M1-NEW)
7 places bypass `apiFetch`, losing 403 handling, token refresh, and env URL config. Create two API module functions:
```typescript
settingsApi.getSettings()        // replaces raw fetch in 4 pages + SetupGuard
settingsApi.postSetup(data)      // replaces raw fetch in setup/page.tsx
settingsApi.getSetupStatus()     // replaces raw fetch in SetupGuard.tsx
```
Then replace every `fetch('http://localhost:8000/...')` call with the module function.

### 2.4 Fix `subscription_tier` TypeScript Type
Change `subscription_tier: string | undefined` to `subscription_tier: 'free' | 'pro' | 'enterprise' | undefined` in `types/index.ts`. This costs one line and catches an entire class of bugs at compile time.

### 2.5 SSRF Protection on `sensor_api_url`
Before calling `requests.get(sensor_api_url)`, validate the URL against an allowlist of schemes and block private/internal IP ranges (10.x, 172.16-31.x, 192.168.x, 169.254.x, localhost). A small helper function is sufficient.

---

## 🏗️ 3. Feature Improvements

### 3.1 Real-Time Alert Scoping
The `auto_forecast_loop` saves all alerts to `db_session.query(User).first()` — the first user in the database. In a multi-user scenario every auto-alert goes to one user. Fix: either broadcast alerts to all users, or run per-user simulated readings in the loop.

### 3.2 Refresh Token Rotation
Currently refresh tokens have no revocation mechanism. A leaked 7-day refresh token is valid for its full lifetime. Add a `refresh_token_hash` column to `User` or a separate `RefreshToken` table and invalidate on logout / on each rotation.

### 3.3 Per-User Settings (M1)
`settings.first()` is used everywhere, meaning all users share one country/tariff/sensor config. For a proper multi-tenant app, tariffs and sensor config should be per-user (or per-org). At minimum, move `is_setup_complete` to per-user only (it already exists on `User` but `register` also sets the global flag).

### 3.4 Admin Subscription Management
The admin panel can change user roles and active status but **cannot manage subscriptions**. Add a tier selector to the admin user edit modal, backed by `PUT /admin/users/{id}` which already calls `billing_service.grant()`. This rounds out the admin capability.

### 3.5 Energy Budget / Goal Setting
Allow users to set a monthly kWh budget or MAD cost target. Track progress against it on the dashboard. This is a natural extension of the existing ONEE pricing calculator and makes the app genuinely useful for Moroccan households.

### 3.6 Historical Comparison View
The forecast page shows one prediction at a time. A comparison view showing today's forecast vs. the same period last week/month (from `ForecastHistory`) would be a high-value feature and straightforward with Recharts' multi-line chart.

### 3.7 Appliance-Level Breakdown (Sub-Metering)
The UCI dataset already has `sub_metering_1` (kitchen), `sub_metering_2` (laundry), `sub_metering_3` (HVAC). The data is stored in `SmartMeterReading` but the dashboard only shows the total. A per-appliance breakdown pie/bar chart is already hinted at in the dashboard lock overlay — complete it for Pro users.

### 3.8 Export to CSV / Excel
The PDF export is Pro-gated and works well. Add a CSV export of raw forecast history and analytics data. This is a one-endpoint addition (`GET /analytics/export/csv`) and an extremely common user request on data dashboards.

### 3.9 Scheduled Reports (Enterprise)
An Enterprise feature: send a weekly/monthly PDF report by email automatically. The email infrastructure (`alert_service.py` SMTP) already exists. A simple `APScheduler` cron job calling the existing `export_pdf_report` function would suffice.

### 3.10 Anomaly Detection Alerts — Make Them Configurable
`AlertConfig.threshold_kw` exists and the auto-forecast loop uses `4.0 kW` hardcoded. Let users set their own threshold via the alert settings UI (the config schema already supports it; the loop just doesn't read it per-user).

---

## 🎨 4. UX / Frontend

### 4.1 Live Dashboard WebSocket Reconnect
The live WebSocket in the dashboard doesn't implement exponential backoff reconnection. If the connection drops (network hiccup, server restart), the dashboard goes silent with no feedback. Add a `useWebSocket` hook with automatic reconnect and a visual "reconnecting…" indicator.

### 4.2 Loading Skeletons vs. Spinners
Several pages (`analytics`, `multi-site`) show a spinner while fetching, which causes layout shift. Replace with skeleton screens (same structure as the loaded content but greyed out) for a much more polished feel.

### 4.3 PDF Lock Icon Checks Wrong Tier
In `analytics/page.tsx:206`, the Lock icon shows when `!isEnterprise` — but PDF export is a **Pro** feature. Change to `!can(user, Feature.PDF_EXPORT)`.

### 4.4 Empty States with CTAs
When a free user visits analytics or multi-site, they see a generic blur overlay. Replace with a proper empty-state component: icon + headline + one-sentence benefit + "Upgrade to Pro" button. This is standard SaaS conversion design.

### 4.5 Onboarding Progress Persistence
If a user closes the browser mid-setup wizard, they have to restart. Persist wizard state to `localStorage` keyed by `user.id` and restore it on next visit.

### 4.6 Mobile Responsiveness Audit
The sidebar, multi-site grid, and forecast chart panels aren't tested on mobile viewports. The collapsible sidebar pattern is in place — ensure the inner content grids use responsive Tailwind breakpoints throughout.

### 4.7 Dark/Light Mode Toggle in Navbar
`next-themes` is already a dependency. A sun/moon toggle in the navbar (one button) would surface a feature users already expect and that's fully supported.

---

## 🧪 5. Testing & Code Quality

### 5.1 Expand Test Coverage to Core Flows
Current: 4 tests, all in `test_entitlements.py`. Priority additions:

| Test Suite | Key Scenarios |
|------------|--------------|
| `test_auth.py` | Register, login, refresh, logout, duplicate email, bad password |
| `test_forecast.py` | Predict (analyst), predict (viewer → 403), CSV upload, history |
| `test_billing.py` | Full checkout flow, cancel, expired subscription, double-confirm |
| `test_admin.py` | List users, grant tier, delete user, health endpoint |
| `test_settings.py` | Setup, preferences, unauthenticated GET |

### 5.2 Structured Logging
Replace `print()` throughout with Python's `logging` module at appropriate levels (`DEBUG`, `INFO`, `WARNING`, `ERROR`). Add a request-ID middleware so all log lines for a single HTTP request share an ID — invaluable for debugging.

### 5.3 API Type Safety — `alertsApi` Returns `any[]`
`alertsApi.getAlerts()` returns `any[]`. Add a proper `Alert` interface to `types/index.ts` and type the response. Same for `alertsApi.getConfig()`.

### 5.4 In-Memory SQLite for Tests
The test suite uses `test_entitlements.db` (file-based). Switch to `sqlite:///:memory:` with a `@pytest.fixture` scoped session for faster, isolated, automatically-cleaned tests.

### 5.5 CI/CD Pipeline
No CI configuration exists. A minimal GitHub Actions / GitLab CI pipeline running:
1. `pytest backend/tests/`
2. `tsc --noEmit` (TypeScript compile check)
3. `eslint frontend/src/`

...on every push would catch regressions before they reach the demo.

---

## 🗂️ 6. Repo & Infrastructure

### 6.1 Remove Committed SQLite Database
`backend/energy_forecast.db` is committed to the repo. This is a data privacy issue (contains user accounts and forecasts) and inflates repo size. Add it to `.gitignore` immediately and create a `db/seed.sql` with only schema + demo data.

### 6.2 Collapse Parallel App Entry Points
Three separate app directories (`app/`, `app_forecast/` Streamlit, `backend/`) share model and sample code via relative `../` path traversal. Consolidate shared logic into `backend/` or a shared `lib/` package.

### 6.3 Unified Migration Strategy
Three overlapping schema management mechanisms:
- Alembic (`alembic/`)
- `Base.metadata.create_all()` in `main.py`
- `add_columns.py` script

Pick one (Alembic) and remove the other two. `create_all` is safe for initial dev but conflicts with Alembic in production.

### 6.4 Docker Production Hardening
The frontend `Dockerfile` relies on default `localhost:8000`. Add:
```dockerfile
ARG NEXT_PUBLIC_API_URL
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL
```
And update `docker-compose.yml` to pass it from the environment.

### 6.5 Clean Up Root Overlapping Files
The repo root has: `AUDIT_REPORT.md`, `pfe_full_audit.md`, `pfe_final_audit_report.md`, `bug_fix_plan.md`, `presentation_plan.md`, `presentation_plan3.md`, `presentation_plan.pdf`, `task.md`, `implementation_plan.md`. Consider a `docs/` directory for all plan/audit files.

---

## Priority Matrix

| # | Improvement | Effort | Impact | Category |
|---|-------------|--------|--------|----------|
| 1 | Fix month encoding inconsistency (1.1) | Low | High | ML Correctness |
| 2 | Persist forecast start hour (1.2) | Low | High | ML Correctness |
| 3 | Authenticate WebSockets (2.1) | Low | High | Security |
| 4 | Authenticate `GET /settings` (2.2) | Trivial | High | Security |
| 5 | Replace hardcoded `localhost` URLs (2.3) | Low | High | Architecture |
| 6 | Label synthetic analytics data (1.4) | Trivial | High | Academic Integrity |
| 7 | Fix retrain sandbox / weight corruption (1.5) | Medium | High | ML Integrity |
| 8 | Fix PDF lock icon tier check (4.3) | Trivial | Medium | UX |
| 9 | Fix auto-alert user attribution (3.1) | Low | Medium | Correctness |
| 10 | `subscription_tier` union type (2.4) | Trivial | Medium | Type Safety |
| 11 | Add uncertainty bands to forecast (1.6) | Medium | High | ML / UX |
| 12 | Multi-step horizon selector (1.7) | Medium | Medium | Feature |
| 13 | Energy budget / goal setting (3.5) | Medium | High | Feature |
| 14 | Expand test coverage (5.1) | Medium | High | Quality |
| 15 | Structured logging (5.2) | Low | Medium | Quality |
| 16 | Refresh token rotation (3.2) | Medium | Medium | Security |
| 17 | CSV export (3.8) | Low | Medium | Feature |
| 18 | WebSocket reconnect with backoff (4.1) | Low | Medium | UX |
| 19 | Admin subscription management (3.4) | Low | Medium | Feature |
| 20 | Remove committed SQLite DB (6.1) | Trivial | Medium | Repo Hygiene |
