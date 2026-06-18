# Subscription Tiers & Entitlements — Implementation Plan

**Date:** 2026-06-18
**Addresses audit findings:** C1 (self-service tier upgrades), C2 (UI-only authorization),
and the `multi-site` `200`-with-error inconsistency.

## Goal

Replace the "self-assign any tier" demo behavior with a real entitlement model:
a single source of truth for what each tier unlocks, server-side enforcement on every
gated endpoint, and a controlled path for tier changes (admin grant + a simulated-but-honest
billing flow), instead of scattered `subscription_tier === 'enterprise'` checks in React
and a one-line self-grant in `auth.py`.

## Design principles

The current problems: (1) tiers are self-assignable via `POST /auth/subscription`,
(2) entitlement logic is duplicated as tier-string checks in the frontend and `multi_site.py`,
and (3) there is no provenance for *why* a user holds a tier. A professional model fixes all
three with one feature catalog, one enforcement dependency, and an auditable subscription record.

## Tier → feature mapping (proposed)

| Feature                | Min tier    |
|------------------------|-------------|
| Pro AI forecast curve  | pro         |
| Analytics summary      | pro         |
| PDF export             | pro         |
| Heatmaps               | enterprise  |
| Multi-site             | enterprise  |

Tiers are ordered (`free < pro < enterprise`) so higher tiers inherit lower-tier features.

## Phases

### Phase 1 — Entitlement catalog (single source of truth) ✅
`backend/app/entitlements.py`: ordered `Tier` enum, `Feature` enum, `FEATURE_MIN_TIER` map,
and `tier_allows(user_tier, feature)` helper. Nothing else hardcodes a tier string.

### Phase 2 — Server-side enforcement dependency (C2) ✅
`require_feature(feature)` dependency factory in `auth_service.py` (mirrors `require_role`),
returning a consistent `403`. Applied on:
- `analytics.py` `summary` and `report/pdf` (previously no check).
- `multi_site.py` (was `200` with `{"error": ...}`; now real `403`).
- Pro forecast curve endpoint in `forecast.py` — **deferred**: no server-side endpoint exists
  yet; the curve is currently gated only in the UI. `Feature.PRO_FORECAST_CURVE` is defined in
  the catalog so it can be wired when that endpoint is added.

### Phase 3 — Controlled tier changes (C1) ✅
Remove the open `POST /auth/subscription` self-grant. Two legitimate paths:
1. **Admin grant** — wire `PUT /admin/users/{id}` to apply `subscription_tier`.
2. **Self-service checkout (honest simulation)** — `POST /billing/checkout` creates a
   `pending` subscription; `POST /billing/confirm` (simulated webhook) activates it and updates
   the tier. Downgrade to `free` (cancel) is allowed immediately.

### Phase 4 — Subscription persistence & audit trail ✅
`Subscription` model (`tier`, `status`, `source`, `started_at`, `current_period_end`,
`cancelled_at`). `user.subscription_tier` becomes a denormalized cache updated only by the
billing/admin service. Alembic migration.

### Phase 5 — Frontend alignment ✅
Replace `changeSubscription` with `billing.checkout` / `billing.cancel`. Add an
`entitlements.ts` mirror (or fetch `GET /entitlements/me`) and a single `can(feature)` helper.
Treat UI gating as cosmetic; handle `403` in `apiFetch` with an upgrade prompt.

### Phase 6 — Tests ✅
`backend/tests/test_entitlements.py`: free user → `403` on analytics/PDF/multi-site;
pro user passes pro features, `403` on enterprise; admin grant changes entitlement;
the self-grant route no longer escalates.

## Execution order

1. Phase 1 + 2 — catalog + `require_feature` (closes C2, lowest risk). **(done)**
2. Phase 3 — remove self-grant, wire admin path (closes C1). **(done)**
3. Phase 4 — Subscription model + migration. **(done)**
4. Phase 5 + 6 — frontend + tests. **(done)**

## Scope notes

- Real payment provider (Stripe, etc.) is out of scope; Phase 3 simulates the webhook honestly.
- Frontend edits (Phase 5) follow `frontend/AGENTS.md`.
