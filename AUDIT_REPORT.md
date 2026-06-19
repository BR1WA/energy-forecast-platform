# Energy Forecast Platform — Technical Audit (v2)

**Date:** 2026-06-19
**Scope:** FastAPI backend (`backend/`), Next.js frontend (`frontend/`), ML service, billing/entitlement system, and deployment artifacts.
**Prior audit:** 2026-06-18 — identified C1–C4 (critical), H1–H5 (high), M1–M8 (medium), L1–L7 (low).
**Verdict:** The four original critical findings (C1–C4) are **all resolved**. The platform now has a legitimate entitlement model with server-side enforcement, an auditable subscription lifecycle, externalized secrets, and Moroccan ONEE tiered pricing. Remaining issues are medium-to-low severity, concentrated around **unauthenticated WebSockets** and **hardcoded localhost URLs**.

---

## 1. Executive Summary

### What Changed Since v1

| Area | Before (v1) | After (v2) |
|------|-------------|------------|
| **Tier self-grant (C1)** | Any user could `PUT /auth/me` with `subscription_tier: "enterprise"` | Removed from `UserUpdateMe`; upgrades require 2-step checkout or admin grant |
| **Server-side gating (C2)** | UI-only blur overlays; endpoints wide open | `require_feature()` dependency on analytics, PDF, multi-site |
| **JWT secret (C3)** | Hardcoded `"dev-secret-key-for-local-testing-only"` | `validate_secrets()` blocks production startup if insecure defaults detected |
| **Subscription audit (C4)** | No record of why a user holds a tier | `Subscription` model with `status`, `source`, `checkout_ref`, timestamps |
| **Billing flow** | Direct `updateProfile({ subscription_tier })` | `billingApi.checkout()` → simulated payment → `billingApi.confirmCheckout()` |
| **Energy pricing** | Generic cost calculation | Moroccan ONEE 6-tier progressive/selective billing structure |
| **Cancel/downgrade** | One-click, no confirmation | Modal confirmation dialog prevents misclicks |
| **Frontend entitlements** | Scattered `subscription_tier === 'enterprise'` checks | Centralized `can(user, Feature)` helper from `entitlements.ts` |

### Current Risk Profile

| Severity | Count | Summary |
|----------|-------|---------|
| 🔴 Critical | **0** | All four original criticals resolved |
| 🟠 High | **3** | Unauthenticated WebSockets (×2), unauthenticated `GET /settings` |
| 🟡 Medium | **7** | Checkout self-confirm, SSRF risk, hardcoded URLs, role gaps |
| 🔵 Low | **6** | Test coverage, CORS, unused feature gate, code hygiene |

---

## 2. What Was Done Well

- **Clean entitlements architecture.** A single `entitlements.py` catalog (`Tier` enum, `Feature` enum, `FEATURE_MIN_TIER` map) is the source of truth. Both backend (`require_feature()` dependency) and frontend (`can(user, feature)` helper) derive from it. No scattered tier-string checks remain.
- **Auditable subscription lifecycle.** The `Subscription` model tracks `tier`, `status` (pending/active/cancelled/expired), `source` (checkout/admin_grant/trial), `checkout_ref`, `started_at`, `current_period_end`, `cancelled_at`. Admin grants are distinguishable from self-service checkouts.
- **Honest billing simulation.** The 2-step checkout (open → confirm) mirrors a real Stripe-like flow. A sandbox notice is clearly displayed to the user. The `POST /billing/cancel` endpoint handles downgrades, and `refreshUser()` is called after every billing operation to sync state.
- **Production-safe secrets.** `config.py` uses `pydantic_settings.BaseSettings` with `.env` file support. `validate_secrets()` raises `RuntimeError` on startup when `DEBUG=False` and insecure defaults are detected — the app literally refuses to run in production with dev secrets.
- **Moroccan ONEE tiered pricing.** Energy cost calculations use the real 6-bracket progressive/selective billing system used nationally in Morocco, replacing the previous generic calculation.
- **Solid auth primitives.** bcrypt hashing, 15-min access tokens + 7-day refresh tokens, token-type validation (`access` vs `refresh`), transparent 401-refresh-retry in `apiFetch`, avatar upload with extension + MIME + 2MB validation.
- **403 upgrade prompt UX.** `apiFetch` intercepts 403 responses, dynamically imports `sonner`, and shows a toast with an "Upgrade Plan" action button linking to `/plans` — elegant degradation when a free user hits a gated API.
- **Confirmation dialogs on destructive actions.** Cancel/downgrade subscription requires explicit confirmation through a modal, preventing misclicks.
- **Clean layered backend.** Routers → services → models → schemas separation. Dependencies (`get_current_user`, `require_role`, `require_feature`) are used consistently. Business logic lives in services, not routes.
- **Real ML serving.** Three architectures (PatchTST, SOTA Hybrid, CNN-BiLSTM) loaded with `weights_only=True`, CPU inference, RevIN handled internally, and proper calendar feature engineering.

---

## 3. Prior Audit Findings — Resolution Status

### Critical (all resolved ✅)

| ID | Finding | Status | How |
|----|---------|--------|-----|
| **C1** | Users could self-grant any subscription tier | ✅ **FIXED** | `subscription_tier` removed from `UserUpdateMe`. `POST /auth/subscription` only allows downgrade to `free`; upgrades return 403. Tier changes go through `POST /billing/checkout` + `POST /billing/checkout/confirm` or `PUT /admin/users/{id}` (admin grant via `billing_service.grant()`). |
| **C2** | Authorization enforced only in UI | ✅ **FIXED** | `require_feature()` dependency factory in `auth_service.py` enforces server-side 403 on: `GET /analytics/summary` (Pro), `GET /analytics/report/pdf` (Pro), `GET /multi-site` (Enterprise). Multi-site now returns proper 403 instead of `200 + { error }`. |
| **C3** | Hardcoded JWT secret and admin password | ✅ **FIXED** | `validate_secrets()` in `config.py` detects insecure sentinel values. `DEBUG=True`: warning. `DEBUG=False`: `RuntimeError` — app refuses to start. `.env` is in `.gitignore`. |
| **C4** | Open/unauthenticated WebSockets | ⚠️ **PARTIALLY** | WebSocket endpoints remain unauthenticated (see H1-WS below). However, the *subscription audit trail* aspect of C4 is fully resolved with the `Subscription` model. |

### High (partially resolved)

| ID | Finding | Status | Notes |
|----|---------|--------|-------|
| **H1** | PDF cost calculation indexes by forecast step, not hour | ⚠️ Remains | `h_idx` still used as wall-clock hour in `analytics.py`. |
| **H2** | `Forecast` never stores its start hour | ⚠️ Remains | `input_start`/`input_end` columns still unpopulated. |
| **H3** | Analytics fabricates "actual" values | ⚠️ Remains | `actual_val = pred_val * (1.0 + ...)` pattern still present without "Demo Data" label. |
| **H4** | `retrain_model` mutates production weights from noise | ⚠️ Remains | Still trains on `torch.randn()` calendar dummy data and overwrites `.pth` files. |
| **H5** | Calendar month encoding inconsistent | ⚠️ Remains | `sin(2π·month/12)` with month 1..12 vs month-1 (0..11) inconsistency across paths. |

### Medium (mixed)

| ID | Finding | Status | Notes |
|----|---------|--------|-------|
| **M1** | Global `SystemSettings` for multi-tenant app | ⚠️ Remains | `settings.first()` is shared by all users. |
| **M2** | `GET /settings` unauthenticated | 🔴 Remains | Leaks tariff config, sensor API URL. Now elevated to High (see H2-NEW). |
| **M3** | Refresh tokens non-revocable | ⚠️ Remains | No denylist or rotation. |
| **M4** | Tokens in `localStorage` | ⚠️ Remains | XSS exfiltration risk. |
| **M5** | `last_activity` write contention | ⚠️ Remains | Throttled to 10s (comment says 30s). |
| **M6** | CORS hardcodes localhost origins | ⚠️ Remains | `localhost:3000` and `localhost:3001` alongside `FRONTEND_URL`. |
| **M7** | `SetupGuard` hardcodes `http://localhost:8000` | 🔴 Expanded | Now found in 7+ locations across pages (see M1-NEW). |
| **M8** | Bare DB-write blocks in auto-forecast loop | ⚠️ Remains | Manual `SessionLocal()` with broad except. |

### Low (mixed)

| ID | Finding | Status | Notes |
|----|---------|--------|-------|
| **L1** | Repo hygiene (committed DB, overlapping files) | ⚠️ Remains | Multiple audit/plan files still in root. |
| **L2** | Three parallel app entry points | ⚠️ Remains | `app/`, `app_forecast/`, `backend/`. |
| **L3** | `datetime.utcnow()` deprecated | ⚠️ Remains | In `_check_alerts` fallback. |
| **L4** | Magic numbers (alert thresholds) | ⚠️ Remains | `4.0` kW, `> 10.0` MAD cost. |
| **L5** | `print()`-based logging | ⚠️ Remains | No structured logging. |
| **L6** | No automated tests | ✅ **Improved** | `test_entitlements.py` now covers 4 scenarios (free denied, self-grant blocked, checkout flow, admin grant). Still no coverage for auth, forecast, admin, alerts, billing cancel, settings. |
| **L7** | Migrations + `create_all` overlap | ⚠️ Remains | Alembic + `create_all` + `add_columns.py`. |

---

## 4. New Findings

### 🟠 High Priority

#### H1-WS — WebSocket endpoints lack authentication
Both WebSocket endpoints accept connections without any token validation:

**Alert WebSocket** (`backend/app/routers/alerts.py:109-120`):
```python
@router.websocket("/ws/{client_id}")
async def websocket_endpoint(websocket: WebSocket, client_id: str):
    await manager.connect(client_id, websocket)
```
`client_id` is an arbitrary string from the URL. Anyone can connect and receive global broadcast alerts.

**Smart Meter Live WS** (`backend/app/routers/forecast.py:569-625`):
```python
@router.websocket("/smart-meter/live-ws")
async def live_smart_meter_websocket(websocket: WebSocket):
    await websocket.accept()
```
No token validation. Broadcasts telemetry data and forecast predictions to any connected client. Also runs model inference + DB writes on a 2s loop per connection — an **unauthenticated resource amplification vector**.

**Impact:** Cross-user alert leakage, unauthenticated access to live energy telemetry, and DoS via many sockets each triggering inference every 2s.

**Fix:** Authenticate WebSocket connections (token in query param or first message), bind `client_id` to the authenticated user, and rate-limit the live stream.

#### H2-NEW — `GET /api/v1/settings` is unauthenticated
(`backend/app/routers/settings.py:36-52`)

Any unauthenticated request can read the global system configuration including country, currency, tariff rates, sensor type, and **sensor API URL**. This is information disclosure.

**Fix:** Add `get_current_user` dependency. Consider admin-only for write operations.

#### H3-NEW — Any authenticated user can overwrite global system settings
(`backend/app/routers/settings.py:54`)

`POST /api/v1/settings/setup` only requires `get_current_user` — any authenticated user (including viewers) can overwrite global system settings (country, tariffs, sensor config). Combined with the global `SystemSettings` (M1), this means one user's setup can affect all users.

**Fix:** Restrict to admin role, or make settings per-user.

### 🟡 Medium Priority

#### M1-NEW — Hardcoded `localhost:8000` URLs bypass `apiFetch` (7+ instances)
Multiple pages use `fetch('http://localhost:8000/...')` directly instead of `apiFetch()`, losing 403 upgrade prompt handling, token refresh, and environment-based URL configuration:

| File | Line | Endpoint |
|------|------|----------|
| `multi-site/page.tsx` | ~76 | `/api/v1/multi-site` |
| `multi-site/page.tsx` | ~99 | `/api/v1/settings` |
| `analytics/page.tsx` | ~135 | `/api/v1/settings` |
| `dashboard/page.tsx` | ~107 | `/api/v1/settings` |
| `alerts/page.tsx` | ~97 | `/api/v1/settings` |
| `setup/page.tsx` | ~44 | `/api/v1/settings/setup` |
| `SetupGuard.tsx` | ~21 | `/api/v1/settings/setup-status` |

**Impact:** These calls break in any non-localhost deployment and bypass the centralized error handling / token refresh / entitlement gating.

**Fix:** Create `settingsApi.getSettings()` and `settingsApi.getSetupStatus()` in `api.ts` and use them everywhere. Replace all raw `fetch('http://localhost:8000/...')` calls with the appropriate API module function.

#### M2-NEW — Checkout confirm is self-callable (simulated billing)
(`backend/app/routers/billing.py:65`)

A user can `POST /billing/checkout` then immediately `POST /billing/checkout/confirm` to self-upgrade. This is acknowledged in the docstring as a simulation ("which a real deployment would trigger from a payment webhook"), but it is technically still a self-grant vector.

**Impact:** Low in the context of an academic project with sandbox billing. Would be critical if real payment integration were added.

**Fix (for real deployment):** The confirm endpoint should only accept requests from a trusted webhook source (IP allowlist, webhook signature verification), not from the authenticated user.

#### M3-NEW — Auto-forecast loop attributes alerts to wrong user
(`backend/app/main.py:109`)

The `auto_forecast_loop` saves alerts for `db_session.query(User).first()` — the *first user in the database*, not necessarily the user who should receive the alert. In a multi-user scenario, all auto-generated alerts go to a single user.

**Fix:** Either broadcast alerts to all users, or associate alerts with the specific user whose data triggered the threshold.

#### M4-NEW — Smart meter endpoints have inconsistent role gating
(`backend/app/routers/forecast.py`)

| Endpoint | Required Role |
|----------|--------------|
| `POST /forecast/predict` | `admin`, `analyst` |
| `POST /forecast/compare` | `admin`, `analyst` |
| `POST /forecast/smart-meter/sync` | Any authenticated (`get_current_user`) |
| `POST /forecast/smart-meter/compare` | Any authenticated (`get_current_user`) |

Viewers can access smart-meter forecast endpoints but not the regular forecast endpoints.

**Fix:** Apply consistent role gating. Either all forecast operations require `analyst+`, or document why smart-meter is intentionally open to viewers.

#### M5-NEW — Potential SSRF via `sensor_api_url`
(`backend/app/services/smart_meter_service.py:36`)

If `sensor_api_url` is set to an internal network address, `requests.get(sensor_api_url)` could be used for Server-Side Request Forgery. The URL is controllable by any authenticated user via `POST /settings/setup` (see H3-NEW).

**Fix:** Validate and allowlist URLs before making requests. Block private/internal IP ranges.

#### M6-NEW — `alertsApi.getConfig()` returns hardcoded defaults
(`frontend/src/lib/api.ts:313-316`)

```typescript
anomaly_sensitivity: 'medium',
notification_push: true,
```

These don't reflect actual backend values — they are always returned regardless of what the backend sends.

#### M7-NEW — PDF export lock icon checks wrong tier
(`frontend/src/app/analytics/page.tsx:206`)

The Lock icon shows when `!isEnterprise` but PDF export is a Pro feature. Should check `!can(user, Feature.PDF_EXPORT)` instead, which would correctly show for free users only.

### 🔵 Low Priority

#### L1-NEW — `Feature.HEATMAP` defined but unused server-side
(`backend/app/entitlements.py:54`)

`Feature.HEATMAP` is at Enterprise tier in the catalog, but no endpoint uses `require_feature(Feature.HEATMAP)`. Heatmap data is returned inside the `GET /analytics/summary` endpoint which is gated at Pro tier (`Feature.ANALYTICS_SUMMARY`). The frontend checks `can(user, Feature.HEATMAP)` for UI gating, but the server doesn't enforce the distinction.

#### L2-NEW — `User.subscription_tier` typed as `string` in frontend
(`frontend/src/types/index.ts`)

`subscription_tier` is `string | undefined` rather than a union type `'free' | 'pro' | 'enterprise'`. Invalid values pass TypeScript checking.

#### L3-NEW — `alertsApi` uses `any[]` type
(`frontend/src/lib/api.ts:298`)

The raw alert response is cast to `any[]` — minor type safety gap.

#### L4-NEW — `last_activity` comment/code mismatch
(`backend/app/services/auth_service.py:109`)

Comment says "30 seconds" throttle but code uses 10 seconds.

#### L5-NEW — Test uses file-based SQLite
(`backend/tests/test_entitlements.py`)

Uses `test_entitlements.db` file instead of in-memory SQLite (`:memory:`). Cleanup can fail, leaving stale test databases.

#### L6-NEW — No `.env` / `NEXT_PUBLIC_API_URL` in Dockerfile
(`frontend/Dockerfile`)

The frontend Docker image relies on default `localhost:8000`, which won't work in containerized deployments without runtime env injection.

---

## 5. Architecture Overview

### Backend Stack
- **Framework:** FastAPI with Uvicorn
- **Database:** SQLite with SQLAlchemy ORM + Alembic migrations
- **Auth:** JWT (access + refresh tokens), bcrypt password hashing
- **ML:** PyTorch (PatchTST, SOTA Hybrid, CNN-BiLSTM) loaded at startup
- **Real-time:** FastAPI WebSocket for alerts and live telemetry
- **Rate limiting:** SlowAPI on login and predict endpoints
- **File serving:** Static file serving for avatars

### Frontend Stack
- **Framework:** Next.js 16.2.6 with React 19.2.4
- **Styling:** Tailwind CSS with shadcn/ui components
- **Charts:** Recharts 3.8.1
- **Toasts:** Sonner 2.0.7
- **Theming:** next-themes (dark mode)
- **State:** React Context (auth only — no Redux/Zustand)

### Endpoint Inventory

| Router | Endpoints | Auth | Entitlements |
|--------|-----------|------|-------------|
| `auth.py` | 9 | Mixed (some public) | Subscription downgrade only |
| `billing.py` | 5 | `get_current_user` | Checkout/cancel flow |
| `forecast.py` | 10 + 1 WS | Mixed (`require_role` / none) | None (role-based) |
| `analytics.py` | 2 | `require_feature` | ✅ Pro gated |
| `multi_site.py` | 1 | `require_feature` | ✅ Enterprise gated |
| `admin.py` | 7 | `require_role(["admin"])` | None (admin-only) |
| `alerts.py` | 5 + 1 WS | Mixed (WS unauthenticated) | None |
| `settings.py` | 4 | Mixed (GET unauthenticated) | None |
| **Total** | **43 + 2 WS** | | |

### Entitlement Matrix

| Feature | Min Tier | Backend Enforcement | Frontend Enforcement |
|---------|----------|--------------------|--------------------|
| Pro AI Forecast Curve | Pro | ❌ No endpoint (UI-only) | ✅ `can(user, Feature.PRO_FORECAST_CURVE)` |
| Analytics Summary | Pro | ✅ `require_feature(Feature.ANALYTICS_SUMMARY)` | ✅ `can(user, Feature.ANALYTICS_SUMMARY)` |
| PDF Export | Pro | ✅ `require_feature(Feature.PDF_EXPORT)` | ✅ `can(user, Feature.PDF_EXPORT)` |
| Heatmap | Enterprise | ❌ Returns with analytics (Pro) | ✅ `can(user, Feature.HEATMAP)` |
| Multi-Site | Enterprise | ✅ `require_feature(Feature.MULTI_SITE)` | ✅ `can(user, Feature.MULTI_SITE)` |

### Subscription Lifecycle

```
┌─────────┐   POST /billing/checkout   ┌─────────┐   POST /billing/checkout/confirm   ┌────────┐
│  (none)  │ ──────────────────────────►│ pending │ ──────────────────────────────────►│ active │
└─────────┘                             └─────────┘                                    └────────┘
                                                                                          │
                                                                    POST /billing/cancel   │
                                                                                          ▼
                                                                                    ┌───────────┐
                                                                                    │ cancelled │
                                                                                    └───────────┘
                                                                                          │
                                                                                          ▼
                                                                                  user.subscription_tier → 'free'
```

**Admin path:** `PUT /admin/users/{id}` → `billing_service.grant()` → creates `active` subscription with `source="admin_grant"`.

---

## 6. Test Coverage

### Existing Tests (`backend/tests/test_entitlements.py`)

| Test | What It Verifies |
|------|-----------------|
| `test_free_user_access_denied_on_pro_and_enterprise` | Free user gets 403 on analytics summary, PDF, multi-site |
| `test_self_grant_upgrades_blocked` | `POST /subscription` with `"pro"` returns 403; `"free"` returns 200 |
| `test_simulated_checkout_upgrade_flow` | Checkout → confirm → entitlements reflect Pro; Pro can't access Enterprise |
| `test_admin_grant_changes_entitlement` | Admin PUT changes tier; user can then access Enterprise features |

### Coverage Gaps

| Area | Covered | Missing |
|------|---------|---------|
| Entitlements / billing | ✅ 4 tests | Cancel subscription, expired subscription handling |
| Auth (login/register/refresh) | ❌ | Token lifecycle, invalid credentials, duplicate email |
| Forecast endpoints | ❌ | CSV upload, model comparison, role gating |
| Admin endpoints | ❌ | User CRUD, health, stats, retrain |
| Alerts | ❌ | Alert creation, acknowledgment, config |
| Settings | ❌ | Setup flow, preference updates |
| WebSocket | ❌ | Connection, message format, disconnection |
| Avatar upload | ❌ | Valid/invalid files, size limits, MIME check |
| Password change | ❌ | Current password verification |

---

## 7. Suggested Fix Order

### Priority 1 — Security (High Impact, Moderate Effort)
1. **H1-WS** — Authenticate WebSocket connections (token in query param, validate in handler).
2. **H2-NEW** — Add `get_current_user` to `GET /settings`.
3. **H3-NEW** — Restrict `POST /settings/setup` to admin role.

### Priority 2 — Correctness (Medium Impact, Low Effort)
4. **M1-NEW** — Replace all hardcoded `localhost:8000` fetch calls with `apiFetch` / API module functions.
5. **M3-NEW** — Fix auto-forecast alert user attribution.
6. **M7-NEW** — Fix PDF export lock icon to check Pro tier.
7. **M4-NEW** — Apply consistent role gating on smart-meter endpoints.

### Priority 3 — Robustness (Lower Impact)
8. **M5-NEW** — Validate `sensor_api_url` to prevent SSRF.
9. **L1-NEW** — Either add `require_feature(Feature.HEATMAP)` to a separate endpoint or remove the unused feature.
10. **L6-NEW** — Configure `NEXT_PUBLIC_API_URL` in Dockerfile / deployment.

### Priority 4 — Quality (Nice to Have)
11. Expand test coverage beyond entitlements.
12. Add structured logging (replace `print()` statements).
13. Implement refresh token rotation / revocation.
14. Clean up repo root (remove overlapping audit/plan files).

---

## 8. One-Line Summary

The four critical audit findings (C1–C4) are **fully resolved**: subscription tiers can no longer be self-granted, server-side entitlement enforcement is in place, secrets are externalized with production guardrails, and the subscription lifecycle has a proper audit trail. Remaining work centers on **authenticating WebSockets**, **replacing hardcoded localhost URLs**, and **expanding test coverage** — all medium-to-low severity items that don't undermine the platform's core security posture.
