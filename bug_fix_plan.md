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
| `8aa38e6` | H1: Add token refresh to file uploads; H2: Preserve alert threshold in settings |
| `d80f474` | H3: Sync frontend type interfaces with backend schemas |
| `956aa4d` | H4/H5: Add missing fields to ModelInfo schema and standardize predict/upload response model |
| `f586fc9` | M2: Replace hardcoded CPU/Memory bars in Admin page with live system stats using psutil |
| `004dd83` | M3: Make alert notification checkboxes controlled React inputs and wire them to save payload |
| `7988179` | M4: Guard against potential crash if model lacks training_metrics on forecast page |
| `fdd44aa` | M5: Update PDF download to use apiFetch with automatic token refresh support |
| `6d7bd9d` | M6: Add Demo Data badge to dashboard consumption trend chart when using fallback data |
| `cb027f5` | M7: Apply rate limiting to login, predict, and predict_upload endpoints using a shared SlowAPI Limiter |
| `4591d53` | M8: Compute estimated 24h cost using time-of-use tariffs (peak/off-peak rates based on hour of the day) rather than a flat rate |

---

## 🔴 HIGH — Must Fix

All high priority bugs have been resolved and verified!

---

## 🟡 MEDIUM — Should Fix

### M1. Analytics data is mostly hardcoded
- **Files**: [analytics.py](file:///c:/Users/salah/Documents/MASTER/PFE2/backend/app/routers/analytics.py#L103-L181), [analytics/page.tsx](file:///c:/Users/salah/Documents/MASTER/PFE2/frontend/src/app/analytics/page.tsx#L76-L135)
- **Problem**: 6 out of 8 analytics chart sections are hardcoded/formula-generated: `consumption_trend`, `weekly_consumption`, `consumption_by_hour`, `monthly_accuracy`, `model_performance`, `heatmap_data`. Only summary cards (total_forecasts, alerts, avg_peak_power) use real data. The frontend also has its own set of hardcoded demo data.
- **Impact**: The analytics page mostly shows fabricated data. The "Demo Data" badges help, but the underlying issue remains.
- **Fix**: Derive chart data from real `Forecast` records in the database. If insufficient data, keep the demo fallback with badges.

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
