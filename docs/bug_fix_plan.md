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
| `f477297` | M1: Integrate real database forecast records into backend analytics router and align schema keys with frontend charts |
| `cb027f5` | M7: Apply rate limiting to login, predict, and predict_upload endpoints using a shared SlowAPI Limiter |
| `4591d53` | M8: Compute estimated 24h cost using time-of-use tariffs (peak/off-peak rates based on hour of the day) rather than a flat rate |
| `f1e3bd9` | L1: Implement drag-and-drop event handlers for file upload zone on forecaster page |
| `063c338` | L2: Add profile page mapping to navbar pageTitles and pageDescriptions |
| `28493fa` | L3: Lift sidebar collapsed state to AppLayout and adjust content area margin dynamically |
| `507b42d` | L4: Remove unused and dead ModelRegistry database table class and imports |
| `773781e` | L7: Explicitly list bcrypt as a backend dependency in requirements.txt |
| `2885de9` | L8: Remove deprecated version key from docker-compose.yml |
| `7fbd464` | L10: Display user-friendly model display_name instead of internal name during loading and configuration |

---

## 🔴 HIGH — Must Fix

All high priority bugs have been resolved and verified!

---

## 🟡 MEDIUM — Should Fix

All medium priority bugs have been resolved and verified!

## 🔵 LOW — Nice to Fix

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
