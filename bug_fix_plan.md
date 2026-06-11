# PFE2 Bug Fix Plan — Full Audit (June 11, 2026)

This document catalogs every known bug in the energy forecast platform, organized by severity. Use this as a checklist to fix remaining issues.

---

## Previously Fixed ✅

These bugs have been resolved in prior commits:

| Commit | Fix |
|--------|-----|
| `04472f2` | Forecast metrics grid layout → `md:grid-cols-4` + "Demo Data" badges on analytics |
| `ba76653` | Analytics R² Score charts + backend key mapping |
| `483d6ed` | Real R² scores in admin model registry |
| `0cdfeb3` | Deterministic baseline forecast generation (seeded PRNG) |
| `2cf6f3d` | Fake "actual" chart line replaced with real historical `input_data` + deterministic analytics demo data |
| `aa95e8f` | Chart H0 bridge gap fix, full 96h lookback display, CSV upload endpoints (`/predict/upload`, `/compare/upload`), Docker HMR with volume mounts |

---

## 🔴 HIGH — Must Fix

### H1. File upload endpoints bypass token refresh
- **Files**: [api.ts](file:///c:/Users/salah/Documents/MASTER/PFE2/frontend/src/lib/api.ts#L188-L195), [api.ts](file:///c:/Users/salah/Documents/MASTER/PFE2/frontend/src/lib/api.ts#L211-L218)
- **Problem**: The `/predict/upload` and `/compare/upload` calls use raw `fetch()` instead of `apiFetch()`. This means they have **no automatic token refresh on 401**. If the user's access token expires while on the forecast page, CSV uploads silently fail with "Prediction failed" — no retry, no refresh, no useful error message.
- **Fix**: Wrap the upload fetch calls with the same 401-retry logic that `apiFetch` uses: catch 401 → call `/auth/refresh` → retry with new token. Also parse `response.json().detail` for meaningful error messages instead of the generic "Prediction failed".

---

### H2. Settings page resets alert threshold to 3.0
- **File**: [settings/page.tsx](file:///c:/Users/salah/Documents/MASTER/PFE2/frontend/src/app/settings/page.tsx#L79-L84)
- **Problem**: `handleSavePreferences` always sends `high_consumption_threshold: 3.0` and `anomaly_sensitivity: 'medium'`, ignoring whatever the user previously configured on the Alerts page. Saving preferences **overwrites** the user's custom threshold.
- **Fix**: Either (a) load the current threshold from the API on mount and preserve it in state, or (b) don't send `high_consumption_threshold` / `anomaly_sensitivity` from the settings page at all — let the Alerts page be the sole owner of those fields.

---

### H3. Type definitions completely out of sync with API
- **File**: [types/index.ts](file:///c:/Users/salah/Documents/MASTER/PFE2/frontend/src/types/index.ts)
- **Problem**: Multiple type interfaces don't match actual API responses:
  - `ForecastResult` (L66-73): defines `predictions` as `ForecastPoint[]` but API returns `number[][]`
  - `SampleDataset` (L91-97): defines `id, rows, columns` but API returns `name, description, season, date_range`
  - `AnalyticsSummary` (L102-111): defines `active_alerts, avg_accuracy` but API returns `unacknowledged_alerts, avg_peak_power, models_used`
  - `SystemHealth` (L171-178): defines `uptime: string` but API returns `uptime_seconds: number`
  - `ModelRegistry` (L161-169): missing `display_name, description, architecture_type, training_metrics`
- **Impact**: Pages use `as unknown as Record<string, unknown>` and `(model as any)` casts everywhere to bypass broken types. Any future developer using these types will write broken code.
- **Fix**: Rewrite all interfaces to match the actual backend response schemas. Remove all `as any` casts from pages.

---

### H4. ModelInfo schema drops critical fields
- **File**: [schemas.py](file:///c:/Users/salah/Documents/MASTER/PFE2/backend/app/schemas/schemas.py#L107-L113)
- **Problem**: `ModelInfo` Pydantic model only includes `name, display_name, architecture_type, description, training_metrics, is_active`. But `get_available_models()` returns additional fields: `id, version, accuracy, last_trained, parameters, status`. Pydantic's `response_model=List[ModelInfo]` **silently strips** these fields from the API response, so the frontend never receives them.
- **Fix**: Add the missing fields (`id`, `version`, `accuracy`, `last_trained`, `parameters`, `status`) to the `ModelInfo` schema.

---

### H5. `/predict/upload` returns inconsistent response format
- **File**: [forecast.py](file:///c:/Users/salah/Documents/MASTER/PFE2/backend/app/routers/forecast.py#L296-L304)
- **Problem**: `/predict` uses `response_model=ForecastResponse` (Pydantic serialization with proper ISO datetime), but `/predict/upload` returns a raw dict with `str(forecast.created_at)` — different datetime format. Frontend code that expects ISO 8601 may break on the upload response.
- **Fix**: Use `response_model=ForecastResponse` on `/predict/upload` too, or at minimum serialize `created_at` with `.isoformat()`.

---

## 🟡 MEDIUM — Should Fix

### M1. Analytics data is mostly hardcoded
- **Files**: [analytics.py](file:///c:/Users/salah/Documents/MASTER/PFE2/backend/app/routers/analytics.py#L103-L181), [analytics/page.tsx](file:///c:/Users/salah/Documents/MASTER/PFE2/frontend/src/app/analytics/page.tsx#L76-L135)
- **Problem**: 6 out of 8 analytics chart sections are hardcoded/formula-generated: `consumption_trend`, `weekly_consumption`, `consumption_by_hour`, `monthly_accuracy`, `model_performance`, `heatmap_data`. Only summary cards (total_forecasts, alerts, avg_peak_power) use real data. The frontend also has its own set of hardcoded demo data.
- **Impact**: The analytics page mostly shows fabricated data. The "Demo Data" badges help, but the underlying issue remains.
- **Fix**: Derive chart data from real `Forecast` records in the database. If insufficient data, keep the demo fallback with badges.

---

### M2. Admin CPU/Memory bars are hardcoded
- **File**: [admin/page.tsx](file:///c:/Users/salah/Documents/MASTER/PFE2/frontend/src/app/admin/page.tsx#L283-L288)
- **Problem**: CPU usage shows a fixed `23%` and Memory shows `48%`. The backend returns `cpu_usage` and `memory_usage` in the `SystemHealth` response, but the frontend ignores them and uses hardcoded values.
- **Fix**: Read `health.cpu_usage` and `health.memory_usage` from the API response. Backend should also use `psutil` or similar to return real values (if it doesn't already).

---

### M3. Alert notification checkboxes are uncontrolled
- **File**: [alerts/page.tsx](file:///c:/Users/salah/Documents/MASTER/PFE2/frontend/src/app/alerts/page.tsx#L341-L358)
- **Problem**: Notification toggle checkboxes use `defaultChecked` (uncontrolled React inputs). They don't bind to state and aren't included in the `handleSaveConfig` payload. Saving config always sends `notification_email: true, notification_push: true` regardless of checkbox state.
- **Fix**: Convert to controlled inputs with `useState` and wire them into the save payload.

---

### M4. Potential crash if model lacks `training_metrics`
- **File**: [forecast/page.tsx](file:///c:/Users/salah/Documents/MASTER/PFE2/frontend/src/app/forecast/page.tsx#L329)
- **Problem**: `model.training_metrics.mae.toFixed(3)` throws `Cannot read properties of undefined` if the API returns a model without `training_metrics`. The ModelInfo schema might strip this field (see H4).
- **Fix**: Add optional chaining: `model.training_metrics?.mae?.toFixed(3) ?? 'N/A'`.

---

### M5. PDF download bypasses token refresh
- **File**: [analytics/page.tsx](file:///c:/Users/salah/Documents/MASTER/PFE2/frontend/src/app/analytics/page.tsx#L164-L191)
- **Problem**: PDF download uses raw `fetch()` with manual token header, same as the upload endpoints — no 401 refresh.
- **Fix**: Add 401-retry logic or use a shared fetch wrapper.

---

### M6. Dashboard chart has no "Demo Data" badge
- **File**: [dashboard/page.tsx](file:///c:/Users/salah/Documents/MASTER/PFE2/frontend/src/app/dashboard/page.tsx#L217-L239)
- **Problem**: The consumption trend chart falls back to `defaultChartData` (hardcoded) when no real data is available. Unlike the analytics page, it shows **no visual indicator** that the data is demo/synthetic.
- **Fix**: Add a "Demo Data" badge (same style as analytics) when using fallback data.

---

### M7. Rate limiting configured but never applied
- **Files**: [config.py](file:///c:/Users/salah/Documents/MASTER/PFE2/backend/app/config.py#L30), [main.py](file:///c:/Users/salah/Documents/MASTER/PFE2/backend/app/main.py#L26)
- **Problem**: `RATE_LIMIT = "10/minute"` is defined in config and `limiter` is set up in `main.py`, but no `@limiter.limit()` decorators are used on any route. Rate limiting is effectively **disabled**.
- **Fix**: Apply `@limiter.limit(settings.RATE_LIMIT)` to sensitive endpoints like `/auth/login`, `/forecast/predict`, `/forecast/predict/upload`.

---

### M8. Cost alert uses peak tariff for all hours
- **File**: [forecast_service.py](file:///c:/Users/salah/Documents/MASTER/PFE2/backend/app/services/forecast_service.py#L344)
- **Problem**: `estimated_cost = total_kwh * EDF_TARIFFS['heures_pleines']` applies the peak tariff to all 24 hours. Off-peak hours (22h-6h) should use the `heures_creuses` rate.
- **Fix**: Split the 24 prediction hours into peak/off-peak buckets and apply the appropriate tariff.

---

## 🔵 LOW — Nice to Fix

### L1. "Drag & drop" text with no drag handler
- **File**: [forecast/page.tsx](file:///c:/Users/salah/Documents/MASTER/PFE2/frontend/src/app/forecast/page.tsx#L357)
- **Problem**: Upload area says "Drag & drop or click to browse" but has no `onDragOver`/`onDrop` handlers.
- **Fix**: Add drag-and-drop event handlers, or change the text to "Click to browse".

---

### L2. Missing `/profile` page title in navbar
- **File**: [navbar.tsx](file:///c:/Users/salah/Documents/MASTER/PFE2/frontend/src/components/navbar.tsx#L22-L29)
- **Problem**: `pageTitles` map doesn't include `/profile`, so the navbar shows "EnergyAI" instead of "Profile".
- **Fix**: Add `'/profile': 'Profile'` to the `pageTitles` object.

---

### L3. Sidebar collapse doesn't adjust content area
- **File**: [app-layout.tsx](file:///c:/Users/salah/Documents/MASTER/PFE2/frontend/src/components/app-layout.tsx#L40)
- **Problem**: Main content has `ml-[260px]` hardcoded. When sidebar collapses to 72px, the content area doesn't shift — leaving a large gap.
- **Fix**: Share sidebar collapsed state via context or CSS variable, and dynamically adjust the margin.

---

### L4. `ModelRegistry` DB table is dead code
- **File**: [models.py](file:///c:/Users/salah/Documents/MASTER/PFE2/backend/app/models/models.py#L81-L93)
- **Problem**: Table is defined but never populated or queried. Admin router imports it but never uses it. Model metadata is hardcoded in `forecast_service.py`.
- **Fix**: Either populate it and use it as the source of truth for model metadata, or remove the dead code.

---

### L5. Hardcoded admin password & JWT secret
- **Files**: [main.py](file:///c:/Users/salah/Documents/MASTER/PFE2/backend/app/main.py#L85), [config.py](file:///c:/Users/salah/Documents/MASTER/PFE2/backend/app/config.py#L18), [docker-compose.yml](file:///c:/Users/salah/Documents/MASTER/PFE2/docker-compose.yml#L32)
- **Problem**: Default admin password is `admin123`, JWT secret is `super-secret-key-change-in-production`, DB password is `pfe_password`.
- **Fix**: Use strong random values and document that these must be changed in production. Add a `.env.example`.

---

### L6. Manual DB migration logic is fragile
- **File**: [main.py](file:///c:/Users/salah/Documents/MASTER/PFE2/backend/app/main.py#L44-L69)
- **Problem**: Raw SQL `ALTER TABLE` runs on every startup with exceptions silently caught. Should use Alembic migrations (already in `requirements.txt`).
- **Fix**: Create proper Alembic migration scripts for `avatar_url` and `last_activity` columns.

---

### L7. `bcrypt` not explicitly listed in requirements
- **File**: [requirements.txt](file:///c:/Users/salah/Documents/MASTER/PFE2/backend/requirements.txt)
- **Problem**: `bcrypt` is imported directly in `auth_service.py` but not in requirements. It's an implicit dependency through `passlib[bcrypt]`.
- **Fix**: Add `bcrypt>=4.0.0` to `requirements.txt`.

---

### L8. `docker-compose.yml` uses deprecated `version` key
- **File**: [docker-compose.yml](file:///c:/Users/salah/Documents/MASTER/PFE2/docker-compose.yml#L1)
- **Problem**: `version: '3.8'` is deprecated in Docker Compose V2 and generates a warning.
- **Fix**: Remove the `version` line entirely.

---

### L9. `active_models` hardcoded to 3 in SystemHealth
- **File**: [admin.py](file:///c:/Users/salah/Documents/MASTER/PFE2/backend/app/routers/admin.py#L92)
- **Problem**: `active_models=3` is hardcoded in `SystemHealth` response.
- **Fix**: Compute dynamically: `active_models=len(get_forecast_service().models)`.

---

### L10. Loading text shows internal model name
- **File**: [forecast/page.tsx](file:///c:/Users/salah/Documents/MASTER/PFE2/frontend/src/app/forecast/page.tsx#L817)
- **Problem**: Shows `currentModel?.name` (e.g., "patchtst") instead of `display_name` (e.g., "PatchTST (Pure Transformer)").
- **Fix**: Use `currentModel?.display_name || currentModel?.name`.

---

## Recommended Fix Order

> [!TIP]
> Fix in this order to maximize impact with minimal risk:

1. **H1** — Token refresh on file uploads (prevents silent failures)
2. **H2** — Settings threshold reset (prevents data loss)
3. **H4 + H5** — Schema fixes (backend, low risk)
4. **H3** — Type definitions (frontend, no runtime impact)
5. **M4** — Optional chaining crash guard (1-line fix)
6. **M3** — Alert notification checkboxes (small UI fix)
7. **M6** — Dashboard demo badge (cosmetic consistency)
8. **L1-L3** — Quick cosmetic fixes (drag-drop, profile title, sidebar)
9. **M1, M2** — Analytics real data + admin CPU (larger effort, lower priority)
10. **L4-L10** — Cleanup and hardening
