# Product V1 Implementation Log

**Branch:** `release/product-v1`  
**Base:** `102f8cd`  
**Started:** 2026-07-22

## G0 - Baseline and capability contracts

**Status:** Complete

- Frozen the merged PFE contract and evidence in `docs/PRODUCT_V1_BASELINE.md`.
- Added disabled-by-default `FORECAST_168H_ENABLED`,
  `EMAIL_DELIVERY_ENABLED`, and `GOOGLE_AUTH_ENABLED` settings.
- Added startup validation that rejects enabled email/Google integrations with
  incomplete configuration without printing secret values.
- Documented all flags in backend/root environment examples and wired them into
  the backend Compose service.
- Added stable forecast capability error codes and frontend support for structured
  `{code, message}` error details.
- Kept database and primary 24-hour artifact readiness as the global readiness
  gate; optional week failure is reported independently.

## G1 - 168-hour Global TFT

**Status:** Complete

### Research promotion

- Source experiment: `full_selected_v1`, seed `2026`.
- Verified 2,000 unique known and 500 unique cold-start household identifiers
  with zero split overlap; 499 cold-start households supplied valid evaluation
  windows.
- Verified strict loading of all 186 checkpoint tensors into the shared
  horizon-dynamic `GlobalTFT` architecture.
- Verified deterministic repeated CPU output within `1e-5`, finite `(1, 168, 3)`
  output, and fixed reference values at the start, middle, and end of the horizon.
- Packaged only `model.pt` and `manifest.json` under
  `backend/model_artifacts/global_tft_168h/`.
- Checkpoint SHA-256:
  `80af16b25af9b912019c6e40cfdc491e2cf5173e5743144596801e28df695f93`.

### Backend

- Replaced the single model cache with a fixed 24/168 artifact catalog while
  retaining PFE compatibility constants and body-less 24-hour execution.
- Isolated manifests, hashes, model instances, warm-up, feature visibility, and
  failure state by horizon.
- Added authenticated capabilities and horizon-aware readiness, execution,
  latest, and history contracts.
- Persisted horizon, fixed artifact fingerprint, forecast window, method,
  preprocessing, inference time, and all target points.
- Added a 168-hour seasonal fallback based on the previous complete 168-hour
  window, available only after the week artifact has first passed its visibility
  gate.
- Extended analytics summaries and PDF reports to preserve the actual horizon.
- Added per-artifact system readiness plus a read-only admin view for both fixed
  artifacts. A failed optional week artifact cannot take the day service offline.

### Frontend

- Kept Day/24h as the default.
- Added the Week/168h selector only when returned by server capabilities.
- Filtered readiness, latest forecast, and history by the selected horizon.
- Added dynamic horizon labels to Dashboard, Forecast, history, Reports, and PDF
  descriptions.
- Grouped 168 stored hourly targets into readable local-day chart totals while
  retaining every hourly value for peak, provenance, persistence, and export.
- Added horizon-specific model evidence, forecast windows, target counts,
  fingerprints, fallback disclosure, and empty states.

### Source safeguards

- Added ignore rules for research data, checkpoints, NumPy arrays, logs, caches,
  experiment runs, and cloned repositories under `models/`.
- Kept research/training folders separate from deployable model artifacts.
- Updated README, operations, baseline, artifact, and execution-plan documents.

## G0-G1 validation evidence

| Gate | Result |
|---|---|
| Backend full suite | `53 passed` |
| Torch-free Docker backend suite | `50 passed, 3 skipped` (ML inference tests intentionally skipped) |
| 24-hour ML inference | Passed with ordered quantiles and deterministic repeated output |
| 168-hour ML inference | Passed with 168 ordered quantiles and deterministic repeated output |
| Production image warm-up | Both 24h and 168h available and warmed with independent fingerprints |
| Frontend ESLint | Passed |
| Frontend TypeScript | Passed |
| Next.js production build | Passed |
| Docker Compose configuration | Passed |
| Alembic graph | Single unchanged head `d3a9f6c1b208` |

The isolated production image check used `FORECAST_168H_ENABLED=true` and loaded
both checkpoints with Torch without starting or changing the local database stack.

## Next gate

G2 introduces the transactional email outbox, provider abstraction, delivery
worker, retry/deduplication rules, health detail, and captured-mail tests. Email
and Google remain disabled and invisible after G0-G1.
