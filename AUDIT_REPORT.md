# Energy Forecast Platform — Technical Audit

**Date:** 2026-06-18
**Scope:** FastAPI backend (`backend/`), Next.js frontend (`frontend/`), ML service, and the academic DEPM replication artifacts.
**Verdict:** The platform is feature-rich and demos well, but the "commercial SaaS" framing is undermined by **client-trusted authorization**. Several security and correctness issues should be fixed before it is presented as production-grade.

---

## 1. What Was Done Well

- **Clean layered backend.** Routers / services / models / schemas are well separated. `get_db`, `get_current_user`, and `require_role` dependencies are used consistently.
- **Solid auth primitives.** Direct `bcrypt` hashing, short-lived access tokens (15 min) + refresh tokens (7 days), token-type checks (`access` vs `refresh`), and a frontend fetch wrapper with transparent 401-refresh-retry.
- **Real ML serving.** Three architectures (PatchTST, SOTA hybrid, CNN-BiLSTM) loaded with `weights_only=True`, CPU inference, RevIN handled internally, and a separate scaler path for CNN-BiLSTM. Calendar features are derived correctly from the datetime index.
- **Intellectually honest core.** The PFE thesis (data leakage from `Global_intensity`, the `precision = acc - 0.01` fabricated-metric pattern) is the strongest part of the project and is reflected in the replication notebooks.
- **Good defensive details.** Avatar upload validates extension + MIME + 2 MB size and cleans up old files; rate limiting via SlowAPI on login/predict; `last_activity` writes are throttled to ~10 s.
- **Prior bug debt was tracked and largely closed** (see `bug_fix_plan.md`).

---

## 2. Critical Issues (fix before any "SaaS" claim)

### C1 — Users can grant themselves any subscription tier (broken access control)
`PUT /api/v1/auth/me` (`backend/app/routers/auth.py`, `update_me`) accepts and writes `subscription_tier` directly from the request body. The frontend openly calls this on the setup, plans, and settings pages (`authApi.updateProfile({ subscription_tier })`).

**Impact:** Every paywalled feature (Pro AI forecast curve, Enterprise multi-site, PDF export, heatmaps) is free. The entire commercial gating story is bypassable with a single API call. This is the single most important finding.

**Fix:** Remove `subscription_tier` from the self-service `UserUpdateMe` path. Tier changes must go through an admin endpoint or a real payment/entitlement flow.

### C2 — Authorization is enforced primarily in the UI
Gating logic lives in React (`user?.subscription_tier === 'enterprise'`, blur overlays, hidden menu items). Most data endpoints only require `get_current_user`:
- `/api/v1/analytics/summary` and `/api/v1/analytics/report/pdf` have **no tier check** — any logged-in user can pull heatmap/analytics data and generate the "Enterprise" PDF.
- `/api/v1/multi-site` does check tier, but returns `200` with `{"error": ...}` instead of `403`, so it is inconsistent with the rest of the API.

**Fix:** Enforce tier/role server-side on every gated endpoint with a dependency (mirror `require_role`, add `require_tier`). Treat the UI as cosmetic only.

### C3 — Hardcoded secrets and default admin credentials
`backend/app/config.py` ships `JWT_SECRET_KEY="dev-secret-key-for-local-testing-only"` and `ADMIN_PASSWORD="admin123"`, and `main.py` auto-seeds an admin with them. With a known JWT secret, anyone can forge valid tokens for any user/role.

**Fix:** Require these from the environment with no insecure default (fail fast if unset in non-debug mode). Force admin password rotation on first login. This was logged as L5 but never resolved.

### C4 — Open / unauthenticated WebSockets
- `/api/v1/alerts/ws/{client_id}` accepts **any** `client_id` with no token, and `broadcast_global` in the auto-forecast loop pushes alerts to all connected sockets regardless of ownership.
- `/api/v1/forecast/smart-meter/live-ws` accepts connections with no auth at all and runs model inference + DB writes on a 2 s loop per client.

**Impact:** Cross-user alert leakage and an unauthenticated, resource-amplifying endpoint (DoS via many sockets, each triggering inference every 2 s).

**Fix:** Authenticate WebSocket connections (token in query/subprotocol), bind `client_id` to the authenticated user, and rate-limit the live stream.

---

## 3. High-Priority Correctness Bugs

### H1 — PDF cost calculation indexes by forecast step, not actual hour
In `analytics.py` `export_pdf_report`, peak/off-peak classification uses `h_idx` (0..23 forecast step) as if it were the wall-clock hour:
```python
is_peak = peak_start <= h_idx < peak_end ...
```
The forecast does not start at midnight, so the tariff window is misaligned. The forecast-service `_check_alerts` does this correctly using `(start_hour + i) % 24`; the PDF path should reuse that logic.

### H2 — `Forecast` never stores its start hour
`Forecast` has `input_start`/`input_end` columns but `predict` never populates them. Any later cost/tariff computation from history (PDF, analytics) cannot know the true hour-of-day alignment, which is the root cause of H1 and the `i % 4`/`f.id % 7` pseudo-data in analytics.

### H3 — Analytics fabricates "actual" values
`analytics.py` derives `actual_val = pred_val * (1.0 + (i % 5 - 2) * 0.02)` and `actual += pred_sum * (1 + (f.id % 7 - 3)*0.01)`. These are presented as real historical actuals/savings. For an academic project whose thesis is *"the original paper fabricated metrics,"* shipping synthetic "actuals" without a "Demo Data" label is a credibility risk. Some charts label demo data; this one does not.

### H4 — `retrain_model` mutates production weights and metrics from noise
The retrain loop trains on `meter_service.fetch_live_readings()` (simulated) and **`calendar_dummy = torch.randn(...)`**, then overwrites the real `.pth` files on disk and bumps `r2_score` by `+0.0035` as "proof of learning." This permanently degrades the served models and inflates reported accuracy.

**Fix:** Train on held-out real data or gate retraining behind a non-destructive sandbox; never persist over the canonical weights from random-calendar batches.

### H5 — `predict_upload` / smart-meter calendar may not match training convention
`predict_upload` builds `month_sin = sin(2π·month/12)` with `month` in 1..12, while the smart-meter path uses `month - 1` (0..11), and `_load_samples` uses raw `df.index.month` (1..12). The month encoding is inconsistent across the three input paths, so identical data through different routes can yield different predictions.

---

## 4. Medium-Priority Issues

- **M1 — Global `SystemSettings` for a multi-tenant app.** `settings.first()` is used everywhere, so all users share one country/tariff/sensor config. `is_setup_complete` is tracked both per-user and globally, and `register` marks the *global* settings complete, which can skip the setup wizard for later users. Tariffs/regions should be per-user (or per-org).
- **M2 — `GET /api/v1/settings` is unauthenticated** and returns the global settings object directly (leaks provider/tariff config and the raw ORM row).
- **M3 — Refresh tokens are non-revocable.** No denylist/rotation; a leaked refresh token is valid for 7 days. Logout only clears `localStorage`.
- **M4 — Tokens in `localStorage`.** Vulnerable to XSS exfiltration. Consider httpOnly cookies for refresh tokens.
- **M5 — `last_activity` write on every authenticated request** still commits inside `get_current_user`; under load this is a write per ~10 s per active user on SQLite (single-writer), a contention bottleneck.
- **M6 — CORS hardcodes localhost origins** in `main.py` alongside `FRONTEND_URL`; `allow_credentials=True` with broad methods/headers. Tighten for any deployment.
- **M7 — `SetupGuard` hardcodes `http://localhost:8000`** instead of `NEXT_PUBLIC_API_URL`, so it breaks in any non-local deployment (the rest of the app uses the env var).
- **M8 — Bare/duplicated DB-write blocks** in the auto-forecast loop and WS handlers open `SessionLocal()` manually with broad `except`; errors are swallowed and only printed.

---

## 5. Low-Priority / Cleanup

- **L1 — Repo hygiene.** Committed SQLite DB (`backend/energy_forecast.db`), `rewrite_git.sh`, multiple overlapping audit/plan files (`pfe_full_audit.md`, `pfe_final_audit_report.md`, `bug_fix_plan.md`, several `presentation_plan*`), and `scratch/`, `investigations/` clutter the root.
- **L2 — Three parallel app entry points** (`app/`, `app_forecast/` Streamlit, `backend/`) with duplicated model/sample logic. Samples are loaded from `app_forecast/samples` via a `../` parent-dir traversal, which is brittle.
- **L3 — `datetime.utcnow()`** used in `_check_alerts` fallback (deprecated; rest of the code correctly uses `datetime.now(timezone.utc)`).
- **L4 — Magic numbers.** Alert thresholds (`4.0` kW auto-loop, `> 10.0` MAD cost) and the `auto_forecast_loop` random simulation are hardcoded in `main.py`.
- **L5 — `print()`-based logging** throughout; no structured logging or log levels.
- **L6 — No automated tests.** Only `test_jwt.py`; no router/service test coverage despite many edge cases (CSV shapes, tariff wrap-around, RBAC).
- **L7 — Migrations + `create_all` both run on startup**, plus an `add_columns.py` script — three overlapping schema-management mechanisms.

---

## 6. Suggested Fix Order

1. **C3** — externalize JWT secret + admin password (fastest, highest risk reduction).
2. **C1** — remove self-service `subscription_tier` upgrades.
3. **C2** — add a `require_tier` dependency and enforce on analytics, PDF, multi-site.
4. **C4** — authenticate WebSockets and scope alerts per user.
5. **H4** — stop overwriting real weights from random-calendar training.
6. **H1 + H2** — persist forecast start hour and fix PDF tariff alignment.
7. **H3 / H5** — label synthetic analytics data; unify calendar/month encoding.
8. **M1–M3** — per-user settings, auth on `GET /settings`, refresh-token rotation.
9. **L1–L7** — repo cleanup, logging, tests.

---

## 7. One-Line Summary

A genuinely impressive, honest academic replication wrapped in a polished dashboard — but the "commercial SaaS" layer is **authorization theater**: tiers are self-assignable, gated data is reachable without entitlement checks, the JWT secret is public, and the "retraining" feature actively corrupts the served models. Fix C1–C4 and H4 first.
